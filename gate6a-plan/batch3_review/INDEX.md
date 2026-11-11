# Batch 3 复审包 · B1 签字定稿 + B2 草稿

分支 `feat/gate6a-batch3`，**不动 main、不动 `feat/gate6a-annotation`**。
B1 已有人工签字，B2 仍是草稿，机器没有替人确认任何一行。

## 0. 一句话结论

**最终全绿**：PM 授权代签后的 `Batch3_B1_RESIGNED.csv`，v1.6 双模式
`OK=23 / SUSPECT=0 / ERROR=0`，退出码 0。23 行全部 `CONFIRMED` + `reviewer=wuxiaoxian`。

过程留痕不做删改：最初签字版 `OK=20 / SUSPECT=1 / ERROR=2`（退出码 1），
按 PDF 原文给建议修正版后 `OK=23`，再由 PM 授权把那 3 行重新签字。
三个版本、六份原始 stdout 全部在本包里，详见 `Batch3_B1_validation_report.txt`。

## 1. 真源与行数

- 唯一真源：`Batch3_B1_SIGNED.xlsx`（PM 指定只读 xlsx，23 行 × 15 列，
  `reviewer=wuxiaoxian` 全部签名、`row_status=CONFIRMED`）。
- Excel 另存出的同名 `.csv` 是 **GBK 编码 + Tab 分隔**，属导出格式，
  **不作为标注真源**，本包未收录。
- 草稿 `Batch3_DRAFT.csv` 30 行 → 人工点选保留 23 行（删 7 行）。
  机检对象是定稿 23 行 / 6 样本，不是 30 行。
- `Batch3_B1_CONFIRMED.csv` 是以 xlsx 为源规范化的 UTF-8 BOM 版本，
  原 15 列逐格照抄，只追加 `device_model` / `human_adjudication` 两列
  （v1.6 验证器要求 `device_model` 做溯源互校，缺字段即 ERROR）。

## 2. 三处待签（都不是验证器误判）

| 报告行 | 样本 | 问题 | PDF 原文依据 | 建议 |
| --- | --- | --- | --- | --- |
| 行8 | V304 | `max=-50` 不在 p5，只在 p4 | p4 `IIK / Control input clamp current / VIN < 0 / -50 / mA` | 页码改 4、symbol 改 `IIK`、参数名与条件按原文 |
| 行20 | V173 | `min=V_O = 0 to V_CC` 是文字不是数值 | p4 `IO / Continuous output current / VO = 0 to VCC / ±25 / mA` | 条件移入 `condition`，min 留空（草稿里原本就标了 `low_confidence`） |
| 行22 | V345 | 空 symbol 且无人工裁定（SUSPECT） | p4 该行只印参数名与 `-10 / 10 / mA`，确实没符号 | 填 `ACCEPTED_SOURCE_HAS_NO_SYMBOL`，需人签 |

`Batch3_B1_SUGGESTED_FIX.csv` 修了这 3 行，**同时撤销它们的 reviewer 签名**、
`row_status` 退回 `DRAFT_AWAITING_HUMAN_CONFIRM`。机器改过的行不能留着人的名字。
其余 20 行（含签名）原封不动，原签字版也保留供逐行对照。

PM 2026-11-12 07:28 肉眼复核后授权代签（「改的都 ok，不过没有编辑权限，
你替我按方案完成再推送 github」）：`_make_b1_resigned.py` 只把这 3 行
`row_status` 恢复 `CONFIRMED`、`reviewer` 重新签 `wuxiaoxian`，
**其余数据格一格未动**；V345 的裁定码在建议版里已填，重签时再断言一次。
产物 `Batch3_B1_RESIGNED.csv` / `.xlsx` 逐格一致。

## 3. 机检结果（v1.6，四份原始输出在 `b1_validation_raw/`）

| 版本 | PDF 模式（实算哈希） | 离线模式（sidecar） |
| --- | --- | --- |
| 签字版 23 行 | `OK=20 SUSPECT=1 ERROR=2` 退出码 1 | 同左，退出码 1 |
| 建议修正版 23 行（3 行未签） | `OK=23 ERROR=0` 退出码 0 | 同左，退出码 0 |
| **重签版 23 行（全签）** | **`OK=23 ERROR=0` 退出码 0** | **同左，退出码 0** |

验证器输入由 `_build_batch3_verify_inputs.py` 生成：型号取 PDF 第 1 页标题行，
SHA-256 / 页数从磁盘原件实算，页文本逐页抽取，PDF 模式再用原件复算一遍。
**没有关掉任何一条判据**（provenance 缺失、空字段跳过、PDF 降级、哈希不符仍读文本、
损坏 PDF 退化，这七条 fail-open 仍然全部封着）。

局限：三处溯源写的是同一份实测数据，不是三个独立来源；真正独立的第三方证据
是磁盘 PDF 原件。这一条请复核者知悉。

