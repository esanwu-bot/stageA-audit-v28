# Batch 3 复审包 · B1 / B2 双定稿 + 生成器底层加固

分支 `feat/gate6a-batch3`，**不动 main、不动 `feat/gate6a-annotation`**。
B1、B2 均为人工签字定稿；机器没有替人确认任何一行，也没有替人改核心数值。
2026-11-12 追加：Reviewer 指出 B2 的 V003 抓错页，已重定位重截，详见第 8 节。
2026-11-12 第二轮追加：修正 V304 表头归属、补齐人工授权链、统一真源口径与两仓
main SHA，详见第 9 节。
2026-11-12 第三轮追加：修复 CORE_ORDER 通用正则漏洞并加固 prescan3，见第 10 节。
2026-11-12 第四轮追加：清理 B1 过期备注、交付 B2 最终版与机检、
补齐 prescan3 四个极端场景回归，见第 11、12 节。
2026-11-12 第五轮追加：B2 七行符号按 PDF 原图回填（不再用裁定码）、
修复 prescan3 边框表格与标题的空间关联并补两个极端测试，见第 13 节。
2026-11-12 第六轮追加（本版·封卷）：B2 七行 `approved_by` 授权链闭合
（错位撤销 → 正确补签 → 最终机检），见第 14 节。

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
  7 行由 WB 代录入（`entered_by=WB_Agent`）；第六轮 PM 已明确授权并在正确
  7 行补签 `approved_by=wuxiaoxian`，授权链闭合，详见第 14 节与
  `Batch3_B2_validation_report.txt` A.3 / A.7。
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
- **授权链**：回填由 WB 完成，7 行 `entered_by=WB_Agent`；第五轮时
  `approved_by` 为空、需 PM 逐行确认，`reviewer` 仍是 PM 对整表的签字，
  不擅自撤销、也不冒充人工已逐行确认。**该复核请求已在第六轮闭合，见第 14 节**
  （PM 明确授权并在正确 7 行补签 `approved_by=wuxiaoxian`）。
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

---

## 14. 第六轮（封卷）：B2 授权链闭合与最终机检

2026-11-12 10:05，PM 明确授权「在正确位置，签署 wuxiaoxian」。
本轮**不改任何核心数值、不改生成器判据、不动 B1、不动两仓 main**，
只闭合 B2 七行 `approved_by` 的授权链并封卷。

### 14.1 为什么需要这一轮

第五轮把 V320 两行、V242 五行的 `symbol` 从 PDF 原文回填后，这 7 行由 WB
代录入（`entered_by=WB_Agent`），`approved_by` 为空，需 PM 逐行确认。
PM 09:48 首次补签时，7 处 `wuxiaoxian` 落在数据行 `8/9/22/23/24/25/26`
（V320 两行 + V003 四行 + V011 一行），其中 5 行并非代录进行，而真正需要
复核的 V242 五行（数据行 `16/17/18/19/20`）反而漏签。

### 14.2 处置全过程（全留痕，不粉饰）

| 时间 | 动作 | 结果 |
| --- | --- | --- |
| 09:48 | PM 首次补签 7 处 | 落点错位，原件留存于 `Batch3_B2_FINAL_SIGNED_approval.xlsx` |
| 09:52 | PM 主动要求全部清空、恢复原样 | WB 用 `_b2_approval_reset.py` 从封卷前快照恢复；主定稿与 `6107ab7` 逐字节一致，**未产生新提交** |
| 09:52 | WB 给出 7 行标红清单 | `Batch3_B2_FINAL_TO_SIGN.xlsx` + `Batch3_B2_APPROVAL_TARGETS.txt` + V320 p12 / V242 p6 两张原表裁图 |
| 10:03 | PM 在标红版 7 个红格自行补签 | 数据行 `8/9/16/17/18/19/20`（Excel 行 9/10/17/18/19/20/21） |
| 10:05 | PM 再次授权 WB 在正确位置落签 | WB 实测位置已正确，**不再代填、不改写任何人工签名**，仅逐格复核并同步封卷定稿 |

留痕文件：

- `Batch3_B2_FINAL_TO_SIGN.xlsx` —— PM 正确补签原件（唯一授权真源，逐格未改）
- `Batch3_B2_FINAL_SIGNED_correct.xlsx` —— 同字节留痕副本
- `Batch3_B2_FINAL_SIGNED_approval.xlsx` —— 09:48 错签原件
- `Batch3_B2_FINAL_pre_approval.xlsx` —— 封卷前无签名版
- `Batch3_B2_approval_revoke_note.txt` / `Batch3_B2_approval_authorization.txt`
- `Batch3_B2_APPROVAL_TARGETS.txt` —— 7 行 Excel 行号与符号现值
- `_sync_b2_approval.py` / `_b2_approval_reset.py` / `_b2_final_seal.py`

### 14.3 封卷断言

- `approved_by` 非空数据行 `[8, 9, 16, 17, 18, 19, 20]`，与
  `entered_by=WB_Agent` 的 7 行集合**完全相等**；其余 23 行保持空白。
- 每个非空值都是 `wuxiaoxian`；`reviewer=wuxiaoxian` 30/30、
  `row_status=CONFIRMED` 30/30、`symbol` 空 0、`human_adjudication` 非空 0。
- 相对封卷前版本，除 `approved_by` 一列 7 处变化外，其余 18 列**逐格零差异**
  （min/typ/max、unit、evidence_page、table_title、notes、symbol、condition 均未动）。
- 主 `Batch3_B2_FINAL.xlsx` / `.csv` / PM 补签原件三方逐格一致。
- **防回归加固**：`_make_b2_final.py` 现在从现有定稿读回 `approved_by` 并原样
  保留；在干净临时目录实测重跑（退出码 0），7 处补签仍在，30 行与封卷定稿
  逐格一致，不会因复核复跑而抹掉人工签字。

### 14.4 最终机检（原始 stdout 均在包内）

| 项目 | 结果 |
| --- | --- |
| B2 v1.6 PDF 模式 | `OK=30 / SUSPECT=0 / ERROR=0`，退出码 0 |
| B2 v1.6 离线 sidecar 模式 | `OK=30 / SUSPECT=0 / ERROR=0`，退出码 0 |
| `_selftest_validator_v2.py` | `PASS=31, FAIL=0, SKIP=0` |
| `_test_core_order_and_header.py` | `PASS=26, FAIL=0, SKIP=0` |
| `_verify_v003_candidates.py` | 13 页真表保留、无多余页、p14 排除 |
| B1 | 已冻结，本轮未改动 |

真实补丁：`Batch3_B2_seal.diff`（相对封卷前提交的文本差异，含 7 行
`approved_by` 落点与报告 / INDEX 变更）。生成器底层代码本轮未改判据，
第 10、13 节的累计补丁仍有效。

### 14.5 尚未做的事（第六轮当时的状态）

B3（6 件）、B4（5 件）、SCAN（3 件按 SOP 标 EXCLUDED）未生成；
33 件全部标完且 Reviewer 终审放行后，才把 CodeUp 本地 main（`a11131a`）
更新并 push。两仓 main 本轮未动。

> 第 14.3 的「从现有定稿读回 `approved_by`」与第 14.4 的 `PASS=26` 都是
> 第六轮封卷当时的真实状态。第七轮已分别替换为「唯一签名源 + 稳定 ID」
> 与 39 例回归，见第 15 节。历史数字不回改，保留当时的 stdout 留痕。

## 15. 第七轮：底层漏洞终极修复与真正的 B3 圈选台

B1 / B2 已冻结，**本轮不改任何一行定稿数据**，只修生成器与签名保护逻辑，
并重建 B3 圈选台。两仓 main 仍未动。

### 15.1 根因：误杀真表不是阈值问题，是 `find_tables()` 跨页脏数据

PyMuPDF 在同一 `Document` 上跨页调 `find_tables()` 会污染先前取到的
`Table` 对象：实测「先取 p101 的 Table、再对 p100 调 `find_tables()`」，
p101 的 `t.extract()` 会吐出 p100 的正文，p102 甚至变成全空行。此前
合成页全绿但真实 PDF 误杀 8~11 页，判据建立在脏数据上，调距离阈值无效。

三道硬隔离（任一不过即丢弃该表）：

