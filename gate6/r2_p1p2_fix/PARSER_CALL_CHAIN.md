# 真实 Parser 调用链与输出对象定位（静态阅读，未执行）

- 目的：先确定 `/api/parse` 适配层可以读什么，**不假定任何输出字段**
- 方法：只读源码，未 import、未调用 `parse_pdf()`、未打开 PDF、未启动服务
- 基线：`E:\workspace\icpdf-extractor`，HEAD `3ed22a4a83564b36ca238792af4b2328fd966469`
- 状态：`CODE_READY / NOT_EXECUTED`，不是 `PARSER_VERIFIED`

---

## 1. 真实调用链

| 步骤 | 文件:行 | 符号 | 作用 |
| --- | --- | --- | --- |
| 入口 | `src/icpdf/parser/pipeline.py:94` | `parse_pdf(pdf_path, requested_mpn, runs_root="runs", *, dpi=None, run_id=None, config_path=None)` | 唯一正式解析入口 |
| 配置 | `pipeline.py:97` -> `src/icpdf/parser/config.py:88` | `load_config()` | `yaml.safe_load` 读 `configs/parser.yaml`，返回 `(ParserConfig, sha256(raw))` |
| 配置路径 | `config.py:16` | `DEFAULT_CONFIG_PATH` | `parents[3] / "configs" / "parser.yaml"` = 仓库根 `configs/parser.yaml` |
| PDF 装载 | `pipeline.py:99` -> `src/icpdf/parser/pdf_loader.py:41` | `load_pdf()` | `fitz.open`，拒绝加密/无页，构造 `Document` 与 `PageGeometry` |
| Run 创建 | `pipeline.py:101` -> `src/icpdf/storage/run_store.py:20` | `RunStore.create()` | 生成 `runs/<run_id>/`，已存在则 `FileExistsError` 拒绝覆盖 |
| 源件留痕 | `pipeline.py:102` -> `run_store.py:32` | `copy_source()` | 复制为 `source.pdf`，返回 SHA-256 |
| 逐页解析 | `pipeline.py:114-134` | `extract_text_blocks` / `detect_tables_with_evidence` / `build_table` / `render_page` | 主进程持有 `fitz.Page`；**当前无逐件子进程 + 超时强杀保护壳** |
| 候选构建 | `pipeline.py:138` -> `src/icpdf/parser/candidate_registry.py:42` | `build_candidates()` | 返回 `CandidateSet` |
| 边界证据 | `pipeline.py:144-149` -> `src/icpdf/parser/logical_evidence.py:1331` | `analyse_document` / `serialize_boundary_decisions` | 写 `boundary_decisions.json` 规范字节 |
| 清单 | `pipeline.py:163` -> `run_store.py:59` | `write_manifest()` | 写 `run_manifest.json` |
| 返回 | `pipeline.py:189-198` | `dict` | `run_id`、`run_dir`、`document_id`、`document_sha256`、`page_count`、`tables`、`candidates`、`manifest_sha256` |

**隔离模块辨析**：`src/icpdf/parser/pipeline_sandbox.py` 是 G2-4 的「逻辑决策链沙盒」（`run_sandbox_chain`），注释明确「no PDF is parsed」。它**不是**子进程超时保护壳，与本工作台无关。因此 `serve_parser.py` 必须自带单件子进程隔离，不能误用该模块。

---

## 2. 真实写出的 9 个 JSON artifacts

| 返回键（适配层命名） | run 目录相对路径 | 产出位置 | 内容类型 |
| --- | --- | --- | --- |
| `run_manifest` | `run_manifest.json` | `pipeline.py:163` / `run_store.py:59` | dict |
| `document` | `document.json` | `pipeline.py:104` | dict（`Document`） |
| `text_blocks` | `text_blocks.json` | `pipeline.py:136` | list[dict] |
| `tables` | `tables.json` | `pipeline.py:137` | list[dict]（`Table`） |
| `candidates` | `candidates.json` | `pipeline.py:139` | dict（`CandidateSet`） |
| `boundary_decisions` | `boundary_decisions.json` | `pipeline.py:146` | dict（canonical，`sort_keys=True`） |
| `product` | `product.json` | `pipeline.py:159` | dict（`Product`） |
| `run_config` | `run_config.json` | `pipeline.py:160` | dict（脱敏配置快照） |
| `geometry` | `pages/geometry.json` | `pipeline.py:105` | list[dict]（`PageGeometry`） |

另有非 JSON 伴生产物：`source.pdf`（`run_store.py:32`）、`pages/page-XXXX.png`（`pipeline.py:124-126`，**仅检测到表格的页才渲染**）。

> 适配层的返回键名由本工作台定义，内容一律原样 JSON 反序列化；不重命名 Parser 内部字段，不合并、不补齐。

---

## 3. 输出对象的确切字段（逐项核对，拒绝假定）

### 3.1 `document.json` — `src/icpdf/domain/document.py:21`

`document_id`、`filename`、`sha256`、`page_count`、`source_uri`、`manufacturer`、`document_title`、`document_type`、`parser_version`、`created_at`、`page_sizes`、`page_rotations`。

适配层读取：`page_count`（第 36 行）、`document_id`（第 33 行）。二者真实存在。

### 3.2 `tables.json` — `src/icpdf/domain/table.py:114`

`table_id`、`document_id`、`page_number`、`page_end`、`bbox`、`title`、`table_type`、`headers: list[str]`（第 134 行）、`header_rows`、`header_path`、`header_cells`、`rows: list[TableRow]`（第 140 行）、`detection_method`、`confidence`、`reconstruction_status`、`uncertainty_reason`、`region_components`、`boundary_source`、`merge_evidence`、`visual_boundaries`、`visual_boundary_status`。

