# -*- coding: utf-8 -*-
"""Batch 3 圈选台生成器 —— VLM 出草稿，人点选确认，机器绝不直接产出 Gold。

与 Batch 2 的关系
------------------
完全复用 Batch 2 的判定内核（`_build_batch2_viewer` 的表格定位/裁剪、
`_build_batch2_interactive` 的 symbol 收敛 / 参数名补齐 / 置信度合成），
只多做两件事：

  1. **只要 3~5 行核心参数**。Batch 2 一件能出十几行，人核到后面会疲。
     这里按 `CORE_ORDER` 打分，每件只留最核心的 3~5 行（供电、温度、电流、功耗…），
     其余行**不丢证据**，只记进 `_dropped` 供复核时追问。
  2. **显式标 low_confidence**。低于阈值的行在 notes 里写 `low_confidence`，
     人可以在 Excel 里按这个词直接筛出来对图。标记归标记，
     `row_status` 一律仍是 DRAFT_AWAITING_HUMAN_CONFIRM ——
     机器无权替人确认。

输出的 CSV 与 HTML 都是**草稿**，不是 Gold。
"""
from __future__ import print_function

import argparse
import csv
import re
import sys
from pathlib import Path

import fitz

import _build_batch2_viewer as B
import _build_batch2_interactive as I2
import _draft_extract as X
from _vl_extract import extract_rows as vl_extract

PREP = Path(__file__).resolve().parent
WORKING = PREP / "Gold_Set_v1.1_WORKING.csv"

OUT_CSV = PREP / "Batch3_DRAFT.csv"
OUT_HTML = PREP / "Batch3_Viewer.html"
REPORTS = PREP / "annotation_reports"

THRESH = I2.THRESH          # 0.85，与 Batch 2 同源，不另起一个阈值
WARN = "low_confidence"     # 人能在 Excel 里直接搜的词

COLS = B.COLS + ["confidence_score"]
KIND_CN = dict(B.KIND_CN)
KIND_CN["ROC"] = "Recommended Operating Conditions"

# Batch 3 多扫一类表：Recommended Operating Conditions。
# 为什么 Batch 2 没扫：那批要的是"能不能抽对 MIN/TYP/MAX"，ROC 表通常只有单值；
# 但这一轮人要的是**核心参数**，供电电压与工作温度恰恰最常出现在 ROC 里，
# 只扫 AMR/ELC 会整件交不出温度行（V319 就是这种：AMR 里没有 TA）。
KINDS = ("AMR", "ROC", "ELC")

# Batch 2 已定稿的 6 件，绝不再进 Batch 3
DONE = {"V097", "V101", "V111", "V145", "V162", "V349"}

# —— TEST CONDITIONS 定向回填（Reviewer 第七轮）——
# VLM 只抄 PARAMETER / MIN / TYP / MAX 列，TEST CONDITIONS 留在图里没抄，
# 导致草稿 condition 全空。V256 p13 的 V(MAIN-AUX) 五行各自对应不同的
# 测试条件，其中第 2、3 行 min/max 完全相同（-7.8 / 6.6），只能按
# 「同一参数块内的出现顺序」逐行绑定：不能按数值反推，更不能当重复数据合并。
# 以下逐字取自 bq79652 p13 原图裁图 annotation_reports/V256/b3_ELC_p0013.png，
# 度符号按原图写 °C；PDF 文本层把 ° 抽成 o（`25oC`），仅影响 OCR 显示，
# v1.6 只用 condition 做分组键，不做原文断言，故按原图语义落盘。
CONDITION_BACKFILL = {
    # B4 V077：原文同一张 Recommended Operating Conditions 表里，CVDD 与 RVDD
    # 各按「375 MHz version / 456 MHz version」给了两组值，VLM 只抄数值不抄条件。
    # 顺序按原表自上而下：375 在前（1.14/1.2/1.32），456 在后（1.25/1.3/1.35）。
    ("V077", "38", "CVDD"): ["375 MHz version", "456 MHz version"],
    ("V077", "38", "RVDD"): ["375 MHz version", "456 MHz version"],
    # DVDD 在原表里有两行（1.8V I/O 与 3.3V I/O），草稿只留了 1.8V 那行，
    # 用原表的行标题把适用范围钉住，免得跟 3.3V 那行的 3.0/3.3/3.45 混起来。
    ("V077", "38", "DVDD"): ["Supply voltage, I/O, 1.8V"],
    # B4 V290：VIL 两行按温度档区分，0.8 V 对应 0°C to +70°C，
    # 0.5 V 对应 −55°C to +125°C（注意原文用的是 U+2212 减号）。
    ("V290", "3", "VIL"): ["0°C to +70°C", "−55°C to +125°C"],
    ("V256", "13", "V(MAIN-AUX)"): [
        "2V<VCELL<4.5V; TA=25°C",
        "2V<VCELL<4.5V; -20°C<TA<65°C",
        "2V<VCELL<4.5V; -40°C<TA<105°C",
        "2V<VCELL<4.5V; -40°C<TA<125°C",
        "1V<VCELL< 5V; -40°C<TA<125°C",
    ],
}


def apply_condition_backfill(rows, sno):
    """按参数块内出现顺序回填 condition；行数不符直接 Fail-Closed，绝不盲配。

    只处理 sno 这一件的条目。B3 是多件串行生成，若遍历全局回填表，
    一件整件 EXCLUDED（keep 为空，如 V328 无文本层）就会被误判成
    「另一件的条件块丢失」而错误退出。
    分工必须分清：
      - 整件没有参数行 → 由 EXCLUDED 结论承接，回填不适用；
      - 有参数行但条件块对不上 → 必须 SystemExit，绝不盲配。
    """
    here = [r for r in rows if r.get("sample_no") == sno]
    for (bsno, page, sym), conds in CONDITION_BACKFILL.items():
        if bsno != sno:
            continue
        hit = [r for r in here
               if str(r.get("evidence_page")) == page
               and (r.get("symbol") or "").strip() == sym]
        if not hit and not here:
            print("  ... %s 整件无参数行（EXCLUDED），condition 回填不适用" % sno)
            continue
        if len(hit) != len(conds):
            raise SystemExit(
                "FAIL %s p%s %s 保留 %d 行，与 condition 表 %d 条不一致，"
                "拒绝按顺序盲配" % (sno, page, sym, len(hit), len(conds)))
        for r, c in zip(hit, conds):
            r["condition"] = c
            # 条件已经落到具体行上了，旧备注里的"有多组取值…疑 VLM 误标"
            # 就成了自相矛盾的话术，必须换掉，否则 PM 会以为还没解决。
            n = r.get("notes", "")
            if "有多组取值" in n:
                segs = [x for x in n.split("；") if "有多组取值" not in x]
                r["notes"] = "；".join(segs + [COND_BOUND_NOTE]).strip("；")
    return rows

# 第一梯队：原 Batch 1 名单（5 件普通文本型）+ 1 件复杂参数表。
# 选它们打头的原因：表格结构最规整，先用它们校准"核心 3~5 行"的取舍标准，
# 再去碰多级表头/跨页那批硬骨头。
BATCH1 = ["V319", "V304", "V199", "V336", "V173", "V345"]

# 供电电压符号。旧版写的是 `^v(cc|dd|s)\b|\bv(cc|dd)\b`：
# `\b` 要求 VDD 后面紧跟非单词字符，可 VDD_CORE / VDDR_CORE / VDDSHV5
# 的后缀以下划线或字母开头，全都是单词字符，词边界根本不成立 ——
# 于是这些行被判成 pri=99 的非核心参数，pick_core 直接丢掉。
# 现在改成「VCC / VDD / VS + 任意字母数字下划线后缀」，另兼容
# AVDD / DVDD / IOVDD 这类带前缀的写法；参数名里的 supply voltage 仍照旧。
SUPPLY_RX = re.compile(
    r"supply\s+voltage|power[- ]supply\s+voltage"
    r"|\bv(?:cc|dd|s)[a-z0-9_]*\b"
    r"|\b[a-z]{1,3}v(?:cc|dd)[a-z0-9_]*\b",
    re.I)

# 核心参数优先级。数字越小越先留；命不中的行排在后面。
# 只收这几类：供电、温度（工作/存储/结温）、电流（输出/输入）、功耗、输入电压。
CORE_ORDER = [
    # 以下几条的符号分支原先也用了 `^` 锚。core_rank() 拼的是
    # 「parameter_name + 空格 + symbol」，串几乎不以符号开头，
    # `^t\s*j\b` 之类永远命中不了符号位（TJ 因此被判 pri=99 漏掉）。
    # 与供电的 `\b` 是同一类缺陷，一并改成词边界锚。
    (SUPPLY_RX, 1, "供电电压"),
    (re.compile(r"operating\s+(free[- ]air\s+)?temperature|ambient\s+temperature"
                r"|\bt\s*a\b", re.I), 2, "工作温度"),
    (re.compile(r"storage\s+temperature|\bt\s*stg\b", re.I), 3, "存储温度"),
    (re.compile(r"junction\s+temperature|\bt\s*j\b", re.I), 4, "结温"),
    (re.compile(r"(continuous\s+)?output\s+current|\bi\s*o\b", re.I), 5, "输出电流"),
    (re.compile(r"input\s+current|\bi\s*i\b", re.I), 6, "输入电流"),
    (re.compile(r"power\s+dissipation", re.I), 7, "功耗"),
    (re.compile(r"input\s+voltage|\bv\s*i\b", re.I), 8, "输入电压"),
]