1. `find_tables(clip=本页矩形)` —— 检测范围锁死在本页；
2. `bbox` 四边必须落在 clip 内（1pt 容差），**Y 轴越界即判脏数据**；
3. 表头词必须能在「本页」`get_text("text")` 核到，命中率 < 0.50 判定为
   上一页正文串入。污染时命中率塌到 0，正常表格接近 1。

再加结构约束：`Table` 对象绝不跨出 `_page_table_signatures()`；本页全部
extract 完成、`PageContext` 释放 `page` 引用后，才允许访问上一页。

隔离 1 的执行口径（Reviewer 第七轮补：此处**不允许静默降级**）：若运行
环境的 `find_tables()` 不接受 `clip` 关键字而抛 `TypeError`，程序直接
`SystemExit` 退出，绝不退回 `page.find_tables()` 无 clip 调用——没有 clip
等于放弃隔离 1，跨页污染会原路回来。返回值缺 `tables` 属性同样退出。
回归里用 `NoClipPage`（`find_tables` 只接受 `self`）证明会退出，且退出
消息必须点明 `clip`。

### 15.2 prescan3 三段式任务队列与页级分流

`页级分类（Page_Title）` → `表头匹配（TableSignature / 指纹）` →
`上下文关联（link_context）`。废弃 `if y0 <= PAGE_TOP_MAX_PT: return True`
这条绝对放行规则。

V003 全书 282 页、13 页真表的真实链路（原始 stdout：
`Batch3_prescan3_v003_evidence.txt`）：

| 分类 | 页数 | 放行链路 |
| --- | --- | --- |
| `STRONG`（本页有独立表题/章节号） | 11 页 | `LOCAL_TITLE`，**完全不读取上一页** |
| `NONE`（无本页标题） | p102 / p106 | `INHERITED_TITLE_FINGERPRINT`，指纹相似度均 `1.00` |

继承分支必须同时满足：上一页有可继承 `Page_Title`、指纹相似度 ≥ 0.80、
左右边界/宽度几何对齐、表格落在页首区间。任一不满足即 Fail-Closed 拦截。
回归硬断言「恰好 2 页走继承」，不是靠观察得出的结论。

### 15.3 描述型表题口径统一（B3 V146 真误杀）

V146（CY74FCT399T）p4 有完整 `MIN/TYP/MAX` 表，但表题写成小写长句
`electrical characteristics over recommended operating free-air
temperature range (unless otherwise noted)`。裁图层 `find_headings3` 用
`X.HEADING`（search 语义）本就能命中，文本层 `title_anchor_lines` 却只认
「整行就是标题词」的严格正则，两处口径不一致把整页拦掉。

补 `DESC_TITLE_RX`：**必须以表题词开头**、不含章节交叉引用词、整行
≤ 120 字符，且后续仍须由 `has_table_header` 验证「完整表头紧邻标题、
中间不夹数据行」。这是结构化补判据，不是放宽阈值；新增 4 个正/反例，
正文句子与「远处无关表头」仍被拦截。

### 15.4 签名保护：Fail-Closed + 稳定 ID

废弃「从现有定稿按行号读回 `approved_by`」。唯一签名源改为
`Batch3_B2_FINAL_TO_SIGN.xlsx`；源文件不存在 / 19 列表头不符 /
数据行数不是 30 / 稳定 ID 重复 / 非 PM 本人签名 / 签名落点与
`entered_by=WB_Agent` 不一致，一律 `SystemExit`。

**实测发现**：PM 指定的五字段
`sample_no + file_name + evidence_page + symbol + parameter_name`
在 30 行中并不唯一 —— V011 p3 的 `VIH` 有 3 行、`VIL` 有 2 行五字段
完全相同（同一页同一符号不同电压档），字典会静默覆盖重复键，这本身
就是另一种 Fail-Open。故追加 4 个 PM 明确「绝不能改」的确定性数值列
`min_value / typ_value / max_value / unit` 消歧，30 行 ID 全唯一。
这些是数据内容，不是行号：行顺序打乱后签名仍精确落位（回归场景 8）。

重跑 `_make_b2_final.py`：退出码 0，定稿 19 列 × 31 行**逐格一致**，
CSV / PROVENANCE 字节一致，7 处 `approved_by` 与代录入行
`[8,9,16,17,18,19,20]` 精确对齐，授权链仍闭合
（`Batch3_B2_regeneration.txt`）。

### 15.5 真正的 B3 圈选台

`Batch3_Viewer.html` 此前是 B1 旧型号（V319/V304/V173 等）的圈选台，
属测试产物；已留痕为 `Batch3_B1_Viewer.html` / `Batch3_B1_DRAFT.csv`，
并用真正的 B3 名单重建：

`V328 V146 V222 V271 V256 V244`

按同一套指纹逻辑裁图，9 张左图与 HTML 同包。真实 VLM 缓存逐一核对：

| 样本 | 结果 | 说明 |
| --- | --- | --- |
| V271 / V256 / V244 | 各 5 行草稿 | 跨页表格类，VLM 真调用，裁图 p117/p13/p44 等；V256 p13 五行 `condition` 已按原图逐行绑定（见 15.7） |
| V146 | 5 行草稿 | 修复描述型表题后命中 p4；5 行全 `low_confidence`，需重点核对列对齐 |
| V328 | `EXCLUDED` | 29 页中 12 页无文本层、前 12 页有连续 4 页空白；无 OCR 能力，无法建立 Gold |
| V222 | `EXCLUDED` | 9 页全为封装/板图/卷带资料，`0.05 MIN/MAX` 是机械尺寸标注，无电气参数表 |

`Batch3_DRAFT.csv` 20 行，全部为 `DRAFT_AWAITING_HUMAN_CONFIRM`，
机器未替人确认任何一行。B1 旧型号、B2 型号在正式 HTML 中均为 0 残留。

### 15.6 全绿回归（原始 stdout 均在包内）

| 项目 | 结果 |
| --- | --- |
| `_test_core_order_and_header.py` | **`PASS=43, FAIL=0, SKIP=0`** |
| `_test_b2_approval.py`（新增） | **`PASS=9, FAIL=0, SKIP=0`** |
| `_selftest_validator_v2.py` | `PASS=31, FAIL=0, SKIP=0` |
| `_verify_v003_candidates.py` | 13 页真表全中、p14 排除、无多余页；恰好 2 页走指纹继承 |
| B2 v1.6 PDF / 离线双模式 | 均 `OK=30 / SUSPECT=0 / ERROR=0`，退出码 0 |
| B2 定稿重跑 | 逐格一致、授权链闭合、冻结数据未改 |
| B1 | 已冻结，本轮未改动 |

`Batch3_V003_regression.txt` 与 `Batch3_prescan3_v003_evidence.txt` 逐字节
相同（`dc355884483f7c14…`）：V003 全书回归重跑可复现，不是人工整理过的文本。

### 15.7 Reviewer 第七轮两条硬伤：`clip` 静默降级与 V256 condition 缺失

**硬伤 1 —— `clip` 静默降级。** 旧代码 `except TypeError` 后退回
`page.find_tables()` 无 clip 调用，等于把隔离 1 悄悄关掉。已改为
`SystemExit`（见 15.1 末段），并补 `NoClipPage` 回归证明真的会退出。

**硬伤 2 —— V256 `V(MAIN-AUX)` 五行 condition 全空。** VLM 不抄
`TEST CONDITIONS` 列，草稿里五行 condition 都是空串。核对原图
`annotation_reports/V256/b3_ELC_p0013.png`，五行各对应一个不同的测试条件；
其中**第 2、3 行的 MIN/MAX 完全相同（-7.8 / 6.6 mV），无法按数值反推**，
只能按参数块内出现顺序绑定：

| # | MIN | TYP | MAX | TEST CONDITION（原图逐行） |
| --- | --- | --- | --- | --- |
| 1 | -7.1 | — | 6.1 | `2V<VCELL<4.5V; TA=25°C` |
| 2 | -7.8 | — | 6.6 | `2V<VCELL<4.5V; -20°C<TA<65°C` |
| 3 | -7.8 | — | 6.6 | `2V<VCELL<4.5V; -40°C<TA<105°C` |
| 4 | -7.8 | — | 6.7 | `2V<VCELL<4.5V; -40°C<TA<125°C` |
| 5 | -7.9 | — | 6.9 | `1V<VCELL< 5V; -40°C<TA<125°C` |

