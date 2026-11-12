# -*- coding: utf-8 -*-
"""按 PM 2026-11-12 09:52 指令：撤销错位的 approved_by，生成待补签清单。

背景
----
PM 09:48 在 Batch3_B2_FINAL.xlsx 的 approved_by 列签了 7 处 wuxiaoxian，
逐格核对后发现落点是数据行 8/9/22/23/24/25/26，而 WB 代录入、
真正需要逐行复核的 7 行是数据行 8/9/16/17/18/19/20。
PM 裁定：7 处全部清空、恢复原样，重新对照 PDF 原图后按正确行号补签。

本脚本做四件事
--------------
1. 从 Batch3_B2_FINAL_pre_approval.xlsx（封卷前无签名版，逐格未改）
   恢复主定稿 xlsx 与 CSV，恢复后与已推送的 6107ab7 版本字节一致；
2. 错签版原件保留在 Batch3_B2_FINAL_SIGNED_approval.xlsx 作为审计留痕，
   同时写一份 Batch3_B2_approval_revoke_note.txt 记录撤销原因与差异；
3. 生成 Batch3_B2_FINAL_TO_SIGN.xlsx：19 列全表副本，仅把 7 个待签
   approved_by 单元格标红并加批注，另附「补签清单」sheet；
4. 生成 Batch3_B2_APPROVAL_TARGETS.txt：纯文本清单，给出 Excel 行号、
   sample_no、evidence_page、symbol、condition、对应 PDF 原图。

本脚本不代填任何人工签名，不改动 min/max/typ / reviewer / symbol / condition。
"""
from __future__ import print_function

import csv
import hashlib
import os
import shutil
from pathlib import Path

import openpyxl
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

PREP = Path(__file__).resolve().parent
MAIN_XLSX = PREP / "Batch3_B2_FINAL.xlsx"
MAIN_CSV = PREP / "Batch3_B2_FINAL.csv"
PRE_APPROVAL = PREP / "Batch3_B2_FINAL_pre_approval.xlsx"
WRONG_SIGNED = PREP / "Batch3_B2_FINAL_SIGNED_approval.xlsx"
AUDIT_CSV = Path(
    r"E:\workspace\github\stageA-audit-v28\gate6a-plan\batch3_review"
    r"\Batch3_B2_FINAL.csv")
TO_SIGN = PREP / "Batch3_B2_FINAL_TO_SIGN.xlsx"
TARGETS_TXT = PREP / "Batch3_B2_APPROVAL_TARGETS.txt"
REVOKE_NOTE = PREP / "Batch3_B2_approval_revoke_note.txt"

FINAL_COLS = [
    "sample_no", "file_name", "evidence_page", "table_title", "symbol",
    "parameter_name", "min_value", "typ_value", "max_value", "unit",
    "condition", "row_status", "notes", "reviewer", "approved_by",
    "entered_by", "confidence_score", "device_model", "human_adjudication",
]
REVIEWER = "wuxiaoxian"
PDF_DIR = Path(r"E:\workspace\IcPdfParser\data\pdfs")
ALIAS = {
    "ADC12QJ1600ALREP.pdf": "ADC12QJ1600ALREP__adc12qj1600-ep.pdf",
    "ADS54J40IRMPT.pdf": "ADS54J40IRMPT__ads54j40.pdf",
    "ADS131B26-Q1.pdf": "ADS131B26QPHPRQ1__ads131b26-q1.pdf",
}
V320_PDF = "DAC3482IRKDR__slas748f.pdf"
V242_PDF = "ADS131B26QPHPRQ1__ads131b26-q1.pdf"


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


def read_xlsx(path):
    ws = openpyxl.load_workbook(str(path), data_only=True, read_only=True).active
    vals = list(ws.values)
    hdr = [str(x or "").strip() for x in vals[0]]
    assert hdr == FINAL_COLS, "%s 表头异常" % path.name
    rows = []
    for v in vals[1:]:
        if not any(x is not None and str(x).strip() for x in v):
            continue
        rows.append({k: cell(v[i]) for i, k in enumerate(FINAL_COLS)})
    assert len(rows) == 30, "%s 应为 30 行" % path.name
    return rows


def write_csv(rows, path):
    tmp = path.with_name(path.name + ".wb_tmp")
    with open(tmp, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FINAL_COLS)
        w.writeheader()
        w.writerows(rows)
    try:
        os.replace(str(tmp), str(path))
    except PermissionError:
        raise SystemExit("CSV 被占用，请关闭 Excel/预览后重跑：%s" % path)
    finally:
        if tmp.exists():
            tmp.unlink()


def restore(src, dst):
    tmp = dst.with_name(dst.name + ".wb_tmp")
    shutil.copy2(str(src), str(tmp))
    try:
        os.replace(str(tmp), str(dst))
    except PermissionError:
        if dst.exists() and sha(dst) == sha(src):
            tmp.unlink()
            return "跳过（目标被占用，字节一致）"
        raise SystemExit("目标被占用且内容不一致，请关闭 Excel 后重跑：%s" % dst)
    finally:
        if tmp.exists():
            tmp.unlink()
    return "已恢复"


