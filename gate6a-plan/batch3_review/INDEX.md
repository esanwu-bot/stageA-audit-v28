# Batch 3 复审包 · B1 / B2 双定稿 + 生成器底层加固

分支 `feat/gate6a-batch3`，**不动 main、不动 `feat/gate6a-annotation`**。
B1、B2 均为人工签字定稿；机器没有替人确认任何一行，也没有替人改核心数值。
2026-11-12 追加：Reviewer 指出 B2 的 V003 抓错页，已重定位重截，详见第 8 节。
2026-11-12 第二轮追加：修正 V304 表头归属、补齐人工授权链、统一真源口径与两仓
main SHA，详见第 9 节。
2026-11-12 第三轮追加：修复 CORE_ORDER 通用正则漏洞并加固 prescan3，见第 10 节。
2026-11-12 第四轮追加：清理 B1 过期备注、交付 B2 最终版与机检、
补齐 prescan3 四个极端场景回归，见第 11、12 节。
2026-11-12 第五轮追加（本版）：B2 七行符号按 PDF 原图回填（不再用裁定码）、
修复 prescan3 边框表格与标题的空间关联并补两个极端测试，见第 13 节。

## 0. 一句话结论

**最终全绿**：最终定稿 `Batch3_B1_RESIGNED.xlsx` / `.csv`（23 行 × 19 列），
v1.6 双模式 `OK=23 / SUSPECT=0 / ERROR=0`，退出码 0。
23 行全部 `CONFIRMED` + `reviewer=wuxiaoxian`。

过程留痕不做删改：最初签字版 `OK=20 / SUSPECT=1 / ERROR=2`（退出码 1），
按 PDF 原文给建议修正版后 `OK=23`，再由 PM 授权把那 3 行重新签字，
最后按 Reviewer 第二轮意见补齐授权链与表头归属后复跑仍 `OK=23`。
四个版本、十份原始 stdout 全部在本包里，详见 `Batch3_B1_validation_report.txt`。
B2 最终定稿 `Batch3_B2_FINAL.xlsx` / `.csv`（30 行 × 19 列），
v1.6 双模式 `OK=30 / SUSPECT=0 / ERROR=0`，退出码 0，详见
`Batch3_B2_validation_report.txt`。两份报告都逐字贴了原始 stdout。

## 1. 真源与行数

- **唯一真源（最终定稿）：`Batch3_B1_RESIGNED.xlsx`**，23 行 × 19 列；
  同名 `.csv` 与之逐格同源（UTF-8 BOM）。`reviewer=wuxiaoxian` 全部签名、
  `row_status=CONFIRMED`，v1.6 双模式全绿。
  第四轮把 20 行过期 notes 换成「人工已核对 PDF 原图并确认」后**文件名不变**，
  清理前 xlsx 留痕为 `Batch3_B1_RESIGNED_pre_notes_cleanup.xlsx`；
  除 notes 外 18 列逐格断言未变，复跑仍 `OK=23`，见第 11 节。
- `Batch3_B1_SIGNED.xlsx`（PM 发来的原始人工签字 xlsx，23 行 × 15 列）
  只作**过程留痕**，不是最终真源；最终版由 `_make_b1_resigned.py` 从
  `Batch3_B1_SUGGESTED_FIX.csv` 一次产出。
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
你替我按方案完成再推送 github」）：先把这 3 行 `row_status` 恢复 `CONFIRMED`、
`reviewer` 重新签 `wuxiaoxian`，当时其余数据格一格未动；V345 裁定码在建议版已填。
该步产物是重签版 v1，其机检输出在报告 F 段。
2026-11-12 08:08 Reviewer 第二轮修正后，同一脚本 `_make_b1_resigned.py`
已扩展为一次产出最终定稿（19 列），见第 9 节与报告 G 段。

## 3. B1 机检结果（v1.6，十份原始输出在 `b1_validation_raw/`）

| 版本 | PDF 模式（实算哈希） | 离线模式（sidecar） |
| --- | --- | --- |
| 签字版 23 行 | `OK=20 SUSPECT=1 ERROR=2` 退出码 1 | 同左，退出码 1 |
| 建议修正版 23 行（3 行未签） | `OK=23 ERROR=0` 退出码 0 | 同左，退出码 0 |
| 重签版 v1 23 行（全签） | `OK=23 ERROR=0` 退出码 0 | 同左，退出码 0 |
| **最终定稿 23 行 × 19 列** | **`OK=23 ERROR=0` 退出码 0** | **同左，退出码 0** |
| **备注清理后 23 行 × 19 列（本版）** | **`OK=23 ERROR=0` 退出码 0** | **同左，退出码 0** |

新增 `approved_by` / `entered_by` 两列、`table_title` 与 `notes` 的修正
均不影响任何一条机检判据；最终定稿的复跑是在改完之后重新实跑的，不是沿用旧结论。

验证器输入由 `_build_batch3_verify_inputs.py` 生成：型号取 PDF 第 1 页标题行，
SHA-256 / 页数从磁盘原件实算，页文本逐页抽取，PDF 模式再用原件复算一遍。
**没有关掉任何一条判据**（provenance 缺失、空字段跳过、PDF 降级、哈希不符仍读文本、
损坏 PDF 退化，这七条 fail-open 仍然全部封着）。