实现为 `CONDITION_BACKFILL` + `apply_condition_backfill()`：命中行数与
条件条数不等即 `SystemExit("…拒绝按顺序盲配")`，不做任何数值匹配猜测。
**五行 condition 互不相同、第 2/3 行未被当成重复数据合并**，这两点都写成
断言，不是靠肉眼。

`mark_dups()` 仍按参数块内「符号 + 条件 + 单位」判重，因此这五行在
`duplicate_group` 上依然是 5 个不同值，不会被误合并。

**回归中发现并修掉的一个新问题（如实记录）：** `apply_condition_backfill`
最初遍历**全局**回填表。B3 是六件串行生成，V328 整件无文本层 → `keep`
为空，于是被误判成「V256 条件块丢失」而 Fail-Closed 退出。这不是纪律
问题而是作用域缺陷，改为按 `sample_no` 隔离，并明确分工：
整件无参数行由 `EXCLUDED` 结论承接、回填不适用；**有参数行但条件块对不上
仍必须退出**。补 `反向 V256 condition 回填 按样本隔离` 用例，同时断言
「V256 自己只剩 2 行时仍退出」，防止把隔离写成放宽。

本轮对 B3 草稿的净影响：与留痕
`Batch3_DRAFT_before_condition_backfill.csv` 逐格比对，**只有 5 格变化，
全部是 V256 这五行的 `condition`**；其余 15 行、20 行的所有数值 / 符号 /
单位一字未动。

### 15.8 尚未做的事

B4（5 件：V077 V130 V290 V347 V041）、SCAN（3 件按 SOP 标 EXCLUDED）
仍未生成；33 件全部标完且 Reviewer 终审放行后，才把 CodeUp 本地 main
（`a11131a`）更新并 push。两仓 main 本轮仍未动。

## 16. B3 定稿：notes 清理、19 列 FINAL 与 v1.6 双模式机检

B3 从「20 行草稿」走到「可进语料的定稿」。本节只处理 B3，
B1 / B2 的定稿数据一格未动。

### 16.1 真源与 notes 清理

唯一真源是 PM 签字的 `Batch3_B3_ANNOTATED.xlsx`（20 行 x 15 列，全部
`CONFIRMED`、`reviewer` 全部 `wuxiaoxian`、空 `symbol` 0）。原件的逐格副本
存为 `Batch3_B3_SIGNED_original.xlsx`，供 Reviewer 反查。

20 行 notes 仍是草稿措辞（`VLM 草稿，须对左图核` / `low_confidence` /
`请确认` 两类后缀）。按裁定统一改为 `人工已核对 PDF 原图并确认`，
清理前全文留在 `Batch3_B3_notes_before_cleanup.txt`。

与签字版逐格比对的结果（`Batch3_B3_regen_report.txt` 为原始 stdout）：

| 列 | 变化格数 | 说明 |
| --- | --- | --- |
| `notes` | 20 | 全部改为定稿口径 |
| `condition` | 5 | 仅 V256 五行，见 16.3 |
| `min/typ/max/unit/symbol/parameter_name` | **0** | 核心数值一字未动 |
| `row_status` / `reviewer` / `confidence_score` | **0** | 状态与签名一格未动 |

定稿里 `VLM 草稿` / `low_confidence` / `请确认` 三类残留均为 0。

### 16.2 device_model 逐件按 PDF 封面原文登记

不按文件名猜，四件都回到 p1 原文核过：

| 样本 | 归档名 | 封面原文依据 | device_model |
| --- | --- | --- | --- |
| V146 | `CY74FCT399ATSOCT__cy74fct399t.pdf` | p1 首行 `CY74FCT399T` | `CY74FCT399T` |
| V271 | `DM3725CBC100__dm3725.pdf` | p1 首行 `DM3730, DM3725`，文件名带 DM3725CBC100 | `DM3725` |
| V256 | `BQ79652PAPRQ1.pdf`（签字简写名） | p1 器件行 `BQ79656-Q1, BQ79654-Q1, BQ79652-Q1` | `BQ79652-Q1` |
| V244 | `AM1802BZWTD3__am1802.pdf` | p1 `AM1802` | `AM1802` |

V256 的封面主标题只写族名 `BQ7965x-Q1`（全书仅 4 处），器件行里能核到
具体型号 `BQ79652-Q1`（全书 439 处），故取后者。签字名 `BQ79652PAPRQ1.pdf`
与语料实文件名 `BQ79652PAPRQ1__bq79652-q1.pdf` 不同，按 B2 的做法在
`b3_pdfs/` 下建硬链接（同一份字节），**不改签字的 file_name 一格**。

### 16.3 V256 五行的 condition 落进定稿

签字版的 `condition` 列**全为空**——那份导出于回填之前。定稿按 15.7 的
原图绑定结果写入五行，且不重抄一份条件表：`_make_b3_final.py` 直接
import 草稿生成器的 `CONDITION_BACKFILL`，与草稿共用唯一真源，
并断言两边逐字相同、五行互不相同、行数不符即退出。

原文断言用 v1.6 同一个 `nos()`，只对 `°C → oC` 做一次替换（PDF 文本层
把度数符号抽成 `o`，实测 p13 写作 `2V<VCELL<4.5V; TA=25oC`）；
落盘仍写 `°C`，因为 v1.6 只用 condition 做分组键、不做原文断言。

效果：判重键 `(样本, 符号, condition, 单位, 页码, min, typ, max)` 20 行
全唯一，V256 第 2、3 行（MIN/MAX 同为 -7.8 / 6.6）不再被判成重复占位。

### 16.4 签名口径：5 格待补签，机器不代签（第八轮当时的状态，已于第 17 节封卷）

这 5 格是签字之后新增的数据，PM 没看过，因此：

* 15 列签字值逐格照抄，`reviewer` 与 `row_status` 不动；
* 5 行 `entered_by=WB_Agent`（明确标出是 WB 按原图代录入），
  `approved_by` **留空**，`human_adjudication` 全部清空；
* 另出 `Batch3_B3_FINAL_TO_SIGN.xlsx`，把这 5 个 `condition` 格与对应
  `approved_by` 格标红，PM 打开即可补签；
* 待补签的稳定 ID 清单落在 `Batch3_B3_APPROVAL_PENDING.txt`（按
  `sample_no+file_name+evidence_page+symbol+parameter_name+min+typ+max+unit`
  九字段，不用行号）。

补签后按 B2 同一套 `load_approval_map` / `apply_approval` 流程继承，
不按行号、不自动补齐。**当前定稿是「待补签」状态，不是已封卷状态。**

### 16.5 v1.6 机检：两种模式都 OK=20

| 模式 | 页文本来源 | 溯源 | 结果 |
| --- | --- | --- | --- |
| PDF | PDF 原件 | 三处一致，PDF 实算哈希已比对 | **`OK=20`**，无 ERROR / SUSPECT / CANNOT_VERIFY |
| 离线 | `page_text_batch3_b3.json` | 三处一致，哈希跳过（非 PDF 模式） | **`OK=20`**，同上 |

原始 stdout：`b3_validation_raw/b3_final_pdf_mode.txt`、
`b3_validation_raw/b3_final_sidecar_mode.txt`。

### 16.6 本轮新增文件

`Batch3_B3_FINAL.csv` / `.xlsx`（19 列 20 行）、`Batch3_B3_FINAL_TO_SIGN.xlsx`、
`Batch3_B3_SIGNED_original.xlsx`、`Batch3_B3_notes_before_cleanup.txt`、
`Batch3_B3_APPROVAL_PENDING.txt`、`Batch3_B3_PDF_PROVENANCE.csv`、
`page_text_batch3_b3.json`、`Batch3_B3_regen_report.txt`、
`b3_validation_raw/`（两份）、`_make_b3_final.py`。

### 16.7 尚未做的事（第八轮当时的状态）

V256 五行 condition 的 PM 补签（`Batch3_B3_FINAL_TO_SIGN.xlsx` 红格）尚未完成，
封卷前必须补；B4（5 件）与 SCAN（3 件）仍未生成；33 件全部标完且 Reviewer
终审放行后，才更新 CodeUp 本地 main（`a11131a`）。两仓 main 本轮仍未动。

