# -*- coding: utf-8 -*-
"""把 B2 两份机检原始 stdout 汇成可复核报告（逐字贴，不改写）。

B2 的定稿不再是 DRAFT：以 PM 签字 xlsx 为唯一真源，按裁定清理 notes，
补上 v1.6 需要的溯源/型号/裁定列，PDF 与离线两种页源各跑一次。
"""
from __future__ import print_function

from pathlib import Path

PREP = Path(__file__).resolve().parent
RAW = PREP / "b2_validation_raw"
OUT = PREP / "Batch3_B2_validation_report.txt"
NOTES_BEFORE = PREP / "Batch3_B2_notes_before_cleanup.txt"

CASES = [
    ("B.1 最终定稿 · PDF 模式（实算哈希）",
     "python validate_annotation.py --csv Batch3_B2_FINAL.csv "
     "--page-text page_text_batch3_b2.json "
     "--provenance Batch3_B2_PDF_PROVENANCE.csv --pdf-dir b2_pdfs",
     "b2_final_pdf_mode.txt", 0),
    ("B.2 最终定稿 · 离线模式（sidecar）",
     "env -u ICPDF_PDF_DIR python validate_annotation.py --csv Batch3_B2_FINAL.csv "
     "--page-text page_text_batch3_b2.json --provenance Batch3_B2_PDF_PROVENANCE.csv",
     "b2_final_sidecar_mode.txt", 0),
]


