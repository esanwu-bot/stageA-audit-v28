# -*- coding: utf-8 -*-
"""Batch 2 Gold 定稿工具：以 CSV 为输入真源，生成 XLSX 并逐格比对。

数据流向（单向，不回流）
------------------------
    Batch2_GOLD_v1.csv  ──读──▶  本脚本  ──写──▶  Batch2_GOLD_v1.xlsx
                                        └──加──▶  meta 页（源 CSV 的 SHA-256 / 行数）
                                        └──加──▶  pdf_provenance 页（6 件 PDF 溯源）

CSV 是唯一输入源，脚本**不改写 CSV**。XLSX 只是它的一个渲染版本，
写完后回读两个文件逐格比对，任何一格不同就非零退出。

为什么强调这一点
----------------
早期版本把脚本内的常量当"真源"，由脚本同时写出 CSV 和 XLSX——那等于有两个真源，
一旦有人手改 CSV，下一次跑脚本就被覆盖，改动无声消失。现在改成单向：
要改数据就改 CSV，XLSX 由它派生，派生结果有逐格比对兜底。

PDF 目录
--------
本脚本不需要 PDF。只有传了 --pdf-dir（或设 ICPDF_PDF_DIR）时，才顺带断言
CSV 里的 file_name 在磁盘上确实存在——用来挡住"文件名被截断"这类错。
"""
import argparse
import csv
import hashlib
import os
import sys
from pathlib import Path

PREP = Path(__file__).resolve().parent
SRC_CSV = PREP / "Batch2_GOLD_v1.csv"
OUT_XLSX = PREP / "Batch2_GOLD_v1.xlsx"
PROV_CSV = PREP / "Batch2_PDF_PROVENANCE.csv"

COLS = [
    "sample_no", "file_name", "device_model", "evidence_page", "table_title",
    "symbol", "parameter_name", "min_value", "typ_value", "max_value",
    "unit", "condition", "row_status", "notes", "human_adjudication",
    "reviewer", "confidence_score",
]


def read_csv():
    with open(SRC_CSV, encoding="utf-8-sig", newline="") as fh:
        rd = csv.DictReader(fh)
        rows = list(rd)
        cols = rd.fieldnames or []
    missing = [c for c in COLS if c not in cols]
    extra = [c for c in cols if c not in COLS]
    if missing:
        raise SystemExit("CSV 缺列: %s" % ",".join(missing))
    if extra:
        raise SystemExit("CSV 有多余列（本脚本不认识）: %s" % ",".join(extra))
    for i, r in enumerate(rows, start=2):
        for c in COLS:
            r[c] = r.get(c) or ""
        if not r["sample_no"]:
            raise SystemExit("第 %d 行 sample_no 为空" % i)
    return rows


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def check_pdf_dir(rows, pdf_dir):
    """只做存在性断言，不读 PDF 内容——溯源哈希归 page_text.json / provenance 管。"""
    miss = []
    for fn in sorted({r["file_name"] for r in rows}):
        if not (pdf_dir / fn).exists():
            miss.append(fn)
    if miss:
        raise SystemExit("--pdf-dir 下找不到这些文件: %s" % ", ".join(miss))
    print("文件名存在性：%d 个文件全部命中 %s" % (len({r["file_name"] for r in rows}), pdf_dir))


def write_xlsx(rows, csv_sha):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Gold"
    ws.append(COLS)
    for r in rows:
        ws.append([r[c] for c in COLS])

    head_fill = PatternFill("solid", fgColor="1F3864")
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = head_fill
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    widths = {"A": 11, "B": 34, "C": 18, "D": 8, "E": 26, "F": 10, "G": 42,
              "H": 10, "I": 10, "J": 10, "K": 9, "L": 26, "M": 12, "N": 52,
              "O": 18, "P": 13, "Q": 16}
    for k, v in widths.items():
        ws.column_dimensions[k].width = v
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(vertical="top",
                                    wrap_text=(c.column_letter in ("B", "E", "G", "L", "N")))
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = "A1:%s%d" % (get_column_letter(len(COLS)), ws.max_row)

    meta = wb.create_sheet("meta")
    for k, v in (("source_csv", SRC_CSV.name),
                 ("source_csv_sha256", csv_sha),
                 ("rows", len(rows)),
                 ("samples", len({r["sample_no"] for r in rows})),
                 ("generated_by", "_freeze_gold.py（CSV 为输入真源，XLSX 为其渲染版本）"),
                 ("note", "改数据请改 CSV，再重跑本脚本；直接改 XLSX 会被逐格比对打回")):
        meta.append([k, v])
    meta.column_dimensions["A"].width = 20
    meta.column_dimensions["B"].width = 74

    if PROV_CSV.exists():
        ps = wb.create_sheet("pdf_provenance")
        with open(PROV_CSV, encoding="utf-8-sig", newline="") as fh:
            pr = list(csv.reader(fh))
        for row in pr:
            ps.append(row)
        for c in ps[1]:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = head_fill
            c.alignment = Alignment(horizontal="center", wrap_text=True)
        for k, v in (("A", 10), ("B", 18), ("C", 46), ("D", 66), ("E", 11), ("F", 12)):
            ps.column_dimensions[k].width = v
        ps.freeze_panes = "A2"

    wb.save(OUT_XLSX)


def verify(rows):
    """回读 CSV 与 XLSX 逐格比对，返回差异列表。"""
    with open(SRC_CSV, encoding="utf-8-sig", newline="") as fh:
        back = list(csv.DictReader(fh))
    diffs = []
    if len(back) != len(rows):
        diffs.append(("行数", "", len(rows), len(back)))

    from openpyxl import load_workbook
    grid = list(load_workbook(OUT_XLSX)["Gold"].iter_rows(values_only=True))
    if list(grid[0]) != COLS:
        diffs.append(("表头", "", "COLS", list(grid[0])))
    for i, (a, b) in enumerate(zip(rows, grid[1:]), start=2):
        for j, col in enumerate(COLS):
            want = a[col]
            got = "" if b[j] is None else str(b[j])
            if want != got:
                diffs.append((i, col, want, got))
    return diffs


def main():
    global SRC_CSV
    ap = argparse.ArgumentParser(description="CSV → XLSX（单向派生 + 逐格比对）")
    ap.add_argument("--csv", default=None, help="输入 CSV（默认同目录 Batch2_GOLD_v1.csv）")
    ap.add_argument("--pdf-dir", default=os.environ.get("ICPDF_PDF_DIR"),
                    help="可选：PDF 目录，给了就断言 file_name 都存在")
    args = ap.parse_args()

    if args.csv:
        SRC_CSV = Path(args.csv)
    if not SRC_CSV.exists():
        print("找不到输入 CSV: %s" % SRC_CSV)
        return 2

    rows = read_csv()
    if args.pdf_dir:
        check_pdf_dir(rows, Path(args.pdf_dir))
    else:
        print("提示：未提供 --pdf-dir / ICPDF_PDF_DIR，跳过文件名存在性检查（不影响 XLSX 生成）")

    csv_sha = sha256_file(SRC_CSV)
    write_xlsx(rows, csv_sha)
    diffs = verify(rows)
    print("输入 %s：%d 行 / %d 样本 / SHA-256 %s…"
          % (SRC_CSV.name, len(rows), len({r["sample_no"] for r in rows}), csv_sha[:16]))
    print("输出 %s，逐格比对：%s" % (OUT_XLSX.name, "全部一致" if not diffs
                                     else "%d 处不一致" % len(diffs)))
    for d in diffs[:10]:
        print("  差异", d)
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())