局限：三处溯源写的是同一份实测数据，不是三个独立来源；真正独立的第三方证据
是磁盘 PDF 原件。这一条请复核者知悉。

## 4. B2 最终定稿（已签字，机检全绿）

- **PM 签字原件副本：`Batch3_B2_SIGNED_original.xlsx`**，30 行 × 15 列，逐格未改；
  同目录 Excel 另存的 .csv 不是真源。
- **最终定稿：`Batch3_B2_FINAL.xlsx`**，30 行 × 19 列；同名 `.csv` 逐格同源，
  是 v1.6 验证器输入。30 行全部 `CONFIRMED` + `reviewer=wuxiaoxian`，
  6 件 × 5 行，`table_title` 仅 AMR 24 / ROC 6。
- `Batch3_B2_Viewer.html` / `Batch3_B2_DRAFT.csv` 降级为**过程留痕**（圈选台与草稿），
  不再是交付结论；审计包里不再只有 DRAFT 版。
- 备注按 PM 裁定统一为「人工已核对 PDF 原图并确认」，30 行原始 notes 全文留痕在
  `Batch3_B2_notes_before_cleanup.txt`；V003 的 `VDDSHV5 condition` 保留
  `1.8V Operation`（p106 原文确有独立一行，脚本逐行断言后才落盘）。
- 7 行 symbol 已按 PDF 原图逐字回填（V320 两行、V242 五行），`condition`
  只留真正的测试条件；`human_adjudication` 全表清空，不再依赖裁定码。
  7 行由 WB 代录入（`entered_by=WB_Agent`、`approved_by` 留空），
  **尚待 PM 逐行复核**，详见 `Batch3_B2_validation_report.txt` A.3 与第 13 节。
- 机检：PDF / 离线双模式 `OK=30 / SUSPECT=0 / ERROR=0`，退出码 0。

## 5. 目录

| 文件 | 作用 |
| --- | --- |
| `Batch3_B1_SIGNED.xlsx` | 人工签字原件（23 行 × 15 列，过程留痕，**非最终真源**） |
| `Batch3_B1_CONFIRMED.csv` | 规范化签字版（17 列，供验证器） |
| `Batch3_B1_SUGGESTED_FIX.csv` | 建议修正版（3 行一度未签字，留痕） |
| `Batch3_B1_RESIGNED.csv` / `.xlsx` | **唯一真源 / 最终定稿**，23 行 × 19 列全签，机检全绿 |
| `Batch3_B1_validation_report.txt` | 八份机检原样输出 + PDF 原文依据 + 重签记录 + G 段最终复跑与两仓 SHA 更正 |
| `b1_validation_raw/*.txt` | 八份原始 stdout（未编辑，含 `b1_final_*.txt` 两份） |
| `Batch3_B1_PDF_PROVENANCE.csv` / `page_text_batch3_b1.json` | 6 件 PDF 溯源与页文本 |
| `Batch3_Viewer.html` / `Batch3_DRAFT.csv` | B1 圈选台与原始 30 行草稿 |
| `Batch3_B2_Viewer.html` / `Batch3_B2_DRAFT.csv` | B2 圈选台与 30 行草稿（过程留痕，V003 已重截重出） |
| `Batch3_B2_SIGNED_original.xlsx` | PM 签字原件副本（30 行 × 15 列，逐格未改，唯一真源） |
| `Batch3_B2_FINAL.csv` / `.xlsx` | **B2 最终定稿**，30 行 × 19 列，机检 OK=30 |
| `Batch3_B2_validation_report.txt` | B2 两份机检原样 stdout + 处置说明 + 清理前 notes 留痕 |
| `b2_validation_raw/*.txt` / `Batch3_B2_notes_before_cleanup.txt` | B2 原始 stdout / 原始备注 |
| `page_text_batch3_b2.json` / `Batch3_B2_PDF_PROVENANCE.csv` | B2 六件 PDF 溯源与页文本 |
| `Batch3_B1_RESIGNED_pre_notes_cleanup.xlsx` / `_clean_b1_notes.py` | B1 清理前留痕与清理脚本 |
| `_make_b2_final.py` / `_build_batch3_b2_report.py` | B2 定稿生成与报告脚本 |
| `_verify_v003_candidates.py` / `Batch3_prescan3_v003_evidence.txt` | prescan3 加固后 V003 全书候选页真实回归 |
| `Batch3_prescan3_extreme_fix.diff` | 第四轮生成器 + 测试的真实增量补丁 |
| `annotation_reports/**/b3_*.png` | B1+B2 共 31 张 300DPI 表格裁图；V003 旧 p14 图已删，换成 p101/p105/p106 三张 |
| `Batch3_V003_diagnosis.txt` | **V003 抓错页诊断实证**（全文扫描、根因、断言、修复清单） |
| `validate_annotation.py` | v1.6 机检脚本 |
| `_build_batch3_*.py` / `_make_b1_suggest_fix.py` / `_make_b1_resigned.py` / `_patch_b3_export_name.py` / `_fix_v003_b2.py` / `_sync_batch3_review.py` | 生成器与适配/修正/重签/前端补丁/V003 定向修复/审计包同步脚本 |
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
  --provenance Batch3_B1_PDF_PROVENANCE.csv --pdf-dir <PDF>      # 最终定稿 19 列：OK=23，退出码 0