def has_num(r):
    """三个数值列里至少有一个非空。"""
    return any((r.get(k) or "").strip()
               for k in ("min_value", "typ_value", "max_value"))


def core_rank(r):
    """给一行打核心度：(优先级, 有没有数值, 置信度)。数值齐的先留。"""
    name = (r.get("parameter_name") or "") + " " + (r.get("symbol") or "")
    pri = 99
    for rx, p, _cn in CORE_ORDER:
        if rx.search(name):
            pri = p
            break
    try:
        conf = float(r.get("confidence_score") or 0)
    except ValueError:
        conf = 0.0
    # 没有数值的核心参数排在"有数值的非核心参数"后面：
    # 人要先看到能核的数，空行放最后面再去补。
    return (pri, 0 if has_num(r) else 1, -conf)


def pick_core(rows, lo=3, hi=5):
    """每件只留最核心的 3~5 行，其余返回给调用方做记录，不落盘。

    V003 事故后加的闸门：一件里若连一行「命中 CORE_ORDER 且带数值」都没有，
    说明定位到的是术语解释页/线图/错表，此时**整件不落草稿**。
    老版会把 5 行无参数名的术语条目凑数交给人，人得先删行再核，
    等于把定位错误伪装成"低置信度草稿"，这是最坏的一种 Fail-Open。
    """
    ranked = sorted(rows, key=core_rank)
    usable = [r for r in ranked if core_rank(r)[0] < 99 and has_num(r)]
    if not usable:
        return [], ranked, [c for _, _, c in CORE_ORDER]
    keep = usable[:hi]
    ids = {id(r) for r in keep}
    drop = [r for r in ranked if id(r) not in ids]
    # 不足 lo 行时不再从脏行里凑——宁可这件只有 2 行，也不拿垃圾行充数。
    return keep, drop, [c for _, _, c in CORE_ORDER]


# —— 二轮兜底：一等电气特性（B4 的 V130 / V347 暴露的盲区）——
# CORE_ORDER 只收供电 / 温度 / 电流 / 功耗 / 输入电压，是给"电源类"器件定的。
# MOSFET 数据手册（V130 的 BVDSS / VGS(th) / RDS(on) / Ciss）与军标运放
# （V347 的 VIN / IIO / AV / tPD）同样有合规参数表，但一个符号都不在白名单里，
# 于是首轮 usable 为空，整件被误判成"没有参数表"。
#
# 纪律：这一轮**只在首轮一行都没留下时**才跑，命中即标注「非白名单核心参数」，
# 让人知道这几行不是按既定白名单选的、要重点核。已能出草稿的样本行为完全不变，
# B1/B2/B3 的封卷结果不受影响。
CORE_ORDER_EXT = [
    (re.compile(r"breakdown|drain[- ]to[- ]source\s+voltage|\bbv\s*dss\b", re.I), 20, "击穿/耐压"),
    (re.compile(r"threshold\s+voltage|\bv\s*gs\s*\(?\s*th", re.I), 21, "阈值电压"),
    (re.compile(r"on[- ]resistance|\br\s*ds\s*\(?\s*on", re.I), 22, "导通电阻"),
    (re.compile(r"leakage\s+current|\bi\s*dss\b|\bi\s*gss\b|\bi\s*io\b|\bi\s*ib\b", re.I), 23, "漏电流"),
    (re.compile(r"capacitance|\bc\s*(?:iss|oss|rss)\b", re.I), 24, "电容"),
    (re.compile(r"transconductance|\bg\s*fs\b", re.I), 25, "跨导"),
    (re.compile(r"offset\s+voltage|\bv\s*oo|\bforward\s+voltage|\bv\s*sd\b", re.I), 26, "失调/正向压降"),
    (re.compile(r"voltage\s+gain|\bgain\b|input\s+resistance|\br\s*in\b", re.I), 27, "增益/输入阻抗"),
    (re.compile(r"delay\s+time|rise\s+time|fall\s+time|\bt\s*pd\b", re.I), 28, "开关时间"),
]

# 二轮命中时写进 notes 的前缀：明确这些行不是按白名单选的
EXT_NOTE = "非白名单核心参数（一等电气特性），WB 建议，请 PM 定夺"
EXT_PREFIX = "【非白名单参数·需 PM 决定是否纳入】"
COND_BOUND_NOTE = ("多组取值已按 condition 分行绑定，请核对是否落在该版本/"
                   "温度档对应的那一行")

# Reviewer 2026-11-12 定稿的三类排除话术。必须按事实分类，不能一刀切：
#   全书确实没有文本层       → OFF_EXCL_NOLAYER
#   只有电气特性页是扫描图   → OFF_EXCL_SCANPAGE
#   有文本层但版式还原不了行序 → OFF_EXCL_SMD
OFF_EXCL_NOLAYER = ("EXCLUDED: 全书无文本层；当前 Gate6A 流程无可用 OCR 取证路径，"
                    "无法建立可验证 Gold")
OFF_EXCL_SCANPAGE = ("EXCLUDED: 电气特性页为扫描图；当前 Gate6A 流程无可用 OCR "
                     "取证路径，无法建立可验证 Gold")
OFF_EXCL_SMD = ("EXCLUDED: 版式不支持稳定还原行序，当前流程无法建立可验证 Gold；"
                "需 SMD 专用规则后重评")


def core_rank_ext(r):
    name = (r.get("parameter_name") or "") + " " + (r.get("symbol") or "")
    pri = 99
    for rx, p, _cn in CORE_ORDER_EXT:
        if rx.search(name):
            pri = p
            break
    try:
        conf = float(r.get("confidence_score") or 0)
    except ValueError:
        conf = 0.0
    return (pri, 0 if has_num(r) else 1, -conf)


def pick_core_ext(rows, lo=3, hi=5):
    """二轮兜底：白名单全落空时，按一等电气特性类别再选一次。"""
    ranked = sorted(rows, key=core_rank_ext)
    usable = [r for r in ranked if core_rank_ext(r)[0] < 99 and has_num(r)]
    if not usable:
        return [], ranked
    keep = usable[:hi]
    ids = {id(r) for r in keep}
    return keep, [r for r in ranked if id(r) not in ids]


# —— 表格定位三道闸门（V003 抓错页事故后加）——
# 事故复盘：AM2431 共 282 页，第 6 章 Specifications（p101~p116）才有参数表，
# 老 scan3 只扫前 40 页，真表整整被漏掉 60 多页；前 40 页里 p14 是
# Pin Attributes 的**术语解释**，正文写着 "For more information, see ... in
# Electrical Characteristics"，宽松标题正则把这句章节交叉引用当成表标题，
# parse_page 再把术语条目当 label，pick_core 最后凑满 5 行 —— 三处叠加，
# 于是 5 行纯文字进了草稿。下面三道闸门分别堵这三处。
NUMCOL_RX = re.compile(r"\b(MIN|TYP|MAX|NOM)\b", re.I)
KIND_TITLE_RX = re.compile(
    r"(absolute\s+)?maximum\s+ratings|recommended\s+operating\s+conditions"
    r"|(electrical|dc\s+electrical|static|dc)\s+(characteristics|specifications)"
    # 军标 SMD 写法：`TABLE I. Electrical performance characteristics.`
    # （B4 V347）—— 老正则要求 characteristics 紧跟 electrical，中间插了
    # performance 就命中不了，整页被当成非候选页，真表被静默漏掉。
    r"|electrical\s+performance\s+characteristics",
    re.I)
REF_RX = re.compile(
    r"\b(see|refer|refer\s+to|for\s+more\s+information|defined\s+in|"
    r"described\s+in|in\s+section|appropriate|values\s+in|table\s+is|"
    r"which\s+.{0,40}\btable\b)\b", re.I)
TOC_PAGE_LIMIT = 10        # 目录只可能在最前面，正文页不参与目录判定

# —— 表头结构判据（Reviewer 2026-11-12 指出旧版只看「页面出现 >=2 个
# MIN/MAX 字样」太松：正文里反复提 minimum / maximum 也会误放行）——
# 真表的表头词在 PDF 文本层里是**竖排独立短行**：
#   p101: PARAMETER / MIN / MAX / UNIT
#   p105: SUPPLY NAME / DESCRIPTION / MIN(1) / NOM / MAX(1) / UNIT
# 而正文句子 "The MIN and MAX values ..." 中的词嵌在长行里，
# 一个独立列词行都没有。用「独立成行 + 表头标记词」当结构化证据。
HEADER_WORD_RX = re.compile(
    r"(?i)^(MIN|MAX|TYP|NOM|UNIT|VALUE|PARAMETER|DESCRIPTION|"
    r"SUPPLY\s+NAME|TEST\s+CONDITIONS)(\(\d+\))?\.?$")
NUM_HEAD_WORDS = {"MIN", "TYP", "MAX", "NOM", "VALUE"}
MARK_HEAD_WORDS = {"UNIT", "PARAMETER", "DESCRIPTION", "SUPPLY NAME",
                   "TEST CONDITIONS"}
HEADER_WINDOW = 8

