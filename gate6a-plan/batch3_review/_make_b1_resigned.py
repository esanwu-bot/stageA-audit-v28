# -*- coding: utf-8 -*-
"""B1 最终定稿：PM 授权代签 + Reviewer 第二轮的授权链/表头/备注修正。

流水线（要复现最终版请依次跑）：
  _build_batch3_verify_inputs.py → _make_b1_suggest_fix.py → 本脚本

两轮修正的历史
----------------
1) PM 2026-11-12 07:28 授权代签：
     「我肉眼看了，改的都 ok，不过没有编辑权限，你替我按方案完成再推送 github」
   把建议修正版的 3 行恢复 CONFIRMED + reviewer=wuxiaoxian。

2) Reviewer 2026-11-12 08:08 第二轮（本脚本一并做掉，避免中间态文件）：
   * 物理行 8（数据行 7）V304 的 table_title 从 Electrical Characteristics
     改为 Absolute Maximum Ratings —— p4 原文第 6.1 节 AMR 表内确有
     IIK / Control input clamp current / VIN < 0 / -50 mA。
   * 新增 approved_by / entered_by 两列，只在这 3 行填
     approved_by=wuxiaoxian、entered_by=WB_Agent，把「谁批准」与「谁录入」
     分开。其余 20 行是人工直接在 Excel 里签的，没有代录入环节，两列留空。
   * 这 3 行 notes 里「待人确认并重新签字」等过期表述全部删掉，
     统一改成「人工已核对 PDF p4 原图并确认此修正。」

前序版本（SIGNED / CONFIRMED / SUGGESTED_FIX）保留不动，作为审计留痕；
本脚本输出覆盖 Batch3_B1_RESIGNED.csv / .xlsx，文件名即最终真源，不再新增别名。

产物：
  Batch3_B1_RESIGNED.csv  —— 验证器输入（UTF-8 BOM，逗号分隔，19 列）
  Batch3_B1_RESIGNED.xlsx —— 给 PM / Reviewer 打开看的同源文件
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
# 数据行号（从 1 计），对应验证器报告的物理行 8 / 20 / 22
RESIGN = {7: "V304", 19: "V173", 21: "V345"}

# Reviewer 第二轮修正
APPROVED_BY = "wuxiaoxian"
ENTERED_BY = "WB_Agent"
FINAL_NOTE = "人工已核对 PDF p4 原图并确认此修正。"
TITLE_FIX = {7: ("Electrical Characteristics", "Absolute Maximum Ratings")}
NEW_COLS = ("approved_by", "entered_by")
STALE_WORDS = ("待人确认", "需人工确认", "重新签字", "须对左图核")


def main():
    rows = list(csv.DictReader(open(SRC, encoding="utf-8-sig")))
    cols = list(rows[0].keys())
    at = cols.index("reviewer") + 1
    cols[at:at] = list(NEW_COLS)
    for r in rows:
        for k in NEW_COLS:
            r.setdefault(k, "")

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

        # 第一轮：恢复签名
        r["row_status"] = "CONFIRMED"
        r["reviewer"] = REVIEWER
        # 第二轮：授权链、表头归属、备注
        r["approved_by"] = APPROVED_BY
        r["entered_by"] = ENTERED_BY
        r["notes"] = FINAL_NOTE
        if i in TITLE_FIX:
            old, new = TITLE_FIX[i]
            assert r["table_title"] == old, \
                "行%d table_title 不是预期旧值：%r" % (i, r["table_title"])
            r["table_title"] = new
        done.append((i + 1, sno, r["symbol"] or "(空)"))

    # 全表回归断言：签名、两列只出现在 3 行、备注无过期词、表头修正到位
    assert len(rows) == 23, "行数不是 23"
    assert all(r["row_status"] == "CONFIRMED" for r in rows)
    assert all(r["reviewer"].strip() == REVIEWER for r in rows)
    assert sum(1 for r in rows if r["approved_by"] == APPROVED_BY) == 3
    assert sum(1 for r in rows if r["entered_by"] == ENTERED_BY) == 3
    assert sum(1 for r in rows if r["approved_by"] or r["entered_by"]) == 3
    for i, r in enumerate(rows, 1):
        if i in RESIGN:
            assert r["notes"] == FINAL_NOTE, "行%d 备注没换成定稿措辞" % i
            assert not any(w in r["notes"] for w in STALE_WORDS)
    assert rows[6]["table_title"] == "Absolute Maximum Ratings"
    assert all(r["table_title"] != "Electrical Characteristics"
               for r in rows if r["sample_no"] == "V304"), "V304 仍有 ELC 归属"

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
                 "human_adjudication": 34, "row_status": 16,
                 "table_title": 32, "approved_by": 16,
                 "entered_by": 15}.get(k, 15)
        ws.column_dimensions[get_column_letter(ci)].width = width
    green = PatternFill("solid", fgColor="E2EFDA")
    for i in RESIGN:
        for k in ("row_status", "reviewer", "approved_by", "entered_by"):
            ws.cell(row=i + 1, column=cols.index(k) + 1).fill = green
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

    print("最终定稿：%d 行 / %d 样本 / %d 列，row_status 全部 CONFIRMED，"
          "reviewer 全部 %s" % (len(rows), len({r["sample_no"] for r in rows}),
                                len(cols), REVIEWER))
    for lineno, sno, sym in done:
        print("  物理行%-3d %-5s %-8s → CONFIRMED / %s / approved_by=%s / entered_by=%s"
              % (lineno, sno, sym, REVIEWER, APPROVED_BY, ENTERED_BY))
    print("  V304 物理行 8 table_title → Absolute Maximum Ratings")
    print("  3 行 notes → %s" % FINAL_NOTE)
    print("  %s" % OUT_CSV.name)
    print("  %s（与 CSV 逐格一致）" % OUT_XLSX.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