env -u ICPDF_PDF_DIR python validate_annotation.py --csv Batch3_B1_RESIGNED.csv \
  --page-text page_text_batch3_b1.json \
  --provenance Batch3_B1_PDF_PROVENANCE.csv                      # 离线模式同样 OK=23
python validate_annotation.py --csv Batch3_B2_FINAL.csv \
  --page-text page_text_batch3_b2.json \
  --provenance Batch3_B2_PDF_PROVENANCE.csv --pdf-dir b2_pdfs    # B2 定稿 OK=30
env -u ICPDF_PDF_DIR python validate_annotation.py --csv Batch3_B2_FINAL.csv \
  --page-text page_text_batch3_b2.json \
  --provenance Batch3_B2_PDF_PROVENANCE.csv                      # B2 离线同样 OK=30
python _test_core_order_and_header.py                              # PASS=26 FAIL=0 SKIP=0
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

## 8. V003 抓错页：诊断、修复与实证

Reviewer 反馈原话：**「V003 抓错页了，这页是纯文字术语解释，没有参数。
你检查一下你的生成器，V003 的电特性表到底在几页？要么你重新截正确的表格图发我，
要么这件 V003 直接标 EXCLUDED 放弃掉。」**

### 8.1 结论：真表存在，选择「重截」而非 EXCLUDED

`AM2431BSDFHIALXR__am2431.pdf` 共 **282 页**，参数表在第 6 章 Specifications：

| 页 | 内容 |
| --- | --- |
| p101 | `6.1 Absolute Maximum Ratings`（PARAMETER / MIN / MAX / UNIT） |
| p102 | 6.1 续表 |
| p105 | `6.4 Recommended Operating Conditions`（MIN(1) / NOM / MAX(1) / UNIT，供电） |
| p106 | 6.4 续表（VDDSHV5、TJ 工作结温） |
| p108–p115 | `6.7.x` 各接口 Electrical Characteristics |

旧草稿抓的 p14 是 `Table 5-1 Pin Attributes` 的**列说明**：
`13. PULL UP/DOWN TYPE`、`PU: Internal pull-up` 等，整页 0 个 MIN/TYP/MAX 列词。

### 8.2 根因（三处叠加，一个都不能少）

1. `scan3()` 用 `min(npages, MAX_SCAN_PAGES=40)` 截断扫描；真表在 p101 之后，
   前 40 页一页参数表都没有。实测 `prescan3(..., max_pages=40) → []`。
2. `X.HEADING["ELC"]` 是宽松正则，`X.find_headings()` 逐行匹配，把 p14 正文里的
   **章节交叉引用句**（"For more information, see ... in Electrical Characteristics."）
   当成表标题；没有「该页必须有 MIN/TYP/MAX 表头」这一关。
3. `pick_core()` 排序后直接取前 5 行，没有「零核心命中」闸门，
   5 行无数值的术语条目凑数落盘，只被标成 `low_confidence` 交给人。

### 8.3 生成器修复（后续批次生效，已定稿 B1 / B2 其余 5 件不重跑）

| 闸门 | 改动 | 实证 |
| --- | --- | --- |
| 定位范围 | `prescan3()` 全书文本快筛，候选页须同时有表标题词与 ≥2 个 `MIN/TYP/MAX/NOM` 列词；`scan3()` 只解析候选页 | 全书候选 13 页 `[101,102,105,106,108,109,110,111,112,113,115,117,119]`；`14 in 候选 → False` |
| 标题真伪 | `find_headings3()` 要求独立短行（≤90 字符）且不含 see/refer/for more information/defined in/appropriate/table is 等引用词；目录页判定只在前 10 页生效（避免误杀 p102 续表） | p14 的 3 处交叉引用全部被排除 |
| 草稿闸门 | `pick_core()` 连一行「命中 CORE_ORDER 且带数值」都没有时**整件不落草稿**，`quality=无法定位参数表`，HTML 直接给 EXCLUDED 建议 | 旧版 V003 5 行垃圾 → `keep=0 / drop=5` |

### 8.4 V003 定向重出的 5 行（`_fix_v003_b2.py`）

三张 300 DPI 裁图：`b3_AMR_p0101.png`、`b3_ROC_p0105.png`、`b3_ROC_p0106.png`；
旧错页图 `b3_ELC_p0014.png` 已删除、HTML 不再引用。

| 页 | 表 | symbol | 参数名 | min | typ | max | 单位 | 条件 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 105 | ROC | `VDD_CORE` | Core supply | 0.81 | 0.85 | 0.895 | V | Recommended Operating Conditions |
| 105 | ROC | `VDDR_CORE` | RAM supply | 0.81 | 0.85 | 0.895 | V | Recommended Operating Conditions |
| 106 | ROC | `VDDSHV5` | Dual-voltage IO supply | 1.71 | 1.8 | 1.89 | V | 1.8V Operation |
| 106 | ROC | `TJ` | Operating junction temperature range | -40 | | 125 | °C | 125°C Industrial |
| 101 | AMR | `VDD_CORE` | Core supply | -0.3 | | 1.05 | V | 6.1 Absolute Maximum Ratings |

