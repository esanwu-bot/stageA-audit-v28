# -*- coding: utf-8 -*-
"""把 B1 四份机检原始输出汇成一份可复核报告。

原始输出固定在 b1_validation_raw/，报告里逐字贴出命令、输出、退出码。
不重跑、不改写、不挑好看的贴 —— 签字版 ERROR=2 的那两份也在里面。
"""
from __future__ import print_function

from pathlib import Path

PREP = Path(__file__).resolve().parent
RAW = PREP / "b1_validation_raw"
OUT = PREP / "Batch3_B1_validation_report.txt"

CASES = [
    ("B.1 签字版 · PDF 模式（实算哈希）",
     "python validate_annotation.py --csv Batch3_B1_CONFIRMED.csv "
     "--page-text page_text_batch3_b1.json "
     "--provenance Batch3_B1_PDF_PROVENANCE.csv --pdf-dir <PDF>",
     "b1_signed_pdf_mode.txt", 1),
    ("B.2 签字版 · 离线模式（sidecar）",
     "env -u ICPDF_PDF_DIR python validate_annotation.py --csv Batch3_B1_CONFIRMED.csv "
     "--page-text page_text_batch3_b1.json --provenance Batch3_B1_PDF_PROVENANCE.csv",
     "b1_signed_sidecar_mode.txt", 1),
    ("D.1 建议修正版 · PDF 模式（实算哈希）",
     "python validate_annotation.py --csv Batch3_B1_SUGGESTED_FIX.csv "
     "--page-text page_text_batch3_b1.json "
     "--provenance Batch3_B1_PDF_PROVENANCE.csv --pdf-dir <PDF>",
     "b1_suggested_pdf_mode.txt", 0),
    ("D.2 建议修正版 · 离线模式（sidecar）",
     "env -u ICPDF_PDF_DIR python validate_annotation.py --csv Batch3_B1_SUGGESTED_FIX.csv "
     "--page-text page_text_batch3_b1.json --provenance Batch3_B1_PDF_PROVENANCE.csv",
     "b1_suggested_sidecar_mode.txt", 0),
]

# PM 2026-11-12 07:28 授权代签后的重跑（3 行恢复 CONFIRMED + reviewer 签名）
RESIGNED = [
    ("F.1 重签版 · PDF 模式（实算哈希）",
     "python validate_annotation.py --csv Batch3_B1_RESIGNED.csv "
     "--page-text page_text_batch3_b1.json "
     "--provenance Batch3_B1_PDF_PROVENANCE.csv --pdf-dir <PDF>",
     "b1_resigned_pdf_mode.txt", 0),
    ("F.2 重签版 · 离线模式（sidecar）",
     "env -u ICPDF_PDF_DIR python validate_annotation.py --csv Batch3_B1_RESIGNED.csv "
     "--page-text page_text_batch3_b1.json --provenance Batch3_B1_PDF_PROVENANCE.csv",
     "b1_resigned_sidecar_mode.txt", 0),
]