## 17. B3 封卷：5 处 PM 补签按稳定 ID 继承

### 17.1 签名来源与「最后一格」的事实核对

PM 2026-11-12 12:14 交回签好的 `Batch3_B3_FINAL_TO_SIGN.xlsx`，并说明
「最后一行好像填写不了，我已核对，授权你帮我填写」。据此逐格核对：

* 打开 PM 保存的原件（12:14:07 落盘，7,669 → 11,872 字节），
  **5 个签名格其实全部已有 `wuxiaoxian`，包括第 15 行**；
* 原始 XML 佐证：`O12..O15` 为 `<c r="O1x" s="2" t="s"><v>105</v></c>`，
  `O16` 为 `<c r="O16" s="3" t="s"><v>105</v></c>`；105 是共享字符串
  `wuxiaoxian`。第 15 行只有样式索引 `s="3"` 与上面四格 `s="2"` 不同，
  属录入方式差异，值本身确已写入；
* 结论：屏幕未刷新，文件里已经签上。**WB 没有代填任何一格，也未改动
  任何签名格**。授权仍留档：若日后发现该格确为空，可按此授权补填。

记录见 `Batch3_B3_approval_authorization.txt`（含签名源 SHA-256）。

### 17.2 稳定 ID 必须并入 condition

B2 的九字段稳定 ID 在 B3 上不够：V256 p13 的 `V(MAIN-AUX)` 第 2、3 行
MIN/MAX 完全相同（-7.8 / 6.6 mV），九个字段一模一样，唯一能区分的是
TEST CONDITIONS。若不并入 `condition`，字典会静默覆盖重复键——
又是一种 Fail-Open。因此 B3 的稳定 ID 取十字段（九字段 + `condition`）。

并入不会误放行：若 PM 改过 condition，ID 就对不上，脚本直接报
「签名落点与 WB 代录入行不一致」。

### 17.3 封卷断言与结果

| 项目 | 结果 |
| --- | --- |
| 签名源 | `Batch3_B3_FINAL_TO_SIGN.xlsx`，SHA-256 `306266374fa4535e20a650d458802d73af614d17663250798a40e6c11a1dc3c7`，11,872 字节 |
| 副本 | `Batch3_B3_FINAL_SIGNED.xlsx`，与签名源逐字节相同 |
| 签名值 | 5 处全部 `wuxiaoxian`（无其他签名者） |
| 落点校验 | `signed_ids` == `entered_by=WB_Agent` 行集合，均为第 11–15 行 |
| 封卷前后差异 | 只有 5 格 `approved_by`（空 → `wuxiaoxian`），其余 15 列一字未动 |
| `human_adjudication` | 全部为空 |

### 17.4 封卷后机检

| 模式 | 结果 |
| --- | --- |
| PDF（实算哈希） | **`OK=20`**，无 ERROR / SUSPECT / CANNOT_VERIFY，溯源三处一致 |
| 离线（sidecar） | **`OK=20`**，同上 |

原始 stdout 已覆盖更新：`b3_validation_raw/b3_final_pdf_mode.txt`、
`b3_validation_raw/b3_final_sidecar_mode.txt`；逐格差异报告为
`Batch3_B3_regen_report.txt`（生成器 `_b3_regen_report.py`）。

### 17.5 脚本的一处安全性修正

`_make_b3_final.py` 原先会重写 `Batch3_B3_FINAL_TO_SIGN.xlsx`。该文件补签后
就是唯一签名源，重跑会覆盖 PM 的签名。现已改为**不再生成 TO_SIGN**，
未签模板只保留在 git 历史 `fd0555c` 中。签名继承走
`load_approval_map` / `apply_approval`，与 B2 同一套，Fail-Closed 条件为：
源缺失 / 表头不符 / 行数不是 20 / 稳定 ID 重复 / 非 PM 签名 / 落点不一致。

### 17.6 尚未做的事

B4（5 件：V077 V130 V290 V347 V041）与 SCAN（3 件按 SOP 标 EXCLUDED）
仍未生成；33 件全部标完且 Reviewer 终审放行后，才把 CodeUp 本地 main
（`a11131a`）更新并 push。两仓 main 本轮仍未动。

## 18. 第十轮：B4 圈选台与 SCAN 登记表

Reviewer 批准 B3 封卷后放行 B4 与 SCAN。本轮不做定稿、不签名，
只交「可点选的圈选台 + 草稿」与「可复核的排除登记表」。

### 18.1 本轮交付物

| 文件 | 说明 | SHA-256（前 16） |
| --- | --- | --- |
| `Batch3_B4_Viewer.html` | B4 圈选台，5 件，左图右文，三条核查提示印在卡片上 | `141c45acd13cddaf` |
| `Batch3_B4_DRAFT.csv` | B4 草稿，14 行 × 15 列 | `1ead41a5a3db0bfc` |
| `Batch3_B4_generation.txt` | 生成器真实 stdout（逐件核心行/丢弃数/质量分层） | 见包内 |
| `Batch3_SCAN_MANIFEST.csv` | SCAN 三件登记表，11 列含溯源 | `e83bab493a851f58` |
| `Batch3_SCAN_Viewer.html` | SCAN 圈选台（仅登记，不进点选） | `186ef2220cf5a199` |
| `Batch3_SCAN_manifest.txt` | SCAN 登记摘要 | 见包内 |

B4 左图依赖 4 张裁图，已与 HTML 同包：`annotation_reports/V077/b3_ELC_p0040.png`、
`V077/b3_ROC_p0038.png`、`V130/b3_ELC_p0002.png`、`V290/b3_ELC_p0003.png`。
V347 / V041 被判排除，不出裁图。

### 18.2 三条 Reviewer 提示已落到网页上

提示写在每张卡片的黄色「核查提示」块里（`REVIEW_HINTS`），不是合集页脚：

* **V077** —— 请核实表格类型。该件 201 页、章节极多，先确认裁到的是电气特性表，
  而不是时序/引脚/封装表；
* **V130** —— 短文档不代表没有有效参数表。p2 是标准 ELECTRICAL CHARACTERISTICS 表
  （PARAMETER / TEST CONDITIONS / MIN / TYP / MAX / UNIT），参数名属 MOSFET 类；
* **V347** —— 核实是否为目标器件数据，而非引用资料。本件是 DSCC 军标 SMD（84185），
  TABLE I 即该器件本身的电气性能表，不是引用别处的资料。

### 18.3 B4 生成结果：两件出草稿，两件逐件排除

| 样本 | 核心行 | 丢弃 | 质量分层 | 处置 |
| --- | --- | --- | --- | --- |
| V077 | 5 | 11 | 好 | 进点选 |
| V130 | 5 | 3 | 需重点核（二轮兜底） | 进点选，参数名非白名单口径 |
| V290 | 4 | 4 | 好 | 进点选 |
| V347 | 0 | 0 | 无电气参数表 | `EXCLUDED`：表格版式不支持稳定还原行序 |
| V041 | 0 | 0 | 无文本层 | `EXCLUDED`：电气特性页为扫描图 |

草稿共 14 行。V077 的 `CVDD` / `RVDD` 各有两组取值（疑不同温度等级），
草稿里两条都留着并注明「请确认」——按 SOP 不替人挑，交 PM 判。

### 18.4 V130：白名单盲区与「二轮兜底」

首轮 `CORE_ORDER` 白名单只收供电/温度/电流/功耗/输入电压（当初为电源类器件所定），
MOSFET 的 `BVDSS` / `RDS(on)` / `Ciss` 不在其中，导致 V130 一行都没留下、
被误判成「无法定位电气参数表」。核实 p2 后确认该表有效，于是加二轮兜底：

* `CORE_ORDER_EXT` 覆盖击穿/耐压、阈值、导通电阻、漏电流、电容、跨导、
  失调/正向压降、增益/输入阻抗、开关时间九类一等电气特性；
* **只在首轮一行都没留下时才跑**（`pick_core_ext`），已能出草稿的样本行为完全不变；
* 命中的行在 `notes` 里写明「非白名单核心参数（一等电气特性），WB 建议，请 PM 定夺」，
  质量分层标「需重点核（二轮兜底）」，不冒充白名单口径。

### 18.5 V347：逐闸门诊断与「属硬凑」的判定