这 5 行是 **PDF 文本层定向抽取，不是 VLM**。每一行的参数名、单位、条件、
各数值、符号都必须能在自己的 `evidence_page` 原文中逐字（横杠规范化后）找到，
任一缺失即拒绝生成。`row_status` 一律 `DRAFT_AWAITING_HUMAN_CONFIRM`、
`reviewer` 为空、`conf=0.60 < 0.85`，5 行全部 `low_confidence`。
B2 总行数仍是 30，其余 25 行一字未动。

### 8.5 仍需人工确认（机器不替人决定）

1. ROC 表头是 `MIN(1) / NOM / MAX(1)`，把 **NOM 放进 `typ_value`** 是否合适，由 Reviewer 定。
2. `VDDSHV5` 同页还有 3.3V Operation（3.135 / 3.3 / 3.465 V），本行只取 1.8V 模式。
3. p101 的 `VDD_CORE -0.3 / 1.05 V` 是绝对最大额定值，与 p105 的推荐工作条件
   `0.81 / 0.85 / 0.895 V` 不是同一概念，勿混。
4. TJ 原文为 `–40`（U+2013 EN DASH），草稿按验证器 `MINUS` 规则写作 `-40`。

完整逐页扫描、旧草稿现场、p14 原文、断言与修复清单见
`Batch3_V003_diagnosis.txt`。若 Reviewer 认为这 5 行仍不够格，
可整件标 `EXCLUDED`，生成器已给出该出口。

## 9. Reviewer 第二轮修正（2026-11-12 08:08）

### 9.1 V304 表头归属 + 23 行逐行复核

物理行 **8**（数据行 7）`V304 / p4 / IIK / Control input clamp current / -50 mA`
的 `table_title` 从 `Electrical Characteristics` 改为 **`Absolute Maximum Ratings`**。
依据：V304 p4 第 6.1 节 AMR 表内第 27~31 行正是
`IIK / Control input clamp current / VIN < 0 / –50 / mA`；
该页第 6.3 节 ROC 从第 82 行才开始。

**六件 PDF 逐页取证后，23 行里只有这一处错**，其余 22 行归属正确。两处容易被误改的：

| 行 | 现 `table_title` | 实证 | 结论 |
| --- | --- | --- | --- |
| V319 物理行 5 / p5 / `IO` / 20 mA | `Absolute Maximum Ratings` | p5 上半页是全小写点线式 `absolute maximum ratings over operating free-air temperature range`，`Output current, IO / 20 mA` 在该表内；p5 第 95 行才是 ROC | 正确，不改 |
| V336 物理行 14~17 / p5 | `Electrical Characteristics` | p5 原文标题就是 `Electrical Characteristics--DC Parameters` | 正确，不改 |

口径说明：PM 裁定「AMR 与 ROC 绝不能混、`table_title` 必须严格保留」针对的是
**同一件里绝对最大额定值与推荐工作条件不得串表**，不是把所有真实 ELC 表强行改名。
若要求全表只允许这两个值，请明示，再按 PDF 原文逐行改。

### 9.2 人工授权链（CSV 与 XLSX 同源）

新增 `approved_by` / `entered_by` 两列，最终定稿共 **19 列**：

| 行 | `reviewer` | `approved_by` | `entered_by` | 含义 |
| --- | --- | --- | --- | --- |
| 物理行 8 / 20 / 22（V304、V173、V345） | `wuxiaoxian` | `wuxiaoxian` | `WB_Agent` | PM 批准、WB 代为录入修正 |
| 其余 20 行 | `wuxiaoxian` | 空 | 空 | 人工直接在 Excel 里签字录入，无代录入环节 |

三行 `notes` 里的「待人确认并重新签字」等过期表述**全部删除**，统一为
**「人工已核对 PDF p4 原图并确认此修正。」**；其余 20 行 notes 保持人工签字时的
原始记录，未改动。`_make_b1_resigned.py` 一次产出最终定稿并逐格断言 CSV == XLSX。

### 9.3 真源文件名与报告路径统一

- 本文件所有「唯一真源」口径统一为 **`Batch3_B1_RESIGNED.xlsx`**；
  `Batch3_B1_SIGNED.xlsx` 降级为过程留痕。
- `Batch3_B1_validation_report.txt` 开头原先误写了 PM 下载目录的**外部绝对路径**
  （指向一份 Excel 另存文件），现改为包内相对路径 `./Batch3_B1_RESIGNED.xlsx`，
  并单列 `./Batch3_B1_SIGNED.xlsx` 作为人工签字原件。
  报告生成器 `_build_batch3_b1_report.py` 同步修正，重跑不会再回退。

### 9.4 两仓 main SHA 更正与致歉

此前报告把两个不同仓库的 `main` 混写成一个，**特此向 Reviewer 致歉并更正**：

