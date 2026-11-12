# -*- coding: utf-8 -*-
"""B2 封卷：以 PM 补签后的标红版为唯一真源，复核授权链并同步 19 列定稿。

PM 授权（2026-11-12 10:05）
---------------------------
「我授权你在正确位置，签署 wuxiaoxian」。
实测 PM 已在 Batch3_B2_FINAL_TO_SIGN.xlsx 的 7 个红格填好 wuxiaoxian，
落点为数据行 8/9/16/17/18/19/20（Excel 行 9/10/17/18/19/20/21），
与 entered_by=WB_Agent 的 7 行完全重合，位置正确。
本脚本不代填、不改写任何人工签名，只做复核 + 同步 + 留痕。

严格断言
--------
1. 签字真源 30 行 × 19 列，表头与定稿一致；
2. approved_by 非空的 7 行必须恰好等于 entered_by=WB_Agent 的 7 行；
3. 每个非空 approved_by 只能是 wuxiaoxian，其余 23 行必须为空；
4. 除 approved_by 外 18 列与封卷前无签名版逐格一致
   （min/max/typ / reviewer / symbol / condition / notes 一字未动）；
5. reviewer 全为 wuxiaoxian、row_status 全为 CONFIRMED、
   symbol 无空、human_adjudication 全空；
6. 主 xlsx 与 CSV 落盘后逐格与签字真源一致。

产物
----
  Batch3_B2_FINAL.xlsx / .csv       封卷定稿（单 sheet，与签字真源同源）
  Batch3_B2_FINAL_SIGNED_correct.xlsx   PM 正确补签原件留痕（逐格未改）
  Batch3_B2_approval_authorization.txt  授权链说明（如实区分人工签字与 WB 复核）
"""
from __future__ import print_function

import csv
import hashlib
import os
import shutil
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

PREP = Path(__file__).resolve().parent
SIGNED = PREP / "Batch3_B2_FINAL_TO_SIGN.xlsx"
PRE_APPROVAL = PREP / "Batch3_B2_FINAL_pre_approval.xlsx"
SIGNED_COPY = PREP / "Batch3_B2_FINAL_SIGNED_correct.xlsx"
MAIN_XLSX = PREP / "Batch3_B2_FINAL.xlsx"
MAIN_CSV = PREP / "Batch3_B2_FINAL.csv"
AUTH_NOTE = PREP / "Batch3_B2_approval_authorization.txt"

