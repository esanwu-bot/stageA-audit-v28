# 12 条机器验收条件逐条定义（Gate 6D 草案 · 暂缓）

**状态：暂缓。** 按 Reviewer 最新路线裁定，Gate 6C（LLM 接入）与 Gate 6D（端到端 30 件）
均未批准；本文件只是把上一轮 Step 2 第 2.4.4 节的 12 条形式化，供 Reviewer 复核，
**不代表已实现、已测试或已批准**。所有「测试实现」均为规格描述，本轮未创建任何测试文件。

编号 `AC-01..AC-12` 与上一轮原文 1..12 一一对应；`AC-01..06` 为前置门禁，
`AC-07..12` 为执行验收。为覆盖 Reviewer 提出的 7 类失败路径，在原有条件内增加
**失败注入子项**（`FP-01..FP-07`），不新增编号、不扩大批准范围。

---

## 逐条定义

### AC-01 · `ICPDF_EXTRACTOR_LLM_READY` 审批门禁

- **定义**：审计方明确签发 `ICPDF_EXTRACTOR_LLM_READY=true`，且签发记录可核。
- **输入**：`approval_gate6c.json`（拟）：`reviewer`、`approved_at`、`decision`、
  `scope`、`approval_sha256`。
- **预期结果**：文件存在、`decision=="APPROVED"`、`scope` 仅限 30 件且不含 320 件；
  缺失/过期/范围不符一律 `BLOCKED`。
- **测试实现（规格）**：`tests/gate6d/test_ac01_approval.py::test_scope_is_30_only()`、
  `::test_missing_approval_blocks()`；纯文件断言，无网络、无 LLM。
- **失败注入**：`FP-07` 同一 PDF 不同版本身份区分——批准记录须绑定候选清单
  `sha256=040a0e78…39`，清单换版则审批自动失效。

### AC-02 · 隔离运行环境基线

- **定义**：隔离 venv 装齐 `pyproject.toml` 依赖，`pytest -q` 与
  `tools/validate_evidence.py` 基线通过。
- **输入**：`pyproject.toml`、`tests/`（45 个测试文件：31 unit + 14 integration）、
  `tools/validate_evidence.py`。
- **预期结果**：依赖清单 7 项全可 import；`pytest -q` 0 failed；
  `validate_evidence.py` 在固定 fixture run 上退出码 0。
- **测试实现（规格）**：`tests/gate6d/test_ac02_env.py::test_declared_deps_importable()`、
  `::test_pytest_baseline_clean()`；环境探针，不解析真实 PDF。
- **当前事实**：`typer` / `yaml` / `rich` / `dotenv` 全缺、`openai` 缺，
  故本条当前 `UNVERIFIED`。

### AC-03 · Provider 真实调用与故障注入

- **定义**：`qwen-flash` 单件最小真实调用成功且 `usage` 非空；同时用 fake provider
  覆盖超时、限流、响应截断。
- **输入**：`DASHSCOPE_API_KEY`（仅环境）、`qwen-flash`、单条最小 messages；
  fake 注入 `TIMEOUT` / `HTTP 429` / 截断 JSON。
- **预期结果**：真实调用返回 `OK` 且 `usage` 含 prompt/completion/total；
  超时→`error_reason=LLM_TIMEOUT`、429→`LLM_RATE_LIMIT` 且退避次数入 `retry_count`、
  截断→`LLM_TRUNCATED` 且 `repair_count>=1` 或判 FAILED；三者均不得产生
  `verified` 参数。
- **测试实现（规格）**：`tests/gate6d/test_ac03_provider.py::test_real_minimal_call()`、
  `::test_timeout` / `::test_rate_limit` / `::test_truncated_response`（后三者用 fake，
  不烧 Token）。
- **覆盖**：`FP-02`（LLM 超时/限流/截断）。

### AC-04 · 严格响应 Schema

- **定义**：模型响应必须满足 `extra="forbid"` 的响应模型，且每个 `candidate_id`
  必须存在于该 run 的 `CandidateSet`。
- **输入**：合法响应、未知 `candidate_id` 响应、多字段响应、残缺 JSON、
  非 JSON 文本、伪造数值字段。
- **预期结果**：合法 1 条通过；其余 5 类全部被拒并写 `error_reason=SCHEMA_REJECT`；
  拒绝后不得进入 `FormalParameterSet`。