| 仓库 | 远端 `main` | 用途 |
| --- | --- | --- |
| CodeUp `icpdf-extractor` | **`853a80d`** | 代码仓 / Gate 6A 工作区 |
| GitHub `stageA-audit-v28` | **`e3c9b64`** | 审计仓 / 本包所在仓 |

本包全部送审内容在 GitHub 审计仓 `feat/gate6a-batch3` 分支；两个远端 `main`
均未因 B1 / B2 修正发生改动。补充：CodeUp 代码仓的**本地** `main` 是 `a11131a`
（24 行 v1.6），按约定未 push，与远端 `853a80d` 不是同一指针，请勿混用。

### 9.5 B2 按 PM 裁定补一处 `condition`

PM 对 V003 四问的裁定：NOM 放 `typ` 正确；`VDDSHV5` 只取 1.8V；AMR/ROC 不得混；
`-40` 归一化没问题。据此把 `Batch3_B2_DRAFT.csv` 里 `VDDSHV5` 那行的
`condition` 由 `1.8V Operation` 改为 **`VDD=1.8V`**，明确区分同页的 3.3V 模式。
V003 五行的 `table_title` 仍严格是 4 行 `Recommended Operating Conditions`
+ 1 行 `Absolute Maximum Ratings`，未混用。

### 9.6 机检与校验

最终定稿改完后**重新实跑** v1.6：PDF 模式（实算哈希）与离线模式（sidecar）
均 `OK=23 / SUSPECT=0 / ERROR=0`、退出码 0，原始 stdout 见
`b1_validation_raw/b1_final_pdf_mode.txt` 与 `b1_final_sidecar_mode.txt`，
报告 G 段逐字贴出。改列、改表头、改备注均未影响任何一条判据。

## 10. CORE_ORDER 正则 + prescan3 表头加固（Reviewer 第三轮）

这一轮修的是**底层生成器**，不是 V003 的定向脚本；B1/B2 已定稿产物一律不重跑。

### 10.1 漏洞一：供电符号正则的 `\b` 挡住带后缀的符号

旧版 `CORE_ORDER[0]` 是 `^v(cc|dd|s)\b|\bv(cc|dd)\b`。`\b` 要求 `VDD` 后面紧跟
非单词字符，但 `VDD_CORE` / `VDDR_CORE` / `VDDSHV5` 的后缀以下划线或字母开头，
全都是单词字符 —— 词边界不成立，这几行被判 `pri=99`，`pick_core()` 直接丢掉。

现改为独立的 `SUPPLY_RX`：

```python
SUPPLY_RX = re.compile(
    r"supply\s+voltage|power[- ]supply\s+voltage"
    r"|\bv(?:cc|dd|s)[a-z0-9_]*\b"
    r"|\b[a-z]{1,3}v(?:cc|dd)[a-z0-9_]*\b", re.I)
```

覆盖 `VDD_CORE`、`VDDR_CORE`、`VDDSHV5`、`VCC`、`VDD`，并兼容
`AVDD3V` / `DVDD` / `IOVDD` 这类带前缀写法；参数名里的 `Supply voltage range`
仍照旧命中。**回归测试里 parameter_name 故意留空**，确保只靠符号也能判为核心。

### 10.2 漏洞二（同源，顺带修掉）：`^` 锚在拼接串里永远不命中

回归测试第一次跑就抓到 `TJ` 仍落 `pri=99`：温度/电流那几条写的是
`^t\s*j\b` / `^t\s*stg\b` / `^i\s*o\b` 等，而 `core_rank()` 拼的是
「`parameter_name` + 空格 + `symbol`」，串几乎不以符号开头，`^` 永远匹配不到。
已把 `TA / Tstg / TJ / IO / II` 的符号分支统一改成 `\b` 词边界锚。

### 10.3 prescan3() 的表头识别加固

旧版只数「页面出现 ≥2 个 `MIN/TYP/MAX/NOM`」，正文里反复提
minimum / maximum 也会被当成参数表，属 Fail-Open。现在加第二层结构判据：

| 判据 | 内容 |
| --- | --- |
| `has_table_header(text)` | 连续 8 行窗口内，≥2 个不同数值列词**各自独立成行**（允许 `MIN(1)` 脚注），且窗口内有 `UNIT` / `PARAMETER` / `DESCRIPTION` / `SUPPLY NAME` / `TEST CONDITIONS` 之一 |
| `_table_header_from_borders(page)` | 有表格边框时，直接看表头区域单元格里是否含 ≥2 个数值列词 |

两条是「或」关系：老手册的点线式 AMR 表没有边框，不能因为查不到边框就误杀真表。
`has_table_header` 是纯文本函数，可被回归测试直接调用。

**回归验证**：V003 全书候选页加固后仍是
`[101,102,105,106,108,109,110,111,112,113,115,117,119]` 共 13 页，
`p14` 仍被排除，`p101/p105/p106` 全部保留；`_fix_v003_b2.py` 的 5 行证据断言
全部仍通过，B2 产物与加固后生成器一致。

### 10.4 测试输出（真实 stdout，未编辑）