# Reviewer 第三轮追加的四个极端场景：页上别处有表头、标题只是正文里的词、
# 有边框但前两行不是表头，都不能把整页放行。文本层表头因此必须与
# **独立成行的参数表标题**紧邻，且标题与表头之间不能夹着数据行。
# 注意 V003 的 p106 是跨页续表，页面上根本没有标题行：它靠下面的
# 边框判据进来，所以边框路径不能要求标题存在，否则会误杀真表。
TITLE_LINE_RX = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*\s+)?"
    r"(?:absolute\s+maximum\s+ratings|maximum\s+ratings"
    r"|recommended\s+operating\s+conditions"
    r"|(?:electrical|dc\s+electrical|static|dc)\s+"
    r"(?:characteristics|specifications))"
    r"(?:\s*[-(].{0,40})?\s*$", re.I)
# 老式 TI / Harris 手册把表题写成小写长句，例如 V146 p4：
#   `electrical characteristics over recommended operating free-air
#    temperature range (unless otherwise noted)`
# find_headings3 用的是 X.HEADING（search 语义），本来就能命中这行并据此
# 裁图；但文本层 title_anchor_lines 只认上面那条「整行就是标题词」的严格
# 正则，两处口径不一致，导致 p4 有完整 MIN/TYP/MAX 表头却被整页拦掉。
# 这里补的是**结构化**判据，不是放宽距离阈值：
#   1. 必须以表题词「开头」（正文句子 `Stresses beyond ... Ratings ...`
#      和 `For more information, see ... in Electrical Characteristics`
#      都不是以表题词开头，天然排除）；
#   2. 不含 REF_RX 的章节交叉引用词；
#   3. 整行长度 <= 120 字符，且后续仍必须由 has_table_header 验证
#      「完整表头结构紧邻标题、中间不夹数据行」。
DESC_TITLE_RX = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*\s+)?(?:TABLE\s+[IVXLC]+\.?\s+)?"
    r"(?:(?:absolute\s+)?maximum\s+ratings"
    r"|recommended\s+operating\s+conditions"
    r"|(?:electrical|dc\s+electrical|static|dc)\s+"
    r"(?:performance\s+)?(?:characteristics|specifications))\b.{0,100}$", re.I)
TITLE_MAX_GAP = 4
DATA_ROW_RX = re.compile(r"[-+]?\d+\.\d+|[-+]\d+(?:\s|$)")
BORDER_MARK_RX = re.compile(
    r"\b(PARAMETER|DESCRIPTION|SUPPLY\s+NAME|TEST\s+CONDITIONS)\b", re.I)

# Reviewer 第五轮：边框路径不能「表头成立即放行」。页上有个 AMR 标题、
# AMR 区域却没有表头，页尾另有一个带完整表头的无关表格 —— 旧逻辑会
# 因为那个无关表格把整页放进候选。现在要求边框表格与「独立标题 /
# 续表标识」有空间关联，或表格本身落在页首（跨页续表的客观特征）。
#
# Reviewer 第六轮（本版）：`if y0 <= PAGE_TOP_MAX_PT: return True` 本身是
# Fail-Open —— 页首的表格完全可能是一张无关表。已废弃这条绝对规则，
# 页首表格现在必须拿出「上一页同结构 + 水平宽度对齐」的跨页续表证据。
# V003 实测：p102 / p106 无本页锚点，但与上一页表格 x0/x1 差仅
# 0.1/2.4pt 与 0.1/3.1pt 且表头数值列词一致；p118→p119 差 66/60pt，
# 明显不是续表（p119 靠本页 Table 6-3 表题关联，不走页首分支）。
CONT_RX = re.compile(r"\bcontinued\b|\(cont'?d\)|\bcont\.", re.I)
# 真实手册的小节标题常写成「6.7.2 Fail-Safe Reset (FS RESET) Electrical
# Characteristics」，整行不是纯标题词，但确实是独立成行的表标题。
SECTION_TITLE_RX = re.compile(
    r"^\s*\d+(?:\.\d+){1,3}\s+.{0,70}\b"
    r"(?:electrical\s+characteristics|specifications"
    r"|recommended\s+operating\s+conditions|absolute\s+maximum\s+ratings)"
    r"\b.{0,45}$", re.I)
# 阈值按 V003 真表页实测几何定，不是拍脑袋：
#   p108 表格 y0=229.4，标题 y=75 → 相距 154.4pt；
#   p119 表格 y0=154.4、p117 y0=144.2、p109~115 y0=107.0、p106 y0=86.0。
# Reviewer 反例里的无关表格在页底 y0=400，离页顶标题 328pt，仍被拦。
TABLE_ANCHOR_MAX_PT = 200.0     # 表格顶端离上方标题/续表标识的最大垂直距离
PAGE_TOP_MAX_PT = 160.0         # 页首区间（仅用于区分「需要跨页证据」的表格）
X_ALIGN_MAX_PT = 20.0           # 跨页续表与上一页表格左右边界/宽度的允许偏差
# 实测：V003 p101→p102 差 0.8/2.4pt，p105→p106 差 0.1/3.1pt；
# 反例的不对齐表格差 144/150pt。20pt 与正反例之间都隔着一个数量级，
# 不是「放宽阈值蒙混」，判据还要同时满足列名指纹一致（见下）。
# 独立成行的表题，如 `Table 6-3. VTM Die Temperature Sensor Characteristics`。
# V003 p119 的首行是章节标题 `6.10 Temperature Sensor Characteristics`，
# 不匹配 SECTION_TITLE_RX / TITLE_LINE_RX，只能靠表题做本页强关联。
# 必须包含 characteristics / specifications / ratings / conditions /
# parameters 之一，避免把 `Table 4-1 Pin Configuration` 之类无关表题算进来。
TABLE_CAPTION_RX = re.compile(
    r"^\s*table\s+\d+(?:[-.]\d+)*\.?\s+.{0,80}"
    r"(?:characteristics|specifications|ratings|conditions|parameters)\b",
    re.I)
# 表头「列名指纹」：跨页续表不只比坐标，还要比列名结构。
# 无关表格（PIN / MIN / MAX / UNIT）与真参数表的指纹重合度明显更低。
FINGERPRINT_RX = re.compile(
    r"\b(MIN|TYP|MAX|NOM|VALUE|UNIT|PARAMETER|DESCRIPTION|"
    r"SUPPLY\s+NAME|TEST\s+CONDITIONS|SYMBOL|PIN)\b", re.I)
MIN_FINGERPRINT_HITS = 3

# —— 跨页污染隔离（PM 2026-11-12 定向修复）——
# 根因：PyMuPDF 在同一 Document 上跨页调 find_tables() 会污染先前拿到的
# Table 对象 —— 实测「先取 p101 的 Table、再对 p100 调 find_tables()」，
# p101 的 t.extract() 会吐出 p100 的正文，p102 甚至变成全空行。
# 三道硬隔离，任何一道不过就丢弃该表，绝不把脏数据带进指纹比对：
#   1. find_tables(clip=page.rect)：检测范围锁死在本页矩形内；
#   2. bbox 越界校验：表格四边必须落在 clip 内（1pt 容差），
#      尤其 y0/y1 不得越出页高（PM 点名的 Y 轴越界）；
#   3. 文本归属校验：表头词汇必须能在「本页」文本里核到，命中率低于
#      阈值即判定为上一页正文串入，直接丢弃。
# 再加一条结构约束：Table 对象绝不跨出 _page_table_signatures()，
# 本页所有 extract 完成后才允许访问上一页，且 PageContext 用完即释放 page。
TABLE_CLIP_PAD_PT = 1.0
TABLE_TEXT_MIN_HIT = 0.50


def _anchor_classes(page):
    """把页面行级锚点分成「强 / 弱」两类，返回 (strong_ys, weak_ys)。

    强锚点（能证明表格归属）：带章节号的小节标题、独立表题、明确续表标识。
    弱锚点：无章节号的纯标题行（如光秃秃的 `Absolute Maximum Ratings`）。
    V003 十三页真表实测：所有本页锚点都是强锚点，没有一页靠弱锚点。
    Reviewer 第六轮反例正是「页首无关表 + 一个纯 AMR 标题」，
    所以弱锚点不能再给页首表格背书。

    从 get_text("dict") 取行级 bbox，才能判断表格是不是紧跟在标题下面；
    只看「页面任意位置出现过标题词」挡不住 Reviewer 的反例。
    """
    strong, weak = [], []
    try:
        data = page.get_text("dict")
    except Exception:
        return strong, weak
    for block in data.get("blocks", []):
        for ln in block.get("lines", []):
            s = " ".join(" ".join(str(sp.get("text", ""))
                                  for sp in ln.get("spans", [])).split())
            if not s or REF_RX.search(s):
                continue
            try:
                y0 = float(ln["bbox"][1])
            except (KeyError, IndexError, TypeError, ValueError):
                continue
            if (SECTION_TITLE_RX.match(s) or TABLE_CAPTION_RX.match(s)
                    or (CONT_RX.search(s) and KIND_TITLE_RX.search(s))):
                strong.append(y0)
            elif TITLE_LINE_RX.match(s):
                weak.append(y0)
    return strong, weak


def _anchor_ys(page, strong_only=False):
    """兼容旧契约：默认返回全部锚点 y；strong_only=True 只返回强锚点。"""
    strong, weak = _anchor_classes(page)
    return list(strong) if strong_only else strong + weak


FINGERPRINT_MIN_SIM = 0.80      # 表头指纹相似度下限（Reviewer 第六轮口径）