- **测试实现（规格）**：`tests/gate6d/test_ac04_schema.py::test_unknown_candidate_id_rejected()`
  等 6 个负例；纯单测，无 LLM。
- **覆盖**：`FP-03`（Schema 校验失败）。

### AC-05 · 文本/解析子进程保护壳与证据校验基线

- **定义**：逐件子进程崩溃隔离 selftest 通过；`validate_evidence.py --strict` 基线通过。
- **输入**：正常 PDF、损坏 PDF、超时样本、MuPDF 写 fd 1 的噪声样本、加密 PDF、
  无文本层 PDF、零表文档；固定 fixture run 目录。
- **预期结果**：损坏件单件 `NATIVE_CRASH` 或 `PDF_LOAD_ERROR` 且**主进程存活**；
  超时被 `kill()`；stdout 噪声被哨兵过滤；`--strict` 0 error。
- **测试实现（规格）**：`tests/gate6d/test_ac05_guard.py`（8 例，详见
  `P1_FIX_DESIGN.md` §1.6）、`tests/gate6d/test_ac05_evidence_validator.py`。
- **覆盖**：`FP-01`（单 PDF 解析进程崩溃）。

### AC-06 · `cli.py::extract` 已接线

- **定义**：`extract` 不再返回 `_not_implemented`，且调用链确实经过
  `parse_pdf()` → provider → schema → postprocess。
- **输入**：`src/icpdf/cli.py` 源码、一条 dry-run 命令（不解析真实 PDF、
  不调 LLM）。
- **预期结果**：源码断言不存在 `_not_implemented("extract")`；dry-run 打印调用链
  各节点名与各节点输入哈希。
- **测试实现（规格）**：`tests/gate6d/test_ac06_cli_wiring.py::test_extract_wired()`。
- **当前事实**：`cli.py:80-82` 仍为 `_not_implemented`，本条当前 FAIL（按设计）。

### AC-07 · 逐件记录、寻址与崩溃不扩散

- **定义**：30/30 在 `per_item_results.csv` 有且仅有一行；`pdf_sha256` 与清单一致、
  `file_path` 与清单逐字符一致；单件崩溃不得终止整批。
- **输入**：`ds_parse_candidates_350_v2.csv` 前 30 件、逐件子进程执行结果。
- **预期结果**：行数 30、唯一 `sample_no` 30、SHA 不一致 0、路径替换 0；
  注入 1 件崩溃时其余 29 件仍全部有记录，崩溃件 `status=EXCEPTION` +
  `error_reason=TEXT_GUARD_NATIVE_CRASH`。
- **测试实现（规格）**：`tests/gate6d/test_ac07_per_item.py::test_30_unique_rows()`、
  `::test_crash_does_not_abort_batch()`、`::test_no_sha_based_path_search()`。
- **覆盖**：`FP-01`、`FP-05`（重复执行/重复写入：`RunStore.create()` 对已存在 run_id
  必须抛 `FileExistsError`）、`FP-06`（部分产物写入后失败：仍须有一行逐件记录，
  且 `status!=SUCCESS`）、`FP-07`（同一 PDF 不同字节版本 → 不同 SHA → 不同 run，
  不得复用旧产物）。

### AC-08 · 真实调用留痕与部分产物检测

- **定义**：`raw_json_path` 指向真实文件；`model_calls` / `llm_usage` /
  `repair_count` / `retry_count` 来自真实拦截记录而非填表。
- **输入**：`llm_calls.jsonl`、`guard_calls.jsonl`、`raw_json/`、run 目录清单。
- **预期结果**：每个 SUCCESS 件 `model_calls>=1` 且 usage 三项可累加；
  截断/超时件的 `retry_count`/`repair_count` 与 JSONL 条数一致；
  存在孤儿产物（写了文件但无逐件记录）时判 FAIL 并列路径。
- **测试实现（规格）**：`tests/gate6d/test_ac08_trace.py::test_usage_matches_jsonl()`、
  `::test_no_orphan_artifacts()`。
- **覆盖**：`FP-02`、`FP-06`。

### AC-09 · Evidence 绑定与 formal 容器

- **定义**：每个 `verified`/`audited` 的 `Parameter` 至少 1 个 `Evidence`
  （`document_sha256` + `page_number>=1` + `bbox` + `raw_text` + table/row/cell id）；
  `FormalParameterSet` 构造 0 校验错误；`validate_evidence.py --strict` 0 error。