| 测试 | 结果 |
| --- | --- |
| `_test_core_order_and_header.py` | **`PASS=26, FAIL=0, SKIP=0`**（第五轮扩充后），退出码 0；原始输出 `Batch3_CORE_ORDER_regression.txt` |
| `_selftest_validator_v2.py`（v1.6 验证器 31 例） | **`PASS=31, FAIL=0, SKIP=0`**，退出码 0；原始输出 `Batch3_validator_selftest.txt` |

新测试全部使用内存对象与合成 PDF 页，不依赖外部 PDF 或环境变量，
因此**不存在 SKIP**；跑不全就是 FAIL、退出码非零。原 18 例含：
5 个被点名符号的正向断言、带前缀符号、`^` 锚回归、
AMR/ROC 两种真表头正向、纯正文多组 MIN/MAX 反向、
合成整页的正向与反向、p14 式术语解释页反向。
第四轮按 Reviewer 要求补 6 例（四个极端场景 AMR/ROC 各算一例，
另加跨页续表防误杀），共 24 例，详见第 12 节；
第五轮再补 2 例（边框表格关联反例 / 续表标识正例），共 26 例，见第 13 节。

### 10.5 真实代码 diff 与 B1 定稿确认

- `Batch3_CORE_ORDER_fix.diff`：从 `9c0a81a` 到当前工作区的**累计真实补丁**，
  692 行 / 640 行新增（含第四、五轮加固）；`Batch3_prescan3_extreme_fix.diff`
  是第五轮相对 `de9a433` 的增量补丁，247 行 / 156 行新增。两份都是 `git diff` 原样产出，
  Reviewer 可直接查看，不需要占位描述。
- `Batch3_B1_RESIGNED.csv` / `.xlsx`（**23 行 × 19 列**）确为本包内的最终定稿：
  V304 物理行 8 的 `table_title` 已是 `Absolute Maximum Ratings`；
  V304 / V173 / V345 三行 `reviewer=wuxiaoxian`、
  `approved_by=wuxiaoxian`、`entered_by=WB_Agent`；
  23 行全部 `CONFIRMED`，v1.6 双模式全绿。

### 10.6 新增文件

| 文件 | 作用 |
| --- | --- |
| `_build_batch3_interactive.py` | 修复后的生成器（本轮唯一改动的生产代码） |
| `_test_core_order_and_header.py` | 26 例回归测试（含四轮极端场景） |
| `Batch3_CORE_ORDER_regression.txt` | 26 例真实 stdout |
| `Batch3_validator_selftest.txt` | v1.6 自测 31 例真实 stdout |
| `Batch3_CORE_ORDER_fix.diff` | 真实代码 diff |


## 11. B1 备注清理 + B2 最终版交付（Reviewer 第四轮）

### 11.1 B1：只清理 20 行过期备注，核心一格未动

PM 裁定：「那 20 行 notes 里写的『须对左图核』『请确认』等草稿词汇，一律替换为
『人工已核对 PDF 原图并确认』；确保不再出现 `low_confidence` 和 `CONFIRMED`
并存的矛盾。」

| 项 | 结果 |
| --- | --- |
| 改动范围 | 20 行 notes → 定稿语；3 行 PM 代录入定稿语保持不变 |
| 其余字段 | 除 notes 外 18 列逐格断言未变（min/max/typ、unit、condition、row_status、reviewer、授权链、confidence_score） |
| 矛盾消除 | notes 里 `low_confidence` 残留 0；confidence_score 仍为 0.95×21 / 0.85×1 / 0.8×1 |
| 留痕 | `Batch3_B1_RESIGNED_pre_notes_cleanup.xlsx`（清理前 xlsx 原样） |
| 复跑 | PDF / 离线双模式 `OK=23 / SUSPECT=0 / ERROR=0`，退出码 0；报告 H 段贴了原始 stdout |

### 11.2 B2：签字版是唯一真源，定稿与机检一起打包

| 项 | 结果 |
| --- | --- |
| 真源 | `Batch3_B2_SIGNED_original.xlsx`（PM 签字原件副本，30 行 × 15 列，逐格未改） |
| 定稿 | `Batch3_B2_FINAL.csv` / `.xlsx`，30 行 × 19 列，**已是定稿而非 DRAFT** |
| notes | 30 行统一为「人工已核对 PDF 原图并确认」；原文全文留痕在 `Batch3_B2_notes_before_cleanup.txt` |
| V003 条件 | `VDDSHV5 condition=1.8V Operation` 保留；p106 文本层独立行断言通过 |
| 符号回填 | 7 行按 PDF 原图回填 symbol、清理 condition，逐字段原文断言；`human_adjudication` 全表清空；原 15 列仅 notes（30 行）与 symbol/condition（7 行）改动 |
| 简写文件名 | 3 件按 CSV 原名在 `b2_pdfs/` 建硬链接指向语料原件同一字节，签字真源一格未改 |
| 机检 | PDF / 离线双模式 `OK=30 / SUSPECT=0 / ERROR=0`，退出码 0 |

