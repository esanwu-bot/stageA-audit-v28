# Gate 6A 跑批状态澄清（书面回复）

- 提交时间：2026-11-10
- 本轮性质：只读状态核实 + 书面澄清
- 本轮硬约束：不启动 / 不重启任何跑批；不运行任何 Parser 或 LLM 代码；不进入 Gate 6B / 6C / 6D
- 唯一权威基线：`E:\workspace\icpdf-extractor`，分支 `feat/s2b-schema-d4-d6`，HEAD `3ed22a4a83564b36ca238792af4b2328fd966469`（commit 时间 2026-11-09T16:08:51+08:00）
- `E:/workspace/github/icpdf-extractor` 为无作用副本，不作审计依据
- `ic-ex = icpdf-extractor`，不存在独立下游仓库

## 0. 结论先行

**30 件 Parser 跑批没有真实启动。正式状态 = `NOT_STARTED`。**

我此前「按 C1 执行 / 已启动」的表述是措辞错误：把「收到授权、开始执行前准备」写成了「跑批已进入执行态」。以文件证据为准：无 Run ID、无启动时间、无解析产物、无 Gold Set、无 LLM / DB 痕迹。本轮不认定为正式 Gate 6A Benchmark，更不认定 PASS，也不倒写为「此前已批准所有前置条件」。

---

## 1. 逐条回复 7 个问题

### Q1. 30 件跑批是否已经真实启动？

**没有启动。** 无 Run ID、无启动时间、无当前跑批状态、无 Run 目录、无启动日志。

`runs/stage_a_350/gate6a/` 当前只有 1 个子目录 `_deps`（PyYAML 6.0.3），共 44 文件 / 738,428 字节，无 `run_manifest.json`、无任何 Run ID 目录。

措辞更正：`APPROVE_GATE_6A_PARSER_BENCHMARK` 之后我回复「按 C1 执行」，随后做的全部是执行前核查（导入自检、路径/SHA 校验、隔离依赖安装），不是解析跑批。该表述造成状态矛盾，责任在我，按 Reviewer 裁定以文件证据为准。

### Q2. 若已启动，已完成多少件、失败多少件？

不适用（未启动）。如实记数：**已完成 0 件、失败 0 件、异常 0 件、重试 0 次**。

没有任何 Parser 产物或解析日志可保留，因此也无从「保留全部产物和日志」。现有 `gate6a/_deps` 原样保留，不清理、不覆盖、不删除。不做任何重试。

旧项目 30 件试跑早前已被取消并标记 `LEGACY_PIPELINE_TRIAL = CANCELLED_PRESERVED`，不重启、不重试，不计入正式成绩。

### Q3. 真实 Parser / LLM / 数据库调用次数？

| 项 | 次数 |
| --- | --- |
| `parser/pipeline.py::parse_pdf()` | **0** |
| LLM Provider / qwen-flash 调用 | **0** |
| 数据库操作（含建库、DDL、连接、写入） | **0** |

证据（本轮只读核查）：

1. `gate6a/` 下 11 类产物计数全为 0：`run_manifest.json`、`document.json`、`text_blocks.json`、`tables.json`、`candidates.json`、`boundary_decisions.json`、`per_item_results.csv`、`metrics.json`、`qc_report.json`、`evidence.json`、`raw_extraction.json`。
2. `gate6a/` 下无任何 `*gold*`、`*.log`、`*llm*`、`*.sql`、`*.db`、`*.jsonl` 文件。无解析日志本身即为「未跑批」的证据。
3. `GATE6A_SAMPLE_STATS.json`：`pdf_opened=false`、`parser_invoked=false`、`llm_called=false`、`gold_labels_created=false`。
4. `gate6_r2/` 冻结件 `sha256sum -c SHA256SUMS.txt` = **18 OK / 0 FAILED**，说明方案轮交付件未被改写为「执行态」。
5. 进程核查：仅 1 个 Python 常驻进程 `PID 3736 pythonw.exe`，命令行 `E:\workspace\IcPdfParser\algorithm_lab\daemon.py`，启动时间 2026-11-10 08:31:46。**如实披露：这是旧项目常驻守护进程，非本轮启动、非解析进程、非 LLM 进程**；按 `parse_pdf|gate6a|_parser_worker|qwen|dashscope|_gate2a_run|pipeline.py` 匹配的 Python 进程数为 0。