def _header_fingerprint(head):
    """表头「结构化指纹」：把表头第一行的列名词向量化。

    不用白名单正则，而是取完整词集合：去脚注 `(1)`、大写、只留字母词。
    只用 head[0]，因为 head[1] 已经是数据行，掺进来会拉低同构表相似度。
    实测 V003：p101/p102 同为 {MAX,MIN,PARAMETER,UNIT}（sim=1.00），
    p105/p106、p108~p113 同理；合成无关表
    {PIN,PARAMETER,DIRECTION,MIN,MAX,UNIT} 与真表 sim=0.67 < 0.80。
    """
    s = " ".join(str(c or "") for c in (head[0] if head else []))
    s = re.sub(r"\([^)]*\)", " ", s.upper())
    s = re.sub(r"[^A-Z ]+", " ", s)
    return {w for w in s.split() if len(w) >= 2}


def fingerprint_similarity(a, b):
    """指纹相似度 = |A∩B| / max(|A|,|B|)；完全同构为 1.0。"""
    sa, sb = set(a or ()), set(b or ())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / float(max(len(sa), len(sb)))


class TableSignature(object):
    """Stage 2 产物：一张表的结构化签名（bbox + 数值列 + 列名指纹）。"""

    def __init__(self, bbox, nums, fp, text_hit=0.0):
        self.bbox = bbox
        self.nums = nums
        self.fp = fp
        # 隔离 3 的实测命中率，留作回归证据（脏数据会被这一步丢弃）
        self.text_hit = text_hit


def _page_rect(page):
    """本页矩形；合成 FakePage 没有 rect 时用标准 Letter 页兜底。"""
    r = getattr(page, "rect", None)
    if r is None:
        return (0.0, 0.0, 612.0, 792.0)
    if hasattr(r, "x0"):
        return (float(r.x0), float(r.y0), float(r.x1), float(r.y1))
    return (float(r[0]), float(r[1]), float(r[2]), float(r[3]))


def _bbox_in_clip(bbox, clip, pad=TABLE_CLIP_PAD_PT):
    """隔离 2：表格四边必须落在本页 clip 内，Y 轴越界即判脏数据。"""
    try:
        x0, y0, x1, y1 = (float(v) for v in bbox)
    except (TypeError, ValueError):
        return False
    cx0, cy0, cx1, cy1 = clip
    if not (x1 > x0 and y1 > y0):
        return False
    return (x0 >= cx0 - pad and y0 >= cy0 - pad and
            x1 <= cx1 + pad and y1 <= cy1 + pad)


def _header_words_in_page(head, page_text):
    """隔离 3：表头词在本页文本里的命中率。

    污染时 t.extract() 吐出的是上一页正文，词集合与本页几乎不重合，
    命中率会塌到 0；正常表格的列名本来就在本页文本里，命中率接近 1。
    只取 >=3 个字母的全大写词，避开单元格里的数字与脚注符号。
    """
    words = {w for row in head for c in row
             for w in re.findall(r"[A-Z]{3,}", str(c or "").upper())}
    if not words:
        return 0.0
    text = page_text or ""
    return float(sum(1 for w in words if w in text)) / float(len(words))


def _table_signature(t, clip, page_text):
    """一次 extract 内把 bbox / 数值列 / 指纹全部读进内存，并做污染隔离。

    Table 对象的生命周期只限本函数：返回的是纯值 TableSignature，
    调用方再也拿不到可跨页复用的 t，从结构上杜绝「先取本页 Table、
    再对上一页 find_tables()」这条污染路径。
    """
    try:
        bbox = tuple(float(x) for x in t.bbox)
    except Exception:
        return None
    if not _bbox_in_clip(bbox, clip):
        return None                       # 隔离 2：四边 / Y 轴越界
    try:
        head = t.extract()[:2]
    except Exception:
        return None
    text_hit = _header_words_in_page(head, page_text)
    if text_hit < TABLE_TEXT_MIN_HIT:
        return None                       # 隔离 3：内容不属于本页
    words = " ".join(str(c or "") for row in head for c in row).upper()
    nums = {w for w in ("MIN", "TYP", "MAX", "NOM", "VALUE")
            if re.search(r"\b%s\b" % w, words)}
    if len(nums) < 2 or not BORDER_MARK_RX.search(words):
        return None
    return TableSignature(bbox, nums, _header_fingerprint(head), text_hit)


def _page_table_signatures(page):
    """Stage 2：一次 find_tables(clip=本页矩形) 后立即全部 extract 完。

    页文本在 find_tables 之前一次读入内存；本页所有 Table 在本函数内
    消费完毕，返回时不再持有任何 Table 对象。这样即使调用方随后访问
    上一页，也不存在可被污染的活对象。
    """
    if page is None:
        return []
    clip = _page_rect(page)
    try:
        page_text = (page.get_text("text") or "").upper()
    except Exception:
        page_text = ""
    try:
        result = page.find_tables(clip=fitz.Rect(*clip))
    except TypeError as e:
        # Reviewer 第七轮：绝不退回 `page.find_tables()` 无 clip 调用。
        # 无 clip 等于放弃隔离 1，跨页污染会原路回来，属于静默降级 → 直接退出。
        raise SystemExit(
            "FAIL find_tables() 不接受 clip 参数，拒绝静默降级：%s" % e)
    except Exception:
        # 页面本身无法解析（加密 / 结构损坏）按「本页无表」处理，不是降级
        return []
    tables = getattr(result, "tables", None)
    if tables is None:
        raise SystemExit("FAIL find_tables() 返回值缺少 tables 属性，拒绝降级")
    out = []
    for t in tables:
        sig = _table_signature(t, clip, page_text)
        if sig is not None:
            out.append(sig)
    return out


def _prev_table_signatures(prev_page):
    """兼容旧契约：上一页有效参数表头签名。"""
    return _page_table_signatures(prev_page)


def _page_title(page):
    """Stage 1 页级分类，返回 (标题文本, y, 类别)。

    类别取「本页最强证据」而不是第一行的类别：只要页面出现过带章节号
    的小节标题 / 独立表题 / 续表标识，整页就归 STRONG，走本页正常提取；
    只有全页没有任何独立标题才是 NONE，才有资格进入跨页指纹继承链。

    V003 十三页真表实测：11 页 STRONG + 2 页 NONE（p102 / p106）。
    """
    try:
        data = page.get_text("dict")
    except Exception:
        return None, None, "NONE"
    weak = None
    for block in data.get("blocks", []):
        for ln in block.get("lines", []):
            s = " ".join(" ".join(str(sp.get("text", ""))
                                  for sp in ln.get("spans", [])).split())
            if not s or REF_RX.search(s):
                continue
            try:
                y = float(ln["bbox"][1])
            except (KeyError, IndexError, TypeError, ValueError):
                continue
            if (SECTION_TITLE_RX.match(s) or TABLE_CAPTION_RX.match(s)
                    or (CONT_RX.search(s) and KIND_TITLE_RX.search(s))):
                return s, y, "STRONG"
            if TITLE_LINE_RX.match(s) and weak is None:
                weak = (s, y)
    if weak is not None:
        return weak[0], weak[1], "WEAK"
    return None, None, "NONE"


class PageContext(object):
    """任务队列里的一页：Stage 1 页级分类 + Stage 2 表头结构（一次完成）。"""

    def __init__(self, page, pno=0):
        self.pno = pno
        self.rect = _page_rect(page)
        self.strong_ys, self.weak_ys = _anchor_classes(page)
        self.page_title, self.title_y, self.title_class = _page_title(page)
        self.signatures = []
        self.inherited_title = None
        self.links = []
        self._page = page
        self._extracted = False

    def extract_tables(self):
        """Stage 2 幂等：只做一次 find_tables，做完立刻释放 page 引用。

        释放后本对象只剩纯值签名，后续访问上一页不可能污染本页的 Table。
        """
        if not self._extracted:
            self.signatures = _page_table_signatures(self._page)
            self._extracted = True
            self._page = None
        return self.signatures


def _geom_close(a, b):
    """辅助复核：左右边界与宽度偏差都 <= X_ALIGN_MAX_PT（同一版式）。"""
    return (abs(a[0] - b[0]) <= X_ALIGN_MAX_PT and
            abs(a[2] - b[2]) <= X_ALIGN_MAX_PT and
            abs((a[2] - a[0]) - (b[2] - b[0])) <= X_ALIGN_MAX_PT)


def link_context(cur, prev):
    """Stage 3：按「页级分类」分流，返回 [(sig, allowed, reason, sim)]。

    页级分流（PM 2026-11-12 指示，V003 13 页实测支撑）：
      STRONG / WEAK（有本页独立标题，11 页）→ 本页正常提取，
          完全不读取 prev，从源头掐断 find_tables() 跨页污染；
      NONE（无本页标题，只有 p102 / p106 两页）→ 才进入跨页
          指纹继承链，且必须同时满足：
            a. 上一页有可继承的 Page_Title；
            b. 表头指纹相似度 >= 0.80；
            c. 左右边界与宽度几何对齐；
            d. 表格落在页首区间（续表的客观特征）。
      任一不满足 → Fail-Closed 拦截，不靠放宽阈值蒙混。
    """
    inherited = None
    if cur.title_class == "NONE" and prev is not None:
        inherited = prev.page_title or getattr(prev, "inherited_title", None)
    cur.inherited_title = inherited
    out = []
    for sig in cur.signatures:
        y0 = float(sig.bbox[1])

        def near(ys):
            return any(0.0 <= y0 - y <= TABLE_ANCHOR_MAX_PT for y in ys)

        if cur.title_class == "STRONG":
            if near(cur.strong_ys):
                out.append((sig, True, "LOCAL_TITLE", 1.0))
            else:
                out.append((sig, False, "NO_LOCAL_STRONG_ANCHOR", 0.0))
            continue
        if cur.title_class == "WEAK":
            if y0 > PAGE_TOP_MAX_PT and near(cur.weak_ys):
                out.append((sig, True, "WEAK_LOCAL_TITLE", 1.0))
            else:
                out.append((sig, False, "WEAK_TITLE_PAGETOP_UNPROVEN", 0.0))
            continue
        # 只有 NONE 页允许走跨页继承
        if y0 > PAGE_TOP_MAX_PT:
            out.append((sig, False, "NO_TITLE_NOT_PAGETOP", 0.0))
            continue
        if prev is None or not inherited or not prev.signatures:
            out.append((sig, False, "NO_INHERITED_CONTEXT", 0.0))
            continue
        sim = max(fingerprint_similarity(sig.fp, ps.fp)
                  for ps in prev.signatures)
        if sim < FINGERPRINT_MIN_SIM:
            out.append((sig, False, "FINGERPRINT_MISMATCH", sim))
            continue
        if not any(_geom_close(sig.bbox, ps.bbox)
                   for ps in prev.signatures):
            out.append((sig, False, "GEOMETRY_MISMATCH", sim))
            continue
        out.append((sig, True, "INHERITED_TITLE_FINGERPRINT", sim))
    cur.links = out
    return out