FINAL_COLS = [
    "sample_no", "file_name", "evidence_page", "table_title", "symbol",
    "parameter_name", "min_value", "typ_value", "max_value", "unit",
    "condition", "row_status", "notes", "reviewer", "approved_by",
    "entered_by", "confidence_score", "device_model", "human_adjudication",
]
REVIEWER = "wuxiaoxian"


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cell(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def read_first_sheet(path):
    wb = openpyxl.load_workbook(str(path), data_only=True, read_only=True)
    ws = wb.active
    vals = list(ws.values)
    sheets = wb.sheetnames
    wb.close()
    hdr = [str(x or "").strip() for x in vals[0]]
    assert hdr == FINAL_COLS, "%s 首个 sheet 表头异常：%r" % (path.name, hdr)
    rows = []
    for v in vals[1:]:
        if not any(x is not None and str(x).strip() for x in v):
            continue
        rows.append({k: cell(v[i]) for i, k in enumerate(FINAL_COLS)})
    assert len(rows) == 30, "%s 应为 30 行，实际 %d" % (path.name, len(rows))
    return rows, sheets


def atomic_replace(tmp, dst):
    try:
        os.replace(str(tmp), str(dst))
    except PermissionError:
        raise SystemExit("目标被占用，请关闭 Excel/预览后重跑：%s" % dst)
    finally:
        if tmp.exists():
            tmp.unlink()


def main():
    for p in (SIGNED, PRE_APPROVAL):
        if not p.is_file():
            raise SystemExit("缺少输入：%s" % p)

    signed, sheets = read_first_sheet(SIGNED)
    clean, _ = read_first_sheet(PRE_APPROVAL)
    assert not any(r["approved_by"] for r in clean), "封卷前版本不应有签名"
    print("签字真源：%s  %d 字节  sheets=%r  sha256=%s" %
          (SIGNED.name, SIGNED.stat().st_size, sheets, sha(SIGNED)[:16]))

    ap = [i for i, r in enumerate(signed, 1) if r["approved_by"]]
    eb = [i for i, r in enumerate(signed, 1) if r["entered_by"] == "WB_Agent"]
    print("approved_by 非空（数据行）：%s" % ap)
    print("entered_by=WB_Agent（数据行）：%s" % eb)
    assert len(ap) == 7 and ap == eb, \
        "补签落点未与 WB 代录进行对齐：approved_by=%r / entered_by=%r" % (ap, eb)
    assert all(r["approved_by"] == REVIEWER for r in signed if r["approved_by"]), \
        "approved_by 出现非 PM 本人签名"

    # 授权链之外 18 列逐格未变
    diffs = []
    for i, (a, b) in enumerate(zip(signed, clean), 1):
        for k in FINAL_COLS:
            if k != "approved_by" and a[k] != b[k]:
                diffs.append((i, k, b[k], a[k]))
    assert not diffs, "除 approved_by 外还有列被改动：%r" % diffs[:5]
    assert all(r["reviewer"] == REVIEWER for r in signed)
    assert all(r["row_status"] == "CONFIRMED" for r in signed)
    assert all(r["symbol"].strip() for r in signed)
    assert not any(r["human_adjudication"] for r in signed)

    # 人工签字原件留痕（逐格未改）
    tmp = SIGNED_COPY.with_name(SIGNED_COPY.name + ".wb_tmp")
    shutil.copy2(str(SIGNED), str(tmp))
    atomic_replace(tmp, SIGNED_COPY)
    assert sha(SIGNED_COPY) == sha(SIGNED), "签字原件留痕字节不一致"

    # 主 xlsx：单 sheet 定稿，样式与第五轮一致
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "B2_FINAL"
    ws.append(FINAL_COLS)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="2F5597")
        c.alignment = Alignment(horizontal="center")
    for r in signed:
        ws.append([r[k] for k in FINAL_COLS])
    for ci, k in enumerate(FINAL_COLS, 1):
        width = {"parameter_name": 42, "notes": 60, "file_name": 40,
                 "human_adjudication": 34, "row_status": 16,
                 "table_title": 32, "approved_by": 16,
                 "entered_by": 15, "condition": 32}.get(k, 15)
        ws.column_dimensions[get_column_letter(ci)].width = width
    green = PatternFill("solid", fgColor="E2EFDA")
    for i in eb:
        for k in ("symbol", "condition", "entered_by", "approved_by"):
            ws.cell(row=i + 1, column=FINAL_COLS.index(k) + 1).fill = green
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    tmp = MAIN_XLSX.with_name(MAIN_XLSX.name + ".wb_tmp")
    wb.save(str(tmp))
    atomic_replace(tmp, MAIN_XLSX)

    # CSV（UTF-8 BOM / CRLF，与历史定稿一致）
    tmp = MAIN_CSV.with_name(MAIN_CSV.name + ".wb_tmp")
    with open(tmp, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FINAL_COLS)
        w.writeheader()
        w.writerows(signed)
    atomic_replace(tmp, MAIN_CSV)

    # 三方逐格一致
    back_xlsx, _ = read_first_sheet(MAIN_XLSX)
    with open(MAIN_CSV, encoding="utf-8-sig", newline="") as fh:
        back_csv = [{k: (r.get(k) or "") for k in FINAL_COLS}
                    for r in csv.DictReader(fh)]
    assert back_xlsx == signed, "主 xlsx 与签字真源不同源"
    assert back_csv == signed, "主 CSV 与签字真源不同源"

    note = [
        "Batch 3 B2 授权链封卷记录",
        "时间：2026-11-12 10:05（PM 明确授权）",
        "PM 原话：「我授权你在正确位置，签署 wuxiaoxian」",
        "",
        "事实经过（如实区分人工操作与 WB 复核）：",
        "  1. 09:48 PM 在 approved_by 列签了 7 处，落点为数据行 "
        "8/9/22/23/24/25/26，其中 5 行不是 WB 代录进行；",
        "  2. 09:52 PM 主动发现并要求全部清空、恢复原样，WB 已按指令撤销，"
        "主定稿恢复为与 6107ab7 逐字节一致；",
        "  3. 10:03 PM 在 WB 提供的标红版 Batch3_B2_FINAL_TO_SIGN.xlsx 中，"
        "自行在 7 个红格补填 wuxiaoxian 并保存；",
        "  4. 10:05 PM 再次授权 WB 在正确位置落签。WB 实测 PM 已填的 7 行"
        "恰为数据行 8/9/16/17/18/19/20（Excel 行 9/10/17/18/19/20/21），",
        "     与 entered_by=WB_Agent 的 7 行完全重合，故不再代填、不改写任何"
        "人工签名，仅做逐格复核并同步到封卷定稿。",
        "",
        "结论：approved_by 的 7 处值由 PM 本人或其明确授权的代签产生，",
        "      WB 未擅自补签、未自动补齐、未改动其余 23 行，也未改动任何核心数值。",
        "真源：Batch3_B2_FINAL_TO_SIGN.xlsx（PM 补签原件，逐格未改）",
        "留痕：Batch3_B2_FINAL_SIGNED_correct.xlsx（同上字节副本）",
        "      Batch3_B2_FINAL_SIGNED_approval.xlsx（09:48 错签原件）",
        "      Batch3_B2_FINAL_pre_approval.xlsx（封卷前无签名版）",
        "      Batch3_B2_approval_revoke_note.txt（撤销说明）",
        "",
        "封卷定稿逐格核对：",
        "  approved_by 非空数据行：%s" % ap,
        "  entered_by=WB_Agent 数据行：%s" % eb,
        "  除 approved_by 外 18 列相对封卷前版本差异：0 处",
        "  reviewer=wuxiaoxian 30/30；row_status=CONFIRMED 30/30；symbol 空 0；",
        "  human_adjudication 非空 0。",
    ]
    AUTH_NOTE.write_text("\n".join(note) + "\n", encoding="utf-8", newline="\n")

    print("\n--- 封卷签字链 ---")
    for i in ap:
        r = signed[i - 1]
        print("  Excel 行%-3d 数据行%-3d %-5s p%-4s approved_by=%-11s symbol=%r" %
              (i + 1, i, r["sample_no"], r["evidence_page"],
               r["approved_by"], r["symbol"]))
    print("\n  除 approved_by 外 18 列差异：0 处；其余 23 行 approved_by 为空")
    print("  主 xlsx / CSV / 签字真源三方逐格一致")
    for p in (MAIN_XLSX, MAIN_CSV, SIGNED_COPY, AUTH_NOTE):
        print("  %-46s %8d 字节" % (p.name, p.stat().st_size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
