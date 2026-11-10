# G6-P1-001 / G6-P1-002 修复设计（仅设计，本轮不实现）

**状态按路线调整**：`G6-P1-001`（Parser 崩溃保护）归入 **Gate 6A/6B** 范畴，
是「先验证 Parser」的前置条件，优先级上升；`G6-P1-002`（evidence.json /
parameters.json 产物）归入 **Gate 6C** 范畴，**暂缓**。两者都只提交设计，不写代码。

---

## 一、G6-P1-001：缺逐件子进程崩溃保护

### 1.1 复核后的完整事实（比第一轮审计更细）

第一轮只指出 `pdf_loader.py:36` 与 `pipeline.py:114` 主进程 `fitz.open`。
本轮补查发现，确定性链在**主进程持有 fitz Page 对象**的调用点共 5 处：

| 位置 | 调用 | 风险 |
| --- | --- | --- |
| `src/icpdf/parser/pdf_loader.py:49` | `with fitz.open(str(path)) as doc:` | 打开/元数据/几何 |
| `src/icpdf/parser/pipeline.py:114` | `with fitz.open(...) as doc:` 并把 `page` 传入下游 | 整页循环 |
| `src/icpdf/parser/text_blocks.py:54` | `page.get_text("dict")` | 文本块抽取 |
| `src/icpdf/parser/rule_primitives.py:138` | `page.get_drawings()` | 矢量规则线（表格边界） |
| `src/icpdf/parser/page_renderer.py:20-25` | 再次 `fitz.open` + `page.get_pixmap()` | 页面 PNG 渲染 |

另外 `coords.py:44` 读 `page.rect`。因此**只给「文本提取」套子进程壳是不够的**：
`get_drawings()` 与 `get_pixmap()` 同样可能触发 MuPDF 原生崩溃，且 `page` 对象
无法跨进程传递。这是第一轮设计需要修正的地方。

现有保护壳只存在于**分类器**：`src/icpdf/classification/classifier.py:794/800/801/868/871`
的 `ProcessPoolExecutor` + `proc.kill()` + `per_file_timeout=20`，不覆盖 parser。

### 1.2 两个候选方案

**方案 A（推荐，最小改动，与 Gate 0/Gate 1 既有模式一致）：整件外层子进程隔离**

- 新增 `src/icpdf/parser/run_isolation.py`：
  `run_parse_pdf_isolated(pdf_path, requested_mpn, runs_root, *, timeout, config_path)`。
- 新增 `src/icpdf/parser/_parse_worker.py`：在子进程内调用现有
  `pipeline.parse_pdf()`，**子进程独占 run 目录并写全部 artifacts**；
  结束时用唯一哨兵包裹状态 JSON：
  `__ICPDF_PARSE_JSON_BEGIN__` / `__ICPDF_PARSE_JSON_END__`
  （解决 PyMuPDF C 层把 `MuPDF error:` 写 fd 1 污染 stdout 的已知问题）。
- 父进程 `Popen` + `communicate(timeout=...)`，超时立即 `kill()`；
  按 `returncode` / 哨兵 / JSON 结构分类：
  `OK` / `TIMEOUT_KILLED` / `NATIVE_CRASH` / `BAD_JSON` /
  `PDF_LOAD_ERROR` / `ENCRYPTED` / `WORKER_EXCEPTION`。
- 父进程只读 `run_manifest.json` 与状态 JSON，**不持有任何 fitz 对象**；
  不修改 `text_blocks.py` / `rule_primitives.py` / `page_renderer.py` 一行代码。
- 优点：覆盖上表全部 5 处原生调用；改动面小；与 Gate 0/1 的
  `_gate0_pdf_probe.py`、`_gate1_classify_worker.py` 模式一致；不重建平行解析器。
- 代价：子进程内需自行构造 `RunStore`，`run_id` 由父进程生成后传入，
  避免父子同时 `RunStore.create()` 冲突。

**方案 B（完整但大改，不建议作为 P1 关闭项）：页面原语序列化**

- 子进程内把 `get_text("dict")` 结果、`get_drawings()` 结果、`page.rect`、
  `pixmap` 全部序列化为纯 JSON；父进程用纯 Python 重建
  `TextBlock` / `Table` / `Candidate` Pydantic 模型。
- 优点：父进程彻底无 PyMuPDF 依赖。
- 代价：需重写 `text_blocks.py` / `layout.py` / `rule_primitives.py` /
  `page_renderer.py` 的输入契约，坐标与旋转语义（`coords.py:85-92` 的
  unrotated → `page.rect` 变换）必须逐项回归；属于 Gate 6B 的结构性改造，
  不应在 P1 关闭阶段引入。

### 1.3 不变量（两个方案共同）

1. 单件崩溃/超时**不得终止整批**，且必须在 `per_item_results.csv` 留一行
   `status=EXCEPTION` + `error_reason`。
2. **禁止静默回退**到未保护路径；`ICPDF_TEXT_GUARD=0` 只允许用于
   A/B 对照，正式 run 中该开关存在即判配置异常。
3. 超时阈值、批次大小必须由配置显式给出并写入 `run_config.json`；
   **不得使用未经批准的隐式默认值**（见 `FIELD_MAPPING_FULL.md` §3.6 口径）。
4. 子进程 stdout 只由哨兵之间的载荷解析；哨兵缺失即 `BAD_JSON`。
5. 子进程崩溃前可能已写入部分 artifacts：父进程必须校验
   `run_manifest.json` 存在且 artifacts 列表完整，否则标 `PARTIAL_ARTIFACTS`，
   不得计入成功（对应 `AC-07`/`AC-08`/`AC-11` 的 FP-06）。

