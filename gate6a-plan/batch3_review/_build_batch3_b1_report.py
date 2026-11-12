# -*- coding: utf-8 -*-
"""把 B1 十份机检原始输出汇成一份可复核报告。

原始输出固定在 b1_validation_raw/，报告里逐字贴出命令、输出、退出码。
不重跑、不改写、不挑好看的贴 —— 签字版 ERROR=2 的那两份也在里面。
B/D/F 段是三个历史版本各两份；G 段是定稿复跑两份；
H 段是第三轮清理 20 行过期备注后的两份复跑。
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

# Reviewer 第二轮修正（授权链 / 表头归属 / 过期备注）后的最终复跑
FINAL = [
    ("G.2 最终定稿 · PDF 模式（实算哈希）",
     "python validate_annotation.py --csv Batch3_B1_RESIGNED.csv "
     "--page-text page_text_batch3_b1.json "
     "--provenance Batch3_B1_PDF_PROVENANCE.csv --pdf-dir <PDF>",
     "b1_final_pdf_mode.txt", 0),
    ("G.3 最终定稿 · 离线模式（sidecar）",
     "env -u ICPDF_PDF_DIR python validate_annotation.py --csv Batch3_B1_RESIGNED.csv "
     "--page-text page_text_batch3_b1.json --provenance Batch3_B1_PDF_PROVENANCE.csv",
     "b1_final_sidecar_mode.txt", 0),
]

# Reviewer 第三轮：PM 裁定把 20 行过期草稿 notes 换成定稿语后的复跑
NOTES_CLEAN = [
    ("H.2 备注清理后 · PDF 模式（实算哈希）",
     "python validate_annotation.py --csv Batch3_B1_RESIGNED.csv "
     "--page-text page_text_batch3_b1.json "
     "--provenance Batch3_B1_PDF_PROVENANCE.csv --pdf-dir <PDF>",
     "b1_notes_clean_pdf_mode.txt", 0),
    ("H.3 备注清理后 · 离线模式（sidecar）",
     "env -u ICPDF_PDF_DIR python validate_annotation.py --csv Batch3_B1_RESIGNED.csv "
     "--page-text page_text_batch3_b1.json --provenance Batch3_B1_PDF_PROVENANCE.csv",
     "b1_notes_clean_sidecar_mode.txt", 0),
]


def main():
    L = []
    A = L.append
    A("=" * 78)
    A("Batch 3 · B1 人工签字定稿 —— v1.6 验证器机检报告")
    A("=" * 78)
    A("")
    A("真源：./Batch3_B1_RESIGNED.xlsx（本包内最终定稿，23 行 × 19 列；同名 .csv 逐格同源）")
    A("      人工签字原件：./Batch3_B1_SIGNED.xlsx（PM 发来的 xlsx，23 行 × 15 列，仅作留痕）")
    A("      Excel 另存出的同名 .csv 是 GBK 编码 + Tab 分隔，属导出格式，不作为标注真源。")
    A("签字：reviewer=wuxiaoxian，23 行全部 CONFIRMED")
    A("      物理行 8 / 20 / 22 另记 approved_by=wuxiaoxian、entered_by=WB_Agent（见 G 段）")
    A("草稿 30 行 → 人工点选后保留 23 行（删 7 行）。机检对象 = 定稿 23 行 / 6 样本。")
    A("")
    A("※ 仓库口径更正与致歉（2026-11-12）")
    A("-" * 78)
    A("  此前报告把两个不同仓库的 main 混写成一个，特此更正，并向 Reviewer 致歉：")
    A("    CodeUp   icpdf-extractor    远端 main = 853a80d   （代码仓 / Gate 6A 工作区）")
    A("    GitHub   stageA-audit-v28   远端 main = e3c9b64   （审计仓 / 本包所在仓）")
    A("  本包全部送审内容都在 GitHub 审计仓的 feat/gate6a-batch3 分支；")
    A("  两个远端 main 均未因 B1 / B2 修正发生任何改动。")
    A("  另：CodeUp 代码仓的「本地」main 为 a11131a（24 行 v1.6），按约定未 push，")
    A("  与上面的远端 main 853a80d 不是同一个指针，请勿混用。")
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
    A("重签版结论：PDF / 离线双模式均 OK=23 / SUSPECT=0 / ERROR=0，退出码 0。")
    A("（该版尚未包含 Reviewer 第二轮的授权链与表头修正，最终结论见 G 段。）")
    A("")
    A("G. Reviewer 第二轮修正与最终复跑（2026-11-12 08:08）")
    A("=" * 78)
    A("G.0  23 行 table_title 逐行复核（对六件 PDF 原件逐页取证）")
    A("-" * 78)
    A("  只发现 1 处错误：物理行 8 / V304 / p4 / IIK / -50 mA，")
    A("  旧值 Electrical Characteristics 改为 Absolute Maximum Ratings。")
    A("  依据：V304 p4 第 6.1 节 Absolute Maximum Ratings 表内第 27~31 行为")
    A("        IIK / Control input clamp current / VIN < 0 / –50 / mA；")
    A("        该页第 6.3 节 Recommended Operating Conditions 从第 82 行才开始。")
    A("  其余 22 行归属正确。两处「看似可疑」的实证：")
    A("    * V319 物理行 5 / p5 / IO / 20 mA 标 AMR —— p5 上半页是")
    A("      「absolute maximum ratings over operating free-air temperature range」")
    A("      （全小写点线式表），Output current, IO / 20 mA 正在该表内；")
    A("      p5 下半页第 95 行才是 recommended operating conditions。AMR 正确，不改。")
    A("    * V336 物理行 14~17 / p5 / 4 行标 Electrical Characteristics ——")
    A("      p5 原文标题就是 Electrical Characteristics--DC Parameters，正确，不改。")
    A("  V173 / V345 的 p4 都是 5.1 Absolute Maximum Ratings（5.3 ROC 在同页更靠后）；")
    A("  V199 p1 是 Absolute Maximum Ratings；V319 p5 上半 AMR、下半 ROC，按行分别归属。")
    A("  口径说明：PM 裁定「AMR 与 ROC 绝不能混、table_title 必须严格保留」针对的是")
    A("  同一件里绝对最大额定值与推荐工作条件不得串表，不是把所有真实 ELC 表强行改名。")
    A("  若 Reviewer 要求全表只允许这两个值，请明示，再按 PDF 原文逐行改。")
    A("")
    A("G.1  人工授权链字段与备注定稿")
    A("-" * 78)
    A("  新增 approved_by / entered_by 两列（CSV 与 XLSX 同源，共 19 列）。")
    A("  reviewer=wuxiaoxian 全表保留；物理行 8 / 20 / 22 三行另有")
    A("  approved_by=wuxiaoxian、entered_by=WB_Agent，把「批准人」与「代录入方」分开。")
    A("  其余 20 行是人工直接在 Excel 里签字录入，无代录入环节，两列留空。")
    A("  三行 notes 里「待人确认并重新签字」等过期表述已全部删除，统一为：")
    A("    「人工已核对 PDF p4 原图并确认此修正。」")
    A("  其余 20 行 notes 当时保持人工签字时的原始记录；第三轮已按 PM 裁定统一清理，见 H 段。")
    A("  最终定稿由 _make_b1_resigned.py 一次产出，逐格断言 CSV == XLSX；")
    A("  前序版本 SIGNED / CONFIRMED / SUGGESTED_FIX 全部保留留痕。")
    for title, cmd, fn, code in FINAL:
        A("")
        A("### " + title)
        A("$ " + cmd)
        A("-" * 78)
        A((RAW / fn).read_text(encoding="utf-8").rstrip())
        A("-" * 78)
        A("[退出码 %d]" % code)
    A("")
    A("第二轮结论：最终定稿 PDF / 离线双模式均 OK=23 / SUSPECT=0 / ERROR=0，退出码 0。")
    A("新增两列与 table_title / notes 修正均未影响任何一条机检判据。")
    A("")
    A("H. 第三轮：清理 20 行过期备注与复跑")
    A("-" * 78)
    A("  PM 2026-11-12 裁定：「那 20 行 notes 里写的『须对左图核』『请确认』等草稿词汇，")
    A("  一律替换为『人工已核对 PDF 原图并确认』；确保不再出现 low_confidence 与")
    A("  CONFIRMED 并存的矛盾。」")
    A("  执行脚本 _clean_b1_notes.py，以 ./Batch3_B1_RESIGNED.xlsx 为真源：")
    A("    * 20 行含过期措辞的 notes → 「人工已核对 PDF 原图并确认」；")
    A("    * 3 行 PM 授权代录入的定稿语「人工已核对 PDF p4 原图并确认此修正。」保持不变；")
    A("    * 清理前 xlsx 原样留痕为 ./Batch3_B1_RESIGNED_pre_notes_cleanup.xlsx；")
    A("    * 逐格断言：除 notes 外 18 列全部未变，min/max/typ、unit、condition、")
    A("      row_status、reviewer、approved_by / entered_by、confidence_score 一字未动；")
    A("    * 清理后 notes 里 low_confidence 残留 0；confidence_score 分布仍为")
    A("      0.95×21 / 0.85×1 / 0.8×1，没有「低置信度却已 CONFIRMED」的矛盾；")
    A("    * 逐格断言清理后 CSV == XLSX == 内存，文件名仍是 Batch3_B1_RESIGNED.*。")
    for title, cmd, fn, code in NOTES_CLEAN:
        A("")
        A("### " + title)
        A("$ " + cmd)
        A("-" * 78)
        A((RAW / fn).read_text(encoding="utf-8").rstrip())
        A("-" * 78)
        A("[退出码 %d]" % code)
    A("")
    A("第三轮结论：备注清理后 PDF / 离线双模式仍 OK=23 / SUSPECT=0 / ERROR=0，退出码 0。")
    A("备注改写不影响任何一条机检判据；机检全绿不是靠放宽判据换来的。")
    A("=" * 78)

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    print("%s：%d 行 / %d 字节" % (OUT.name, len(L), OUT.stat().st_size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
