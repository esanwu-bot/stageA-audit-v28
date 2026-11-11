# -*- coding: utf-8 -*-
"""冻结 Batch 2 Gold：CSV 与 XLSX 出自同一份行数据，并附封面上可对账的型号。

为什么要单独一个脚本
--------------------
以前 CSV 和 XLSX 是两条生成路径，改一处忘另一处就会出现"表里 24 行、Excel 里 18 行"。
现在只有一个真源：这里定义的 COLS + ROWS。CSV 从它写，XLSX 也从它写，
写完立刻回读两个文件逐格比对，不相等就报错退出。

型号一列从哪来
--------------
不看文件名，看 PDF 封面（人工读图 + `page_text.json` 里的第 1 页原文可复核）：
  V349 文件名 ADC3544IRSBT → 封面 "ADC3544 14-bit, 125-MSPS..."      → ADC3544
  V145 文件名 DAC8775IRWFR → 封面 "DAC8775 Quad-Channel, 16-Bit..."   → DAC8775
README 早期版本写的 ADC3541 / DAC7750 是错的，此处一并纠正。
"""
import csv
import hashlib
import json
from pathlib import Path

PREP = Path(__file__).resolve().parent
OUT_CSV = PREP / "Batch2_GOLD_v1.csv"
OUT_XLSX = PREP / "Batch2_GOLD_v1.xlsx"
SRC_CSV = PREP / "Batch2_GOLD_v1.csv"

# 样本 -> (订购码, 封面型号)。封面型号进 CSV 的 device_model 列，机检会用第 1 页原文核对。
MODELS = {
    "V101": ("CD74HCT574E", "CD74HCT574"),        # 封面族名：CD54/74HC374 ... CD54/74HCT574
    "V097": ("DEM-OPA-MSOP-2A", "OPA2830"),       # DEM-OPA-MSOP-2A 是评估板订购码，手册讲 OPA2830
    "V162": ("SN74LVTH182504APMG4", "SN74LVTH182504A"),
    "V349": ("ADC3544IRSBT", "ADC3544"),
    "V145": ("DAC8775IRWFR", "DAC8775"),
    "V111": ("DS90C189TWRTDTQ1", "DS90C189-Q1"),
}

# 真实文件名。旧 CSV 里 V145 写成 DAC8775IRWFR.pdf、V111 写成 DS90C189TWRTDTQ1.pdf，
# 都把 "__<手册名>.pdf" 尾巴截掉了，照着找文件必然找不到——这里一并纠正，并断言文件真的在。
PDF_DIR = Path(r"E:\workspace\IcPdfParser\data\pdfs")
FILES = {
    "V101": "CD74HCT574EE4__schs183c.pdf",
    "V097": "DEM-OPA-MSOP-2A__opa2830.pdf",
    "V162": "74LVTH182504APMG4__sn74lvth18504a.pdf",
    "V349": "ADC3544IRSBT__adc3544.pdf",
    "V145": "DAC8775IRWFR__dac8775.pdf",
    "V111": "DS90C189TWRTDTQ1__ds90c189-q1.pdf",
}

COLS = [
    "sample_no", "file_name", "device_model", "evidence_page", "table_title",
    "symbol", "parameter_name", "min_value", "typ_value", "max_value",
    "unit", "condition", "row_status", "notes", "reviewer", "confidence_score",
]


def load_rows():
    """读现有 24 行（旧的 15 列），补 device_model 后按新列序重排。"""
    with open(SRC_CSV, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    out = []
    for r in rows:
        sno = r["sample_no"].strip()
        r["device_model"] = MODELS[sno][1]
        r["file_name"] = FILES[sno]
        if not (PDF_DIR / r["file_name"]).exists():
            raise SystemExit("文件不存在，先核对文件名: %s" % r["file_name"])
        out.append({c: (r.get(c) or "") for c in COLS})
    return out


def write_csv(rows):
    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return hashlib.sha256(OUT_CSV.read_bytes()).hexdigest()


def write_xlsx(rows, csv_sha):
    """从同一份 rows 写 Excel；另开 meta 页记录 CSV 的 SHA-256，便于对账。"""
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
              "H": 10, "I": 10, "J": 10, "K": 9, "L": 20, "M": 12, "N": 60,
              "O": 13, "P": 16}
    for k, v in widths.items():
        ws.column_dimensions[k].width = v
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(vertical="top", wrap_text=(c.column_letter in ("B", "E", "G", "N")))
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = "A1:%s%d" % (get_column_letter(len(COLS)), ws.max_row)

    meta = wb.create_sheet("meta")
    for k, v in (("source_csv", OUT_CSV.name),
                 ("source_csv_sha256", csv_sha),
                 ("rows", len(rows)),
                 ("samples", len({r["sample_no"] for r in rows})),
                 ("generated_by", "_freeze_gold.py"),
                 ("note", "本表由 CSV 同源生成；改动请改脚本，勿直接编辑表格")):
        meta.append([k, v])
    meta.column_dimensions["A"].width = 20
    meta.column_dimensions["B"].width = 70
    wb.save(OUT_XLSX)


def verify(rows):
    """回读 CSV 与 XLSX，逐格比对；任何差异都算失败。"""
    with open(OUT_CSV, encoding="utf-8-sig", newline="") as fh:
        back = list(csv.DictReader(fh))
    assert len(back) == len(rows), "CSV 回读行数不符"

    from openpyxl import load_workbook
    ws = load_workbook(OUT_XLSX)["Gold"]
    grid = list(ws.iter_rows(values_only=True))
    header = list(grid[0])
    assert header == COLS, "XLSX 表头与 COLS 不一致"

    diffs = []
    for i, (a, b) in enumerate(zip(rows, grid[1:]), start=2):
        for j, col in enumerate(COLS):
            want = a[col]
            got = "" if b[j] is None else str(b[j])
            if want != got:
                diffs.append((i, col, want, got))
    if len(grid) - 1 != len(rows):
        diffs.append(("行数", "", len(rows), len(grid) - 1))
    return diffs


def main():
    rows = load_rows()
    sha = write_csv(rows)
    write_xlsx(rows, sha)
    diffs = verify(rows)
    print("CSV 行数 %d，样本 %d 件，SHA-256 %s"
          % (len(rows), len({r["sample_no"] for r in rows}), sha[:16]))
    for d in diffs[:10]:
        print("  差异", d)
    print("CSV/XLSX 逐格比对：" + ("全部一致" if not diffs else "%d 处不一致" % len(diffs)))
    return 1 if diffs else 0


if __name__ == "__main__":
    raise SystemExit(main())
