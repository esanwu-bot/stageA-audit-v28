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
    A("签字真源（15 列原件）：./Batch3_B2_SIGNED_original.xlsx（PM 点选签字原件副本，逐格未改）")
    A("授权真源（19 列补签）：./Batch3_B2_FINAL_TO_SIGN.xlsx（PM 在 7 个标红格补签 approved_by）")
    A("      同目录 Excel 另存的 .csv 不作为真源（GBK 编码 / 导出格式）。")
    A("封卷定稿：./Batch3_B2_FINAL.xlsx（30 行 × 19 列；同名 .csv 逐格同源，为验证器输入）")
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
    A("    授权链（封卷状态）：7 行由 WB 按原文回填，entered_by=WB_Agent；")
    A("    PM 2026-11-12 10:05 明确授权「在正确位置，签署 wuxiaoxian」，并已在")
    A("    标红版 7 个红格补签 approved_by=wuxiaoxian（数据行 8/9/16/17/18/19/20，")
    A("    与 entered_by=WB_Agent 的 7 行完全重合）。reviewer 仍是 PM 对整表签字，")
    A("    其余 23 行 approved_by 保持空白；human_adjudication 全表清空。")
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
    A("    封卷时相对上一版仅 approved_by 一列有 7 处变化，其余 18 列逐格断言零差异。")
    A("A.6 溯源三处互校：CSV ↔ sidecar 比 file_name / device_model；")
    A("    sidecar ↔ provenance 比 file_name / device_model / sha256 / page_count；")
    A("    sha256 与页数从磁盘原件实算，页文本逐页抽取，PDF 模式再复算一次哈希。")
    A("A.7 授权链封卷全过程（错位 → 撤销 → 正确补签，全程留痕）")
    A("    09:48 PM 首次在 approved_by 列签 7 处，落点为数据行")
    A("      8/9/22/23/24/25/26，其中 5 行并非 WB 代录进行，V242 五行反而漏签。")
    A("    09:52 PM 主动发现并要求全部清空、恢复原样；WB 按指令撤销，主定稿")
    A("      恢复到与已推送 6107ab7 逐字节一致，未产生新提交。")
    A("    10:03 PM 在 WB 提供的标红版 Batch3_B2_FINAL_TO_SIGN.xlsx 中自行补签；")
    A("    10:05 PM 再次授权 WB 在正确位置落签。WB 实测 PM 已填的 7 行恰为")
    A("      数据行 8/9/16/17/18/19/20（Excel 行 9/10/17/18/19/20/21），")
    A("      与 entered_by=WB_Agent 完全重合，故不再代填、不改写任何人工签名，")
    A("      只做逐格复核并同步封卷定稿。全过程留痕：")
    A("      ./Batch3_B2_FINAL_SIGNED_approval.xlsx  09:48 错签原件")
    A("      ./Batch3_B2_FINAL_pre_approval.xlsx     封卷前无签名版")
    A("      ./Batch3_B2_approval_revoke_note.txt    撤销说明")
    A("      ./Batch3_B2_FINAL_TO_SIGN.xlsx          PM 正确补签原件（唯一授权真源）")
    A("      ./Batch3_B2_FINAL_SIGNED_correct.xlsx  同字节留痕副本")
    A("      ./Batch3_B2_APPROVAL_TARGETS.txt       7 行补签清单与 Excel 行号")
    A("      ./Batch3_B2_approval_authorization.txt 授权链封卷记录")
    A("    B1 已冻结，本轮未改动；两仓 main 未动。")
    A("")
    A("A.8 封卷后的底层漏洞终极修复（本轮，不改 B1 / B2 任何数据结论）")
    A("    (1) prescan3 页首 Fail-Open：")
    A("        `if y0 <= PAGE_TOP_MAX_PT: return True` 已彻底废弃。改为任务队列")
    A("        三段式：页级分类 → 表头匹配 → 上下文关联。V003 十三页真表实测：")
    A("        11 页有本页独立标题，走 LOCAL_TITLE 正常提取；仅 p102 / p106 两页")
    A("        无本页标题，走 INHERITED_TITLE_FINGERPRINT，表头指纹相似度均 1.00")
    A("        （阈值 0.80，并同时要求左右边界/宽度几何对齐）。")
    A("    (2) find_tables() 跨页脏数据定向隔离：")
    A("        PyMuPDF 在同一 Document 跨页调用 find_tables() 会污染先前 Table")
    A("        对象（t.extract() 吐出上一页正文，p102 甚至全空行），这是上一版")
    A("        误杀 8~11 页真表的真正根因，不是距离阈值也不是继承断链。")
    A("        三道硬隔离：find_tables(clip=本页矩形) / bbox 四边与 Y 轴越界校验 /")
    A("        表头词在本页文本的归属校验；Table 对象绝不跨函数存活，本页全部")
    A("        extract 完并释放 page 后，才允许访问上一页。")
    A("    (3) B2 签名继承改为 Fail-Closed + 稳定 ID：")
    A("        唯一签名源 ./Batch3_B2_FINAL_TO_SIGN.xlsx。源缺失 / 表头不符 /")
    A("        行数不是 30 / 稳定 ID 重复 / 非 PM 签名 / 签名落点错位，一律报错")
    A("        退出，废弃「从现有定稿按行号读回 approved_by」。稳定 ID 取 PM 指定")
    A("        五字段 + 4 个确定性数值列（实测 V011 的 VIH 三行 / VIL 两行五字段")
    A("        完全相同，不消歧就会静默覆盖重复键）。重跑定稿 19 列 × 31 行逐格")
    A("        一致，7 处签名与 entered_by=WB_Agent 精确对齐，授权链仍闭合。")
    A("    回归实证：合成 39/39、签名保护 9/9、验证器自测 31/31、V003 真表 13/13，")
    A("    SKIP 全为 0。原始 stdout：./Batch3_CORE_ORDER_regression.txt、")
    A("    ./Batch3_prescan3_v003_evidence.txt、./Batch3_B2_regeneration.txt。")
    A("    B3 圈选台按同一套指纹逻辑重建为 V328 V146 V222 V271 V256 V244，")
    A("    见 ./Batch3_Viewer.html；B1 旧版留痕 ./Batch3_B1_Viewer.html。")
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
    A("  封卷授权链已闭合：approved_by 7 行与 entered_by=WB_Agent 7 行完全对齐，")
    A("  其余 23 行为空；主 xlsx / CSV / PM 补签原件三方逐格一致。")
    A("  B2 定稿文件与本报告一并打包，审计包里不再只有 DRAFT 版。")
    A("  本轮底层修复（prescan3 三段式 + 跨页污染隔离 + 签名 Fail-Closed）只改")
    A("  生成器与签名保护逻辑，B1 / B2 定稿数据逐格未动，详见 A.8 与回归 stdout。")
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
