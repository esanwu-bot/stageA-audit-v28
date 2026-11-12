# -*- coding: utf-8 -*-
"""CORE_ORDER 供电符号正则 + prescan3 表头结构判据的回归测试。

Reviewer 2026-11-12 指出的两个通用漏洞：
  1. `^v(cc|dd|s)\\b|\\bv(cc|dd)\\b` 里的 `\\b` 挡住了带后缀的供电符号
     （VDD_CORE / VDDR_CORE / VDDSHV5），它们会被判成 pri=99 的非核心参数，
     在 pick_core() 里被整行丢掉。
  2. prescan3() 只数「页面出现 >=2 个 MIN/TYP/MAX/NOM」，正文里反复提
     minimum / maximum 也会被当成参数表，属于 Fail-Open。

本测试**全部用内存对象与合成 PDF 页**，不依赖任何外部 PDF 或环境变量，
因此不存在 SKIP：跑不全就是 FAIL，退出码非零。
"""
from __future__ import print_function

import sys
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _build_batch3_interactive as I3

CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


def row(symbol, name="", minv="0.8"):
    """构造一行：parameter_name 故意留空，只让符号去命中供电正则。"""
    return {"parameter_name": name, "symbol": symbol,
            "min_value": minv, "typ_value": "", "max_value": "",
            "unit": "V", "condition": "", "confidence_score": "0.90"}


def pdf_page(lines):
    """合成一页只有文本层、没有表格边框的 PDF。"""
    doc = fitz.open()
    pg = doc.new_page()
    y = 72.0
    for ln in lines:
        pg.insert_text((72.0, y), ln, fontsize=9)
        y += 14.0
    return doc


REAL_HEADER_AMR = [
    "6.1 Absolute Maximum Ratings",
    "over operating free-air temperature range",
    "PARAMETER", "MIN", "MAX", "UNIT",
    "VDD_CORE", "Core supply", "-0.3", "1.05", "V",
]

REAL_HEADER_ROC = [
    "6.4 Recommended Operating Conditions",
    "SUPPLY NAME", "DESCRIPTION", "MIN(1)", "NOM", "MAX(1)", "UNIT",
    "VDD_CORE", "Core supply", "0.81", "0.85", "0.895", "V",
]

# 正文里 MIN/MAX/TYP/NOM 出现很多次，也带表标题词，但没有任何表头结构。
PROSE_ONLY = [
    "6.1 Absolute Maximum Ratings",
    "The MIN value and the MAX value must both be observed in this section.",
    "MIN is the lower bound; MAX is the upper bound of the operating range.",
    "TYP and NOM are typical ratings, not MIN or MAX limits.",
    "Stresses beyond those listed under Absolute Maximum Ratings may cause damage.",
    "Refer to the Recommended Operating Conditions for MIN and MAX limits.",
]


# —— 正向：5 个被点名的符号，只靠 symbol 也要判成核心供电 ——
def _positive(sym):
    def _t():
        r = row(sym)
        pri = I3.core_rank(r)[0]
        assert pri == 1, "%s 的优先级应为 1（供电），实际 %d" % (sym, pri)
        keep, drop, _ = I3.pick_core([r])
        assert keep and keep[0] is r, "%s 被 pick_core 丢掉了" % sym
        assert not drop, "%s 不该产生 dropped 行" % sym
    return _t


for _sym in ("VDD_CORE", "VDDR_CORE", "VDDSHV5", "VCC", "VDD"):
    case("正向 供电符号 %-10s → pri=1 且被 pick_core 保留" % _sym)(_positive(_sym))


@case("正向 带前缀的供电符号 AVDD3V / DVDD / IOVDD 同样命中")
def _prefixed():
    for s in ("AVDD3V", "DVDD", "IOVDD"):
        assert I3.core_rank(row(s))[0] == 1, "%s 未命中" % s


@case("正向 参数名里的 Supply voltage range 仍能命中（不依赖符号）")
def _by_name():
    assert I3.core_rank(row("VA19", "Supply voltage range"))[0] == 1
    assert I3.core_rank(row("VFUSE", "Power-supply voltage"))[0] == 1


@case("反向 非供电的术语条目不得被放宽的正则误判为核心")
def _not_core():
    for s in ("PULL UP/DOWN TYPE", "BUFFER TYPE", "MUX MODE AFTER RESET"):
        assert I3.core_rank(row(s))[0] == 99, "%s 被误判为核心" % s