def title_anchor_lines(text):
    """页面里「独立成行的参数表标题」所在行号（0 基）。

    'Stresses beyond those listed under Absolute Maximum Ratings may ...'
    这种把标题词嵌进句子的正文行不算标题，整行必须基本就是标题本身
    （允许前导章节号和尾部短括注 / 破折号说明）。
    """
    lines = [" ".join(ln.split()) for ln in (text or "").splitlines()]
    out = []
    for i, ln in enumerate(lines):
        if not ln or len(ln) > 120 or REF_RX.search(ln):
            continue
        # 严格短标题，或老式手册「描述型表题」（见 DESC_TITLE_RX 注释）。
        # 两种都必须再经 has_table_header 验证紧邻的完整表头结构。
        if TITLE_LINE_RX.match(ln) or DESC_TITLE_RX.match(ln):
            out.append(i)
    return out


def _looks_like_data_row(line):
    return bool(DATA_ROW_RX.search(line))


def has_table_header(text, title_positions=None, max_gap=TITLE_MAX_GAP):
    """MIN/MAX 是否真的以「列名」身份出现在表头结构里。

    在任意连续 HEADER_WINDOW 行的窗口内，要求至少 2 个不同的数值列词
    各自独立成行，且窗口内还有 UNIT / PARAMETER / DESCRIPTION /
    SUPPLY NAME / TEST CONDITIONS 之一作为表头标记。
    纯正文（含多少 MIN/MAX 词汇都算）不满足，返回 False。

    `title_positions` 传入后（prescan3 用），表头窗口还必须紧跟
    title_anchor_lines() 找到的独立标题行：距离不超过 max_gap 行，
    且标题与窗口之间不能夹着参数数据行。单独调用本函数时
    title_positions=None，保持旧的纯文本契约不变。
    """
    lines = [" ".join(ln.split()) for ln in (text or "").splitlines()]
    tags = []
    for ln in lines:
        m = HEADER_WORD_RX.match(ln.strip())
        tags.append(" ".join(m.group(1).upper().split()) if m else None)
    for i in range(len(tags)):
        # 带锚点时，窗口必须从「第一个表头词行」起算。否则窗口起点可以
        # 退到标题后第 1 行，把 i - p 算成 1，页尾无关表格的 MIN/MAX
        # 就会借着标题的距离被放行（Reviewer 场景 a 实测抓到过一次）。
        if title_positions is not None and tags[i] is None:
            continue
        win = [w for w in tags[i:i + HEADER_WINDOW] if w]
        nums = {w for w in win if w in NUM_HEAD_WORDS}
        if len(nums) < 2 or not any(w in MARK_HEAD_WORDS for w in win):
            continue
        if title_positions is None:
            return True
        for p in title_positions:
            if (0 <= i - p <= max_gap and
                    not any(_looks_like_data_row(lines[j])
                            for j in range(p + 1, i))):
                return True
    return False


def _auto_prev_page(page):
    """调用方没显式给上一页时，真实 fitz Page 可自行从 parent 取。

    FakePage 没有 parent → 返回 None → 无跨页证据 → 页首表格被拦截，
    这正是 Fail-Closed 期望的行为，绝不靠猜。
    """
    doc = getattr(page, "parent", None)
    if doc is None:
        return None
    try:
        pno = int(page.number)
    except (AttributeError, TypeError, ValueError):
        return None
    if pno <= 0:
        return None
    try:
        return doc.load_page(pno - 1)
    except Exception:
        return None


def _table_header_from_borders(page, prev_page=None):
    """有表格边框时，看表头区域单元格里有没有 >=2 个数值列词，且表格
    与独立标题 / 表题 / 续表标识存在空间关联，或有跨页续表证据。

    这是文本判据之外的第二条结构化证据。老手册的点线式 AMR 表没有边框，
    所以两条是「或」关系，不是「与」—— 不能把无边框的真表误杀。
    但「或」不等于「边框表头成立就无条件放行」：表格必须属于目标表。
    第六轮起，页首表格不再凭 y 坐标放行，必须有上一页同结构且水平
    对齐的表格签名（或本页强锚点）。
    """
    # 三段任务队列的薄封装：本页 Stage 2 全部 extract 完并释放 page 引用。
    cur = PageContext(page)
    if not cur.extract_tables():
        return False
    # 页级分流：只有 NONE 页才加载上一页做指纹继承；STRONG / WEAK 页
    # 连上一页都不打开，find_tables() 根本没有跨页污染的发生机会。
    prev = None
    if cur.title_class == "NONE":
        if prev_page is None:
            prev_page = _auto_prev_page(page)
        if prev_page is not None:
            prev = PageContext(prev_page)
            prev.extract_tables()
    return any(allowed for _, allowed, _, _ in link_context(cur, prev))


def prescan3(doc, npages, max_pages=0):
    """全书文本快筛：只留「有表标题词 + 真实表头结构」的页。

    为什么分两阶段：find_tables()/parse_page() 对 282 页全做一遍很慢，
    get_text("text") 是纯文本，全书扫一遍几乎不耗时；只有过了文本关的
    少数页才值得做边框取证。

    两层判据：
      1. NUMCOL_RX 快筛 —— 页面至少 2 个数值列词，且出现表标题词；
      2. has_table_header(t) 或 _table_header_from_borders(page) ——
         这些词必须真的以列名身份出现在表头结构里。
    V003 p14 的 Pin Attributes 术语解释页两层都过不了。
    max_pages=0 表示全书；调试时可传小值做回归。
    """
    limit = npages if max_pages <= 0 else min(npages, max_pages)
    cand = []
    for pno in range(1, limit + 1):
        page = doc.load_page(pno - 1)
        t = page.get_text("text")
        if not t.strip():
            continue
        if len(NUMCOL_RX.findall(t)) < 2 or not KIND_TITLE_RX.search(t):
            continue
        # 文本层表头必须锚在独立标题行附近；边框表头走独立判据。
        # p102/p106 那种「标题在上一页」的跨页续表，现在靠显式传入的
        # 上一页表格签名（同结构 + 水平对齐）证明身份，不再凭页首 y 坐标。
        prev_page = None
        if pno > 1:
            try:
                prev_page = doc.load_page(pno - 2)
            except Exception:
                prev_page = None
        anchors = title_anchor_lines(t)
        if (has_table_header(t, anchors)
                or _table_header_from_borders(page, prev_page)):
            cand.append(pno)
    return cand


def find_headings3(rows, kind):
    """标题行 → [(y, 行文本)]，并排除章节交叉引用句。

    X.find_headings 只返回 y，会把 "see ... in Electrical Characteristics"
    整句算命中。真表标题是独立短行（如 "6.1 Absolute Maximum Ratings"），
    引用句是长句且带 see/refer/for more information，必须排掉。
    """
    rx = re.compile(X.HEADING[kind], re.I)
    out = []
    for r in rows:
        line = " ".join(w[4] for w in r["w"]).strip()
        if not rx.search(line):
            continue
        if len(line) > 90 or REF_RX.search(line):
            continue
        out.append((r["y"], line))
    return out


def scan3(doc, npages, max_scan_pages=0):
    """全书候选页扫描：先文本快筛，再只对候选页做表格解析。

    返回 (hits, nav)，结构与 B.scan 一致，只是 key 多了 "ROC"。
    与老版三点不同：
      1. 不再被 MAX_SCAN_PAGES=40 截断（V003 真表在 p101）；
      2. 候选页必须同时出现标题词与 MIN/TYP/MAX/NOM 列词；
      3. 标题必须是独立短行，排除 see/refer 之类的章节交叉引用。
    目录页仍排除，但只在最前 10 页判：p102 这类续表正文会同时出现
    AMR/ELC/ROC 字样，若沿用「同页命中 3 种即跳过」会误杀真表。
    """
    hits = {k: [] for k in KINDS}
    nav = {k: [] for k in KINDS}
    for pno in prescan3(doc, npages, max_scan_pages):
        page = doc.load_page(pno - 1)
        rows = X.group_lines(X.dedup(page.get_text("words")))
        found = {k: find_headings3(rows, k) for k in KINDS}
        if pno <= TOC_PAGE_LIMIT and sum(1 for v in found.values() if v) >= 3:
            continue                      # 目录页
        for kind in KINDS:
            hs = found.get(kind) or []
            if not hs:
                continue
            bbs = X.table_bboxes(page)
            for h_y, _htext in hs:
                bb = X.choose_bbox(bbs, h_y)
                recs, _ = X.parse_page(page, kind, bbox=bb)
                good = [r for r in recs if r.get("label")]
                if not any(n[0] == pno for n in nav[kind]):
                    nav[kind].append((pno, h_y, bb, len(good)))
                for r in good:
                    hits[kind].append((B.rank(r), pno, r, h_y, bb))
    return hits, nav