### 1.4 与 Gate 6A 的关系

Gate 6A 的 `_parser_worker.py`（方案见 `GATE6A_PARSER_BENCHMARK.md` §8）
可直接复用方案 A 的隔离层；这样 30 件 Parser-only 评估从第一件起就带崩溃保护，
不需要先修完 P1 再评估。但**是否允许在 6A 中引入该隔离层，须 Reviewer 批准**，
本轮不实现、不执行。

### 1.5 测试设计（8 例，仅规格）

| 用例 | 输入 | 预期 |
| --- | --- | --- |
| T1 正常 PDF | 普通文本型 | `OK`，artifacts 齐全 |
| T2 损坏 PDF | 触发 native crash 的样本 | `NATIVE_CRASH`，主进程存活 |
| T3 超时 | fake 长耗时样本 | `TIMEOUT_KILLED`，子进程已 `kill()` |
| T4 stdout 噪声 | `MuPDF error:` 写 fd 1 样本 | 哨兵解析成功，状态 `OK` |
| T5 加密 PDF | 需密码 | `ENCRYPTED`（沿用 `PDFEncryptedError` fail-closed） |
| T6 无文本层 | 扫描件 | `OK` 且 `text_blocks.json` 为空，不误判崩溃 |
| T7 零表文档 | 无表格 | `OK` 且 `tables.json=[]`、`boundary_decisions.json` 仍写出 |
| T8 部分写入 | 子进程中途被杀 | `PARTIAL_ARTIFACTS`，不进成功分母 |

---

## 二、G6-P1-002：缺 `evidence.json` / `parameters.json`

**状态：Gate 6C 暂缓。** 本轮只把缺口与目标态写清，不实现。

### 2.1 缺口（工作台 §5 期望 vs 当前实际）

`backstage/icpdf-extractor_独立工作台规划_修订版.md:245-259` 期望 7 个产物，
当前 `pipeline.parse_pdf():104-161` 实际写出 9 个：
`document.json` / `pages/geometry.json` / `text_blocks.json` / `tables.json` /
`candidates.json` / `boundary_decisions.json` / `product.json` / `run_config.json` /
`run_manifest.json`。

- 期望 `evidence.json` → **缺失**；`src/icpdf/domain/evidence.py:20` 的
  `Evidence` 模型在 `src/icpdf/parser/` 与 `pipeline.py` 中**零实例化**。
- 期望 `qc_report.json` → **缺失**；只有外部只读校验器 `tools/validate_evidence.py`。
- 期望 `raw_extraction.json` → 实际名 `text_blocks.json`，**契约命名不一致**。
- `Parameter` / `FormalParameterSet` 同样零实例化；`product.json` 是占位
  （`normalized_mpn=requested_mpn`、`identity_scope="unknown"`）。

### 2.2 目标产物链（设计，不实现）

```
candidates.json (已存在)
  → evidence_builder.py   : candidate → Evidence（document_sha256 + page + bbox + raw_text + ids）
  → parameter_builder.py  : 同组 candidate（SYMBOL/MIN/TYP/MAX/UNIT/CONDITION）→ Parameter
  → formal_set_builder.py : 仅 verified/audited → FormalParameterSet；其余 → parameters_unresolved.json
  → qc_report_builder.py  : 规则校验/冲突/跳过/unresolved 汇总
  → RunStore.write_json() : evidence.json / parameters.json / qc_report.json
  → run_manifest.json artifacts 追加 3 项
```

### 2.3 不变量

1. `Evidence.document_sha256` 必须等于 `RunStore.copy_source()` 重算的 SHA，
   `page_number>=1`，`bbox` 与 `raw_text` 非空；`cell_text`/`table_row` 必须有
   `table_id/row_id/cell_id`（`domain/evidence.py:41-51` 已强制）。
2. `Parameter` 的 `value/min/typ/max/unit` 全部是 `str | None`，
   保留原文；**禁止**单位换算、范围折叠、`±` 丢符号。
3. `verified`/`audited` 必须带 `evidence_ids`；`unresolved`/`quarantined`/`rejected`
   必须带 `unresolved_reason`（`domain/parameter.py:69-81` 已强制）。
4. `FormalParameterSet` 构造期拒绝非 formal 状态与重复 `parameter_id`。
5. **fail-closed**：任一 Evidence 校验失败，整件标 `SCHEMA_FAIL`，
   不写出部分 formal 参数；`unmapped_legacy` 与原始终 LLM 响应分开保存。
6. 契约版本：新增 3 个产物属于 `data-contract/v0.2` 之外的扩展，
   若要升 `v0.3` 须单独审批；本轮不改契约版本号。

### 2.4 与 Gate 6A 的边界

Gate 6A **不要求**产出 `parameters.json`；它只评估 Parser 是否保留了足够信息
（candidate 的 `column_role`、bbox、页码、原文）让未来系统能正确抽取参数。
`evidence.json` / `parameters.json` 是 Gate 6C 交付物，
在 Parser 基线确认前不实施，避免把 Parser 缺陷误判成 LLM/后处理缺陷。

---

## 三、本轮实际动作

只读核查 5 处主进程 fitz 调用点、工作台 §5 契约、Domain 校验器；
输出上述设计。**新增代码 0 行、修改代码 0 行、测试 0 例、PDF 解析 0 件、
LLM 调用 0 次、数据库操作 0 次。**