# —— 表头结构：正向真表头 ——
@case("正向表头 AMR 型（PARAMETER / MIN / MAX / UNIT）识别为表头")
def _hdr_amr():
    assert I3.has_table_header("\n".join(REAL_HEADER_AMR)) is True


@case("正向表头 ROC 型（MIN(1) / NOM / MAX(1) / UNIT）识别为表头")
def _hdr_roc():
    assert I3.has_table_header("\n".join(REAL_HEADER_ROC)) is True


@case("反向表头 只有 1 个独立列词行时不放行")
def _hdr_single():
    assert I3.has_table_header("MIN\nUNIT\nsome other text") is False


@case("反向表头 含多个 MIN/MAX 词汇的纯正文不识别为表头")
def _hdr_prose():
    assert I3.has_table_header("\n".join(PROSE_ONLY)) is False


# —— prescan3：合成整页，验证不会误放行 ——
@case("反向整页 纯正文（含多组 MIN/MAX + 表标题词）不进候选页")
def _prescan_prose():
    doc = pdf_page(PROSE_ONLY)
    got = I3.prescan3(doc, doc.page_count)
    assert got == [], "正文被误放行：%s" % got


@case("正向整页 真 AMR 表头页进候选页")
def _prescan_amr():
    doc = pdf_page(REAL_HEADER_AMR)
    assert I3.prescan3(doc, doc.page_count) == [1]


@case("正向整页 真 ROC 表头页进候选页")
def _prescan_roc():
    doc = pdf_page(REAL_HEADER_ROC)
    assert I3.prescan3(doc, doc.page_count) == [1]


@case("反向整页 p14 式术语解释页（无 MIN/MAX 表头）不进候选页")
def _prescan_terms():
    lines = [
        "5 Pin Configuration and Functions",
        "13. PULL UP/DOWN TYPE: Indicates the presence of an internal pull-up.",
        "For more information, see the hysteresis values in Electrical Characteristics.",
        "PU: Internal pull-up", "PD: Internal pull-down",
        "For electrical characteristics, refer to the appropriate buffer type table.",
    ]
    doc = pdf_page(lines)
    assert I3.prescan3(doc, doc.page_count) == []


@case("回归 温度/电流符号不再被 ^ 锚漏判（TA/Tstg/TJ/IO/II）")
def _symbol_anchors():
    for s, want in (("TA", 2), ("Tstg", 3), ("TJ", 4), ("IO", 5), ("II", 6)):
        pri = I3.core_rank(row(s))[0]
        assert pri == want, "%s 优先级应为 %d，实际 %d" % (s, want, pri)


@case("回归 V003 的 VDD_CORE/VDDR_CORE/VDDSHV5/TJ 全部仍为核心参数")
def _v003_symbols():
    for s in ("VDD_CORE", "VDDR_CORE", "VDDSHV5"):
        assert I3.core_rank(row(s))[0] == 1, "%s 应是核心供电" % s
    assert I3.core_rank(row("TJ"))[0] == 4, "TJ 应是结温（优先级 4）"


# —— Reviewer 第三轮：prescan3 的四个极端场景 ——
# 用可控的「文本层 + 边框表格」对象，精确构造排版，而不是靠真实 PDF 碰运气。
DEFAULT_BORDER_BBOX = (56.0, 400.0, 550.0, 500.0)   # 页底：离页顶标题很远


class FakeTable(object):
    def __init__(self, rows, bbox=DEFAULT_BORDER_BBOX):
        self._rows = rows
        self.bbox = bbox

    def extract(self):
        return self._rows


class FakeTables(object):
    def __init__(self, tables):
        self.tables = tables


class FakePage(object):
    """可控的文本层 + 边框表格；borders 元素可为 rows 或 (rows, bbox)。

    新增 rect / last_clip：用来验证 find_tables(clip=本页矩形) 这道
    跨页污染隔离确实生效，而不是只在真实 PDF 上「碰巧通过」。
    """

    def __init__(self, lines, borders=()):
        self._lines = list(lines)
        self._text = "\n".join(lines)
        self.rect = fitz.Rect(0.0, 0.0, 612.0, 792.0)
        self.last_clip = None
        self._tables = []
        for spec in borders:
            if (isinstance(spec, tuple) and len(spec) == 2
                    and isinstance(spec[0], list)):
                rows, bbox = spec
            else:
                rows, bbox = spec, DEFAULT_BORDER_BBOX
            self._tables.append(FakeTable(rows, bbox))

    def get_text(self, *a, **k):
        fmt = a[0] if a else k.get("option", "text")
        if fmt == "dict":
            lines = [{"spans": [{"text": ln}],
                      "bbox": (72.0, 72.0 + 14.0 * i, 400.0, 82.0 + 14.0 * i)}
                     for i, ln in enumerate(self._lines)]
            return {"blocks": [{"lines": lines}]}
        return self._text

    def find_tables(self, clip=None):
        self.last_clip = clip
        return FakeTables(self._tables)