def mark_dups(rows):
    """同一符号出现多组不同取值时提醒人工。

    V319 就是实例：两行都写 TA，一行 -40~85、一行 -55~125。
    真实手册里这是温度等级不同（商用/工业/军品）或 VLM 把 Tstg 误标成 TA，
    机器分不清哪种，也不该替人决定——只在 notes 里点出来，让人看一眼左图。
    """
    seen = {}
    for r in rows:
        sym = (r.get("symbol") or "").strip().upper()
        if not sym:
            continue
        vals = tuple((r.get(k) or "").strip()
                     for k in ("min_value", "typ_value", "max_value"))
        seen.setdefault(sym, []).append((r, vals))
    for sym, items in seen.items():
        if len(items) < 2:
            continue
        uniq = {v for _, v in items}
        if len(uniq) < 2:            # 完全重复的行，同样值得提醒
            for r, _ in items[1:]:
                r["notes"] = (r.get("notes", "")
                              + "；与上一行完全重复，可能该删").strip("；")
            continue
        for r, _ in items:
            # 条件已经按原图落到这一行了，就不再喊"疑似误标" —— 那句话会让 PM
            # 以为问题没解决；只提醒核对落行是否对。
            if (r.get("condition") or "").strip():
                tail = COND_BOUND_NOTE
            else:
                tail = ("%s 有多组取值（疑不同温度等级或 VLM 误标），请确认" % sym)
            r["notes"] = (r.get("notes", "") + "；" + tail).strip("；")
    return rows


def value_flags(r):
    """数值列自身的坏味道。返回问题描述列表，非空即判 low_confidence。

    为什么置信度公式抓不到这些：公式只问"这个串在页面上找不找得到"，
    而 `V_O =`、`V_DD +` 这类**截断残留**恰恰是从页面上原样抠下来的，
    找得到，于是照样满分。但它们已经不是数值了，必须单独拦。

    实测来源（第一批）：
      V173 `Continuous output current` min=`V_O =`  —— 条件被抄进 min 列
      V345 `V_FBX to AGND` max=`V_DD +`            —— 公式被截断，丢了 0.3
    """
    issues = []
    for col, cn in (("min_value", "min"), ("typ_value", "typ"), ("max_value", "max")):
        v = (r.get(col) or "").strip()
        if not v:
            continue
        if "=" in v:
            issues.append("%s 列含等号，疑把条件抄进数值" % cn)
        elif re.search(r"[+\-*/]\s*$", v) and not re.fullmatch(r"[+\-]\d+(\.\d+)?", v):
            issues.append("%s 列以运算符结尾，疑被截断" % cn)
        elif not re.search(r"\d", v) and not re.match(r"(?i)^see\b", v):
            issues.append("%s 列没有数字" % cn)
    return issues


def det_score3(doc, r, cache):
    """确定性证据分（0-1）。每一项都能被人复算，不依赖模型自报。

    与 Batch 2 的差别只一处：v1.6 的验证器把 `normalize()` 拆成了
    `unify/collapse/nos` 三个函数，单位核对改用 `check_unit()`，
    它还会区分"独立出现"和"只作为更长串的一部分"（后者只降分不判错）。
    """
    import validate_annotation as V

    try:
        pno = int(r["evidence_page"])
    except (TypeError, ValueError):
        return 0.30
    if pno not in cache:
        cache[pno] = V.collapse(doc.load_page(pno - 1).get_text("text"))
    txt = cache[pno]

    vals = [r.get("min_value"), r.get("typ_value"), r.get("max_value")]
    vals = [v for v in vals if v]
    hit = 0
    for v in vals:
        rx = V.num_pattern(v)
        if rx and rx.search(txt):
            hit += 1

    s = 0.50
    if vals and hit == len(vals):
        s += 0.25
    elif hit:
        s += 0.10
    else:
        s -= 0.10

    unit = (r.get("unit") or "").strip()
    if unit:
        verdict, _why = V.check_unit(unit, txt)
        s += {"OK": 0.10, "SUSPECT": 0.03}.get(verdict, -0.10)

    sym = (r.get("symbol") or "").strip()
    # 允许下划线：`V_IH` 是手册里的真实写法
    if sym and re.fullmatch(r"[A-Za-z\u0394][A-Za-z0-9()/_\-±.\u0394]{1,11}", sym):
        s += 0.05

    name = (r.get("parameter_name") or "").strip()
    if 6 <= len(name) <= 60:
        s += 0.05
    if "=" in name:              # 把条件当参数名是典型坏行
        s -= 0.15
    if not name:
        s -= 0.20
    # 我们自己按规则清空的 symbol 不再倒扣，否则等于因规范化二次惩罚
    if not sym and not r.get("_sym_cleared"):
        s -= 0.05
    return max(0.0, min(1.0, s))


def score_rows3(doc, rows):
    """补置信度。最终分只取确定性证据分——VLM 自报分实测恒为 1.00，
    掺进公式只会给所有行统一加 0.3，反而抹平区分度（Batch 2 已验证）。
    自报分仍写在 notes 里备查。"""
    cache = {}
    for r in rows:
        det = det_score3(doc, r, cache)
        r["confidence_score"] = "%.2f" % round(min(0.95, det), 2)
    return rows


def build_js(rows, export_name):
    """把批次名注入前端，导出文件不再一律叫 Batch2_ANNOTATED.csv。

    I2.build_js() 会把 _b2_app.js 里的 __DRAFT__/__THRESH__ 换成实值；
    这里在它前面加一行 window.B3_EXPORT_NAME，前端的 EXPORT_NAME 就会用它。
    不改 I2 本身，Batch 2 生成器的行为完全不变（读不到这个变量时退回默认名）。
    """
    import json
    return ("window.B3_EXPORT_NAME=%s;\n" % json.dumps(export_name)
            + I2.build_js(rows))


# —— Reviewer 指定的逐件核查提示（B4）——
# 这些不是自动判定，是人点选时**必须先回答的问题**，直接印在圈选台卡片上，
# 避免「机器说 EXCLUDED 就照着标」或「机器出了草稿就默认对」。
# 数值长得像但适用条件不同，最容易看错。这类必须红底提醒，不能只放灰字提示。
WARN_BANNER = {
    "V077": ("本件原文同一张 Recommended Operating Conditions 里同时给出 "
             "<b>375 MHz version</b> 与 <b>456 MHz version</b> 两套条件："
             "CVDD 与 RVDD 各两组值已分别绑定 —— 375 MHz → 1.14 / 1.2 / 1.32 V，"
             "456 MHz → 1.25 / 1.3 / 1.35 V。"
             "签字前请重点核对这两组 <code>condition</code> 是否落在正确的行上，"
             "不要只看数值。"),
    "V290": ("VIL 两行按温度档区分，数值不同、适用温度不同："
             "0.8 V 对应 0°C to +70°C，0.5 V 对应 −55°C to +125°C。"
             "本件 II（输入电流）原文条件是 VCC = Max、VI = 5.5V，"
             "文本层抽成 “V CC = Max, VI Max = 5.5V”，是否补录请 PM 定夺。"),
}

REVIEW_HINTS = {
    "V077": "Reviewer 提示：请核实表格类型。该件 201 页、章节极多，"
            "先确认裁到的是电气特性表，而不是时序/引脚/封装表。",
    "V130": "Reviewer 提示：短文档不代表没有有效参数表。"
            "p2 是标准 ELECTRICAL CHARACTERISTICS 表（PARAMETER / TEST CONDITIONS / "
            "MIN / TYP / MAX / UNIT），参数名属 MOSFET 类，不在既有白名单里。",
    "V347": "Reviewer 提示：核实是否为目标器件数据，而非引用资料。"
            "本件是 DSCC 军标 SMD（84185），TABLE I 即该器件本身的电气性能表，"
            "不是引用别处的资料；但只有 Min/Max 两列且带测试分组，行序需人工判读。",
}


# —— 逐件排除理由（人工核定，覆盖自动判定给的泛化措辞）——
# 只在自动判定为 EXCLUDED 类时生效：把「为什么不能建 Gold」写成可复核的事实，
# 而不是一句「无参数表」。每条都必须能对着 PDF 原文验证。
EXCLUDED_REASON = {
    "V347": (
        "确为目标器件数据（DSCC 标准微电路图纸 84185，TABLE I 即该器件本身的"
        "电气性能表，不是引用别处资料）；但该表同一符号按 Group A subgroup / "
        "Device type 拆成 2~4 行（例：IIO 上限按 01,02 / 03 分别为 3、5、6、"
        "20、30、40 μA），且 find_tables 在该页探不到边框表格（0 张）。"
        "VLM 实测只能给出「每符号一行」的合并值，并固定取 01,02 那一行，"
        "会掩盖器件类型差异 —— 属硬凑，故不进点选。"
        + OFF_EXCL_SMD
    ),
    "V041": (
        "电气特性页是 p2~p4 的扫描图（无文本层）；有文本层的 10 页为 "
        "PACKAGE OPTION ADDENDUM / PACKAGE MATERIALS / PACKAGE OUTLINE / "
        "LAND PATTERN / STENCIL DESIGN / 免责声明，其中的 MIN/MAX 是机械尺寸公差，"
        "不是电气参数。" + OFF_EXCL_SCANPAGE
    ),
}