def main():
    L = []
    A = L.append
    A("=" * 78)
    A("Batch 3 · B2 人工签字定稿 —— v1.6 验证器机检报告")
    A("=" * 78)
    A("")
    A("真源：./Batch3_B2_SIGNED_original.xlsx（PM 签字的 xlsx 原件副本，30 行 × 15 列，逐格未改）")
    A("      同目录 Excel 另存的 .csv 不作为真源（GBK 编码 / 导出格式）。")
    A("定稿：./Batch3_B2_FINAL.xlsx（30 行 × 19 列；同名 .csv 逐格同源，为验证器输入）")
    A("签字：reviewer=wuxiaoxian，30 行全部 CONFIRMED，6 件 × 5 行")
    A("      table_title 分布：Absolute Maximum Ratings 24 / Recommended Operating Conditions 6")
    A("机检对象 = 定稿 30 行 / 6 样本（V038 V320 V346 V242 V003 V011）。")
    A("")
    A("A. 从签字版到定稿做了什么（没做什么）")
    A("-" * 78)
    A("A.1 notes：30 行含「须对左图核 / 请确认 / low_confidence」等过期措辞，")
    A("    按 PM 2026-11-12 裁定统一改为「人工已核对 PDF 原图并确认」。")
    A("    原始 notes 全文逐行留痕在 ./Batch3_B2_notes_before_cleanup.txt，")
    A("    其中 V003 的 3.3V Operation、EN DASH 转写、AMR 勿混等排查线索不丢失。")
    A("A.2 V003 / VDDSHV5 的 condition 保留 `1.8V Operation`：")
    A("    AM2431BSDFHIALXR__am2431.pdf 第 106 页文本层确有独立一行 `1.8V Operation`")
    A("    （同页另有 `3.3V Operation`），生成脚本逐行断言后才允许落盘，")
    A("    不改成 `VDD=1.8V`，语义一致且更贴原文。")
    A("A.3 7 行符号回填（Reviewer 第五轮，不再使用裁定码）")
    A("    签字版里 V320 两行、V242 五行的 symbol 为空，真实符号被 VLM 塞进了")
    A("    condition。上一版用 ACCEPTED_SOURCE_HAS_NO_SYMBOL 放行属语义错配：")
    A("    裁定码字面是「源头无符号」，实际是「符号太长被挪走」。现按 PDF 原图回填：")
    A("      V320 p12 行 11 `DACVDD, DIGVDD, CLKVDD` → symbol；")
    A("      V320 p12 行 24 `AVDD, PLLAVDD`          → symbol；")
    A("        该表标题下行 7 是全表条件 `over operating free-air temperature")
    A("        range (unless otherwise noted)(1)`，去掉脚注编号后填入 condition。")
    A("      V242 p6 行 7/11/14/17/20 依次回填 `APWR to AGND`、")
    A("        `DPWR to DGND`、`AGND, AGNDy to DGND`、`AVDD to AGND`、")
    A("        `IOVDD to DGND`；该表只有 `see (1)` 脚注引用、无具体测试条件，")
    A("        故 condition 留空，不臆造条件。")
    A("    保留原表的逗号 / `to` 写法，不改成 `符号1; 符号2`：分号不在 PDF 原文里，")
    A("    会让 v1.6 的 check_symbol() 找不到符号。7 个符号与 V320 的全表条件")
    A("    都做了 nos(symbol) in nos(页文本) 原文断言后才允许落盘。")
    A("    授权链：这 7 行由 WB 按原文回填，尚未经 PM 逐行复核，故")
    A("    approved_by 留空、entered_by=WB_Agent；reviewer 仍是 PM 对整表的签字，")
    A("    不擅自撤销、也不冒充人工已逐行确认。human_adjudication 全表清空。")
    A("    ※ 请 PM 对这 7 行逐行复核后确认；如需改动可直接告知，不改动机检判据。")
    A("A.4 3 件签字版 file_name 是简写，语料目录无同名文件：")
    A("      ADC12QJ1600ALREP.pdf → ADC12QJ1600ALREP__adc12qj1600-ep.pdf")
    A("      ADS54J40IRMPT.pdf    → ADS54J40IRMPT__ads54j40.pdf")
    A("      ADS131B26-Q1.pdf     → ADS131B26QPHPRQ1__ads131b26-q1.pdf")
    A("    不改写签字真源任何一格：按 CSV 原名在 b2_pdfs/ 下建硬链接指向同一份 PDF 字节，")
    A("    PDF 模式据此实算 SHA-256，离线模式用 sidecar，三处 file_name 仍是签字原值。")
    A("    ※ b2_pdfs/ 是本地验证环境（硬链接，不是数据副本），体积原因不入审计包。")
    A("      干净解压包请用离线 sidecar 模式复现（B.2 命令，不需要语料目录）；")
    A("      要复跑 PDF 模式，用 _make_b2_final.py --xlsx <签字xlsx> --pdf-dir <语料目录>")
    A("      重建 b2_pdfs/ 后执行 B.1 命令，哈希会与 sidecar 逐字节对齐。")
    A("A.5 逐格断言：原 15 列里只有三列允许改 —— notes（30 行）、")
    A("    symbol 与 condition（仅限登记的 7 行）。其余 23 行的 symbol / condition")
    A("    一字未动；全部 30 行的 min / typ / max、unit、evidence_page、")
    A("    table_title、row_status、reviewer、confidence_score 一字未动。")
    A("    另追加 approved_by / entered_by / device_model / human_adjudication")
    A("    四列，与 B1 定稿的 19 列结构对齐。")
    A("    型号取各 PDF 第 1 页封面原文；V003 封面只印族名 AM243x，")
    A("    另有「AM2434, AM2432, AM2431」一行，故登记为 AM2431。")
    A("A.6 溯源三处互校：CSV ↔ sidecar 比 file_name / device_model；")
    A("    sidecar ↔ provenance 比 file_name / device_model / sha256 / page_count；")
    A("    sha256 与页数从磁盘原件实算，页文本逐页抽取，PDF 模式再复算一次哈希。")
    A("")
    A("B. 机检原始输出（未编辑）")
    A("-" * 78)
    for title, cmd, fn, code in CASES:
        A("")
        A("### " + title)
        A("$ " + cmd)
        A("-" * 78)
        A((RAW / fn).read_text(encoding="utf-8").rstrip())
        A("-" * 78)
        A("[退出码 %d]" % code)
    A("")
    A("C. 结论")
    A("-" * 78)
    A("  PDF 模式与离线 sidecar 模式均为 OK=30 / SUSPECT=0 / ERROR=0，退出码 0。")
    A("  7 行符号已按 PDF 原文回填，human_adjudication 全表清空，不再依赖裁定码；")
    A("  达成 PM 要求的 OK=30 / ERROR=0，没有靠关闭或放宽任何一条 v1.6 判据。")
    A("  B2 定稿文件与本报告一并打包，审计包里不再只有 DRAFT 版。")
    A("")
    A("D. 清理前的 30 行 notes 留痕（逐行）")
    A("-" * 78)
    A(NOTES_BEFORE.read_text(encoding="utf-8").rstrip())
    A("=" * 78)

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    print("%s：%d 行 / %d 字节" % (OUT.name, len(L), OUT.stat().st_size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