class FakeDoc(object):
    """单页或多页；多页用于验证跨页续表的上一页上下文证据。"""

    def __init__(self, pages):
        if not isinstance(pages, (list, tuple)):
            pages = [pages]
        self._pages = list(pages)
        self.page_count = len(self._pages)

    def load_page(self, i):
        assert 0 <= i < len(self._pages), "页号越界：%d" % i
        return self._pages[i]


def prescan_fake(lines, borders=()):
    return I3.prescan3(FakeDoc(FakePage(lines, borders)), 1)


# a. 目标表（AMR）没有表头，同页另一处有个无关的 Pin Configuration 表格。
CASE_A = [
    "6.1 Absolute Maximum Ratings",
    "VDD_CORE  -0.3  1.05  V",
    "VDDR_CORE  -0.3  1.05  V",
    "",
    "Table 4-1 Pin Configuration",
    "PIN", "MIN", "MAX", "UNIT",
    "A1   1.0   2.0   V",
]
CASE_A_BORDER = [
    [["PIN", "MIN", "MAX", "UNIT"], ["A1", "1.0", "2.0", "V"]],
]

# b. 标题词只出现在正文句子里，MIN/MAX 列词在页面另一区域。
CASE_B = [
    "Stresses beyond those listed under Absolute Maximum Ratings may cause permanent damage.",
    "The MIN and MAX values are the limits of the operating range.",
    "TYP and NOM are typical ratings, not MIN or MAX limits.",
    "",
    "PARAMETER", "MIN", "MAX", "UNIT",
    "Some unrelated row without numbers",
]

# c. 有边框表格，但前两行是文档信息而不是表头；文本层的列词挤在同一行。
CASE_C = [
    "6.1 Absolute Maximum Ratings",
    "PARAMETER   MIN   MAX   UNIT",
    "The MIN and MAX ratings are listed below.",
    "VDD_CORE  -0.3  1.05  V",
]
CASE_C_BORDER = [
    [["Device Information", "Rev A", ""], ["Note", "Value", ""]],
]

# e. V003 p106 实测形态：既无独立标题行，也没有 (continued) 字样，
#    只有表格顶端落在页首 y0=86.0。第六轮起光靠 y 坐标不再放行，
#    必须拿出「上一页同结构 + 水平宽度对齐」的跨页续表证据。
CASE_E = [
    "Refer to the Recommended Operating Conditions for OTP eFuse Programming table.",
    "SUPPLY NAME", "DESCRIPTION", "MIN(1)", "NOM", "MAX(1)", "UNIT",
    "VDDSHV5", "Dual-voltage IO supply", "1.8V Operation",
    "1.71", "1.8", "1.89", "V",
]
CASE_E_BORDER = [
    ([["SUPPLY NAME", "DESCRIPTION", "", "MIN(1)", "NOM", "MAX(1)", "UNIT"],
      ["VDDSHV5", "Dual-voltage IO supply", "1.8V Operation",
       "1.71 1.8 1.89", "", "", "V"]],
     (56.0, 86.0, 550.0, 200.0)),
]
# 上一页（V003 p105 实测 x0=56.8 / x1=555.3），与 p106 差 0.8 / 5.3pt。
PREV_E_LINES = [
    "6.4 Recommended Operating Conditions",
    "SUPPLY NAME", "DESCRIPTION", "MIN(1)", "NOM", "MAX(1)", "UNIT",
    "VDD_CORE", "Core supply", "0.81", "0.85", "0.895", "V",
]
PREV_E_BORDER = [
    ([["SUPPLY NAME", "DESCRIPTION", "MIN(1)", "NOM", "MAX(1)", "UNIT"],
      ["VDD_CORE", "Core supply", "0.81", "0.85", "0.895", "V"]],
     (56.8, 108.2, 555.3, 300.0)),
]