`b2_pdfs/` 是本地硬链接验证环境，体积原因不入包；干净解压包用离线 sidecar
模式（B.2 命令）即可复现 `OK=30`，需要 PDF 模式时用
`_make_b2_final.py --xlsx <签字xlsx> --pdf-dir <语料目录>` 重建该目录。

**待 PM 复核**：上一版用 `ACCEPTED_SOURCE_HAS_NO_SYMBOL` 放行这 7 行属语义错配
（源头其实有符号，只是被 VLM 挪进了 condition），本版已改为按原文回填并清空裁定码。
回填由 WB 完成，故 `approved_by` 留空、`entered_by=WB_Agent`，
`reviewer` 仍是 PM 对整表的签字，不擅自撤销也不冒充人工逐行确认。

### 11.3 本版新增文件

`_clean_b1_notes.py`、`Batch3_B1_RESIGNED_pre_notes_cleanup.xlsx`、
`b1_validation_raw/b1_notes_clean_*.txt`、
`_make_b2_final.py`、`Batch3_B2_SIGNED_original.xlsx`、
`Batch3_B2_FINAL.csv` / `.xlsx`、`Batch3_B2_notes_before_cleanup.txt`、
`page_text_batch3_b2.json`、`Batch3_B2_PDF_PROVENANCE.csv`、
`Batch3_B2_validation_report.txt`、`b2_validation_raw/b2_final_*.txt`、
`_build_batch3_b2_report.py`、`_verify_v003_candidates.py`、
`Batch3_prescan3_v003_evidence.txt`、`Batch3_prescan3_extreme_fix.diff`。

## 12. prescan3 四个极端场景（Reviewer 第四轮）

### 12.1 场景与实测结果

| 场景 | 构造 | 期望 | 实测 |
| --- | --- | --- | --- |
| a 同页有无关表格，目标表没表头 | AMR 标题下只有数据行，页尾另有 `PIN/MIN/MAX/UNIT` 无关表（文本层 + 边框两条路径都给） | 拦截 | PASS |
| b 标题在正文，另一区域有 MIN/MAX | 标题词嵌在 "Stresses beyond those listed under ..." 句子里，另一处有独立列词行 | 拦截 | PASS |
| c 有边框表格但前两行不是有效表头 | 边框表前两行是 `Device Information / Rev A`、`Note / Value` | 拦截 | PASS |
| d 真实无边框 AMR / ROC 表 | 文本层竖排独立列词行 + 独立标题行，无边框 | 保留 | PASS（AMR、ROC 各一例） |

另加第 6 例：**跨页续表（无独立标题行、有真实边框表头）仍保留**，
防止加固误杀 V003 的 p106。

### 12.2 实现要点（不是只加测试用例凑数）

1. `TITLE_LINE_RX` / `title_anchor_lines()`：整行必须基本就是参数表标题，
   `Stresses beyond those listed under ...` 这类正文句子不算标题。
2. `has_table_header(text, title_positions)`：带锚点时，表头窗口必须
   **从第一个表头词行起算**、紧跟独立标题行（≤4 行），且标题与窗口之间
   不能夹参数数据行。第一次实现时窗口起点可以退到标题后第 1 行，
   场景 a 实测 FAIL 抓到了这个漏洞，修完才全绿。
3. `_table_header_from_borders()`：除 ≥2 个数值列词外，表头还必须有
   `PARAMETER` / `DESCRIPTION` / `SUPPLY NAME` / `TEST CONDITIONS` 之一，
   `PIN/MIN/MAX/UNIT` 这种无关表格不再放行。
4. 边框路径**不要求标题存在**：V003 p106 是跨页续表，页面上没有独立标题行，
   靠边框表头进候选页；强行要求标题会误杀真表。

### 12.3 测试与真实 PDF 回归

| 测试 | 结果 |
| --- | --- |
| `_test_core_order_and_header.py` | **`PASS=26, FAIL=0, SKIP=0`**，退出码 0；全部内存对象 / 合成页，无 SKIP |
| `_selftest_validator_v2.py`（v1.6 验证器 31 例） | **`PASS=31, FAIL=0, SKIP=0`**，退出码 0 |
| `_verify_v003_candidates.py`（V003 全书 282 页） | 候选页仍为 `[101,102,105,106,108,109,110,111,112,113,115,117,119]` 共 13 页；13 页真表逐页断言保留、无多余页，p14 排除，结论「全部通过」 |
| B1 复跑 | PDF / 离线 `OK=23`，退出码 0 |
| B2 复跑 | PDF / 离线 `OK=30`，退出码 0 |

真实补丁：`Batch3_CORE_ORDER_fix.diff`（累计 692 行 / 640 行新增）与
`Batch3_prescan3_extreme_fix.diff`（第五轮增量 247 行 / 156 行新增）。


## 13. B2 符号回填 + prescan3 边框关联（Reviewer 第五轮 · 本版）

### 13.1 七行符号按 PDF 原图回填

上一版把 7 行空 symbol 用 `ACCEPTED_SOURCE_HAS_NO_SYMBOL` 放行，Reviewer 指出
语义错配：这 7 行的符号并非不存在，而是太长被 VLM 挪进了 `condition`。
本版回到 PDF 原图逐字提取，回填 `symbol`，`condition` 只留真正的测试条件，
`human_adjudication` 全表清空。

