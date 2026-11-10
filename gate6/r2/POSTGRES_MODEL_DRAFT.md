# PostgreSQL 持久化契约草案（**仅契约，不建库、不写可执行 DDL**）

**状态：暂缓草案。** Reviewer 明确「PostgreSQL 暂时不进入实施」，且最新路线调整后
Gate 6C/6D 均未批准。本文件只定义逻辑实体与边界，**没有**连接数据库、
创建 schema、生成迁移脚本或执行任何 DDL；也刻意**不提供可复制执行的
`CREATE TABLE` 语句**，避免把临时 JSON 结构固化成长期表结构。

---

## 0. 设计前提与不变量

1. 内容身份 = `SHA-256(PDF 字节)`；路径/文件名不参与同一性判定。
2. 请求料号 `requested_mpn` 与 PDF 观测料号 `normalized_mpn` 分开存储。
3. 置信度只是提示，不能替代证据校验；形式参数必须可回溯到源 PDF 单元格。
4. **四类数据必须分表**：① 原始 LLM 响应 ② 规范化参数 ③ Evidence ④ 人工审核记录。
   禁止用一个 `payload_json` 大字段混装。
5. 原始提取结果**不可覆盖**：人工裁决写入独立 `review` 实体，通过版本引用生效，
   对应工作台 §6.2「不允许静默覆盖原始提取结果」「不允许把人工裁决直接写回原始 PDF 提取层」。
6. 任务唯一键包含会影响结果的输入版本（文档 SHA、Parser/Schema/Prompt/模型版本），
   见 `backstage/…修订版.md:221`。
7. 每个实体记录 `contract_version`、`created_at`（timezone-aware）、`sha256`（自哈希）。
8. 本契约与 `docs/DATA_CONTRACT.md` `data-contract/v0.2` 对齐；
   若新增 `parameters`/`evidence`/`qc_report` 产物，须先批准契约版本升级。

---

## 1. 实体链

```
Document ──1:N──> ParseRun ──1:N──> Candidate ──1:N──> Extraction
                                          │                │
                                          │                └─> raw LLM response (独立)
                                          └─> FieldEvidence <─┐
                                                              │
Extraction ──1:N──> Parameter ──N:M──> FieldEvidence          │
       │                │                                    │
       │                └─> FormalParameterSet 视图（只 verified/audited）
       └─> Validation ──1:N──> Review
```

---

## 2. 逻辑实体定义（不是 DDL）

### 2.1 `document` — 文档身份

| 逻辑字段 | 类型意图 | 约束 |
| --- | --- | --- |
| `document_sha256` | 64 位小写 hex，**主键** | 等于 PDF 字节 SHA-256 |
| `filename` / `file_path_snapshot` | 文本 | 仅快照，不作身份 |
| `page_count` | int ≥1 | 与 PDF 一致 |
| `page_sizes` / `page_rotations` | 结构化 | 每页一条，冻结坐标口径 |
| `metadata_author` / `metadata_title` | 可空 | PDF 元数据 |
| `first_seen_at` / `contract_version` | 时间 / 文本 | — |

同一 PDF 不同字节版本 → 不同主键，天然区分（对应 `FP-07`）。

### 2.2 `parse_run` — 一次解析运行

| 逻辑字段 | 约束 |
| --- | --- |
| `run_id` **主键** | 由 `RunStore.create()` 生成，已存在拒绝覆盖（幂等） |
| `document_sha256` **FK→document** | — |
| `parser_version` / `classifier_version` / `schema_version` / `prompt_version` / `model_name` | 影响结果的版本全部入键 |
| `parser_config_sha256` / `table_params_sha256` | 来自 `run_manifest.json` |
| `stage` / `status` | `parse / llm / candidate / qc / build`；`OK / EXCEPTION / TIMEOUT_KILLED / NATIVE_CRASH / PARTIAL_ARTIFACTS` |
| `started_at` / `finished_at` / `worker_id` / `attempt` | 至少一次投递假设，业务写入幂等 |
| `input_artifact_refs[]` / `output_artifact_refs[]` | 对应工作台 §4.2 |
| `error_code` / `error_summary` | 失败必填 |

`RunStore` 当前是文件 artifact store；本实体是**未来**落库映射，不改变当前存储实现。

### 2.3 `candidate` — 候选单元格

| 逻辑字段 | 约束 |
| --- | --- |
| `candidate_id` 与 `run_id` 组成复合主键 | `candidate_id = document_id:cell_id` |
| `table_id` / `row_id` / `cell_id` / `page_number` | 必填，绑定表格归属 |
| `bbox` | `(x0,y0,x1,y1)`，PDF page display 空间 pt |
| `raw_text` / `normalized_value` / `unit` | 原文与标准化值**分列**，不覆盖原文 |
| `column_role` / `role_source` | `symbol/min/typ/max/unit/condition/unknown`；`header_text/heuristic/fail_closed` |
| `extraction_method` / `source_text_type` / `reconstruction_status` | 溯源 |

### 2.4 `extraction` — 一次 LLM 调用与**原始响应**

| 逻辑字段 | 约束 |
| --- | --- |
| `extraction_id` **主键**、`run_id` **FK** | 一次调用一行，重试各占一行 |
| `model_name` / `prompt_version` / `prompt_sha256` / `temperature` / `max_tokens` | 请求侧可复现 |
| `request_messages_hash` / `response_raw_text` / `response_sha256` | **原始响应单独保存，不解析后丢弃** |
| `response_status` | `OK / TIMEOUT / RATE_LIMIT / TRUNCATED / SCHEMA_REJECT / PARSE_ERROR` |
| `usage_prompt_tokens` / `usage_completion_tokens` / `usage_total_tokens` | 真实 usage |
| `started_at` / `duration_ms` / `retry_index` / `repair_index` | 与 `llm_calls.jsonl` 一致 |