# h. Reviewer 第六轮反例：页首一张无关的「完整参数表」，页面上方有
#    一个无章节号的纯 AMR 标题。旧逻辑 `y0<=160 → True` 会直接放行。
CASE_H = [
    "Absolute Maximum Ratings",
    "over operating free-air temperature range",
    "",
    "Table 4-1 Pin Configuration",
    "PIN", "PARAMETER", "MIN", "MAX", "UNIT",
    "A1", "Pull-up", "1.0", "2.0", "V",
]
CASE_H_BORDER = [
    ([["PIN", "PARAMETER", "MIN", "MAX", "UNIT"],
      ["A1", "Pull-up", "1.0", "2.0", "V"]],
     (56.0, 100.0, 550.0, 210.0)),
]
# 上一页表格同结构但水平宽度明显不对齐（x0 差 144pt / x1 差 150pt）。
CASE_I_PREV_LINES = [
    "6.1 Absolute Maximum Ratings",
    "PARAMETER", "MIN", "MAX", "UNIT",
    "VDD_CORE", "-0.3", "1.05", "V",
]
CASE_I_PREV_BORDER = [
    ([["PARAMETER", "MIN", "MAX", "UNIT"], ["VDD_CORE", "-0.3", "1.05", "V"]],
     (200.0, 108.0, 400.0, 300.0)),
]

# j. 弱锚点（无章节号纯标题）对非页首表格仍应有效，避免修得过紧。
CASE_J = [
    "Absolute Maximum Ratings",
    "PARAMETER", "MIN", "MAX", "UNIT",
    "VDD_CORE", "-0.3", "1.05", "V",
]
CASE_J_BORDER = [
    ([["PARAMETER", "MIN", "MAX", "UNIT"], ["VDD_CORE", "-0.3", "1.05", "V"]],
     (56.0, 230.0, 550.0, 330.0)),
]

# f. Reviewer 第五轮反例：独立 AMR 标题 + AMR 区域无表头 + 页底无关表格带表头。
CASE_F = [
    "6.1 Absolute Maximum Ratings",
    "over operating free-air temperature range (unless otherwise noted)",
    "VDD_CORE   -0.3   1.05   V",
    "VDDR_CORE  -0.3   1.05   V",
    "",
    "Table 4-1 Pin Configuration",
    "PIN   MIN   MAX   UNIT",
    "A1    1.0   2.0   V",
]
CASE_F_BORDER = [
    ([["PARAMETER", "MIN", "MAX", "UNIT"], ["A1", "1.0", "2.0", "V"]],
     (56.0, 400.0, 550.0, 500.0)),
]

# g. Reviewer 第五轮正例：明确的续表标识 + 对应的真实 AMR 续表边框表头。
CASE_G = [
    "Table 6-1. Absolute Maximum Ratings (continued)",
    "PARAMETER", "MIN", "MAX", "UNIT",
    "VDD_CORE", "-0.3", "1.05", "V",
]
CASE_G_BORDER = [
    ([["PARAMETER", "MIN", "MAX", "UNIT"],
      ["VDD_CORE", "-0.3", "1.05", "V"]],
     (56.0, 130.0, 550.0, 220.0)),
]


@case("反向极端 a 同页有无关表格、目标表没表头 → 拦截")
def _extreme_a():
    txt = "\n".join(CASE_A)
    assert I3.title_anchor_lines(txt) == [0], "AMR 独立标题行没找到"
    assert I3.has_table_header(txt, I3.title_anchor_lines(txt)) is False, \
        "无关表格的 MIN/MAX 被当成目标表表头"
    assert I3._table_header_from_borders(FakePage(CASE_A, CASE_A_BORDER)) is False, \
        "无关边框表格（PIN/MIN/MAX/UNIT）被当成参数表"
    assert prescan_fake(CASE_A, CASE_A_BORDER) == [], "整页被误放行"


@case("反向极端 b 标题只在正文句子里、另一区域有 MIN/MAX → 拦截")
def _extreme_b():
    txt = "\n".join(CASE_B)
    assert I3.title_anchor_lines(txt) == [], "正文句子被当成独立标题行"
    assert I3.has_table_header(txt, I3.title_anchor_lines(txt)) is False
    assert prescan_fake(CASE_B) == [], "标题与表头不同区域仍被误放行"


@case("反向极端 c 有边框表格但前两行不是有效表头 → 拦截")
def _extreme_c():
    assert I3._table_header_from_borders(FakePage(CASE_C, CASE_C_BORDER)) is False
    assert prescan_fake(CASE_C, CASE_C_BORDER) == [], "无效边框表头被误放行"