def main():
    L = []
    A = L.append
    A("=" * 78)
    A("Batch 3 · B1 人工签字定稿 —— v1.6 验证器机检报告")
    A("=" * 78)
    A("")
    A("真源：D:/Documents/Downloads/Batch2_ANNOTATED (1).xlsx（PM 指定只读 xlsx）")
    A("      Excel 另存出的同名 .csv 是 GBK 编码 + Tab 分隔，属导出格式，不作为标注真源。")
    A("签字：reviewer=wuxiaoxian，23 行全部 CONFIRMED")
    A("草稿 30 行 → 人工点选后保留 23 行（删 7 行）。机检对象 = 定稿 23 行 / 6 样本。")
    A("")
    A("A. 验证器输入从哪来（不能让报告变绿就关检查）")
    A("-" * 78)
    A("v1.6 验证器要求 CSV 有 device_model、sidecar 有溯源四项、provenance 与之全一致，")
    A("PDF 模式还要实算 SHA-256。圈选台草稿没有这些字段，因此由")
    A("_build_batch3_verify_inputs.py 补齐，补的都是实测值，没有绕过任何一条判据：")
    A("  * device_model 取各 PDF 第 1 页标题行（V173 SN74AHCT1G04 / V199 CSD18504Q5A /")
    A("    V304 SN74CB3T3306 / V319 TLV2354 / V336 DS96F173MQML / V345 DAC63202W）")
    A("  * sha256 / page_count / size_bytes 从磁盘 PDF 原件实算")
    A("  * pages 逐页抽文本；PDF 模式验证器再用原件复算哈希与页文本")
    A("  * 原 xlsx 的 15 列逐格照抄，只追加 device_model / human_adjudication 两列")
    A("局限：三处溯源写的是同一份实测数据，不是三个独立来源；真正独立的第三方证据")
    A("是磁盘 PDF 原件（哈希实算 + 页内文字核对）。这一条请复核者知悉。")
    A("")
    A("B. 签字版实跑结果 —— ERROR=2，不是全绿")
    A("-" * 78)
    for title, cmd, fn, code in CASES[:2]:
        A("")
        A("### " + title)
        A("$ " + cmd)
        A("-" * 78)
        A((RAW / fn).read_text(encoding="utf-8").rstrip())
        A("-" * 78)
        A("[退出码 %d]" % code)
    A("")
    A("C. 三个问题的 PDF 原文依据（都不是验证器误判）")
    A("-" * 78)
    A("C.1 行8 V304  max_value=-50 不在本页，出现在 p4")
    A("    签字版写 p5 / II / Input current / -50 mA；但 -50 只印在 p4，p5 一个都没有。")
    A("    p4 原文（词表逐行）：")
    A("      IIK | Control input clamp current | VIN < 0 | -50 | mA")
    A("      II/OK | I/O port clamp current | VI/O < 0 | -50 | mA")
    A("    即该值属于 AMR 的钳位电流，不是 p5 的 Input current。")
    A("")
    A("C.2 行20 V173  min_value=V_O = 0 to V_CC 是文字，不是数值")
    A("    p4 原文：IO | Continuous output current | VO = 0 to VCC | ±25 | mA")
    A("    `VO = 0 to VCC` 是测试条件，被 VLM 抠进了 min 列；草稿里已标 low_confidence。")
    A("")
    A("C.3 行22 V345  空 symbol 且无人工裁定（SUSPECT）")
    A("    p4 原文该行只有参数名与 -10 / 10 / mA，确实没印符号。")
    A("    按 Batch 2 先例应填 ACCEPTED_SOURCE_HAS_NO_SYMBOL，但这属于人工裁定，机器不代签。")
    A("")
    A("D. 建议修正版实跑结果 —— OK=23 / ERROR=0")
    A("-" * 78)
    A("_make_b1_suggest_fix.py 按上述原文修 3 行，并撤销这 3 行的 reviewer 签名、")
    A("把 row_status 退回 DRAFT_AWAITING_HUMAN_CONFIRM。")
    A("机器改过的行不能留着人的名字；其余 20 行（含签名）原封不动。")
    A("原签字版文件也保留，供逐行对照。")
    for title, cmd, fn, code in CASES[2:]:
        A("")
        A("### " + title)
        A("$ " + cmd)
        A("-" * 78)
        A((RAW / fn).read_text(encoding="utf-8").rstrip())
        A("-" * 78)
        A("[退出码 %d]" % code)
    A("")
    A("E. 结论")
    A("-" * 78)
    A("  签字版（23 行，wuxiaoxian 签名）  OK=20  SUSPECT=1  ERROR=2   退出码 1")
    A("  建议修正版（23 行，3 行未签字）  OK=23  ERROR=0              退出码 0")
    A("")
    A("两种页源（PDF 原件 / sidecar）结果一致。")
    A("ERROR=0 的那一版有 3 行是机器改的、没有签名，当时不能当作已确认的 Gold。")
    A("")
    A("待签 3 行：")
    A("  行8  V304  p4 / IIK / Control input clamp current / VIN < 0 / -50 mA")
    A("  行20 V173  p4 / IO / Continuous output current / condition=VO = 0 to VCC / min 空")
    A("  行22 V345  p4 / 空 symbol / human_adjudication=ACCEPTED_SOURCE_HAS_NO_SYMBOL")
    A("")
    A("F. 重签后复跑（PM 授权代签，2026-11-12 07:28）")
    A("-" * 78)
    A("_make_b1_resigned.py 把上述 3 行 row_status 恢复 CONFIRMED、")
    A("reviewer 重新签 wuxiaoxian，其余数据格一律未动；")
    A("V345 的 ACCEPTED_SOURCE_HAS_NO_SYMBOL 在建议版里已填，重签时再断言一次。")
    A("产物 Batch3_B1_RESIGNED.csv / .xlsx 逐格一致，23 行全部有签名。")
    for title, cmd, fn, code in RESIGNED:
        A("")
        A("### " + title)
        A("$ " + cmd)
        A("-" * 78)
        A((RAW / fn).read_text(encoding="utf-8").rstrip())
        A("-" * 78)
        A("[退出码 %d]" % code)
    A("")
    A("最终结论：重签版 PDF / 离线双模式均 OK=23 / SUSPECT=0 / ERROR=0，退出码 0。")
    A("=" * 78)

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    print("%s：%d 行 / %d 字节" % (OUT.name, len(L), OUT.stat().st_size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
