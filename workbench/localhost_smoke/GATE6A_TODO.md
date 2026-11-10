# Gate 6A 待办登记（Reviewer 冻结期内，全部未实施）

- 登记时间：2026-11-10
- 来源：Reviewer 对 Gate 6A 方案的 4 项硬整改要求 + 状态矛盾裁定
- 当前状态：Gate 6A = `NOT_STARTED`；本文件所有条目 = `PENDING_REVIEWER_UNFREEZE`
- 硬约束：Reviewer 解除冻结前，不跑任何 Parser 或 LLM 代码，不启动/重启跑批，不进入 Gate 6B / 6C / 6D
- 配套文件：`GATE6A_STATUS_CLARIFICATION.md`

---

## A. 扫描件不能光看页数

**Reviewer 要求**：扫描型样本不能靠页数认定，必须检查是否有文本层、文本字符数量、乱码比例、页面是否主要由图像构成、是否需要 OCR。

**当前缺口**：`GATE6A_SAMPLE_PROPOSAL.csv` 的分层依据来自 `page_count`、`evidence_page_no` 与文件名线索；`GATE6A_SAMPLE_STATS.json` 第 6 类名称本身带「待人工确认」。`page_count=5–10` 只是短文档线索，不等于扫描件。

**落地验收口径**：

| 字段 | 要求 |
| --- | --- |
| `has_text_layer` | 逐件逐页判定，布尔 |
| `text_char_count` | 逐页可提取字符数 |
| `garbled_ratio` | 不可解码 / 替换字符占比 |
| `image_area_ratio` | 图像区域占页面面积比例 |
| `ocr_required` | 布尔，须给出判定依据 |
| `scan_type_confirmed_by` | 人工确认人与时间，未确认一律留空 |

逐件写入 `scan_profile.csv`，30 件全覆盖且可由原始 PDF 盲重复核。禁止用文件名或页数直接推断扫描件；`evidence_page_no=NONE` 不得当作解析页码。

**阻断**：A 未完成前，30 件样本不得冻结，`PROPOSED_PENDING_GOLD_CONFIRMATION` 状态保持。

---

## B. Gold Set 必须先于成绩

**Reviewer 要求**：Gold Set 必须先于质量成绩；严禁用 Parser 输出反填 Gold。

**落地验收口径**：

1. Gold 独立于 Parser 结果建立，记录 PDF 原文页码、原文片段、标注人、标注时间、Gold 版本号。
2. Gold 文件生成时间必须早于对应 Parser 产物，或由独立人工标注来源证明；时间戳/哈希留痕。
3. `gold_status` 为 `PENDING_HUMAN` / `DRAFT` 时，7 项指标只能输出探索性描述，**不得计算正式通过率**。
4. 严禁从 `tables.json` / `candidates.json` 反向生成 Gold 标签；代码中不得出现以 Parser 产物为输入的 Gold 生成路径。
5. 质量报告必须携带 `gold_status`、`gold_confirmed_at`、`gold_sha256`，否则视为无效成绩。

**阻断**：Gold 未人工确认，质量指标 = `NOT_COMPUTABLE`，不得作为 Gate 6B 修复清单的正式依据。

---

## C. 新增指标：Failure / Unresolved Accounting

**Reviewer 要求**：作为第 8 项指标，防止 Parser 通过丢弃难内容抬高表面准确率。

**落地验收口径**：至少统计并逐件留痕

| 统计项 | 口径 |
| --- | --- |
| `unparsed_table_count` | 无法解析的表格数 |
| `unresolved_decision_count` | `boundary_decisions` 中未决决策数 |
| `crash_count` / `timeout_count` | 崩溃 / 超时件数 |
| `missing_artifact_count` | 缺少必要产物的件数（按 D 的映射表口径） |
| `unlocatable_evidence_candidate_count` | 无法定位 Evidence 的候选数 |

写入 `metrics.json` 独立 `failure_unresolved_accounting` 段；所有数字必须能由 `per_item_results.csv` 与 artifacts 清单只读盲重算复现。失败/未决件不得静默从分母剔除；分母口径必须在报告中写明。

---

## D. 产物映射表

**Reviewer 要求**：区分真实生成、改名、部分存在、完全缺失；严禁把 `candidates.json` 当 `evidence.json`，严禁把外部 `validate_evidence.py` 当作每次 Run 产出的 `qc_report.json`。

**工作台 §5 契约期望 7 产物 → 当前 Parser 实际产物映射（现状，非承诺）**：

| 契约产物 | 实际文件 | 状态 |
| --- | --- | --- |
| `run_manifest.json` | `run_manifest.json` | 真实生成 |
| `document.json` | `document.json` | 真实生成 |
| `raw_extraction.json` | `text_blocks.json` | **改名**（不是同一文件名） |
| `tables.json` | `tables.json` | 真实生成 |
| `candidates.json` | `candidates.json` | 真实生成；**不得充当 `evidence.json`** |
| `evidence.json` | 无 | **完全缺失**；`domain.Evidence` / `FormalParameterSet` 生产链零实例化 |
| `qc_report.json` | 无 | **完全缺失**；外部 `validate_evidence.py` 不等于每次 Run 的 QC 产物 |

Parser 实际还产出 `pages/geometry.json`、`boundary_decisions.json`、`product.json`、`run_config.json`、`source.pdf` 与 `pages/page-XXXX.png`（仅检测到表格的页）。

**落地验收口径**：`artifact_inventory.csv` 逐件记录 `contract_artifact`、`actual_file`、`status(REAL_GENERATED/RENAMED/PARTIAL/MISSING)`、`sha256`、`bytes`、`note`；报告中必须写明「缺少证据页码回溯」造成的评估困难，不得用替代产物掩盖。

---

## E. 其他冻结待办（沿用既有状态，未解除）

| 项 | 状态 |
| --- | --- |
| 30 件样本冻结 | 未冻结（Reviewer「暂不冻结」） |
| Gold Set | 未创建 |
| 运行保护壳（G6-P1-001：`parser/` 缺逐件子进程 + 超时强杀） | 未修复，运行边界未确认 |
| `G6-P1-002`（Evidence / FormalParameterSet 零实例化） | 未修复 |
| `ICPDF_EXTRACTOR_LLM_READY` | `false` |
| `CLASSIFIER_AUDIT` / `CONTENT_QC` | `FAIL` / `PENDING` |
| Gate 6B / 6C / 6D、剩余 320 件 | `NOT_APPROVED` |
| 数据侧 8 个哈希 | 冻结，不改；主项目零 add / commit / push |
| `runs/stage_a_350/gate6a/_deps`（PyYAML 6.0.3，44 文件 / 738,428 字节） | 原样保留，不清理、不覆盖、不删除 |

---

## F. 解除冻结后的执行顺序（本轮不执行）

1. A：30 件逐件扫描型画像 → 2. 样本冻结确认 → 3. B：Gold Set 建立并人工确认 → 4. C：指标定义含 Failure / Unresolved → 5. D：产物映射表 → 6. 运行保护壳与 Run ID / 落盘目录确认 → 7. 重新申请正式跑批授权。

单文件人工观察工具 `workbench/` 已按「冻结期只写代码」实现，默认开关 `ICEX_WORKBENCH_ALLOW_PARSE=0`，不触发解析；其本身不构成 Gate 6A 正式跑批授权。