@case("正向极端 d 真实无边框 AMR 表 → 保留")
def _extreme_d_amr():
    pg = FakePage(REAL_HEADER_AMR, ())
    assert pg.find_tables().tables == [], "本用例应模拟无边框文本层表"
    assert I3.prescan3(FakeDoc(pg), 1) == [1], "真 AMR 表被误杀"


@case("正向极端 d 真实无边框 ROC 表 → 保留")
def _extreme_d_roc():
    pg = FakePage(REAL_HEADER_ROC, ())
    assert pg.find_tables().tables == []
    assert I3.prescan3(FakeDoc(pg), 1) == [1], "真 ROC 表被误杀"


@case("正向第六轮 页首续表 + 上一页同结构且水平对齐 → 保留（V003 p102/p106 形态）")
def _extreme_continuation():
    pg = FakePage(CASE_E, CASE_E_BORDER)
    prev = FakePage(PREV_E_LINES, PREV_E_BORDER)
    txt = "\n".join(CASE_E)
    assert I3.title_anchor_lines(txt) == [], "续表不该有独立标题行"
    assert I3._anchor_ys(pg) == [], "p106 式页面确实没有标题/续表锚点"
    assert I3.has_table_header(txt, []) is False
    # Fail-Closed：没有上一页证据时，页首表格绝不能凭 y 坐标放行
    assert I3._table_header_from_borders(pg) is False, \
        "页首表格没有跨页证据仍被放行，Fail-Open 未修复"
    assert prescan_fake(CASE_E, CASE_E_BORDER) == [], \
        "单页（无上一页）的页首表格不该进候选页"
    # 有上一页证据时保留
    assert I3._table_header_from_borders(pg, prev) is True, \
        "真实跨页续表被误杀"
    got = I3.prescan3(FakeDoc([prev, pg]), 2)
    assert 2 in got, "跨页续表没进候选页：%s" % got


@case("反向第六轮 页首无关完整参数表 + 页面上方 AMR 标题 → 拦截（旧逻辑会放行）")
def _extreme_h():
    pg = FakePage(CASE_H, CASE_H_BORDER)
    assert I3._anchor_ys(pg, strong_only=True) == [], \
        "无关表题 / 纯 AMR 标题不该被算成强锚点"
    assert I3._anchor_ys(pg), "纯 AMR 标题应被识别为弱锚点"
    assert I3._table_header_from_borders(pg) is False, \
        "页首无关表格借 y0<=160 被误放行"
    assert prescan_fake(CASE_H, CASE_H_BORDER) == [], "整页被误放行"


@case("反向第六轮 页首表格 + 上一页同结构但水平宽度不对齐 → 拦截")
def _extreme_i():
    pg = FakePage(CASE_H, CASE_H_BORDER)
    prev = FakePage(CASE_I_PREV_LINES, CASE_I_PREV_BORDER)
    sig = I3._prev_table_signatures(prev)
    assert len(sig) == 1, "上一页应有一个有效参数表头签名"
    assert I3._table_header_from_borders(pg, prev) is False, \
        "宽度不对齐的上一页表格被当成续表证据"
    got = I3.prescan3(FakeDoc([prev, pg]), 2)
    assert 2 not in got, "页首无关表借不对齐的上一页被误放行：%s" % got


@case("正向第六轮 弱锚点（纯 AMR 标题）对非页首表格仍有效 → 保留，防过度收紧")
def _extreme_j():
    pg = FakePage(CASE_J, CASE_J_BORDER)
    assert I3._anchor_ys(pg, strong_only=True) == [], "纯标题不是强锚点"
    assert I3._table_header_from_borders(pg) is True, \
        "非页首真表被过度收紧误杀"


@case("反向第五轮 独立 AMR 标题 + AMR 区无表头 + 页底无关边框表 → 拦截")
def _extreme_f():
    pg = FakePage(CASE_F, CASE_F_BORDER)
    txt = "\n".join(CASE_F)
    assert I3.title_anchor_lines(txt) == [0], "AMR 独立标题行没找到"
    assert I3.has_table_header(txt, [0]) is False, "AMR 区没有表头却被当成有表头"
    assert I3._table_header_from_borders(pg) is False, \
        "页底无关表格借页顶 AMR 标题被误关联"
    assert prescan_fake(CASE_F, CASE_F_BORDER) == [], "整页被误放行"