先修表题正则：军标写法是 `TABLE I. Electrical performance characteristics.`，
老正则要求 `characteristics` 紧跟 `electrical`，中间插了 `performance` 就命中不了；
已支持 `TABLE <罗马号>` 前缀与 `performance` 插入。

修完仍是 0 行，逐闸门诊断结果：`NUMCOL=2`、`KIND_TITLE=True`、
`title_anchor_lines=[22]`、`has_table_header=False`、`_page_table_signatures=0 张`。
表头顺序是 `Test / Symbol / Conditions / Group A subgroups / Device type /
Limits(Min,Max) / Unit`——`UNIT` 在 `MIN/MAX` 之前，而表头判定只向后看
`HEADER_WINDOW=8`，取不到 `MARK_HEAD_WORDS`。

更关键的是版式本身：同一符号按 Group A subgroup / Device type 拆成 2~4 行。
例如 `IIO` 的上限按 `01,02 / 03 / …` 分别是 3、5、6、20、30、40 μA。
手工裁图实测 VLM 只能给出「每符号一行」，并固定取 `01,02` 那一行，
等于把器件类型差异抹平。**这是硬凑，不是提取**，因此按 SOP 直接排除，
理由写进 `EXCLUDED_REASON`：确为目标器件数据，但版式不支持稳定还原行序，
需 SMD 专用规则后再做。

### 18.6 V041：部分页扫描 ≠ 整本无文本层

实测 16 页里 6 页无文本层，有文本层的 10 页是 `PACKAGE OPTION ADDENDUM` /
`PACKAGE MATERIALS` / `PACKAGE OUTLINE` / `LAND PATTERN` / `STENCIL DESIGN` /
免责声明，其中的 MIN/MAX 是机械尺寸公差，不是电气参数；电气特性在 p2~p4 的扫描图里。

原来的措辞统一写成「全书 N/N 页无文本层」，对 V041 不成立。现按两分支判定：
`blank == npages` 才说全书无文本层；否则明说「电气特性页是扫描图，
其余页虽有文本层但未定位到参数表」。判据不变——只要有任意一页有文字，
就不能拿「无文本层」当排除理由。

### 18.7 SCAN：把 EXCLUDED 从结论变成可复核证据

`S01 / S02 / S03` 不跑 VLM，直接登记（`_make_scan_manifest.py`）：

| 样本 | 文件 | 页数 | 字节 | 无文本层页 | 判定 |
| --- | --- | --- | --- | --- | --- |
| S01 | `CY74FCT162827CTPAC__CYPRS379-1.pdf` | 6 | 149,887 | 6 | `EXCLUDED` |
| S02 | `ATOPA4343NA_2K5__BURRS00055-1.pdf` | 11 | 677,523 | 11 | `EXCLUDED` |
| S03 | `32P4752-CGT__SISYD006-4-73.pdf` | 53 | 1,502,553 | 53 | `EXCLUDED` |

理由统一为 `EXCLUDED: 无 OCR 能力，无法建立 Gold`。生成器带硬断言：
若 `blank_pages != page_count` 直接 `SystemExit`，不允许拿「无 OCR」当万能理由。
`sha256 / page_count / size_bytes / blank_pages` 全部从磁盘实算，可独立复核。

### 18.8 措辞统一：十字段稳定 ID（含 condition）

`Batch3_B3_APPROVAL_TARGETS.txt` 原来写「九字段稳定 ID 匹配」，与 17.2 的口径不一致。
第 4 行已改为「十字段稳定 ID（九字段 + condition）匹配，不按行号」。
该文件由 `_make_b3_final.py` 生成，重跑即产新措辞；落盘后与手工同步文本逐字节一致。

### 18.9 封卷件字节零漂移：write_xlsx 加内容幂等

重跑生成器时发现 `Batch3_B3_FINAL.xlsx` 的 SHA-256 会变。拆包比对：
`xl/worksheets/sheet1.xml` 逐字节相同，只有 `docProps/core.xml` 的
`dcterms:created/modified` 变了——openpyxl 每次 `save()` 都写当前时刻。
数据一字未改，却让封卷件整包哈希漂移，这在审计上不可接受。

处置分两步：

1. 先把封卷字节复原为 `b437658dc8d2f8f39b4fdc44ea0b5fb233c1adf3dab72ec2df846c80f7f43035`
   （与第九轮提交 `92f170c` 内的版本一致）；
2. 给 `write_xlsx` 加内容签名（`_wb_signature`：表名/冻结/筛选/列宽 + 每格值与填充色、加粗）
   比对——一致就丢弃临时文件、保留原字节，不一致才原子替换。

此后三件套重跑结果：

| 文件 | SHA-256 | 与封卷前 |
| --- | --- | --- |
| `Batch3_B3_FINAL.csv` | `b940e2e4802d505f69728cbf313f844392c073bd7e2b2c5a7a47d6e36e019b12` | 逐字节相同 |
| `Batch3_B3_FINAL.xlsx` | `b437658dc8d2f8f39b4fdc44ea0b5fb233c1adf3dab72ec2df846c80f7f43035` | 逐字节相同 |
| `Batch3_B3_FINAL_TO_SIGN.xlsx` | `306266374fa4535e20a650d458802d73af614d17663250798a40e6c11a1dc3c7` | 逐字节相同 |
| `Batch3_B3_FINAL_SIGNED.xlsx` | `306266374fa4535e20a650d458802d73af614d17663250798a40e6c11a1dc3c7` | 逐字节相同 |

生成器 stdout 对应行：`xlsx 写入：未改写（内容与磁盘一致，保留原字节）`。

同一轮还发现 `page_text_batch3_b3.json` 也只差一个 `generated_at` 字段（正文逐样本
完全一致，双模式机检输出逐字节相同）。同一处缺陷，同一套处置：若除 `generated_at`
外内容一致，就保留原字节不重写。生成器 stdout 对应行：
`sidecar：未改写（除 generated_at 外内容一致，保留原字节）`。

### 18.10 本轮回归

| 项目 | 结果 |
| --- | --- |
| v1.6 PDF 模式（`Batch3_B3_FINAL.csv`） | `OK=20`，无 ERROR；输出与第九轮逐字节相同 |
| v1.6 离线模式 | `OK=20`，无 ERROR；输出与第九轮逐字节相同 |
| 合成回归 | `PASS=43 FAIL=0 SKIP=0` |
| 签名继承 | 5 处落在第 11–15 行，`signed_ids == entered_by` |
| B4 网页自检 | 三条提示均在（`hint-review` × 3）、V347/V041 逐件理由已覆盖自动措辞、不再出现「全书 16/16 页无文本层」 |
| 草稿行数 | 14 行（V077=5、V130=5、V290=4） |

### 18.11 尚未做的事

B4 的 14 行仍需 PM 逐格对左图核并签字；SCAN 三件只登记、不进点选。
33 件全部标完且 Reviewer 终审放行后，才把 CodeUp 本地 main（`a11131a`）
更新并 push。两仓 main 本轮仍未动。

## 19. 第十一轮：封卷保护改硬哈希、排除话术按事实分类、B4 条件绑定

Reviewer 指出两处必须修：封卷保护仍是 Fail-Open，B4 存在严重条件缺失。
本轮不封 B4（草稿刚修完，等 PM 点选），也不动 B3 的任何已封卷字节。

### 19.1 封卷保护：从「内容签名软比较」改为「硬哈希拦截」

上一版 `_wb_signature()` 只比对值/填充/列宽，有两个洞：

* **只改数字格式**——值一模一样、字节变了，签名相同 → 判成"内容一致"，静默跳过；
* **增删工作表**——非活动表根本不在签名范围里 → 同样被放过。

两种情况都会让封卷件的字节已经变了、生成器还报告"未改写"。现在整段逻辑删掉，
换成登记冻结哈希的闸门 `guard_sealed()`：

| 情形 | 行为 |
| --- | --- |
| 未登记（本就不是封卷件） | `write`，正常生成 |
| 哈希 = 登记值 | `skip`，原字节保留 |
| 哈希 ≠ 登记值 | `SystemExit`，绝不自动替换 |
| 已登记但登记表里哈希为空 | `SystemExit`，不默认放行 |
| 封卷件缺失 | `SystemExit`，不许凭生成器重造 |
| 路径存在但读不出字节 | `SystemExit`（无法读取分支） |