def one_sample(meta, args):
    """处理一件：定位表格 → 裁剪 → VLM → 收敛 → 打分 → 留 3~5 行。"""
    sno = meta["sample_no"]
    path = Path(meta["file_path"])
    fname = path.name
    npages = int(meta["page_count"])
    pdf_url = "file:///" + str(path).replace("\\", "/")

    doc = fitz.open(str(path))
    hits, nav = scan3(doc, npages)
    out_dir = REPORTS / sno
    out_dir.mkdir(parents=True, exist_ok=True)

    panes, rows = [], []
    for kind in KINDS:
        if not nav.get(kind):
            continue
        withrows = [c for c in nav[kind] if c[3] > 0]
        if withrows:
            pno, hy, bb, _n = max(withrows, key=lambda c: (c[3], -c[0]))
        else:
            pno, hy, bb, _n = min(nav[kind], key=lambda c: c[0])
        png = out_dir / ("b3_%s_p%04d.png" % (kind, pno))
        page = doc.load_page(pno - 1)
        rect, used = B.render_clip(page, hy, bb, png)
        lines = I2.lines_in_rect(page, rect)

        vrows, vmeta = [], {}
        if not args.no_vlm:
            try:
                vrows, vmeta = vl_extract(png)
            except Exception as e:
                vmeta = {"error": "%s: %s" % (type(e).__name__, e)}

        pane_rows = []
        ptxt = I2.page_text(page)
        for vr in vrows:
            row = {
                "sample_no": sno, "file_name": fname,
                "evidence_page": str(pno), "table_title": KIND_CN[kind],
                "symbol": vr["symbol"],
                "parameter_name": vr["parameter_name"],
                "min_value": vr["min_value"], "typ_value": vr["typ_value"],
                "max_value": vr["max_value"], "unit": vr["unit"],
                "condition": "",
                "row_status": "DRAFT_AWAITING_HUMAN_CONFIRM",
                "notes": "VLM 草稿，须对左图核；vlm自报=%.2f" % vr["vlm_confidence"],
                "reviewer": "",
            }
            pane_rows.append(row)

        if not pane_rows:      # VLM 空手而归时退回文本表格解析，别让页面白给
            pane_rows = B.to_rows(sno, fname, kind, hits.get(kind, []))
            for r in pane_rows:
                r["notes"] = (r.get("notes", "")
                              + "；VLM 无结果，退回文本表格解析").strip("；")

        for r in pane_rows:
            I2.sanitize_row(r, ptxt)
            I2.repair_name(r)
        rows.extend(pane_rows)

        panes.append({"kind": kind, "pno": pno,
                      "rel": png.relative_to(PREP).as_posix(),
                      "bbox": used, "lines": lines,
                      "vmeta": vmeta, "use_vl": bool(vrows),
                      "span": sorted({n[0] for n in nav[kind]})})

    score_rows3(doc, rows)          # 必须在 close 之前，det_score 要读页文本
    # doc 暂不 close：下面的 EXCLUDED 理由还要逐页探测文本层。

    # —— 只留核心 3~5 行 ——
    keep, drop, _ = pick_core(rows)
    # 首轮一行都没留下、但确实抽到了行 → 走二轮「一等电气特性」兜底。
    # 只在首轮为空时启用，已有草稿的样本行为完全不变。
    ext_used = False
    if not keep and rows:
        keep_ext, drop_ext = pick_core_ext(rows)
        if keep_ext:
            keep, drop, ext_used = keep_ext, drop_ext, True
            for r in keep:
                # 逐行打头标「非白名单」，供 PM 逐条决定是否纳入 Gold；
                # 不能只在样本级说明里提一句，Excel 里筛不出来。
                r["notes"] = (EXT_PREFIX
                              + (r.get("notes", "") + "；" + EXT_NOTE).strip("；"))
    # VLM 不抄 TEST CONDITIONS：按参数块内出现顺序从原图回填（Fail-Closed）
    apply_condition_backfill(keep, sno)
    # 回填完必须回原文核一遍：条件在原页文本里找不到，就是绑错了页或错了行。
    # 归一化只做 °→o（PDF 文本层常把度数符号抽成 o）与空白折叠，不做同义改写。
    for r in keep:
        cond = (r.get("condition") or "").strip()
        if not cond:
            continue
        _p = doc.load_page(int(r["evidence_page"]) - 1).get_text("text")
        _norm = lambda x: " ".join(x.replace("\u00b0", "o").split())
        if _norm(cond) not in _norm(_p):
            raise SystemExit(
                "FAIL %s p%s %s 的 condition %r 在原页文本里核不到，"
                "拒绝交付未经验证的条件" % (sno, r["evidence_page"],
                                            r.get("symbol"), cond))
    mark_dups(keep)

    # low_confidence 标记：低于阈值的行在 notes 里打词，方便 Excel 筛。
    for r in keep:
        try:
            low = float(r.get("confidence_score") or 0) < THRESH
        except ValueError:
            low = True
        bad = value_flags(r)
        if bad:
            low = True
            r["notes"] = (r.get("notes", "") + "；" + "；".join(bad)).strip("；")
        if low and WARN not in r.get("notes", ""):
            r["notes"] = (r.get("notes", "") + " | " + WARN).strip(" |")

    nlines = sum(len(p["lines"]) for p in panes)
    nlow = sum(1 for r in keep if WARN in r.get("notes", ""))
    if not panes:
        # 「没定位到表」不等于「可以出草稿」。把原因分成两类可审计结论，
        # 让 PM 在圈选台里一眼看到该件该不该点选，而不是只看到「未定位」。
        # 判据：datasheet 主体在前 12 页；连续 >=3 页无文本层 → 扫描图主体。
        chars = [len(doc.load_page(i).get_text("text").strip())
                 for i in range(npages)]
        blank = sum(1 for n in chars if n == 0)
        run = best = 0
        for n in chars[:12]:
            run = run + 1 if n == 0 else 0
            best = max(best, run)
        if best >= 3:
            quality = "无文本层"
            if blank == npages:
                note = ("全书 %d/%d 页无文本层，前 12 页有连续 %d 页空白；"
                        "%s（不进点选）" % (blank, npages, best, OFF_EXCL_NOLAYER))
            else:
                # 只部分页是扫描图（B4 V041 的情形）：不能说「整本无文本层」，
                # 文本层页确实存在，只是它们不是电气特性页。
                note = ("全书 %d/%d 页无文本层（前 12 页有连续 %d 页空白），"
                        "其余 %d 页虽有文本层，但未定位到电气参数表；"
                        "%s（不进点选）"
                        % (blank, npages, best, npages - blank, OFF_EXCL_SCANPAGE))
        else:
            quality = "无电气参数表"
            note = ("全书有文本层，但未定位到带 MIN/TYP/MAX 列的参数表"
                    "（本件多为封装 / 机械 / 卷带 / 免责声明资料）；"
                    "EXCLUDED: 无标准参数表，无法建立 Gold（不进点选）")
    elif nlines == 0:
        quality = "无文本层"
        note = "页面抓不到文字（纯图形/扫描），建议整件标 EXCLUDED"
    elif not keep:
        # 术语解释页/线图/错表：全部行都不是「带数值的核心参数」，
        # 此时绝不能交草稿给人，直接给 EXCLUDED 建议。
        quality, note = ("无法定位参数表",
                         "定位到 %d 页，白名单与一等电气特性两轮都没抽到"
                         "带数值的核心参数行；建议整件标 "
                         "EXCLUDED: 表格定位失败/无标准参数表" % len(panes))
    elif ext_used:
        quality = "需重点核（二轮兜底）"
        note = ("白名单核心参数 0 行，改按一等电气特性兜底选出 %d 行"
                "（非白名单口径，须逐行对图核）" % len(keep))
    elif nlow:
        quality, note = "需重点看", "核心 %d 行中 %d 行 low_confidence，先核这些" % (len(keep), nlow)
    else:
        quality, note = "好", "核心 %d 行置信度均 ≥%.2f" % (len(keep), THRESH)

    if sno in EXCLUDED_REASON and (not keep):
        note = EXCLUDED_REASON[sno]
        if quality == "好" or quality.startswith("需重点"):
            quality = "无电气参数表"

    card = {"sno": sno, "fname": fname, "npages": npages, "pdf": pdf_url,
            "panes": panes, "rows": keep, "quality": quality, "note": note,
            "dropped": len(drop), "nlow": nlow, "ext": ext_used,
            "hint": REVIEW_HINTS.get(sno, ""),
            "warn": WARN_BANNER.get(sno, ""),
            "stratum": meta.get("stratum_proposed", "")}
    doc.close()
    return keep, card


