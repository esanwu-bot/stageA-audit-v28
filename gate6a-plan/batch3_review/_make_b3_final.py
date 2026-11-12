# -*- coding: utf-8 -*-
"""B3 最终定稿 + v1.6 验证输入三件套（唯一真源：PM 签字的 Batch3_B3_ANNOTATED.xlsx）。

与 B2 定稿完全同构（19 列），差别只在 B3 自己的四处事实。

一、notes 清理
    签字版 20 行 notes 还是草稿措辞（`VLM 草稿，须对左图核` / `low_confidence` /
    `请确认`）。按 PM 裁定统一改成「人工已核对 PDF 原图并确认」，
    核心数值、symbol、unit、reviewer 一格不动，清理前全文留痕。

二、device_model 逐件按 PDF 封面原文登记（不按文件名猜）
    V146  p1 首行 `CY74FCT399T`                    → CY74FCT399T
    V271  p1 首行 `DM3730, DM3725`                 → DM3725（文件名 DM3725CBC100）
    V256  p1 器件行 `BQ79656-Q1, BQ79654-Q1, BQ79652-Q1` → BQ79652-Q1
          （封面主标题只写族名 `BQ7965x-Q1`，故取器件行能核到的具体型号；
           全书 BQ79652 出现 439 次，族名仅 4 次）
    V244  p1 `AM1802`                              → AM1802

三、V256 五行 condition（Reviewer 第七轮硬伤 2 的落盘）
    签字版 condition 列**全部为空**——那份是回填之前导出的。VLM 不抄
    TEST CONDITIONS 列，五行各自对应不同条件，其中第 2、3 行 MIN/MAX
    完全相同（-7.8 / 6.6 mV），无法按数值反推，只能按参数块内出现顺序绑定。

    这里不重抄一份条件表：直接 import `_build_batch3_interactive.py` 的
    `CONDITION_BACKFILL`，与草稿生成器共用唯一真源，并断言两边逐字相同。
    行数不符即 Fail-Closed，绝不盲配。

四、签名口径（绝不由机器替人确认）
    这 5 格是签字之后新增的数据。处置与 B2 完全同构：
      * 15 列签字值逐格照抄；
      * 5 行 condition 由 WB 按原图代录入，entered_by=WB_Agent；
      * `Batch3_B3_FINAL_TO_SIGN.xlsx` 的 5 个 condition 格与对应
        approved_by 格标红交给 PM，PM 补签后该文件即**唯一签名源**；
      * 本脚本按十字段稳定 ID（九字段 + condition）从签名源继承 approved_by，绝不按行号、
        绝不代填、绝不自动补齐：源缺失 / 表头不符 / 行数不是 20 /
        ID 重复 / 非 PM 签名 / 落点与 entered_by=WB_Agent 行不一致，
        一律 Fail-Closed 退出。

    脚本**不再重写 TO_SIGN**：它补签后就是签名源，重跑会覆盖掉 PM 的签名。
    未签模板可在 git 历史（fd0555c）里取回。

file_name 简写处置（不改签字真源一格）
    V256 签字名 `BQ79652PAPRQ1.pdf` 在语料目录不存在，实际文件是
    `BQ79652PAPRQ1__bq79652-q1.pdf`。在 `b3_pdfs/` 下按签字原名建硬链接，
    PDF 模式据此实算哈希，离线模式用 sidecar，CSV 里仍是签字原值。

产物
    Batch3_B3_SIGNED_original.xlsx     PM 签字原件副本（逐格未改）
    Batch3_B3_FINAL.csv / .xlsx        19 列最终定稿（验证器直接吃）
    Batch3_B3_notes_before_cleanup.txt 20 行原始 notes 留痕
    Batch3_B3_APPROVAL_TARGETS.txt     5 处补签落点（稳定 ID + 继承结果）
    Batch3_B3_PDF_PROVENANCE.csv       第三方溯源表
    page_text_batch3_b3.json           页文本 + 溯源期望值
"""
from __future__ import print_function

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import shutil
import sys
from collections import Counter, OrderedDict
from datetime import datetime
from pathlib import Path

import fitz
import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

PREP = Path(__file__).resolve().parent
PDF_DIR = Path(r"E:\workspace\IcPdfParser\data\pdfs")
LINK_DIR = PREP / "b3_pdfs"
SRC_XLSX = Path(r"D:\Documents\Downloads\Batch3_B3_ANNOTATED.xlsx")