`TableRow`（第 77 行）：`row_id`、`cells: list[Cell]`、`bbox`。`Cell`（第 61 行）：`cell_id`、`row_id`、`column_id`、`text`、`bbox`、`page_number`、`extraction_method`、`raw_tokens`、`word_ids`。

适配层与右侧卡片只用这些真实字段做计数与展示，不生成 `specs.electrical` / `specs.thermal`。

### 3.3 `candidates.json` — `src/icpdf/domain/candidate.py:76`

顶层 `CandidateSet`：`run_id`、`document_id`、`candidates: list[Candidate]`（第 83 行）。
`Candidate`（第 43 行）：`candidate_id`、`document_id`、`table_id`、`row_id`、`cell_id`、`page_number`、`bbox`、`raw_text`、`normalized_value`、`unit`、`column_role`、`role_source`、`role_header_cell_id`、`candidate_type`、`extraction_method`、`source_text_type`、`reconstruction_status`。

适配层读取 `candidates.candidates` 长度，真实存在。**这些是单元格级原始候选，不是已归一化的器件参数。**

### 3.4 `boundary_decisions.json` — `src/icpdf/parser/logical_evidence.py:1296`

顶层：`schema`、`design_document`、`contract_version`、`document_id`、`tables`、`disclosure`、`totals`（第 1317 行）。
`totals`：`table_count`、`completed_tables`、`failed_tables`、`no_decision_tables`、`decision_count`、`decisions`、`skipped_groups`。

适配层读取 `totals`，真实存在；用于 Diagnostics 的「失败 / 未决边界」，符合 Reviewer 整改 C 的数据来源要求。

### 3.5 `run_manifest.json` — `pipeline.py:163-188`

含 `run_id`、`document_id`、`document_sha256`、`requested_mpn`、`python_version`、`project_version`、`parser_version`、`contract_version`、`parser_config_sha256`、`platform`、`dpi`、`page_count`、`table_count`、`boundary_decisions`、`candidate_count`、`detection_methods`、`rendered_pages`、`model`、`prompt_version`，以及 `artifacts`（`run_store.py:60` 追加）。

适配层读取的版本 / SHA / 平台字段全部真实存在。`parse_pdf()` 返回的 `manifest_sha256` 来自 `write_json` 的哈希记录（`src/icpdf/storage/artifact_store.py:42`），不是 manifest 内容字段。

### 3.6 明确不存在的字段

`evidence.json`、`qc_report.json` 不由 Parser 产出（`pipeline.py` 无写入）。契约中的 `raw_extraction.json` 实际文件名为 `text_blocks.json`，属于**改名**而非缺失。`candidates.json` 不得充当 `evidence.json`。

---

## 4. 依赖加载路径（不悄悄改用全局环境）

- `config.py:11` 有 `import yaml`；`load_config()` 第 92 行调用 `yaml.safe_load`。
- 全局 `site-packages` **没有** `yaml`；隔离目录 `runs/stage_a_350/gate6a/_deps` 内有 PyYAML 6.0.3。
- 全局有 `fastapi`、`pymupdf`、`pydantic`；**没有** `uvicorn`、`python-multipart`。
- 适配层因此：
  1. 用 `Request.body()` 接收原始 PDF 二进制，不用 `UploadFile` / `File`，规避 multipart 依赖；
  2. worker 子进程把隔离 `_deps` 与仓库 `src/` 显式 `sys.path.insert`，并校验 `yaml.__file__` 确实位于隔离目录内，否则拒绝执行；
  3. 不安装任何依赖、不改 `pyproject.toml`、不复制 Parser 逻辑；
  4. 冻结期不启动服务；`__main__` 检测到缺 `uvicorn` 时只打印解冻后的安装命令并退出。

---

## 5. 据此确定的 `/api/parse` 适配层契约

| 项 | 结论 |
| --- | --- |
| 输入 | PDF 二进制请求体 + `X-Filename` 请求头（URL 编码）+ 可选 `X-Requested-Mpn` |
| 执行 | worker 子进程调用 `parse_pdf(pdf_path, requested_mpn, runs_root, run_id)`，不另造解析链 |
| 输出 | `parser_output` 命名空间下 9 个真实 artifacts 的原样 JSON；`extraction: null`（第二阶段 LLM 专用） |
| 元数据 | `run_id`、上传 SHA-256、`code_version`（`project_version` / `parser_version` / `contract_version` / `parser_config_sha256` / `git_head`）、`llm_called=false`、`database_written=false` |
| 状态 | `FROZEN` / `INVALID_FILE` / `PARSE_TIMEOUT` / `PARSE_CRASH` / `PARSE_ERROR` / `PARSE_COMPLETED`，分别独立，不统一伪装成功 |
| 产物映射 | `artifact_inventory` 逐项 `REAL_GENERATED` / `RENAMED` / `PARTIAL` / `MISSING`；`contract_gaps` 明写 evidence/qc 缺失 |
| 校验 | 上传 SHA 与 `run_manifest.json.document_sha256` 交叉核对，不一致记入 diagnostics |

**分层红线**：`parser_output` = 纯代码 Parser 原始产物（文本块、表格、候选、边界决策）；`extraction` = 后续 LLM/Domain 语义归一化结果。第一阶段绝不把 candidates 包成 `specs.electrical` / `specs.thermal` / `pin_configuration`。