def main():
    ap = argparse.ArgumentParser(description="Batch 3 草稿 + 圈选台")
    ap.add_argument("--samples", default=",".join(BATCH1),
                    help="逗号分隔的 sample_no；默认第一批 6 件")
    ap.add_argument("--out-prefix", default="Batch3",
                    help="输出文件名前缀，默认 Batch3")
    ap.add_argument("--no-vlm", action="store_true",
                    help="不调视觉模型，只用文本表格解析（调试用）")
    ap.add_argument("--label", default="Batch 3",
                    help="圈选台标题里的批次名，如 B4 / SCAN")
    args = ap.parse_args()
    want = [s.strip() for s in args.samples.split(",") if s.strip()]

    meta_all = {r["sample_no"]: r for r in
                csv.DictReader(open(WORKING, encoding="utf-8-sig"))}
    todo = []
    for s in want:
        if s in DONE:
            print("跳过 %s：Batch 2 已定稿" % s)
            continue
        if s not in meta_all:
            print("警告 %s：不在 Gold_Set_v1.1_WORKING.csv 里，跳过" % s)
            continue
        todo.append(meta_all[s])

    rows_out, cards = [], []
    for meta in todo:
        print("  ... %s" % meta["sample_no"], end="", flush=True)
        got, card = one_sample(meta, args)
        rows_out.extend(got)
        cards.append(card)
        print(" → 核心 %d 行（low=%d，丢弃 %d）"
              % (len(got), card["nlow"], card["dropped"]))

    out_csv = PREP / ("%s_DRAFT.csv" % args.out_prefix)
    out_html = PREP / ("%s_Viewer.html" % args.out_prefix)

    # utf-8-sig：Excel 靠 BOM 判编码，否则 ° µ − 会变 ?（中文 Windows 按 GBK 解码）
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        for r in rows_out:
            w.writerow({k: r.get(k, "") for k in COLS})

    p = []
    p.append('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">')
    p.append("<title>%s 圈选台（左图右文）</title>" % B.esc(args.label))
    p.append("<style>%s%s%s</style></head><body>"
             % (B.CSS, I2.EXTRA_CSS,
                ".hint-review{background:#fff4ce;border-left:4px solid #d68b00;"
                "padding:8px 10px;margin:8px 0;border-radius:4px;font-size:13px}"
                ".hint-warn{background:#fdecea;border-left:4px solid #c0392b;"
                "padding:9px 11px;margin:8px 0;border-radius:4px;font-size:13px;"
                "color:#7b1a12}"))
    p.append("<header><h1>%s 圈选台 · %d 件 · 核心参数草稿</h1>"
             % (B.esc(args.label), len(cards)))
    p.append("<p>左边是原图，右边是同区域抓出的纯文本。"
             "页面下方已载入 <b>VLM 草稿</b>，每件只留最核心的 3~5 行；"
             "红底行是 <code>low_confidence</code>，请优先对图。</p></header>")
    p.append('<div class="wrap">')

    p.append('<div class="note"><h2>怎么用</h2><ul>'
             "<li>草稿<b>不是 Gold</b>。每一行都要对着左图核一遍再改状态。</li>"
             "<li>核过的行改 <code>CONFIRMED</code>；说不清的改 <code>UNRESOLVED</code>；"
             "不是参数（表头、注释）直接删。</li>"
             "<li><b>红底 = low_confidence</b>：数值在页面文本里没对上、或单位对不上、"
             "或模型自报很低。这些行最可能有错。</li>"
             "<li>草稿没覆盖的核心参数，用「新增空行」自己补。</li>"
             "<li>最后按「下载 CSV」。<b>不要用 Excel 另存</b>，会把编码变成 GBK。</li>"
             "</ul>"
             '<div class="hint">导出时会拦：状态 CONFIRMED 却没有数值的行、'
             "既无参数名又无符号的行。</div></div>")

    for c in cards:
        p.append('<div class="card"><div class="head">')
        p.append('<span class="sn">%s</span><span class="fn">%s</span>'
                 % (B.esc(c["sno"]), B.esc(c["fname"])))
        p.append('　<a href="%s" target="_blank">在 PDF 中打开</a>' % B.esc(c["pdf"]))
        cls = "t-ok" if c["quality"] == "好" else "t-warn"
        tags = ['<span class="tag %s">草稿：%s</span>' % (cls, B.esc(c["quality"]))]
        if c.get("ext"):
            tags.append('<span class="tag t-warn">二轮兜底：非白名单</span>')
        for pn in c["panes"]:
            tags.append('<span class="tag %s">%s = p%s</span>'
                        % ("t-amr" if pn["kind"] == "AMR" else "t-elc",
                           pn["kind"], "/".join(str(x) for x in pn["span"])))
        p.append('<div class="meta">共 %d 页 　%s</div>' % (c["npages"], "".join(tags)))
        p.append('<div class="meta">%s</div>' % B.esc(c["note"]))
        if c.get("warn"):
            # 高亮块：这段是 HTML，带 <b>/<code>，不再转义
            p.append('<div class="hint hint-warn"><b>必须核对</b>　%s</div>'
                     % c["warn"])
        if c.get("hint"):
            p.append('<div class="hint hint-review"><b>核查提示</b>　%s</div>'
                     % B.esc(c["hint"]))
        p.append('</div><div class="body">')

        if c["quality"] == "无文本层":
            p.append('<div class="err">本页抓不到任何文字（纯图形/扫描件）。'
                     "排除话术请按事实选：全书确实无文本层用 "
                     "<code>%s</code>；只有电气特性页是扫描图则用 "
                     "<code>%s</code>，不要一刀切。</div>"
                     % (B.esc(OFF_EXCL_NOLAYER), B.esc(OFF_EXCL_SCANPAGE)))
        if c["quality"] == "无法定位参数表":
            p.append('<div class="err">全书未抽到任何带数值的核心参数行，'
                     '本件<b>不落草稿</b>。请整件标 '
                     "<code>EXCLUDED: 表格定位失败/无标准参数表</code>，"
                     "不要把术语解释、引脚说明当成参数行。</div>")
        for pn in c["panes"]:
            p.append('<div class="pane" data-sno="%s" data-fn="%s" data-page="%d" '
                     'data-title="%s">'
                     % (B.esc(c["sno"]), B.esc(c["fname"]), pn["pno"],
                        B.esc(KIND_CN[pn["kind"]])))
            p.append('<div class="cols"><div class="left">'
                     '<a href="%s" target="_blank"><img src="%s" alt="%s p%d"></a>'
                     '<div class="cap">%s · 第 %d 页%s</div></div>'
                     % (B.esc(pn["rel"]), B.esc(pn["rel"]), B.esc(c["sno"]),
                        pn["pno"], B.esc(KIND_CN[pn["kind"]]), pn["pno"],
                        "（按表格边框裁剪）" if pn["bbox"] else "（按标题位置裁剪）"))
            p.append('<div class="right"><div class="rh">点下面任意一行 → 自动填字段'
                     '<span class="cnt">%d 行</span></div><ol class="lines">'
                     % len(pn["lines"]))
            for ln in pn["lines"]:
                p.append('<li class="line" data-t="%s">%s</li>'
                         % (B.esc(ln), B.esc(ln)))
            p.append("</ol></div></div></div>")

        if c["rows"]:
            p.append('<div class="dh">本件核心草稿 %d 行（另有 %d 行非核心未载入）；'
                     '<span class="pill ok">绿 ≥%.2f</span> '
                     '<span class="pill low">红 &lt;%.2f = low_confidence</span></div>'
                     % (len(c["rows"]), c["dropped"], THRESH, THRESH))
        p.append("</div></div>")

    p.append('<div class="work"><h2>标注编辑区　<span id="cnt">0</span></h2>')
    p.append('<div class="filter">'
             '<label>样本 <select id="fsample"></select></label>'
             '<label><input type="checkbox" id="fnum"> 只看有数值的行</label>'
             '<label><input type="checkbox" id="ftodo"> 只看未确认的行</label>'
             '<button class="ghost" onclick="addBlank()">新增空行</button>'
             '<button class="ghost" onclick="dropNoName()">删掉无参数名的行</button>'
             '<button class="ghost" onclick="resetDraft()">恢复机器草稿</button>'
             '<label class="imp">导入上次的 CSV <input type="file" id="fimp" accept=".csv"></label>'
             "</div>")
    p.append('<div id="stat" class="stat"></div>')
    p.append('<table class="rows" id="tbl"><thead><tr>'
             "<th>样本</th><th>页</th><th>符号</th><th>参数名</th><th>min</th>"
             "<th>typ</th><th>max</th><th>单位</th><th>状态</th><th>草稿分</th>"
             "<th></th></tr></thead><tbody id=\"tbody\"></tbody></table>")
    p.append('<div class="bar"><button onclick="downloadCSV()">下载 CSV（UTF-8 带 BOM）</button>'
             '<button onclick="copyOut()" class="dl">复制 CSV</button> '
             '<label style="font-size:12.5px;margin-left:8px">'
             '<input type="checkbox" id="dropEmpty" checked> 导出时丢掉无值行/无参数名行</label>'
             '<span id="msg" class="msg"></span></div>')
    p.append('<textarea id="out" readonly></textarea>')
    p.append("</div>")
    p.append("</div><script>%s</script></body></html>"
             % build_js(rows_out, args.out_prefix + "_ANNOTATED"))
    out_html.write_text("".join(p), encoding="utf-8", newline="\n")

    print("\n圈选台: %s (%.1f KB, %d 件)"
          % (out_html.name, out_html.stat().st_size / 1024, len(cards)))
    print("草稿  : %s (%d 行)" % (out_csv.name, len(rows_out)))
    for c in cards:
        print("  %-5s %-6s 核心=%d low=%d 丢弃=%d  %s"
              % (c["sno"], c["quality"], len(c["rows"]), c["nlow"],
                 c["dropped"], c["note"][:36]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