如实补充两件「发生过但不是解析」的动作：

- 执行前导入自检：`PYTHONPATH=src python -c "from icpdf.parser.pipeline import parse_pdf"`，首次报 `ModuleNotFoundError: No module named 'yaml'`，安装隔离依赖后输出 `IMPORT_OK icpdf.parser.pipeline yaml 6.0.3 pydantic 2.14.2 pymupdf 1.24.14`。**这是模块导入，不是 `parse_pdf()` 调用，不是 PDF 解析。**
- 30 行清单只读校验：读取文件字节计算 SHA-256，`rows 30, ok 30, bad 0`。**这是字节一致性校验，不是 PDF 内容解析。**

### Q4. 是否有代码修改、依赖安装或 Git 提交？

| 项 | 结论 |
| --- | --- |
| 代码修改 | **0 行**。未改 `src/`、未改 `tools/`、未改 r2 冻结交付件、未改数据侧文件 |
| Git 提交 | **0 次**。HEAD 未变，主项目零 `add` / `commit` / `push` |
| 依赖安装 | **1 次，如实承认**（见下） |
| 工作区既有改动 | ` M src/icpdf/cli.py` 及若干未跟踪项为 Gate 6 r2 已登记的历史既有状态（`GIT_BASELINE_ISOLATION.md`），非本轮产生 |

依赖安装明细（隔离目录，未装进 site-packages、未改项目依赖声明）：

```sh
python -m pip install --disable-pip-version-check --no-deps \
  --target runs/stage_a_350/gate6a/_deps pyyaml
```

结果：`PyYAML 6.0.3`，目录 `runs/stage_a_350/gate6a/_deps`（`_yaml/`、`yaml/`、`pyyaml-6.0.3.dist-info/`）。

**主动披露第二处时点差异（不隐瞒）**：`GATE6A_PARSER_BENCHMARK.md` 第 4 行写「未安装依赖」，该句描述的是**方案提交时点**，当时成立；此后执行前核查阶段安装了隔离 PyYAML，故相对当前时点该句已不再完全成立。建议后续修订为：「截至方案提交时未安装依赖；后续执行前核查在 `runs/stage_a_350/gate6a/_deps` 隔离安装 PyYAML 6.0.3，未解析、未调用 LLM、未建库」。本轮不擅自改写冻结件，等 Reviewer 指示。

### Q5. 当前实际执行样本是否与 `GATE6A_SAMPLE_PROPOSAL.csv` 完全一致？

**不存在「实际执行样本」**，因此不能声称「已按清单完全一致地执行」。

实际发生的只是对清单 30 行的只读存在性与 SHA-256 校验（30/30 一致）。清单共 31 行（1 表头 + 30 数据），30 行 `gold_status` 全部为 `PROPOSED_PENDING_GOLD_CONFIRMATION`。按 Reviewer 裁定「30 件样本基本认可，但暂不冻结」，样本处于**建议未冻结**状态；且整改 A（扫描型判定）完成前不得冻结。

### Q6. 是否已经创建 Gold Set？

**未创建。** `gate6a/` 下无 `gold/` 目录、无任何 Gold 标注文件；`GATE6A_SAMPLE_STATS.json` 中 `gold_labels_created=false`、`type_labels_are_proposals_only=true`。