@case("正向第五轮 明确续表标识 + 真 AMR 续表边框表头 → 保留")
def _extreme_g():
    pg = FakePage(CASE_G, CASE_G_BORDER)
    txt = "\n".join(CASE_G)
    assert I3.title_anchor_lines(txt) == [], "续表标识行不是纯标题行"
    assert I3._anchor_ys(pg), "续表标识行没被识别为空间锚点"
    assert I3._table_header_from_borders(pg) is True, "真 AMR 续表被误杀"
    assert prescan_fake(CASE_G, CASE_G_BORDER) == [1]


# —— PM 2026-11-12 定向修复：find_tables() 跨页污染隔离 + 页级分流 ——
STRONG_LINES = [
    "6.1 Absolute Maximum Ratings",
    "PARAMETER", "MIN", "MAX", "UNIT",
    "VDD_CORE", "-0.3", "1.05", "V",
]
STRONG_BORDER = [
    ([["PARAMETER", "MIN", "MAX", "UNIT"],
      ["VDD_CORE", "-0.3", "1.05", "V"]],
     (56.0, 230.0, 550.0, 330.0)),
]
DIRTY_ROWS = [["PREVIOUS PAGE BODY", "REVISION HISTORY"],
              ["OLD TEXT", "UNRELATED"]]

# 页首无关表（PIN / DIRECTION），与真参数表指纹重合度 3/7 = 0.43 < 0.80。
CASE_K = [
    "Refer to the Recommended Operating Conditions for the OTP table.",
    "PIN", "PARAMETER", "DIRECTION", "MIN", "MAX", "UNIT",
    "A1", "Input", "1.0", "2.0", "V",
]
CASE_K_BORDER = [
    ([["PIN", "PARAMETER", "DIRECTION", "MIN", "MAX", "UNIT"],
      ["A1", "Input", "1.0", "2.0", "V"]],
     (56.0, 100.0, 550.0, 210.0)),
]


@case("定向修复 隔离1 find_tables 必须带 clip=本页矩形")
def _iso_clip():
    pg = FakePage(STRONG_LINES, STRONG_BORDER)
    I3._page_table_signatures(pg)
    assert pg.last_clip is not None, "find_tables 没收到 clip，隔离 1 未生效"
    r = pg.last_clip
    assert (float(r.x0), float(r.y0), float(r.x1), float(r.y1)) == \
        (0.0, 0.0, 612.0, 792.0), "clip 不是本页矩形：%r" % (r,)


@case("定向修复 隔离2 表格 bbox 越过页高（Y 轴越界）→ 判脏数据丢弃")
def _iso_bbox():
    clip = (0.0, 0.0, 612.0, 792.0)
    assert I3._bbox_in_clip((56.0, 230.0, 550.0, 330.0), clip) is True
    assert I3._bbox_in_clip((56.0, 700.0, 550.0, 900.0), clip) is False
    pg = FakePage(STRONG_LINES,
                  [([["PARAMETER", "MIN", "MAX", "UNIT"],
                     ["VDD_CORE", "-0.3", "1.05", "V"]],
                    (56.0, 700.0, 550.0, 900.0))])
    assert I3._page_table_signatures(pg) == [], "Y 轴越界表格未被隔离"


@case("定向修复 隔离3 extract 吐出上一页正文 → 文本归属校验丢弃")
def _iso_text():
    pg = FakePage(STRONG_LINES, [(DIRTY_ROWS, (56.0, 230.0, 550.0, 330.0))])
    assert I3._header_words_in_page(
        DIRTY_ROWS[:1], pg.get_text("text").upper()) < I3.TABLE_TEXT_MIN_HIT
    assert I3._page_table_signatures(pg) == [], "上一页正文串入未被隔离"


@case("定向修复 页级分流 STRONG 页完全不读取上一页（11 页走正常提取）")
def _dispatch_strong():
    class Boom(object):
        def get_text(self, *a, **k):
            raise AssertionError("STRONG 页不该访问上一页")

        def find_tables(self, *a, **k):
            raise AssertionError("STRONG 页不该对上一页调 find_tables")

    pg = FakePage(STRONG_LINES, STRONG_BORDER)
    assert I3._page_title(pg)[2] == "STRONG"
    assert I3._table_header_from_borders(pg, Boom()) is True, \
        "本页有独立强标题的真表被误杀"
    assert prescan_fake(STRONG_LINES, STRONG_BORDER) == [1]