登记表 `SEALED_SHA` 现在覆盖 4 件：`Batch3_B3_FINAL.csv`、`Batch3_B3_FINAL.xlsx`、
`Batch3_B3_FINAL_TO_SIGN.xlsx`、`page_text_batch3_b3.json`。签名源在启动时也要过闸门——
生成器不写它，但必须能发现它被动过。

### 19.2 七场景回归（`_test_seal_guard.py`，12 项断言全 PASS）

| # | 场景 | 期望 | 结果 |
| --- | --- | --- | --- |
| 1 | 哈希与登记一致 | `skip` 且字节不动 | PASS |
| 2 | 只改数字格式（值不变） | 退出「拒绝自动替换」 | PASS |
| 2b | 该场景确实只改了字节 | 证明老逻辑会误判一致 | PASS |
| 3 | 新增工作表 | 退出 | PASS |
| 3b | 删除工作表 | 退出 | PASS |
| 4 | 文件损坏（非 zip） | 退出 | PASS |
| 4b | 路径存在但读不出字节 | 退出（无法读取分支） | PASS |
| 5 | 封卷件被删 | 退出（不许重造） | PASS |
| 6 | 未登记文件 | `write`，不误伤草稿 | PASS |
| 7 | 登记缺哈希 | 退出（不默认放行） | PASS |
| 8 | 真实 `Batch3_B3_FINAL.xlsx` | 与登记一致 | PASS |
| 8b | 真实件过闸门 | `skip` | PASS |

原始输出：`Batch3_seal_guard_test.txt`（`PASS=12, FAIL=0`）。

另做了一次**真实件负向验证**：复制 `Batch3_B3_FINAL.xlsx`、只把 `A2` 的数字格式改成
`0.000000`（值仍是 `V146`），闸门报「封卷件字节与登记不一致，拒绝自动替换」；
原件本身过闸门返回 `skip`。

实跑 `_make_b3_final.py` 的输出：

```
CSV 写入：未改写（封卷件哈希与登记一致，保留原字节）
xlsx 写入：未改写（封卷件哈希与登记一致，保留原字节）
sidecar 写入：未改写（封卷件哈希与登记一致，保留原字节）
```

四件封卷产物前后 `sha256sum -c` 全 OK，一个字节没动。

### 19.3 排除理由按事实分三类

「一刀切」会写出与事实不符的理由：V347/V041 都有文本层，说「全书无文本层」是假的。
按 Reviewer 定稿口径拆开，并把三类话术写成常量，供后续复用：

| 类别 | 话术 | 适用 |
| --- | --- | --- |
| 全书无文本层 | `EXCLUDED: 全书无文本层；当前 Gate6A 流程无可用 OCR 取证路径，无法建立可验证 Gold` | S01 S02 S03 |
| 电气特性页为扫描图 | `EXCLUDED: 电气特性页为扫描图；当前 Gate6A 流程无可用 OCR 取证路径，无法建立可验证 Gold` | V041（16 页里 6 页无文本层）、V328 |
| 版式无法还原行序 | `EXCLUDED: 版式不支持稳定还原行序，当前流程无法建立可验证 Gold；需 SMD 专用规则后重评` | V347（DSCC 84185，按 subgroup 拆行） |

V222 不属这三类：它 9 页全是封装/板图/卷带资料，属「文档内无标准参数表」，
理由照旧，不改写。圈选台的状态下拉也同步换成这三条，避免手输时又冒出旧措辞。

### 19.4 B4 条件绑定（原文逐条核过）

**V077**（AM1707，p38 Recommended Operating Conditions）：同一张表里 CVDD 与 RVDD
各给两套条件，VLM 只抄数值不抄条件。现按版本分行绑定：

| 行 | 值 | condition |
| --- | --- | --- |
| CVDD | 1.14 / 1.2 / 1.32 | `375 MHz version` |
| CVDD | 1.25 / 1.3 / 1.35 | `456 MHz version` |
| RVDD | 1.14 / 1.2 / 1.32 | `375 MHz version` |
| RVDD | 1.25 / 1.3 / 1.35 | `456 MHz version` |
| DVDD | 1.71 / 1.8 / 1.89 | `Supply voltage, I/O, 1.8V`（与 3.3V I/O 那行区分） |

网页上该件有红底「必须核对」块，明确写了两组值各属哪个版本。

**V290**（DS9638，p3）：VIL 两行按温度档绑定 —— 0.8 V ↔ `0°C to +70°C`，
0.5 V ↔ `−55°C to +125°C`（原文用 U+2212 减号，照录）。II 行原文条件是
`VCC = Max, VI = 5.5V`，文本层抽成 `V CC = Max, VI Max = 5.5V`，未擅自补录，
在网页提示里交 PM 定夺。

**V130**：二轮兜底选出的 5 行逐行加前缀 `【非白名单参数·需 PM 决定是否纳入】`，
并在卡片上加「二轮兜底：非白名单」标签，不再只在样本级说明里提一句。

**可核性**：回填完立刻回原文断言——每行 condition 归一化后必须能在证据页文本里
找到，否则 `SystemExit`。三条新绑定都是在通过该断言后才落盘的。

### 19.5 33 件总清单（`Batch3_MASTER_INVENTORY.csv`）

| 批次 | 件数 | Gold 行数 |
| --- | --- | --- |
| B1 | 6 | 23（已定稿） |
| B2 | 6 | 30（已定稿） |
| B3 | 4 + 2 EXCLUDED | 20（已封卷） |
| B4 | 3 待签 + 2 EXCLUDED | 14（待 PM 点选） |
| SCAN | 3 EXCLUDED | 0 |
| Batch 2 已完成件 | 6 | 24 |
| 诊断件 V022 | 1（DIAGNOSTIC_ONLY） | 0 |
| **合计** | **33** | **111** |

清单生成器带三条硬断言：33 件唯一、无未归类项、行数合计与各批 CSV 逐一相符。
计划的批次表只有 32 行，第 33 件是 Gate 6A 指定的诊断检查点 V022（EVM 板卡手册，
不参与 Gold 分母），两处口径由此对齐。

### 19.6 本轮回归

| 项目 | 结果 |
| --- | --- |
| 封卷闸门 | `PASS=12, FAIL=0` |
| B3 封卷件 | 4 件哈希全 OK，逐字节未动 |
| B4 生成 | 14 行（V077=5、V130=5、V290=4），条件行 7 条 |
| B4 网页自检 | 三类话术正确、旧话术清零、高亮块 2 处、非白名单标签与逐行标记齐全 |
| 总清单 | 33 件、111 行，断言通过 |

### 19.7 尚未做的事

B4 的 14 行等 PM 点选签字；签完后才做 19 列 FINAL 与封卷。
33 件全部签完且 Reviewer 终审放行后，才把 CodeUp 本地 main（`a11131a`）
更新并 push。两仓 main 本轮仍未动。

## 20. 第十二轮：B4 封卷（14 行定稿，双模式 OK=14）

### 20.1 认哪一份签字件

`D:\Documents\Downloads` 下同时存在两份 `Batch3_B4_ANNOTATED`：

| 文件 | 保存时间 | 行数 | 有 condition 的行 | 处置 |
| --- | --- | --- | --- | --- |
| `Batch3_B4_ANNOTATED.xlsx` | 13:48:07 | 14 | **0** | 条件缺失那版草稿的签字副本，作废 |
| `Batch3_B4_ANNOTATED (1).xlsx` | 14:04:23 | 14 | **7** | 本轮签字件，以此为准 |

旧件 `SHA-256 6b71cbd16193e9ab7dd348acc732327e0b15d4226e463265b77dfc91e4d29979`，
condition 一列全空——如果拿它封卷，等于把 Reviewer 刚指出的「严重条件缺失」
原样写进 Gold。故只本地留档，不进交付包，避免两份签字件并存造成口径冲突。

认定件 `SHA-256 cc1b2ae030ee93cecce22e42a9edbbd8888aa514b67c7573d7ca111427cbc7b2`，
14 行 × 15 列，`row_status` 全 `CONFIRMED`，`reviewer` 全 `wuxiaoxian`，
condition 与草稿逐格一致。

### 20.2 notes 清理：只清模型话术，不动 PM 的裁定信息