**明确承认：质量指标尚不能正式计算。** 原 7 项指标（Table Recall、Table Structure Accuracy、Cell Text Accuracy、Column Alignment Accuracy、Candidate Recall、Evidence Localization Accuracy、Cross-page Continuity）以及新增第 8 项 Failure / Unresolved Accounting，在 Gold Set 经人工确认前均不得输出正式通过率，也不得作为 Gate 6B 修复清单的正式成绩依据。

### Q7. 为什么方案文档和统计 JSON 仍写 `NOT_STARTED`？

因为它们记录的是**方案轮提交时点的真实状态**，且此后没有任何足以把状态改写为「执行态」的事实：

- `GATE6A_PARSER_BENCHMARK.md` 第 1 行标题即「方案（仅供 Reviewer 审批，未执行）」，第 3–4 行明确「本文件是方案，不是测试报告……未调用 `pipeline.parse_pdf()`」。
- `GATE6A_SAMPLE_STATS.json` 三个 `false` 与 `gold_labels_created=false`。
- `ROUND2_VERIFY.json` 的 9/9 PASS 只验证 18 份交付件的字节完整与内部一致性，**不证明方案通过、样本冻结、Gold 确认或跑批启动**。
- 方案本身写明：Gold、样本、运行保护壳等前置事项未确认前 Gate 6A 保持 `NOT_STARTED`。

`APPROVE_GATE_6A_PARSER_BENCHMARK` 之后发生的全部动作（导入自检、路径/SHA 校验、隔离依赖安装）属于执行前准备，没有 `parse_pdf()` 调用、没有 Run ID、没有产物、没有 Gold，因此没有依据把状态改写为「已启动」。**文档与统计 JSON 保持 `NOT_STARTED` 是准确的；错的是我的口头表述。**

路线认可与执行授权必须分开：`APPROVE_GATE_6A_PARSER_BENCHMARK` 不等于样本已冻结、Gold 已确认、运行边界已批准；Reviewer 后续已指出样本「暂不冻结」。本轮不倒写审批历史。

---

## 2. Reviewer 4 项整改：已登记待办

已写入同目录 `GATE6A_TODO.md`，状态全部为 `PENDING_REVIEWER_UNFREEZE`，摘要：

| 编号 | 要求 | 落地口径 |
| --- | --- | --- |
| A | 扫描件不能光看页数 | 逐件检查文本层、字符数、乱码比例、图像主导比例、是否需要 OCR；`page_count=5–10` 只是线索，不得据此判定扫描件 |
| B | Gold Set 必须先于成绩 | Gold 未人工确认时不得算正式指标；严禁用 Parser 输出反填 Gold；Gold 需记录原文页码与片段、标注人与时间 |
| C | 新增 Failure / Unresolved Accounting | 统计无法解析表格数、unresolved 决策数、崩溃/超时件数、缺产物件数、无法定位 Evidence 的候选数；逐件 CSV 可盲重算，不得静默从分母剔除 |
| D | 产物映射表 | 区分真实生成 / 改名 / 部分存在 / 完全缺失；`candidates.json` 不得当 `evidence.json`；外部 `validate_evidence.py` 不得当每次 Run 的 `qc_report.json`；`raw_extraction.json` 实际名为 `text_blocks.json` |

---

## 3. 本轮边界声明

- 未启动、未重启任何批次；无后台跑批任务在跑。
- 未运行任何 Parser 或 LLM 代码；未进入 Gate 6B / 6C / 6D；剩余 320 件仍 `NOT_APPROVED`。
- 不将本轮称为正式 Gate 6A Benchmark，也不称 PASS。
- `ICPDF_EXTRACTOR_LLM_READY` 保持 `false`；`CLASSIFIER_AUDIT` 保持 `FAIL`；`CONTENT_QC` 保持 `PENDING`。
- 数据侧 8 个哈希冻结；不改数据文件；主项目零 add / commit / push。
- 在 Reviewer 解除冻结并确认样本、Gold、运行边界之前，Gate 6A 保持 `NOT_STARTED`。
