# Batch 3 复审包 · B1 签字定稿 + B2 草稿（含 V003 错页修复）

分支 `feat/gate6a-batch3`，**不动 main、不动 `feat/gate6a-annotation`**。
B1 已有人工签字，B2 仍是草稿，机器没有替人确认任何一行。
2026-11-12 追加：Reviewer 指出 B2 的 V003 抓错页，已重定位重截，详见第 8 节。
2026-11-12 第二轮追加：修正 V304 表头归属、补齐人工授权链、统一真源口径与两仓
main SHA，详见第 9 节。

## 0. 一句话结论

**最终全绿**：最终定稿 `Batch3_B1_RESIGNED.xlsx` / `.csv`（23 行 × 19 列），
v1.6 双模式 `OK=23 / SUSPECT=0 / ERROR=0`，退出码 0。
23 行全部 `CONFIRMED` + `reviewer=wuxiaoxian`。

过程留痕不做删改：最初签字版 `OK=20 / SUSPECT=1 / ERROR=2`（退出码 1），
按 PDF 原文给建议修正版后 `OK=23`，再由 PM 授权把那 3 行重新签字，
最后按 Reviewer 第二轮意见补齐授权链与表头归属后复跑仍 `OK=23`。
四个版本、八份原始 stdout 全部在本包里，详见 `Batch3_B1_validation_report.txt`。

## 1. 真源与行数

- **唯一真源（最终定稿）：`Batch3_B1_RESIGNED.xlsx`**，23 行 × 19 列；
  同名 `.csv` 与之逐格同源（UTF-8 BOM）。`reviewer=wuxiaoxian` 全部签名、
  `row_status=CONFIRMED`，v1.6 双模式全绿。
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

## 3. 机检结果（v1.6，八份原始输出在 `b1_validation_raw/`）

| 版本 | PDF 模式（实算哈希） | 离线模式（sidecar） |
| --- | --- | --- |
| 签字版 23 行 | `OK=20 SUSPECT=1 ERROR=2` 退出码 1 | 同左，退出码 1 |
| 建议修正版 23 行（3 行未签） | `OK=23 ERROR=0` 退出码 0 | 同左，退出码 0 |
| 重签版 v1 23 行（全签） | `OK=23 ERROR=0` 退出码 0 | 同左，退出码 0 |
| **最终定稿 23 行 × 19 列** | **`OK=23 ERROR=0` 退出码 0** | **同左，退出码 0** |

新增 `approved_by` / `entered_by` 两列、`table_title` 与 `notes` 的修正
均不影响任何一条机检判据；最终定稿的复跑是在改完之后重新实跑的，不是沿用旧结论。

验证器输入由 `_build_batch3_verify_inputs.py` 生成：型号取 PDF 第 1 页标题行，
SHA-256 / 页数从磁盘原件实算，页文本逐页抽取，PDF 模式再用原件复算一遍。
**没有关掉任何一条判据**（provenance 缺失、空字段跳过、PDF 降级、哈希不符仍读文本、
损坏 PDF 退化，这七条 fail-open 仍然全部封着）。

局限：三处溯源写的是同一份实测数据，不是三个独立来源；真正独立的第三方证据
是磁盘 PDF 原件。这一条请复核者知悉。

## 4. B2 草稿（待点选）

`Batch3_B2_Viewer.html` + `Batch3_B2_DRAFT.csv`：6 件 / 30 行 / 16 张裁图，
样本 `V038 V320 V346 V242 V003 V011`，每件只留 5 行核心参数。

**V003 已按第 8 节重截重出**：原 5 行是 p14 的 Pin Attributes 术语解释（无参数），
现替换为 p101/p105/p106 的 5 行文本层定向草稿，5 行全部 `low_confidence`
（conf=0.60），**必须人工点选**；其余 5 件各 5 行未改动。
其余 5 件各 5 行均 ≥0.85。

置信度 0.95 只证明"抄的字在页面上都找得到"，**不证明数值归到了正确的列** ——
B1 签字版漏掉的两处恰好都是这类问题（页码串页、条件混进数值列）。

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
| `Batch3_B2_Viewer.html` / `Batch3_B2_DRAFT.csv` | B2 圈选台与 30 行草稿（V003 已重截重出） |
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