OUT_CSV = PREP / "Batch3_B3_FINAL.csv"
OUT_XLSX = PREP / "Batch3_B3_FINAL.xlsx"
SIGNED_COPY = PREP / "Batch3_B3_SIGNED_original.xlsx"
NOTES_BEFORE = PREP / "Batch3_B3_notes_before_cleanup.txt"
OUT_SIDE = PREP / "page_text_batch3_b3.json"
OUT_PROV = PREP / "Batch3_B3_PDF_PROVENANCE.csv"
TO_SIGN = PREP / "Batch3_B3_FINAL_TO_SIGN.xlsx"
TARGETS = PREP / "Batch3_B3_APPROVAL_TARGETS.txt"

ORIG_COLS = [
    "sample_no", "file_name", "evidence_page", "table_title", "symbol",
    "parameter_name", "min_value", "typ_value", "max_value", "unit",
    "condition", "row_status", "notes", "reviewer", "confidence_score",
]
FINAL_COLS = [
    "sample_no", "file_name", "evidence_page", "table_title", "symbol",
    "parameter_name", "min_value", "typ_value", "max_value", "unit",
    "condition", "row_status", "notes", "reviewer", "approved_by",
    "entered_by", "confidence_score", "device_model", "human_adjudication",
]

DEVICE_MODEL = {
    "V146": "CY74FCT399T",
    "V271": "DM3725",
    "V256": "BQ79652-Q1",
    "V244": "AM1802",
}

# 签字简写名 → 语料目录实际文件名（精确指定，不做模糊猜）
ALIAS = {
    "BQ79652PAPRQ1.pdf": "BQ79652PAPRQ1__bq79652-q1.pdf",
}

FINAL_NOTE = "人工已核对 PDF 原图并确认"
REVIEWER = "wuxiaoxian"
ENTERED_BY = "WB_Agent"
EXPECT_ROWS = 20
EXPECT_SAMPLES = 4

# 唯一签名源：PM 在 5 个红格补签后的原件（2026-11-12 12:14 保存）。
# 补签后按稳定 ID 继承，绝不按行号、绝不代填、绝不自动补齐。
APPROVAL_SRC = PREP / "Batch3_B3_FINAL_TO_SIGN.xlsx"
SIGNERS = {"wuxiaoxian"}

# 唯一条件真源在本体生成器里，这里只声明"取哪一块"
CONDITION_KEY = ("V256", "13", "V(MAIN-AUX)")

STABLE_ID_FIELDS = (
    "sample_no", "file_name", "evidence_page", "symbol", "parameter_name",
    "min_value", "typ_value", "max_value", "unit",
    # B3 必须再并入 condition：V256 p13 的 V(MAIN-AUX) 第 2、3 行
    # MIN/MAX 完全相同（-7.8 / 6.6 mV），九个字段一模一样，
    # 唯一能区分的就是 TEST CONDITIONS。B2 靠 min/typ/max/unit 就能消歧，
    # B3 这两行消不掉，若不加会把同一 ID 静默覆盖成一条 —— 正是要堵的 Fail-Open。
    # 加了也不会误放行：若 PM 改过 condition，ID 就对不上，直接报「落点不一致」。
    "condition",
)

sys.path.insert(0, str(PREP))
from validate_annotation import nos   # 与 v1.6 同一归一化函数做原文断言