@case("反向 页首表格表头指纹与上一页不匹配 → FINGERPRINT_MISMATCH 拦截")
def _fingerprint_mismatch():
    pg = FakePage(CASE_K, CASE_K_BORDER)
    prev = FakePage(PREV_E_LINES, PREV_E_BORDER)
    assert I3._page_title(pg)[2] == "NONE", "负例应是 NONE 页"
    cur, pc = I3.PageContext(pg), I3.PageContext(prev)
    cur.extract_tables()
    pc.extract_tables()
    assert len(cur.signatures) == 1, "页首表格应通过三道隔离"
    links = I3.link_context(cur, pc)
    assert links and all((not ok) and r == "FINGERPRINT_MISMATCH"
                         for _, ok, r, _ in links), \
        "指纹不匹配未拦住：%s" % ([(r, s) for _, ok, r, s in links],)
    assert I3._table_header_from_borders(pg, prev) is False
    got = I3.prescan3(FakeDoc([prev, pg]), 2)
    assert 2 not in got, "指纹不匹配的页首表被误放行：%s" % got


@case("反向 合成反例回归 页首无关完整参数表 + 上方 AMR 标题仍被拦截")
def _reviewer_negative_still_blocked():
    assert prescan_fake(CASE_H, CASE_H_BORDER) == []
    assert I3._table_header_from_borders(
        FakePage(CASE_H, CASE_H_BORDER)) is False


class NoClipPage(FakePage):
    """模拟「环境不支持 find_tables(clip=...)」的旧版库 / 受限对象。"""

    def find_tables(self):
        raise TypeError(
            "find_tables() got an unexpected keyword argument 'clip'")


@case("定向修复 clip 静默降级 环境不支持 clip → Fail-Closed 退出，绝不退回无 clip 调用")
def _clip_fail_closed():
    pg = NoClipPage(STRONG_LINES, STRONG_BORDER)
    try:
        I3._page_table_signatures(pg)
    except SystemExit as e:
        assert "clip" in str(e), "退出原因未点明 clip：%r" % str(e)
    else:
        raise AssertionError(
            "不支持 clip 时仍静默降级回无 clip 调用，未 Fail-Closed")


@case("定向修复 V256 V(MAIN-AUX) 五行按参数块内顺序绑定 condition")
def _v256_condition():
    specs = [("-7.1", "6.1"), ("-7.8", "6.6"), ("-7.8", "6.6"),
             ("-7.8", "6.7"), ("-7.9", "6.9")]
    rows = [{"sample_no": "V256", "evidence_page": "13",
             "symbol": "V(MAIN-AUX)", "min_value": mn, "max_value": mx,
             "condition": ""} for mn, mx in specs]
    I3.apply_condition_backfill(rows, "V256")
    want = I3.CONDITION_BACKFILL[("V256", "13", "V(MAIN-AUX)")]
    assert [r["condition"] for r in rows] == want, "condition 没有逐行绑定"
    assert rows[1]["condition"] != rows[2]["condition"], \
        "min/max 完全相同的第 2/3 行被当成重复数据"
    assert len({r["condition"] for r in rows}) == 5, \
        "五行 condition 必须互不相同，不能合并"


@case("反向 V256 condition 回填 行数不符 → Fail-Closed，绝不盲配")
def _v256_condition_mismatch():
    rows = [{"sample_no": "V256", "evidence_page": "13",
             "symbol": "V(MAIN-AUX)", "min_value": "-7.1",
             "max_value": "6.1", "condition": ""}]
    try:
        I3.apply_condition_backfill(rows, "V256")
    except SystemExit as e:
        assert "不一致" in str(e), "退出原因未说明不一致：%r" % str(e)
    else:
        raise AssertionError("行数不符仍按顺序盲配，未 Fail-Closed")