**关键**：`response_raw_text` 与 `parameter` 分表；Schema 校验失败的响应也要落库并标
`SCHEMA_REJECT`，不得静默丢弃（对应 `FP-02`/`FP-03`）。

### 2.5 `parameter` — 规范化参数

| 逻辑字段 | 约束 |
| --- | --- |
| `parameter_id` **主键**、`extraction_id` **FK**、`run_id` **FK** | — |
| `name` / `category` | `electrical / absolute_maximum / recommended_operating / thermal / mechanical / timing / other` |
| `value` / `min` / `typ` / `max` / `unit` / `conditions` | 全部 `str \| None`，**保留原文**，禁止单位换算/范围折叠 |
| `applicable_mpn` / `package` / `table_id` | 必填；参数永不全局 |
| `verification_status` | `verified / audited / unverified / unresolved / quarantined / rejected` |
| `unresolved_reason` | `unresolved/quarantined/rejected` 必填 |
| `evidence_ids[]` | `verified/audited` 必填且非空 |

形式容器是**视图/约束**（只收 `verified|audited`），不是另一张宽表；
未决行保留在 `parameter` 中但状态受限，或单独 `parameter_unresolved` 分区，
由 Reviewer 决定。

### 2.6 `field_evidence` — 证据

| 逻辑字段 | 约束 |
| --- | --- |
| `evidence_id` **主键**、`document_sha256` **FK** | 证据按 SHA 绑定文档，不按文件名 |
| `page_number` ≥1 / `bbox` / `raw_text` | 必填，非空 |
| `table_id` / `row_id` / `cell_id` | `cell_text`/`table_row` 类型三者必填 |
| `evidence_type` | `cell_text / table_row / paragraph / page_image / manual` |
| `screenshot_reference` | 可空，指向页面 PNG |
| `candidate_id` | 可空；`manual` 类型可无 candidate |

**与人工证据分离**：`manual` 类型证据必须关联 `review_id`，不得与机器 Evidence 混写。

### 2.7 `validation` — 规则校验

| 逻辑字段 | 约束 |
| --- | --- |
| `validation_id` **主键**、`run_id` / `extraction_id` **FK** | — |
| `validator` / `validator_version` / `rule_id` | 如 `validate_evidence --strict`、`schema.py` |
| `subject_type` / `subject_id` | 被校验对象 |
| `result` / `severity` | `PASS / FAIL / SKIP`；`P0/P1/P2/P3` |
| `detail` / `checked_at` | 可复核文本，禁止只写「通过」 |

### 2.8 `review` — 人工审核

| 逻辑字段 | 约束 |
| --- | --- |
| `review_id` **主键**、`validation_id`（可空）/`subject_id` | — |
| `reviewer` / `reviewed_at` / `action` | `accept / modify / unresolved / not_applicable / reject / rerun / gold_proposal` |
| `before_value` / `after_value` / `reason` | 修改动作必须记录前后值与理由 |
| `evidence_refs[]` / `input_version` / `output_version` / `audit_event_id` | 对应工作台 §6.2 |

禁止动作（工作台 §6.2）：无证据确认高风险参数、静默覆盖原始提取结果、
把人工裁决写回原始提取层、未授权发布。

---

## 3. 四类数据分离检查表

| 数据 | 实体 | 禁止混入 |
| --- | --- | --- |
| 原始 LLM 响应 | `extraction.response_raw_text` | 不得塞进 `parameter.value` 或 `candidate.raw_text` |
| 规范化参数 | `parameter` | 不得覆盖 `candidate.normalized_value` |
| 机器证据 | `field_evidence`（非 `manual`） | 不得由 LLM 生成 `raw_text` |
| 人工审核 | `review` + `field_evidence(manual)` | 不得回写 `extraction` / `candidate` |

---

## 4. 幂等、版本与恢复（契约层）

- 至少一次投递：`parse_run` 以 `run_id` 幂等；重复执行同一 `run_id` 必须拒绝
  （当前 `RunStore.create():27-28` 已用 `FileExistsError` 实现，落库时须保持）。
- 任务唯一键含阶段 + 文档 SHA + Parser/Schema/Prompt 版本；版本任一变化即新 run。
- 部分写入：以 `run_manifest.json` 的 artifacts 列表为提交边界，
  不完整则标 `PARTIAL_ARTIFACTS`，不产生正式 `parameter` 行。
- 同一 PDF 不同版本 → 不同 `document_sha256` → 不同 `parse_run` →
  证据不得跨文档 SHA 引用。

---

## 5. 待 Reviewer 决定后才可进入设计的问题

1. 先确认 Gate 6A Parser 基线与 `evidence.json` / `qc_report.json` 契约，
   再决定是否落 PG；**当前顺序不倒置**。
2. 是否需要 `parameter_unresolved` 独立分区，或仅用 `verification_status` 区分。
3. `paragraph` 证据引入是否触发 `data-contract/v0.3` 版本升级
   （工作台 §5 原文：「如果当前数据契约只支持 table/row/cell，段落证据应通过
   明确的 Schema 版本升级引入」）。
4. 原始响应保留期、脱敏（密钥绝不落库）与存储成本核算。
5. `review` 的审计事件是否需要独立 `audit_event` 实体与不可改日志。

---

## 6. 本轮边界

只读工作台规划与 Domain 契约，输出逻辑实体表。
**DDL 0 条、连接 0 次、建库 0 次、迁移脚本 0 个、代码改动 0 行。**
`ICPDF_EXTRACTOR_STORAGE_PASS` 保持 `NOT_RUN`；当前实际持久化仍是
`runs/<run_id>/` 文件 artifacts。