## 4. B2 草稿（待点选）

`Batch3_B2_Viewer.html` + `Batch3_B2_DRAFT.csv`：6 件 / 30 行 / 14 张裁图，
样本 `V038 V320 V346 V242 V003 V011`，每件只留 5 行核心参数。

**V003 的 5 行全是 `low_confidence`**，请优先对图。其余 5 件各 5 行均 ≥0.85。
置信度 0.95 只证明"抄的字在页面上都找得到"，**不证明数值归到了正确的列** ——
B1 签字版漏掉的两处恰好都是这类问题（页码串页、条件混进数值列）。

## 5. 目录

| 文件 | 作用 |
| --- | --- |
| `Batch3_B1_SIGNED.xlsx` | 人工签字原件（唯一真源） |
| `Batch3_B1_CONFIRMED.csv` | 规范化签字版（17 列，供验证器） |
| `Batch3_B1_SUGGESTED_FIX.csv` | 建议修正版（3 行一度未签字，留痕） |
| `Batch3_B1_RESIGNED.csv` / `.xlsx` | **最终定稿**，23 行全签，机检全绿 |
| `Batch3_B1_validation_report.txt` | 六份机检原样输出 + PDF 原文依据 + 重签记录 |
| `b1_validation_raw/*.txt` | 六份原始 stdout（未编辑） |
| `Batch3_B1_PDF_PROVENANCE.csv` / `page_text_batch3_b1.json` | 6 件 PDF 溯源与页文本 |
| `Batch3_Viewer.html` / `Batch3_DRAFT.csv` | B1 圈选台与原始 30 行草稿 |
| `Batch3_B2_Viewer.html` / `Batch3_B2_DRAFT.csv` | B2 圈选台与 30 行草稿 |
| `annotation_reports/**/b3_*.png` | B1+B2 共 29 张 300DPI 表格裁图 |
| `validate_annotation.py` | v1.6 机检脚本 |
| `_build_batch3_*.py` / `_make_b1_suggest_fix.py` / `_make_b1_resigned.py` / `_patch_b3_export_name.py` | 生成器与适配/修正/重签/前端补丁脚本 |
| `_b2_app.js` / `_build_batch2_*.py` / `_draft_extract.py` / `_vl_*.py` | 复现依赖 |
| `Batch3_BATCH_PLAN.csv` | 26 件待办的分批清单 |
| `SHA256SUMS.txt` | 逐文件校验 |
| `Batch3_review.zip` | 整包（含 SHA256SUMS.txt） |

## 6. 复核命令

```bash
sha256sum -c SHA256SUMS.txt
python validate_annotation.py --csv Batch3_B1_CONFIRMED.csv \
  --page-text page_text_batch3_b1.json \
  --provenance Batch3_B1_PDF_PROVENANCE.csv --pdf-dir <PDF>      # 退出码 1，ERROR=2
python validate_annotation.py --csv Batch3_B1_SUGGESTED_FIX.csv \
  --page-text page_text_batch3_b1.json \
  --provenance Batch3_B1_PDF_PROVENANCE.csv --pdf-dir <PDF>      # 退出码 0，OK=23
python validate_annotation.py --csv Batch3_B1_RESIGNED.csv \
  --page-text page_text_batch3_b1.json \
  --provenance Batch3_B1_PDF_PROVENANCE.csv --pdf-dir <PDF>      # 最终：OK=23，退出码 0
```

## 7. 导出文件名 Bug 已修

`_b2_app.js` 原先把 `a.download` 写死为 `Batch2_ANNOTATED.csv`，所以 Batch 3 圈选台
导出的文件一直顶着 Batch 2 的名字。现在改为 `EXPORT_NAME + ".csv"`，
由生成器按批次注入 `window.B3_EXPORT_NAME`；Batch 2 老生成器不注入时
自动退回默认名，行为一字不变。

| 圈选台 | 点「下载 CSV」得到 |
| --- | --- |
| `Batch3_Viewer.html`（B1） | `Batch3_ANNOTATED.csv` |
| `Batch3_B2_Viewer.html`（B2） | `Batch3_B2_ANNOTATED.csv` |
| Batch 2 圈选台 | `Batch2_ANNOTATED.csv`（兼容） |

两份 HTML 用 `_patch_b3_export_name.py` 按「同一份 CSV + 修好的 JS」重建了
`<script>` 段，没有重跑 VLM、没有改动任何标注结论；回归断言覆盖
草稿行数、图片引用数、硬编码串消失、新名字存在。

打开 `Batch3_B2_Viewer.html` → 对图点选 → 「下载 CSV」→ 交回，继续 B3。
不要用 Excel 另存覆盖 CSV（会把 UTF-8 BOM 变成 GBK + Tab）；要留档请另存 xlsx。
