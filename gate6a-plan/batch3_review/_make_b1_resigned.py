# -*- coding: utf-8 -*-
"""B1 重签（PM 授权代签）：把建议修正版的 3 行恢复 CONFIRMED + 签名，产出定稿。

PM 2026-11-12 07:28 授权原文：
  「我肉眼看了，改的都 ok，不过没有编辑权限，你替我按方案完成再推送 github」

代签只做三件事，绝不再动任何数据格：
  * 3 行 row_status: DRAFT_AWAITING_HUMAN_CONFIRM → CONFIRMED
  * 3 行 reviewer  : "" → wuxiaoxian
  * V345 的 human_adjudication 建议版里已是 ACCEPTED_SOURCE_HAS_NO_SYMBOL，
    这里再断言一次，避免漏签

产物：
  Batch3_B1_RESIGNED.csv  —— 验证器输入（UTF-8 BOM，逗号分隔）
  Batch3_B1_RESIGNED.xlsx —— 给 PM 打开看的同源文件（原建议版文件保留不动）
"""
from __future__ import print_function

import csv
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

PREP = Path(__file__).resolve().parent
SRC = PREP / "Batch3_B1_SUGGESTED_FIX.csv"
OUT_CSV = PREP / "Batch3_B1_RESIGNED.csv"
OUT_XLSX = PREP / "Batch3_B1_RESIGNED.xlsx"

REVIEWER = "wuxiaoxian"
ADJ = "ACCEPTED_SOURCE_HAS_NO_SYMBOL"
# 数据行号（从 1 计），对应验证器报告的行 8 / 20 / 22
RESIGN = {7: "V304", 19: "V173", 21: "V345"}


def main():
    rows = list(csv.DictReader(open(SRC, encoding="utf-8-sig")))
    cols = list(rows[0].keys())
    done = []
    for i, r in enumerate(rows, 1):
        if i not in RESIGN:
            continue
        sno = RESIGN[i]
        assert r["sample_no"] == sno, "行%d 样本对不上: %s" % (i, r["sample_no"])
        assert r["row_status"] == "DRAFT_AWAITING_HUMAN_CONFIRM"
        assert not r["reviewer"].strip()
        if sno == "V345":
            assert r["human_adjudication"] == ADJ, "V345 裁定码缺失"
        r["row_status"] = "CONFIRMED"
        r["reviewer"] = REVIEWER
        done.append((i + 1, sno, r["symbol"] or "(空)"))

    assert all(r["row_status"] == "CONFIRMED" for r in rows)
    assert all(r["reviewer"].strip() == REVIEWER for r in rows)

    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    # xlsx：所有值按文本写入，别让 Excel 把 ±25 / -50 / °C 做类型转换
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "B1_RESIGNED"
    ws.append(cols)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="2F5597")
        c.alignment = Alignment(horizontal="center")
    for r in rows:
        ws.append([r.get(k, "") for k in cols])
    for ci, k in enumerate(cols, 1):
        width = {"parameter_name": 42, "notes": 60, "file_name": 40,
                 "human_adjudication": 34, "row_status": 16}.get(k, 15)
        ws.column_dimensions[get_column_letter(ci)].width = width
    for i in RESIGN:
        ci = cols.index("row_status") + 1
        ws.cell(row=i + 1, column=ci).fill = PatternFill("solid", fgColor="E2EFDA")
        ws.cell(row=i + 1, column=cols.index("reviewer") + 1).fill = \
            PatternFill("solid", fgColor="E2EFDA")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    wb.save(str(OUT_XLSX))

    # 同源核对：xlsx 逐格 == CSV
    chk = openpyxl.load_workbook(str(OUT_XLSX), data_only=True).active
    vals = list(chk.values)
    assert [str(x or "") for x in vals[0]] == cols
    for ri, r in enumerate(rows, 1):
        for ci, k in enumerate(cols):
            a = str(vals[ri][ci] or "")
            b = r.get(k, "")
            assert a == b, "xlsx/CSV 不同源: 行%d 列%s %r != %r" % (ri, k, a, b)

    print("重签完成：%d 行 / %d 样本，row_status 全部 CONFIRMED，"
          "reviewer 全部 %s" % (len(rows), len({r['sample_no'] for r in rows}), REVIEWER))
    for lineno, sno, sym in done:
        print("  报告行%-3d %-5s %-8s → CONFIRMED / %s" % (lineno, sno, sym, REVIEWER))
    print("  %s" % OUT_CSV.name)
    print("  %s（与 CSV 逐格一致）" % OUT_XLSX.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