@case("反向 V256 condition 回填 按样本隔离 别件整件 EXCLUDED 不得误伤")
def _v256_condition_scope():
    # B3 串行生成时真实事故：V328 整件无文本层 → keep 为空，
    # 旧版遍历全局回填表，把 V328 的空 keep 当成「V256 条件块丢失」而退出。
    empty = []
    assert I3.apply_condition_backfill(empty, "V328") == []
    # 同一次调用里 V256 有行、另一件为空 → V256 仍须正常绑定
    rows = [{"sample_no": "V256", "evidence_page": "13",
             "symbol": "V(MAIN-AUX)", "min_value": "-7.1",
             "max_value": "6.1", "condition": ""} for _ in range(5)]
    assert I3.apply_condition_backfill(rows, "V256") is rows
    assert all(r["condition"] for r in rows), "样本隔离后 V256 反而没绑上"
    # 但 V256 自己只剩 2 行时仍必须退出，不能借隔离放行
    try:
        I3.apply_condition_backfill(rows[:2], "V256")
    except SystemExit as e:
        assert "不一致" in str(e), "隔离开得过宽，缺行仍放行：%r" % str(e)
    else:
        raise AssertionError("样本隔离被写成了放宽，缺行也放行")


# —— B3 V146：老式手册「描述型表题」的口径统一（结构化补判据，非放宽阈值）——
V146_LINES = [
    "CY74FCT399T",
    "QUAD 2-INPUT REGISTER",
    "4",
    "electrical characteristics over recommended operating free-air temperature range (unless",
    "otherwise noted)",
    "PARAMETER", "TEST CONDITIONS", "MIN", "TYP", "MAX", "UNIT",
    "VIK", "VCC = 4.75,", "-1.2", "-0.7", "V",
]
V146_PROSE = [
    "Stresses beyond those listed under Absolute Maximum Ratings may cause permanent damage.",
    "For more information, see the hysteresis values in Electrical Characteristics.",
    "The MIN and MAX values are the limits of the operating range.",
    "TYP and NOM are typical ratings, not MIN or MAX limits.",
]
V146_NOHDR = [
    "electrical characteristics over recommended operating free-air temperature range",
    "The MIN and MAX values are described in the text below.",
    "Some unrelated prose without any column headers.",
]


@case("正向 B3 V146 描述型表题 + 紧邻完整表头 → 真表放行（修复误杀）")
def _desc_title_positive():
    txt = "\n".join(V146_LINES)
    anchors = I3.title_anchor_lines(txt)
    assert anchors == [3], "描述型表题未被识别：%s" % anchors
    assert I3.has_table_header(txt, anchors) is True, \
        "V146 式真表头被误杀"
    assert prescan_fake(V146_LINES) == [1], "V146 真表页未进候选"


@case("反向 B3 描述型表题 正文句子与章节交叉引用不得被当成表题")
def _desc_title_prose():
    assert I3.title_anchor_lines("\n".join(V146_PROSE)) == [], \
        "正文句子 / 交叉引用被当成表题"
    assert I3.has_table_header("\n".join(V146_PROSE), []) is False


@case("反向 B3 描述型表题 + 无表头结构 → 仍拦截（不能靠新正则 Fail-Open）")
def _desc_title_no_header():
    txt = "\n".join(V146_NOHDR)
    assert I3.title_anchor_lines(txt) == [0]
    assert I3.has_table_header(txt, [0]) is False
    assert prescan_fake(V146_NOHDR) == [], "无表头页被描述型表题放行"


@case("反向 B3 描述型表题 + 远处无关表头（超过 TITLE_MAX_GAP）→ 拦截")
def _desc_title_far_header():
    lines = (["electrical characteristics over recommended operating "
              "free-air temperature range"] + ["prose line %d" % i
                                               for i in range(6)]
             + ["PARAMETER", "MIN", "MAX", "UNIT", "A1", "1.0", "2.0", "V"])
    assert I3.has_table_header("\n".join(lines), [0]) is False, \
        "远处无关表头借描述型表题被放行"
    assert prescan_fake(lines) == []


def main():
    print("=" * 72)
    print("CORE_ORDER 正则 + prescan3 表头结构判据 · 回归测试")
    print("=" * 72)
    n_pass = n_fail = n_skip = 0
    for name, fn in CASES:
        try:
            fn()
        except AssertionError as e:
            print("FAIL  %s\n        %s" % (name, e))
            n_fail += 1
        except Exception as e:
            print("FAIL  %s\n        %s: %s" % (name, type(e).__name__, e))
            n_fail += 1
        else:
            print("PASS  %s" % name)
            n_pass += 1
    print("-" * 72)
    print("PASS=%d, FAIL=%d, SKIP=%d" % (n_pass, n_fail, n_skip))
    print("测试全部使用内存对象 / 合成 PDF 页，不依赖外部 PDF，故 SKIP 必须为 0。")
    if n_fail or n_skip:
        print("结论：未通过")
        return 1
    print("结论：全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