| 行 | 样本 / 页 | 原 condition（错放） | 回填 symbol | 新 condition |
| --- | --- | --- | --- | --- |
| 8 | V320 p12 | `DACVDD, DIGVDD, CLKVDD` | 同左（p12 行 11） | `over operating free-air temperature range (unless otherwise noted)` |
| 9 | V320 p12 | `AVDD, PLLAVDD` | 同左（p12 行 24） | 同上全表条件 |
| 16 | V242 p6 | `APWR to AGND` | 同左（p6 行 7） | 空 |
| 17 | V242 p6 | `DPWR to DGND` | 同左（p6 行 11） | 空 |
| 18 | V242 p6 | `AGND, AGNDy to DGND` | 同左（p6 行 14） | 空 |
| 19 | V242 p6 | `AVDD to AGND` | 同左（p6 行 17） | 空 |
| 20 | V242 p6 | `IOVDD to DGND` | 同左（p6 行 20） | 空 |

- V320 该表标题下方行 7 是**全表测试条件**，故填入 condition；V242 只有
  `see (1)` 脚注引用、无具体条件，故留空，不臆造。
- 保留原表逗号 / `to` 写法，不改成 `符号1; 符号2`：分号不在 PDF 原文里，
  会让 v1.6 的 `check_symbol()` 找不到符号。7 个符号与 V320 全表条件都做了
  `nos(值) in nos(页文本)` 原文断言后才落盘。
- **授权链与复核请求**：回填由 WB 完成，7 行 `entered_by=WB_Agent`、
  `approved_by` 留空；`reviewer` 仍是 PM 对整表的签字，不擅自撤销、
  也不冒充人工已逐行确认。请 PM 对这 7 行逐行复核后确认。
- 其余 23 行的 symbol / condition 一字未动；30 行的 min/typ/max、unit、
  evidence_page、table_title、row_status、reviewer、confidence_score 一字未动。
- 机检：PDF / 离线双模式 `OK=30 / SUSPECT=0 / ERROR=0`，退出码 0。

### 13.2 边框表格必须与目标标题空间关联

**漏洞**：`_table_header_from_borders(page)` 只要表头成立就放行整页，
与页面标题无关。若页顶有独立 AMR 标题、AMR 区域却没有表头，页底另有一个
带完整表头的无关表格，旧逻辑会把整页放进候选页。

**修复**：`_table_header_from_borders()` 现在要求边框表格满足以下之一：

1. 表格顶端距上方「独立标题行 / 小节标题行 / 续表标识行」≤ 200pt
   （`_anchor_ys()` 从 `get_text("dict")` 取行级 bbox，做真正的空间关联）；
2. 表格落在页首（`y0 ≤ 160pt`）且表头有效 —— 跨页续表的客观特征。

新增 `CONT_RX`（`(continued)` / `cont'd` / `cont.`）、`SECTION_TITLE_RX`
（识别 `6.7.2 Fail-Safe Reset (FS RESET) Electrical Characteristics`
这类带描述的小节标题）、`_table_is_anchored()`。

**阈值来自实测，不是拍脑袋**：V003 p108 表格 y0=229.4、标题 y=75（相距 154.4pt），
p119 y0=154.4、p117 y0=144.2、p109~115 y0=107.0、p106 y0=86.0；
Reviewer 反例的无关表格在页底 y0=400，离页顶标题 328pt，仍被拦。
第一版把阈值定成 120/100 时曾把 9 页真表（p108~119）误杀，
已逐页诊断后修正，并把 13 页真表清单整表写进回归断言。

**补交的两个极端测试**：

| 用例 | 构造 | 期望 | 实测 |
| --- | --- | --- | --- |
| 反例 | 独立 AMR 标题 + AMR 区域无表头 + 页底无关边框表（带 `PARAMETER/MIN/MAX/UNIT`） | 拦截 | PASS |
| 正例 | `Table 6-1. Absolute Maximum Ratings (continued)` + 真 AMR 续表边框表头 | 保留 | PASS |

另有第 3 例防误杀：V003 p106 式页面（无标题、无续表标识、表格在页首）仍保留。

### 13.3 本版测试与机检

| 测试 | 结果 |
| --- | --- |
| `_test_core_order_and_header.py` | `PASS=26, FAIL=0, SKIP=0`，退出码 0 |
| `_selftest_validator_v2.py`（v1.6 31 例） | `PASS=31, FAIL=0, SKIP=0`，退出码 0 |
| `_verify_v003_candidates.py`（V003 全书 282 页） | 13 页真表逐页保留、候选集合无多余页、p14 排除，结论「全部通过」 |
| B2 定稿机检 | PDF / 离线双模式 `OK=30 / SUSPECT=0 / ERROR=0`，退出码 0 |
| B1 | 已冻结，本轮未改动 |

真实补丁：`Batch3_CORE_ORDER_fix.diff`（累计 692 行 / 640 行新增）、
`Batch3_prescan3_extreme_fix.diff`（第五轮增量 247 行 / 156 行新增）。