V130 那五行带着前缀 `【非白名单参数·需 PM 决定是否纳入】`，那是「这行要不要进
Gold」的依据，一句话清掉就丢了。规则改为：

```
notes = 原有【…】前缀（若有） + 「人工已核对 PDF 原图并确认」
```

结果：9 行是纯 `人工已核对 PDF 原图并确认`，5 行（V130）带前缀。
生成器带断言：notes 必须以该句结尾、且不得残留 `VLM` 字样。

### 20.3 approved_by 为什么整列为空

B1/B2/B3 的规矩：只有「WB 代录入」的行，才由 PM 在 19 列 TO_SIGN 上逐格补签
`approved_by`，WB 再按稳定 ID 继承；其余行的签字凭据是签字件本身
（B3 就是 5 格有值、15 格为空）。本轮 B4 没有代录入任何一格——condition 是
生成器按原图回填、PM 在签字件里看到并确认整行 `CONFIRMED`——签字件也没有
`approved_by` 列。因此该列留空，**没有把 `reviewer` 复制成 `approved_by`**。

### 20.4 定稿与机检

| 项目 | 结果 |
| --- | --- |
| 行数 / 样本 / 列数 | 14 / 3 / 19 |
| device_model | V077=`AM1707`、V130=`CSD17505Q5A`、V290=`DS9638`（均取封面原文） |
| condition | 7 行有值（V077 五行、V290 两行）；V130 无（该表无 CONDITIONS 列） |
| v1.6 PDF 模式 | **`OK=14`**，无 ERROR |
| v1.6 离线模式 | **`OK=14`**，无 ERROR |

一处如实记录：`V290 VIH` 的 min 原文是 `2.0`，PM 的 Excel 存成数值 `2`。
定稿照签字原样保留 `2`，没擅自改回 `2.0`——值相同，且不该动已签的格。

### 20.5 封卷登记与闸门自证

`_make_b4_final.py` 内置 `SEALED_SHA_B4`，复用 B3 的 `guard_sealed`
（11 轮改的硬哈希闸门），登记 4 件：

| 文件 | SHA-256 |
| --- | --- |
| `Batch3_B4_FINAL.csv` | `2db19c9753f053dda83f4a110fc7099e55797fb22738c3f91b66e03c5c0f551d` |
| `Batch3_B4_FINAL.xlsx` | `972b23f79408da8a568409204db7f25f2ee595e08ef3fc8b602a6cfb6aea86c1` |
| `page_text_batch3_b4.json` | `43e42b3c831b2fcf1df5bb94eb0ca4332937e5af84d6976d671f981315f59aef` |
| `Batch3_B4_ANNOTATED.xlsx` | `cc1b2ae030ee93cecce22e42a9edbbd8888aa514b67c7573d7ca111427cbc7b2` |

登记后重跑生成器，三处均输出「未改写（封卷件哈希与登记一致，保留原字节）」，
哈希不变。这就是 19.1 那套闸门在真实件上的第二次自证（第一次是 B3）。

签字凭据另存 `Batch3_B4_approval_record.txt`（含两份签字件的对比与作废理由）。

### 20.6 33 件总清单状态更新

B4 三件从「待签字」改为「已定稿」，数据源从 `Batch3_B4_DRAFT.csv` 换成
`Batch3_B4_FINAL.csv`；件数仍 33，Gold 行数合计仍 111（B4 仍记 14 行）。

### 20.7 尚未做的事

33 件里 29 件已定稿（含 4 件 EXCLUDED 与 3 件 SCAN、1 件诊断件不参与分母），
没有未签的 Gold 行。Reviewer 终审放行后，才把 CodeUp 本地 main（`a11131a`）
更新并 push。两仓 main 本轮仍未动。

---

## 21. Reviewer 三处 P0 修复（第十三轮）

复审给出三条 P0：V130 五行缺 TEST CONDITIONS、B4 签字源入口没走硬哈希闸门、
33 件总清单把诊断件与排除件混在一张账上。本节记录修复与验证方式。

### 21.1 P0-1：V130 五行的 TEST CONDITIONS

原图 `CSD17505Q5A__csd17505q5a.pdf` 第 2 页 ELECTRICAL CHARACTERISTICS 表，
Conditions 列逐字照录（不做同义改写）：

| Symbol | TEST CONDITIONS |
| --- | --- |
| `BVDSS` | `VGS = 0V, IDS = 250μA` |
| `IDSS` | `VGS = 0V, VDS = 24V` |
| `IGSS` | `VDS = 0V, VGS = 20V` |
| `VGS(th)` | `VDS = VGS, IDS = 250μA` |
| `RDS(on)` | `VGS = 4.5V, IDS = 20A` |

两道机械保证：

* **`MUST_HAVE_COND`**：`{"V130": {BVDSS, IDSS, IGSS, VGS(th), RDS(on)}}`。
  出草稿前，这五个符号缺任一 condition、或某个符号整行缺失，一律 `SystemExit`。
* **回原文核断言**：condition 必须能在该证据页文本里找到。归一化只做
  `°→o` 与空白折叠；本轮新增一道「去掉全部空白」的兜底 —— PDF 文本层会把下标
  拆成 `V C C = Max`，这是排版空隙而非差异。

顺带查出两件事，一并处置：

1. **V130 的 RDS(on) 原表有两行**：`VGS = 4.5V, IDS = 20A` → 3.7 / 4.6 mΩ，
   `VGS = 10V, IDS = 20A` → 2.9 / 3.5 mΩ。5 行预算只收了 4.5 V 那行，
   已在圈选台 `EXTRA_ROWS_NOTE` 里写明未收进草稿的是哪一行，供 PM 决定是否补收。
2. **V290 的 `II` 是同一类缺陷**：原表 Conditions 写着 `VCC = Max, VI Max = 5.5V`，
   VLM 漏抄，已按原文补录；同表 `VIH`（Input Voltage HIGH）原表本来就没给条件，
   保持为空**不是漏填**，`WARN_BANNER` 已写明，避免下次又被当成缺陷。

### 21.2 P0-2：签字源入口闸门

`_make_b4_final.main()` 的第一件事就是
`B3.guard_sealed(SIGNED, SEALED_SHA_B4)`，通过之后才 `SIGNED.exists()` 与读内容。
闸门失败包一层 `SystemExit("签字源校验失败，拒绝继续：…")`，错误前缀固定，便于断言。

负向回归 `_test_b4_signed_gate.py`（报告 `Batch3_b4_signed_gate_test.txt`），
**13 项断言全 PASS**：

| 用例 | 期望 | 结果 |
| --- | --- | --- |
| 1 登记一致 | 放行并跑通 `main()` | PASS |
| 1a 放行后 V130 五行 condition 非空 | 5/5 | PASS |
| 1b V130 五行 `entered_by=WB_Agent` | 5/5 | PASS |
| 1c V130 五行 notes 带补录前缀 | 5/5 | PASS |
| 1d V290 `II` 条件已补 | `VCC = Max, VI Max = 5.5V` | PASS |
| 2 篡改后哈希确实变了 | 是 | PASS |
| 2a 篡改签字源 | 拦下 | PASS |
| 2b **是闸门拦的（先于内容校验）** | 错误以「签字源校验失败」开头 | PASS |
| 2c 拦下后没有产出 FINAL | 无文件 | PASS |
| 3 签字源缺失 | 拦下（不允许凭生成器重造） | PASS |
| 4 登记里哈希为空 | 拦下（不默认放行） | PASS |
| 5 未登记的文件名 | 放行（`write`） | PASS |
| 6 真实签字源 vs 出厂登记 | 一致 | PASS |

**2b 是这套测试的关键**：篡改的是 `confidence_score` 一个数值格，
`load_signed()` 完全能通过 —— 如果报错来自内容校验而不是闸门，就说明闸门放得太晚。
实测错误信息以「签字源校验失败」开头，证明闸门确实在读内容之前。

### 21.3 P0-3：33 件总清单改四分法

此前按 `batch` 分组，V022（诊断件）与 V328（排除件）落在同一张账上，
Reviewer 判为分类错误。改为 Reviewer 定稿的四分法：