def main():
    for p in (PRE_APPROVAL, WRONG_SIGNED, AUDIT_CSV):
        if not p.is_file():
            raise SystemExit("缺少输入文件：%s" % p)

    clean = read_xlsx(PRE_APPROVAL)
    wrong = read_xlsx(WRONG_SIGNED)
    assert not any(r["approved_by"] for r in clean), "封卷前版本不应有签名"
    signed_lines = [i for i, r in enumerate(wrong, 1) if r["approved_by"]]
    assert len(signed_lines) == 7, "错签版应有 7 处签名"

    # 除 approved_by 外 18 列必须完全一致，撤销才不会碰到数据
    for i, (a, b) in enumerate(zip(clean, wrong), 1):
        for k in FINAL_COLS:
            if k != "approved_by":
                assert a[k] == b[k], "行%d 列%s 在错签版里被动过" % (i, k)

    # 待签 7 行 = WB 代录入行（entered_by=WB_Agent），按真源动态识别，不写死行号
    targets = [i for i, r in enumerate(clean, 1) if r["entered_by"] == "WB_Agent"]
    assert len(targets) == 7, "代录入行应为 7 行，实际 %d" % len(targets)
    assert [clean[i - 1]["sample_no"] for i in targets] == \
        ["V320", "V320", "V242", "V242", "V242", "V242", "V242"]

    # ---- 1. 恢复主定稿 ----
    print("撤销错签：%s" % ", ".join("数据行%d" % i for i in signed_lines))
    print("  主 xlsx -> %s" % restore(PRE_APPROVAL, MAIN_XLSX))
    write_csv(clean, MAIN_CSV)
    assert sha(MAIN_XLSX) == sha(PRE_APPROVAL), "主 xlsx 未恢复到封卷前字节"
    assert sha(MAIN_CSV) == sha(AUDIT_CSV), \
        "主 CSV 与已推送 6107ab7 版本字节不一致"
    assert not any(r["approved_by"] for r in read_xlsx(MAIN_XLSX))
    print("  主 CSV  -> 已重建；两者与已推送 6107ab7 逐字节一致")

    # ---- 2. 撤销留痕 ----
    lines = [
        "Batch 3 B2 授权链签字撤销留痕",
        "时间：2026-11-12 09:52（PM 主动发现并要求）",
        "原因：PM 09:48 在 approved_by 列签的 7 处 wuxiaoxian 落点错位。",
        "      实际签字行（数据行）：%s" % signed_lines,
        "      真正需要逐行复核的代录进行（数据行）：%s" % targets,
        "      仅数据行 8/9 重合；数据行 22/23/24/25/26（V003 四行、V011 一行）"
        "并非 WB 代录入，数据行 16-20（V242 五行）反而漏签。",
        "处置：按 PM 指令把 7 处 approved_by 全部清空，恢复到封卷前状态；",
        "      PM 对照 PDF 原图重新核一遍后，在正确行号上补 approved_by=wuxiaoxian。",
        "留痕文件：Batch3_B2_FINAL_SIGNED_approval.xlsx（错签版原件，逐格未改）",
        "          Batch3_B2_FINAL_pre_approval.xlsx（封卷前无签名版，逐格未改）",
        "=" * 72,
        "被撤销的 7 处（数据行 / Excel 行 / 样本 / symbol / 原值）：",
    ]
    for i in signed_lines:
        r = wrong[i - 1]
        lines.append("  数据行%-3d Excel行%-3d %-5s %-30s  %r -> 空" %
                     (i, i + 1, r["sample_no"], r["symbol"][:30],
                      r["approved_by"]))
    lines.append("=" * 72)
    lines.append("待补签 7 行见 Batch3_B2_APPROVAL_TARGETS.txt / "
                 "Batch3_B2_FINAL_TO_SIGN.xlsx")
    REVOKE_NOTE.write_text("\n".join(lines) + "\n", encoding="utf-8",
                           newline="\n")

    # ---- 3. 纯文本清单 ----
    out = [
        "Batch 3 B2 待补签清单（approved_by=wuxiaoxian）",
        "主文件：Batch3_B2_FINAL.xlsx / Batch3_B2_FINAL.csv（已恢复为无签名版）",
        "填写位置：O 列 approved_by；Excel 行号 = 数据行号 + 1（第 1 行是表头）",
        "只需填下面 7 个格子，其余 23 行保持空白，不要改任何数值或 reviewer。",
        "=" * 104,
        "%-9s %-9s %-7s %-6s %-30s %-30s %-12s %s" %
        ("Excel行", "数据行", "样本", "页码", "symbol（回填后的现值）",
         "condition（现值）", "表类型", "PDF 原图"),
        "-" * 104,
    ]
    for i in targets:
        r = clean[i - 1]
        pdf = V320_PDF if r["sample_no"] == "V320" else (
            V242_PDF if r["sample_no"] == "V242" else
            ALIAS.get(r["file_name"], r["file_name"]))
        out.append("%-9d %-9d %-7s %-6s %-30s %-30s %-12s %s" %
                   (i + 1, i, r["sample_no"], r["evidence_page"],
                    r["symbol"], r["condition"] or "(空)",
                    "AMR" if r["table_title"] == "Absolute Maximum Ratings"
                    else "ROC", pdf))
    out += [
        "-" * 104,
        "核对依据：",
        "  V320 两行 -> %s 第 12 页 Absolute Maximum Ratings 表；" % V320_PDF,
        "              符号原文行 11 `DACVDD, DIGVDD, CLKVDD`、行 24 `AVDD, PLLAVDD`；",
        "              全表条件 `over operating free-air temperature range "
        "(unless otherwise noted)(1)`。",
        "  V242 五行 -> %s 第 6 页 Absolute Maximum Ratings 表；" % V242_PDF,
        "              符号原文行 7/11/14/17/20；该表只有 `see (1)` 脚注引用，",
        "              没有具体测试条件，故 condition 留空是正确的。",
        "=" * 104,
        "填法二选一：① 直接在 Batch3_B2_FINAL_TO_SIGN.xlsx 的 7 个红格填好后保存发回；",
        "          ② 或在已打开的 Batch3_B2_FINAL.xlsx 的 O 列对应 Excel 行号填好后保存发回。",
        "WB 只做逐格核对 + v1.6 机检 + 封卷，不会代填、不会自动补齐、不会改动其他格子。",
    ]
    TARGETS_TXT.write_text("\n".join(out) + "\n", encoding="utf-8",
                           newline="\n")

    # ---- 4. 标红待签版 ----
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "B2_FINAL_待补签"
    ws.append(FINAL_COLS)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="2F5597")
        c.alignment = Alignment(horizontal="center")
    for r in clean:
        ws.append([r[k] for k in FINAL_COLS])
    red = PatternFill("solid", fgColor="FFC7CE")
    red_font = Font(color="9C0006", bold=True)
    ap_col = FINAL_COLS.index("approved_by") + 1
    for i in targets:
        c = ws.cell(row=i + 1, column=ap_col)
        c.fill = red
        c.font = red_font
        c.comment = Comment(
            "请在此填 wuxiaoxian（第 %d 行，%s，符号 %s）。\n"
            "其余 23 行保持空白。" % (i + 1, clean[i - 1]["sample_no"],
                                     clean[i - 1]["symbol"]),
            "WB_Agent")
    for ci, k in enumerate(FINAL_COLS, 1):
        width = {"parameter_name": 42, "notes": 60, "file_name": 40,
                 "human_adjudication": 34, "row_status": 16,
                 "table_title": 32, "approved_by": 16,
                 "entered_by": 15, "condition": 32, "symbol": 28}.get(k, 15)
        ws.column_dimensions[get_column_letter(ci)].width = width
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    cl = wb.create_sheet("补签清单")
    cl.append(["Excel 行号", "数据行号", "sample_no", "evidence_page",
               "table_title", "symbol（现值）", "condition（现值）",
               "entered_by", "approved_by（当前）", "approved_by（应填）",
               "PDF 原图"])
    for c in cl[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="2F5597")
        c.alignment = Alignment(horizontal="center")
    for i in targets:
        r = clean[i - 1]
        pdf = V320_PDF if r["sample_no"] == "V320" else V242_PDF
        cl.append([i + 1, i, r["sample_no"], int(r["evidence_page"]),
                   r["table_title"], r["symbol"], r["condition"],
                   r["entered_by"], "", REVIEWER, pdf])
        for c in cl[cl.max_row]:
            c.fill = red
            c.font = red_font
    for ci, width in enumerate([12, 12, 12, 15, 34, 30, 46, 15, 19, 21, 44], 1):
        cl.column_dimensions[get_column_letter(ci)].width = width
    cl.freeze_panes = "A2"
    wb.save(str(TO_SIGN))

    # 标红版数据必须与主定稿逐格一致（只有样式 / 批注不同）
    back = read_xlsx(TO_SIGN)
    assert back == clean, "待签版数据与主定稿不一致"
    assert not any(r["approved_by"] for r in back), "待签版不得预填人工签名"

    print("\n--- 待补签 7 行（Excel 行号 = 数据行号 + 1）---")
    for i in targets:
        r = clean[i - 1]
        print("  Excel 行%-3d 数据行%-3d %-5s p%-4s symbol=%-28r condition=%r" %
              (i + 1, i, r["sample_no"], r["evidence_page"],
               r["symbol"], r["condition"]))
    print("\n产物：")
    for p in (MAIN_XLSX, MAIN_CSV, TO_SIGN, TARGETS_TXT, REVOKE_NOTE,
              WRONG_SIGNED, PRE_APPROVAL):
        print("  %-46s %8d 字节" % (p.name, p.stat().st_size))
    print("\n主定稿已恢复为无签名版，与 6107ab7 逐字节一致；封卷暂停，等 PM 补签。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