def cell(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_id(r):
    return "|".join(str(r.get(k, "") or "").strip() for k in STABLE_ID_FIELDS)


def pdf_form(text):
    """PDF 文本层把度数符号抽成 `o`（`25°C` → `25oC`）。

    只在**原文断言**这一步做这个替换，落盘的 condition 仍写 `°C`：
    v1.6 只用 condition 做分组键、不做原文断言，按原图写 `°C` 语义正确。
    """
    return text.replace("°C", "oC").replace("°c", "oc")


def load_condition_backfill(key=CONDITION_KEY):
    """从草稿生成器 import 条件表，保证定稿与草稿同源，不重抄一份。"""
    src = PREP / "_build_batch3_interactive.py"
    if not src.is_file():
        raise SystemExit("FAIL 找不到草稿生成器，无法取得唯一条件真源：%s" % src)
    spec = importlib.util.spec_from_file_location("_b3gen_for_cond", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    table = getattr(mod, "CONDITION_BACKFILL", None)
    if not isinstance(table, dict):
        raise SystemExit("FAIL 生成器里没有 CONDITION_BACKFILL 表")
    if key not in table:
        raise SystemExit("FAIL 生成器条件表缺 %r" % (key,))
    conds = list(table[key])
    if len(conds) != 5:
        raise SystemExit("FAIL %r 条件条数应为 5，实际 %d" % (key, len(conds)))
    if len(set(conds)) != 5:
        raise SystemExit("FAIL %r 条件有重复，拒绝按顺序绑定" % (key,))
    return conds


def read_signed_xlsx(path):
    ws = openpyxl.load_workbook(str(path), data_only=True).active
    vals = list(ws.values)
    hdr = [str(x or "").strip() for x in vals[0]]
    missing = [c for c in ORIG_COLS if c not in hdr]
    if missing:
        raise SystemExit("签字 xlsx 缺列：%s" % missing)
    rows = []
    for v in vals[1:]:
        if not any(x is not None and str(x).strip() for x in v):
            continue
        rows.append({k: cell(v[hdr.index(k)]) for k in ORIG_COLS})
    return rows


def ensure_link(real, link):
    if link.exists():
        if sha(link) != sha(real):
            raise SystemExit("硬链接目录里已有同名但字节不同的文件：%s" % link)
        return "复用"
    try:
        os.link(str(real), str(link))
        return "硬链接"
    except OSError:
        shutil.copy2(str(real), str(link))
        if sha(link) != sha(real):
            raise SystemExit("复制后字节不一致：%s" % link)
        return "复制（os.link 不可用，已校验字节一致）"


def atomic_replace(tmp, dst):
    try:
        os.replace(str(tmp), str(dst))
    except PermissionError:
        raise SystemExit("目标被占用且需要改写，请关闭 Excel/预览后重跑：%s" % dst)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def _wb_signature(path):
    """工作簿内容签名：表名/冻结/筛选/列宽 + 每格的值与填充色、加粗。

    只比对「内容」，不含 docProps 时间戳，用于判断是否需要真的重写。
    """
    wb = openpyxl.load_workbook(str(path), data_only=False)
    ws = wb.active
    sig = [ws.title, ws.freeze_panes or "", ws.auto_filter.ref or ""]
    sig.append(tuple(sorted((k, round(float(v.width or 0), 4))
                            for k, v in ws.column_dimensions.items())))
    for row in ws.iter_rows():
        for c in row:
            fill = c.fill
            fg = ""
            if fill is not None and fill.fill_type == "solid":
                rgb = getattr(fill.fgColor, "rgb", None)
                fg = rgb if isinstance(rgb, str) else str(fill.fgColor.index or "")
            font = c.font
            frgb = ""
            try:
                frgb = font.color.rgb if font and font.color else ""
            except (TypeError, AttributeError):
                frgb = ""
            sig.append((c.coordinate, c.value,
                        bool(font.b) if font else False,
                        frgb if isinstance(frgb, str) else ""))
    return tuple(sig)


def write_xlsx(path, rows, sheet, highlights=None, head_color="2F5597"):
    """写 19 列定稿表；highlights={(行号, 列名): 颜色}，行号从 1 起（数据行）。"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet
    ws.append(FINAL_COLS)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=head_color)
        c.alignment = Alignment(horizontal="center")
    for r in rows:
        ws.append([r.get(k, "") for k in FINAL_COLS])
    for ci, k in enumerate(FINAL_COLS, 1):
        width = {"parameter_name": 46, "notes": 32, "file_name": 40,
                 "human_adjudication": 30, "row_status": 16,
                 "table_title": 32, "approved_by": 16,
                 "entered_by": 15, "condition": 34}.get(k, 15)
        ws.column_dimensions[get_column_letter(ci)].width = width
    for (lineno, col), color in (highlights or {}).items():
        ws.cell(row=lineno + 1, column=FINAL_COLS.index(col) + 1).fill = \
            PatternFill("solid", fgColor=color)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    # 临时文件必须带 .xlsx 后缀：openpyxl 读取时会校验扩展名
    tmp = path.with_name(path.name + ".wb_tmp.xlsx")
    wb.save(str(tmp))
    # 幂等保护：要写的内容与磁盘现件逐格一致时，保留原字节、不重写。
    # openpyxl 每次 save 都会刷新 docProps/core.xml 的 dcterms:modified，
    # 会让封卷件的整包 SHA-256 无意义漂移（数据其实一字未改）。
    if path.exists():
        try:
            if _wb_signature(tmp) == _wb_signature(path):
                tmp.unlink()
                return "未改写（内容与磁盘一致，保留原字节）"
        except (OSError, ValueError, KeyError):
            pass
    atomic_replace(tmp, path)
    return "已改写"


def load_approval_map(path=None):
    """Fail-Closed 读取唯一签名源，返回 {稳定ID: approved_by}。

    以下任一情况直接报错退出，绝不「读不到就按无签名处理」：
      源文件不存在 / 表头不是 19 列定稿结构 / 数据行数不是 20 /
      稳定 ID 重复 / 出现非 PM 本人签名。
    """
    src = Path(path) if path is not None else APPROVAL_SRC
    if not src.exists():
        raise SystemExit("FAIL 找不到唯一签名源：%s" % src)
    wb = openpyxl.load_workbook(str(src), data_only=True, read_only=True)
    try:
        vals = list(wb.active.values)
    finally:
        wb.close()
    if not vals:
        raise SystemExit("FAIL 签名源是空表：%s" % src)
    hdr = [str(x or "").strip() for x in vals[0]]
    if hdr != FINAL_COLS:
        raise SystemExit("FAIL 签名源表头不符（应为 19 列定稿结构）：%s" % hdr)
    data = [v for v in vals[1:] if any(x is not None and str(x).strip() for x in v)]
    if len(data) != EXPECT_ROWS:
        raise SystemExit("FAIL 签名源数据行数异常：%d（应为 %d）"
                         % (len(data), EXPECT_ROWS))
    amap = {}
    for v in data:
        r = {k: cell(v[hdr.index(k)]) for k in FINAL_COLS}
        sid = stable_id(r)
        if sid in amap:
            raise SystemExit("FAIL 签名源稳定 ID 重复：%s" % sid)
        sig = r["approved_by"].strip()
        if sig and sig not in SIGNERS:
            raise SystemExit("FAIL 签名源出现非 PM 签名：%r（行 %s）"
                             % (sig, r["sample_no"]))
        amap[sid] = sig
    return amap


def apply_approval(rows, approval_map):
    """按稳定 ID 把 PM 补签落到定稿；落点与 WB 代录入行必须完全一致。"""
    signed_ids = {k for k, v in approval_map.items() if v}
    wb_ids = {stable_id(r) for r in rows if r["entered_by"] == ENTERED_BY}
    if not signed_ids:
        raise SystemExit("FAIL 签名源里没有任何 approved_by，拒绝出「已封卷」定稿")
    if signed_ids != wb_ids:
        miss = wb_ids - signed_ids
        extra = signed_ids - wb_ids
        raise SystemExit(
            "FAIL 签名落点与 WB 代录入行不一致：漏签 %d 行 %r；多处签名 %d 行 %r"
            % (len(miss), sorted(x.split("|")[0] for x in miss),
               len(extra), sorted(x.split("|")[0] for x in extra)))
    for r in rows:
        if r["entered_by"] != ENTERED_BY:
            continue
        sid = stable_id(r)
        if sid not in approval_map:
            raise SystemExit("FAIL 定稿行在签名源里找不到稳定 ID：%s" % sid)
        r["approved_by"] = approval_map[sid]
    return rows


def main():
    global SRC_XLSX, PDF_DIR
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", default=str(SRC_XLSX),
                    help="PM 签字的 xlsx（唯一真源）")
    ap.add_argument("--pdf-dir", default=str(PDF_DIR),
                    help="PDF 语料目录")
    ap.add_argument("--approval", default=str(APPROVAL_SRC),
                    help="PM 补签后的 TO_SIGN 原件（唯一签名源）")
    args = ap.parse_args()
    SRC_XLSX, PDF_DIR = Path(args.xlsx), Path(args.pdf_dir)
    if not SRC_XLSX.exists():
        raise SystemExit("找不到 PM 签字 xlsx：%s" % SRC_XLSX)
    if not PDF_DIR.is_dir():
        raise SystemExit("找不到 PDF 语料目录：%s" % PDF_DIR)

    signed = read_signed_xlsx(SRC_XLSX)
    if len(signed) != EXPECT_ROWS:
        raise SystemExit("签字版应为 %d 行，实际 %d" % (EXPECT_ROWS, len(signed)))
    if not all(r["row_status"] == "CONFIRMED" for r in signed):
        raise SystemExit("签字版存在非 CONFIRMED 行")
    if not all(r["reviewer"] == REVIEWER for r in signed):
        raise SystemExit("签字版存在非 %s 签名行" % REVIEWER)
    if any(not r["symbol"].strip() for r in signed):
        raise SystemExit("签字版仍有空 symbol，须先回填再定稿")
    if any(r["condition"].strip() for r in signed):
        raise SystemExit("签字版 condition 非空，与登记事实不符（应全空）")

    # 签字原件留痕（逐格未改，供 Reviewer 反查）
    if not SIGNED_COPY.exists() or sha(SIGNED_COPY) != sha(SRC_XLSX):
        tmp = SIGNED_COPY.with_name(SIGNED_COPY.name + ".wb_tmp")
        shutil.copy2(str(SRC_XLSX), str(tmp))
        atomic_replace(tmp, SIGNED_COPY)

    # 原始 notes 留痕：V146 列对齐、V256 多组取值等排查线索不能丢
    lines = [
        "B3 签字版原始 notes（清理前全文留痕）",
        "真源：Batch3_B3_SIGNED_original.xlsx（PM 签字原件副本，逐格未改）",
        "清理后统一为：%s" % FINAL_NOTE,
        "=" * 72,
    ]
    for i, r in enumerate(signed, 1):
        lines.append("物理行%-3d %-5s %-18s | %s" %
                     (i, r["sample_no"], r["symbol"] or "(空)", r["notes"]))
    lines.append("=" * 72)
    for k, v in Counter(r["notes"] for r in signed).items():
        lines.append("%2d 行 | %s" % (v, k))
    NOTES_BEFORE.write_text("\n".join(lines) + "\n", encoding="utf-8",
                            newline="\n")

    # ---- 生成 19 列定稿 ----
    conds = load_condition_backfill()
    rows, cond_lines = [], []
    for i, s in enumerate(signed, 1):
        r = {k: s[k] for k in ORIG_COLS}
        r["notes"] = FINAL_NOTE
        r["approved_by"] = ""     # 5 格待 PM 补签，机器不代签
        r["entered_by"] = ""
        r["device_model"] = DEVICE_MODEL.get(s["sample_no"], "")
        r["human_adjudication"] = ""
        rows.append(r)

    key_sno, key_page, key_sym = CONDITION_KEY
    hit = [(i, r) for i, r in enumerate(rows, 1)
           if r["sample_no"] == key_sno
           and r["evidence_page"] == key_page
           and r["symbol"].strip() == key_sym]
    if len(hit) != len(conds):
        raise SystemExit(
            "FAIL %s p%s %s 命中 %d 行，与条件表 %d 条不一致，拒绝按顺序盲配"
            % (key_sno, key_page, key_sym, len(hit), len(conds)))
    for (i, r), c in zip(hit, conds):
        r["condition"] = c
        r["entered_by"] = ENTERED_BY
        cond_lines.append((i, c))

    cond_row_ids = {i for i, _ in hit}
    if len(cond_row_ids) != 5:
        raise SystemExit("condition 回填行数应为 5，实际 %d" % len(cond_row_ids))
    if len({r["condition"] for _, r in hit}) != 5:
        raise SystemExit("五行 condition 有重复，等于把不同测试条件合并了")
    if not any(r["device_model"] for r in rows):
        raise SystemExit("device_model 全空")
    if any(not r["device_model"] for r in rows):
        raise SystemExit("存在未登记型号的样本")
    if sum(1 for r in rows if r["entered_by"]) != 5:
        raise SystemExit("entered_by 应恰好 5 行")

    # 签名继承：唯一源是 PM 补签后的 TO_SIGN 原件，按稳定 ID 落位，不按行号。
    approval_map = load_approval_map(args.approval)
    apply_approval(rows, approval_map)
    if sum(1 for r in rows if r["approved_by"]) != 5:
        raise SystemExit("定稿应恰好继承 5 处 PM 补签")
    if any("low_confidence" in r["notes"].lower() for r in rows):
        raise SystemExit("notes 仍有 low_confidence 残留")
    if any(r["notes"] != FINAL_NOTE for r in rows):
        raise SystemExit("notes 未统一为定稿口径")

    # 逐格断言：原 15 列里只有 notes 全行可改、condition 仅那 5 行可改，
    # 其余一律照抄签字版（含 confidence_score 的数值归一化）
    for i, (a, b) in enumerate(zip(signed, rows), 1):
        allowed = {"notes"}
        if i in cond_row_ids:
            allowed |= {"condition"}
        for k in ORIG_COLS:
            if k in allowed:
                continue
            if a[k] != b[k]:
                raise SystemExit("行%d 列%s 被改动：%r → %r" % (i, k, a[k], b[k]))

    # ---- 硬链接验证环境 + 溯源 ----
    LINK_DIR.mkdir(exist_ok=True)
    samples = OrderedDict()
    for r in rows:
        sno, fname = r["sample_no"], r["file_name"]
        if sno not in DEVICE_MODEL:
            raise SystemExit("未登记型号：%s" % sno)
        samples.setdefault(sno, {"file_name": fname, "pages": set()})
        samples[sno]["pages"].add(1)
        try:
            samples[sno]["pages"].add(int(r["evidence_page"]))
        except ValueError:
            raise SystemExit("%s 的 evidence_page 非整数：%r" %
                             (sno, r["evidence_page"]))
    if len(samples) != EXPECT_SAMPLES:
        raise SystemExit("样本数应为 %d，实际 %d" % (EXPECT_SAMPLES, len(samples)))

    side, prov_rows = OrderedDict(), []
    print("PDF 溯源（按签字版 file_name 建硬链接，字节与语料原件一致）：")
    for sno, meta in samples.items():
        fname = meta["file_name"]
        real = PDF_DIR / ALIAS.get(fname, fname)
        if not real.exists():
            raise SystemExit("语料缺失：%s（签字名 %s）" % (real, fname))
        link = LINK_DIR / fname
        how = ensure_link(real, link)
        raw = real.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        doc = fitz.open(str(real))
        npages = doc.page_count
        pages = {}
        for pno in sorted(meta["pages"]):
            if pno > npages:
                raise SystemExit("%s 的 evidence_page=%d 超出页数 %d" %
                                 (sno, pno, npages))
            pages[str(pno)] = doc.load_page(pno - 1).get_text("text")
        doc.close()

        # 条件回填的原文断言：符号与每条条件都必须能在 V256 p13 核到
        if sno == key_sno:
            ptxt = nos(pages[key_page])
            if nos(key_sym) not in ptxt:
                raise SystemExit("符号 %r 在 %s p%s 原文找不到"
                                 % (key_sym, sno, key_page))
            for _, c in cond_lines:
                if nos(pdf_form(c)) not in ptxt:
                    raise SystemExit("条件 %r 在 %s p%s 原文找不到"
                                     % (c, sno, key_page))

        node = OrderedDict([
            ("sample_no", sno),
            ("file_name", fname),
            ("device_model", DEVICE_MODEL[sno]),
            ("sha256", digest),
            ("page_count", npages),
            ("size_bytes", len(raw)),
            ("pages", pages),
        ])
        side[sno] = node
        prov_rows.append({k: node[k] for k in
                          ("sample_no", "file_name", "device_model",
                           "sha256", "page_count", "size_bytes")})
        print("  %-5s %-38s %3d 页  %-14s %-14s sha256=%s…" %
              (sno, fname[:38], npages, how, DEVICE_MODEL[sno], digest[:16]))

    # ---- 落盘 ----
    tmp_csv = OUT_CSV.with_name(OUT_CSV.name + ".wb_tmp")
    with open(tmp_csv, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FINAL_COLS)
        w.writeheader()
        w.writerows(rows)
    atomic_replace(tmp_csv, OUT_CSV)

    tmp_prov = OUT_PROV.with_name(OUT_PROV.name + ".wb_tmp")
    with open(tmp_prov, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(prov_rows[0]))
        w.writeheader()
        w.writerows(prov_rows)
    atomic_replace(tmp_prov, OUT_PROV)

    obj = OrderedDict([
        ("generated_at", datetime.now().astimezone().isoformat()),
        ("source_xlsx", "Batch3_B3_SIGNED_original.xlsx"),
        ("extractor", "_make_b3_final.py"),
        ("note", "file_name 沿用 PM 签字原值；V256 简写名通过 b3_pdfs/ 硬链接"
                 "指向语料原件同一字节。sha256/页数从磁盘实算，页文本逐页抽取，"
                 "验证器 PDF 模式会再复算一次哈希。"),
        ("samples", side),
    ])
    side_text = json.dumps(obj, ensure_ascii=False, indent=2)
    # 幂等保护：例外字段只有 generated_at。除它以外全部一致时保留原字节，
    # 免得封卷件旁挂的 sidecar 仅因重跑时刻不同就改字节。
    side_same = False
    if OUT_SIDE.exists():
        try:
            cur = json.loads(OUT_SIDE.read_text(encoding="utf-8"))
            new = json.loads(side_text)
            cur.pop("generated_at", None)
            new.pop("generated_at", None)
            side_same = (cur == new)
        except (OSError, ValueError, KeyError):
            side_same = False
    if side_same:
        print("  sidecar：未改写（除 generated_at 外内容一致，保留原字节）")
    else:
        tmp_side = OUT_SIDE.with_name(OUT_SIDE.name + ".wb_tmp")
        tmp_side.write_text(side_text, encoding="utf-8", newline="\n")
        atomic_replace(tmp_side, OUT_SIDE)

    xlsx_state = write_xlsx(
        OUT_XLSX, rows, "B3_FINAL",
        highlights={(i, "condition"): "E2EFDA" for i in cond_row_ids}
        | {(i, "entered_by"): "E2EFDA" for i in cond_row_ids})

    # 注意：这里刻意不再重写 TO_SIGN。
    # 该文件补签后就是唯一签名源（APPROVAL_SRC），重跑会覆盖掉 PM 的签名。
    # 未签模板只存在于 git 历史（fd0555c）；需要重出时手工另存新名，别覆盖它。

    # 补签落点清单：稳定 ID 落纸，补签按 ID 继承，不按行号
    plines = [
        "B3 补签落点清单（V256 五行 condition 由 WB 按原图代录入，PM 已补签）",
        "=" * 72,
        "唯一签名源：Batch3_B3_FINAL_TO_SIGN.xlsx（PM 2026-11-12 12:14 保存）",
        "继承方式：十字段稳定 ID（九字段 + condition）匹配，不按行号；"
        "落点与 entered_by=WB_Agent 行必须一致。",
        "-" * 72,
    ]
    for i, c in cond_lines:
        r = rows[i - 1]
        plines.append("物理行%-3d %s" % (i, stable_id(r)))
        plines.append("        condition = %s" % c)
        plines.append("        approved_by = %s（entered_by = %s）"
                      % (r["approved_by"] or "(空)", r["entered_by"] or "(空)"))
    plines.append("-" * 72)
    plines.append("其余 %d 行 %s 的签字由 PM 在签字版确认，entered_by/approved_by 均空。"
                  % (len(rows) - 5, "/".join(sorted(samples))))
    TARGETS.write_text("\n".join(plines) + "\n", encoding="utf-8", newline="\n")

    # 落盘后逐格断言 CSV == XLSX
    vals = list(openpyxl.load_workbook(str(OUT_XLSX), data_only=True).active.values)
    if [str(x or "") for x in vals[0]] != FINAL_COLS:
        raise SystemExit("FINAL.xlsx 表头不是 19 列定稿结构")
    with open(OUT_CSV, encoding="utf-8-sig", newline="") as fh:
        csv2 = list(csv.DictReader(fh))
    if not len(csv2) == len(vals) - 1 == EXPECT_ROWS:
        raise SystemExit("CSV/XLSX 行数不一致：%d / %d" % (len(csv2), len(vals) - 1))
    for ri, r in enumerate(csv2, 1):
        for ci, k in enumerate(FINAL_COLS):
            if str(vals[ri][ci] or "") != (r.get(k) or ""):
                raise SystemExit("xlsx/CSV 不同源：行%d 列%s" % (ri, k))

    print("\nB3 最终定稿：%d 行 / %d 样本 / %d 列" %
          (len(rows), len(samples), len(FINAL_COLS)))
    print("  notes 全部为：%s" % FINAL_NOTE)
    print("  device_model：" + "，".join("%s=%s" % (k, v)
                                    for k, v in DEVICE_MODEL.items()))
    print("  V256 五行 condition 按原图逐行绑定（与草稿生成器同源）：")
    for i, c in cond_lines:
        print("    行%-3d %s" % (i, c))
    print("  代录入 %d 行 entered_by=%s；已按稳定 ID 继承 %d 处 PM 补签。"
          % (len(cond_row_ids), ENTERED_BY,
             sum(1 for r in rows if r["approved_by"])))
    print("  签名源：%s" % Path(args.approval).name)
    print("  补签落点清单：%s" % TARGETS.name)
    print("  xlsx 写入：%s" % xlsx_state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