| 分类 | 件数 | 成员 |
| --- | --- | --- |
| 已定稿 Gold | **25** | Batch2 6 + B1 6 + B2 6 + B3 4 + B4 3 |
| 排除 Gold 候选 | **4** | V222 / V328 / V041 / V347 |
| SCAN 排除 | **3** | S01 / S02 / S03 |
| 诊断件 | **1** | V022 |
| 合计 | **33** | |

`_make_master_inventory.py` 加五条硬断言：

1. 四类并集 = 全表，不允许出现四类之外的取值；
2. 各类件数恰为 25 / 4 / 3 / 1，四类合计 33；
3. 四类样本集合两两无交集（互不重叠）；
4. 成员集合写死比对：排除候选 `{V222,V328,V041,V347}`、SCAN `{S01,S02,S03}`、
   诊断 `{V022}` —— 分类再漂就直接报错；
5. Gold 内部按批次 6+6+6+4+3。

实跑结果：合计 33 件，Gold 行数 111，与各批 CSV 逐一相符。

### 21.4 封卷登记主动撤销（如实记录）

V130 的 5 条 condition 与 V290 的 `II` 是 **WB 按原图补录、PM 尚未复核**，
不能当成「已签内容」登记哈希。处置：

* `SEALED_SHA_B4` 只保留签字源一件
  （`Batch3_B4_ANNOTATED.xlsx` = `cc1b2ae030ee93cecce22e42a9edbbd8888aa514b67c7573d7ca111427cbc7b2`）；
* 上一轮登记的 FINAL 三件移入 `NO_LONGER_SEALED`，留档备查、不再作为放行依据；
* 补录行标 `entered_by=WB_Agent`，notes 前置
  `【condition 由 WB 按原图补录，待 PM 复核】`；
* `approved_by` 仍整列为空 —— 不代签、也不假装签过。

也就是说：**本轮定稿处于「已修复、待重签」状态**，封卷要等 PM 在补录版上重新签字。

### 21.5 与上一版定稿的逐格差异

干跑比对新旧 19 列定稿：14 行结构不变，仅 6 行（V130 五行 + V290 `II`）
各有 3 格变化，合计 **18 格**，全部落在 `condition` / `notes` / `entered_by`：

| 行 | condition | notes | entered_by |
| --- | --- | --- | --- |
| V130 BVDSS | `'' → VGS = 0V, IDS = 250μA` | 前置补录前缀 | `'' → WB_Agent` |
| V130 VGS(th) | `'' → VDS = VGS, IDS = 250μA` | 同上 | 同上 |
| V130 RDS(on) | `'' → VGS = 4.5V, IDS = 20A` | 同上 | 同上 |
| V130 IDSS | `'' → VGS = 0V, VDS = 24V` | 同上 | 同上 |
| V130 IGSS | `'' → VDS = 0V, VGS = 20V` | 同上 | 同上 |
| V290 II | `'' → VCC = Max, VI Max = 5.5V` | 同上 | 同上 |

V077 五行、V290 `VIL` 两行与 `VIH`、以及所有 min/typ/max/unit 一格未动。

### 21.6 PM 直接在签字件上改稿（15:30 / 15:32）

21.5 之后，PM 没有在草稿上重签，而是**直接在 19 列定稿件上动手**，分两次保存：

| 时间 | 动作 |
| --- | --- |
| 15:30:11 | 删除 6 行 |
| 15:32:56 | 剩余 8 行逐格补签 `approved_by` |

被删的 6 行，正是上一轮由 WB 按原图补录 condition 的那些行：

| 样本 | Symbol | 值 | 删除前的 condition |
| --- | --- | --- | --- |
| V130 | `BVDSS` | 30 / – / – V | WB 补录 `VGS = 0V, IDS = 250μA` |
| V130 | `VGS(th)` | 1 / 1.3 / 1.8 V | WB 补录 `VDS = VGS, IDS = 250μA` |
| V130 | `RDS(on)` | – / 3.7 / 4.6 mΩ | WB 补录 `VGS = 4.5V, IDS = 20A` |
| V130 | `IDSS` | – / – / 1 μA | WB 补录 `VGS = 0V, VDS = 24V` |
| V130 | `IGSS` | – / – / 100 nA | WB 补录 `VDS = 0V, VGS = 20V` |
| V290 | `II` | – / – / 50 μA | WB 补录 `VCC = Max, VI Max = 5.5V` |

读法很清楚：PM 不接受「由 WB 补录条件」的行，直接删除，而不是逐格复核后签字。
这是 PM 的处置权；WB 不做二次解释，只如实记录并让下游跟着变。

签字件终态：

| 项目 | 值 |
| --- | --- |
| 文件 | `Batch3_B4_FINAL.xlsx` |
| 保存时间 | 2026-11-12 15:32:56 |
| SHA-256 | `685caff0da9c568658057c5b2d1a4949abea506589de12846709e78d984bd28e` |
| 字节 | 10616 |
| 结构 | 1 个工作表、19 列、表头 + **8 行**、无隐藏行 |
| 行状态 | 8/8 `CONFIRMED` |
| 签字 | `reviewer` = `approved_by` = `wuxiaoxian`（8/8） |
| `entered_by` | 全空（PM 亲手签，不经 WB 代录继承） |

定稿内容：V077 五行（CVDD/RVDD 按 375·456 MHz 分行、DVDD 锚 1.8V I/O）+
V290 三行（VIH、VIL 两档）。

### 21.7 定稿事实源切换与旧链路停用

签字件变成 `FINAL.xlsx` 本身之后，原链路（`ANNOTATED` → `FINAL`）会按 14 行重造，
把 PM 的删行与签名一起覆盖。处置：

* 新增 `_final_from_signed_xlsx.py`：以签字 xlsx 为唯一事实源，只向下游派生
  `Batch3_B4_FINAL.csv` / `page_text_batch3_b4.json` / `Batch3_B4_PDF_PROVENANCE.csv`，
  **不回写 xlsx 一个字节**；
* 脚本内置 `SIGNED_SHA`：签字件字节一变就停，不许拿来历不明的定稿件派生；
* `_make_b4_final.py` 顶部加 `SUPERSEDED` 停用闸，一跑就 `SystemExit` 并指向新脚本；
* 落盘后回读断言：19 列同序、8 行、每格与 xlsx 完全一致；CSV 换行统一 BOM + CRLF
  （与 B3/B4 历史定稿一致，不混裸 LF）。

闸门回归 `_test_b4_signed_gate.py` 扩到 **15 项断言全 PASS**，新增用例 7/7a
专门验证「停用闸生效、且不产出任何文件」。

### 21.8 机检与产物哈希

| 项目 | 结果 |
| --- | --- |
| v1.6 PDF 模式（`--pdf-dir b4_pdfs`，实算哈希） | **`OK=8`**，无 ERROR |
| v1.6 离线模式（用随包 sidecar） | **`OK=8`**，无 ERROR |
| 数值分类 | 数值 18 |

| 产物 | SHA-256 |
| --- | --- |
| `Batch3_B4_FINAL.xlsx` | `685caff0da9c568658057c5b2d1a4949abea506589de12846709e78d984bd28e`（签字件，未改写） |
| `Batch3_B4_FINAL.csv` | `096ff7c068d01bbedeb0d392e1df9bad12e47baa0c45acfe3fe28ef2618927f9` |

### 21.9 由此产生的口径变化（须 Reviewer 判定）

1. **B4 由 14 行 3 件降为 8 行 2 件。**
2. **V130 在 Gold 里不再有任何行**，整件移入「排除 Gold 候选」。排除理由属
   **范围决定**（PM 不纳入），不是流程能力不足，因此新增第四类话术：

   ```
   PM 裁定不纳入（非白名单参数，签字件已删除该件全部行）
   ```

   这与 Reviewer 定稿的三类（版式不支持 / 扫描图 / 无文本层）性质不同，
   **是否接受该分类由 Reviewer 判定**，本轮不自行并入那三类。
3. 33 件四分法件数由 **25 / 4 / 3 / 1 → 24 / 5 / 3 / 1**；
   Gold 内部批次 6+6+6+4+3 → **6+6+6+4+2**。
4. Gold 行数合计 **111 → 105**。
5. `_make_master_inventory.py` 的断言同步改为 24/5/3/1 与 6+6+6+4+2，
   并把 `V130` 写进 `EXPECT_EXCL` 固定集合 —— 分类再漂就直接报错。