- **输入**：`evidence.json`、`parameters.json`、`candidates.json`、`document.json`。
- **预期结果**：`Evidence.document_sha256 == source.pdf` 重算值；页码缺失或
  bbox 与原文不匹配的条目一律 `UNRESOLVED` + `unresolved_reason`，
  不得进 formal 容器；同一 PDF 不同版本的证据不得交叉引用。
- **测试实现（规格）**：`tests/gate6d/test_ac09_evidence.py::test_formal_requires_evidence()`、
  `::test_page_mismatch_is_unresolved()`、`::test_sha_binds_evidence()`。
- **覆盖**：`FP-03`、`FP-04`（Evidence 页码缺失/不匹配）、`FP-07`。

### AC-10 · `metrics.json` 盲重算一致

- **定义**：所有汇总数字只能由只读逐件 CSV 复现。
- **输入**：`per_item_results.csv`、`evidence_audit/*.csv`、`metrics.json`。
- **预期结果**：逐项 `recomputed == declared`，0 不一致；重复执行校验器两次结果相同。
- **测试实现（规格）**：`tests/gate6d/test_ac10_recompute.py::test_blind_recompute()`、
  `::test_idempotent_verifier()`。
- **覆盖**：`FP-05`（重复执行幂等）。

### AC-11 · 完整性清单

- **定义**：`SHA256SUMS.txt` 全部 OK / 0 FAILED。
- **输入**：正式产物目录全部文件。
- **预期结果**：`sha256sum -c` 每行 OK；清单外的新增/缺失文件被列为
  `UNLISTED_ORPHAN` 并判 FAIL（防部分写入）。
- **测试实现（规格）**：`tests/gate6d/test_ac11_integrity.py::test_checksums_all_ok()`、
  `::test_no_partial_artifacts()`。
- **覆盖**：`FP-06`。

### AC-12 · 人工证据抽检记录

- **定义**：`evidence_audit/random_30.csv` 与 `high_risk_20.csv` 逐条记录
  关键参数值、PDF 原文页码、系统输出、判定结果、缺陷等级（P0/P1/P2/P3）。
- **输入**：Gold/人工复核结论、原始 PDF 页码、系统输出。
- **预期结果**：不得出现「抽检通过」这类无字段结论；每条至少 1 个
  `(参数名, 页码, 原文片段, 系统输出, 判定, 等级)` 六元组；页码缺失或
  不匹配的条目判 FAIL 并记缺陷等级。
- **测试实现（规格）**：`tests/gate6d/test_ac12_evidence_audit.py::test_six_tuple_present()`、
  `::test_page_mismatch_recorded_as_defect()`。
- **覆盖**：`FP-04`。

---

## 失败路径覆盖矩阵（Reviewer 七项要求）

| 失败路径 | 覆盖条件 | 关键断言 |
| --- | --- | --- |
| FP-01 单 PDF 解析进程崩溃 | AC-05、AC-07 | 主进程存活、其余 29 件仍有逐件记录 |
| FP-02 LLM 超时 / 限流 / 响应截断 | AC-03、AC-08 | 三类 `error_reason` 分流、retry/repair 与 JSONL 一致 |
| FP-03 Schema 校验失败 | AC-04、AC-09 | 未知 `candidate_id` 被拒、拒绝后不进 formal 容器 |
| FP-04 Evidence 页码缺失或不匹配 | AC-09、AC-12 | `UNRESOLVED` + `unresolved_reason`、抽检判缺陷 |
| FP-05 重复执行和重复写入 | AC-07、AC-10 | `FileExistsError` 拒绝覆盖、校验器幂等 |
| FP-06 部分产物写入后失败 | AC-07、AC-08、AC-11 | 仍有逐件行且 `status!=SUCCESS`、无孤儿文件 |
| FP-07 同一 PDF 不同版本身份区分 | AC-01、AC-07、AC-09 | SHA 不同 → run 不同 → 证据不交叉引用 |

**覆盖声明**：7 类路径均至少被 2 条条件覆盖。本文件是规格，未写测试代码、
未执行任何用例；`GATE6_VERIFY.json` 的 9/9 PASS 只证明交付件完整性，
不证明这 12 条已通过。
