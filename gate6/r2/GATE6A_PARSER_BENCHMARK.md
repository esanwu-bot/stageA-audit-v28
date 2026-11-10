# Gate 6A · Parser-only Benchmark 方案（仅供 Reviewer 审批，未执行）

**本文件是方案，不是测试报告。** 本轮未打开任何 PDF、未调用 `pipeline.parse_pdf()`、
未调用大模型、未建数据库、未安装依赖、未创建 Gold Set 标注、未修改代码。

路线按 Reviewer 最新裁定调整：**先证明 `icpdf-extractor` 能可靠读懂 PDF，
再让 LLM 理解它读出来的内容**。Gate 6C（LLM 接入）暂缓，Gate 6D 与 320 件未批准。

---

## 0. 路线与状态（按 Reviewer 最新裁定）

| 阶段 | 状态 | 本轮动作 |
| --- | --- | --- |
| Gate 6 原始审计 | 已提交，待证据复核 | 不改第一轮文件 |
| Gate 6A Parser-only 质量测试 | **待方案批准** | 仅提交本方案 + 建议样本清单 |
| Gate 6B Parser 缺陷修复与回归 | 待 6A 结果 | 不实施 |
| Gate 6C LLM 抽取能力建设 | **暂缓** | 上一轮的 Provider/Prompt/Schema/调用链/字段映射材料全部降级为「暂缓草案」 |
| Gate 6D 端到端 30 件正式试跑 | 未批准 | 12 条验收条件仅作草案，不执行 |
| 320 件批次 | 未批准 | 不执行 |

`ICPDF_EXTRACTOR_LLM_READY = false` 保持不变；但**当前主要阻塞项不再是「接 LLM」，
而是「Parser 质量未经基线验证」**。

---

## 1. 前置架构核查：`ic-ex` 是读 JSON 还是自带解析？

### 1.1 身份边界（沿用已确认口径，不另造系统）

`ic-ex = icpdf-extractor`，唯一权威基线 `E:\workspace\icpdf-extractor`；
不存在独立 ic-ex 仓库或独立下游系统；`E:/workspace/github/icpdf-extractor` 是副本，不作依据。

### 1.2 核查结论

**`ic-ex` 自带一套确定性 PDF 解析逻辑；工作台只读 JSON，不解析 PDF；
权威仓库内不存在读取旧项目 JSON 的 importer。**

| 问题 | 结论 | 证据 |
| --- | --- | --- |
| 自带解析模块？ | **是** | `src/icpdf/parser/pipeline.py:94 parse_pdf()` → `pdf_loader.py:41 load_pdf()` → `text_blocks.py:52 extract_text_blocks()` → `table_detector.py:160 detect_tables_with_evidence()` → `table_rebuilder.build_table()` → `candidate_registry.py:42 build_candidates()`。入口 `src/icpdf/cli.py:33 parse()` |
| 工作台是否自带解析？ | **否** | `backstage/icpdf-extractor_独立工作台规划_修订版.md:5` 原文：「本工作台是生产控制面与质量审核面，**不替代解析器、任务队列、数据库或对象存储**」；`backstage/*.html` 只有展示与审核 UI |
| 是否读取旧 `IcPdfParser` 的 JSON（`basic_info`/`specs.electrical`/`data/parsed`）？ | **否** | 对 `src/icpdf/` 与 `backstage/` 全量检索 `basic_info\|specs.electrical\|data/parsed\|parsed_json\|SCHEMA_BASE\|IcPdfParser`，唯一命中是 `src/icpdf/domain/table.py:158` 的注释 `# Physical row lattice copied from TableGrid; empty on legacy artifacts.`，不是读取代码 |
| `ic-ex` 期望的 JSON 字段在哪里定义？ | **有两层** | ① `docs/DATA_CONTRACT.md`（`data-contract/v0.2`）+ `src/icpdf/domain/` Pydantic 模型；② `backstage/…修订版.md:245-259` §5「Extraction Package 数据契约」列出 7 个期望产物 |
| 是否调用 LLM？ | **否** | `parse_pdf()` 全程无 LLM SDK import；`cli.py:80 extract` 仍是 `_not_implemented` |

`backstage/…修订版.md:247` 原文：「第一层交付物是**忠实表达 PDF 的 Extraction Package**，
不是面向网站的最终型号 JSON。」这正是 Gate 6A 要验证的对象。

### 1.3 由此产生的「5 件基线」悖论，必须如实说明

Reviewer 要求「如果 `ic-ex` 内部自带解析模块，提取 5 件跑 `ic-ex` 自带的解析逻辑，
作为现有基线，看 `icpdf-extractor` 能否超越它」。

按已确认身份，`ic-ex` 自带的解析逻辑**就是** `icpdf-extractor` 的 `pipeline.parse_pdf()`。
若 5 件同时跑两者，是自己与自己比，无法得出「超越」结论。因此本方案给出三种条件化对比口径，
请 Reviewer 指定其一（**本轮不执行任何一种**）：

| 口径 | 做法 | 能回答什么 | 限制 |
| --- | --- | --- | --- |
| **C1（推荐）自身基线快照** | 5 件跑当前 `pipeline.parse_pdf()`，产物冻结到 `gate6a/baseline/`，作为 Gate 6B 修复前后的回归对照 | 「修复后相对基线是否提升」 | 不回答「超越另一套系统」 |
| **C2 跨代对照** | 5 件同时取旧项目 `LEGACY_PIPELINE_TRIAL` 残留的**参数级/文本级**结果作对照 | 「旧链与新 Parser 在参数层差异」 | 旧链是 LLM 抽取，不是 parser-only，**不能**与六维度 Parser 指标直接比高低；且本建议清单与旧 30 件仅 1 件重叠（V003） |
| **C3 第三套系统** | 若 Reviewer 指的是另一套解析实现，请指认**具体仓库路径与入口函数** | 「跨实现比较」 | 本轮不臆造、不寻找、不实现；未指认前不启动 |

本方案默认按 **C1** 设计 5 件基线子集（`GATE6A_SAMPLE_PROPOSAL.csv` 中 `baseline_5=TRUE`），
并保留 C2/C3 的切换点。若选 C2 且要求 5 件都与旧 30 件重叠，必须先批准修改样本清单
（当前 30 件为全 350 件目的性抽样，非固定 V001–V030）。

---

## 2. 字段对齐：旧方案 / 新方案 / `ic-ex` 期望结构 三方对比

### 2.1 产物层（Extraction Package 7 件）

| `ic-ex` 期望产物（工作台 §5） | 旧方案 `IcPdfParser` | 新方案 `icpdf-extractor` Parser 实际 | 判定 |
| --- | --- | --- | --- |
| `run_manifest.json` | 无；`rec` 内存 dict → summary CSV | `pipeline.py:163 write_manifest()` ✅ | 新 IMPLEMENTED / 旧 MISSING |
| `document.json` | `metadata.pdf_hash` / `parse_timestamp` / `pages="used/total"` | `pipeline.py:104` ✅ | 新 IMPLEMENTED / 旧 PARTIAL |
| `raw_extraction.json`（文本块/行/词/坐标） | 只有 `metadata.selected_pages` 与送入模型的纯文本字符串，无坐标 | `text_blocks.json` + `pages/geometry.json`（含 bbox/words）✅ 但**文件名不同** | 新 PARTIAL（命名/契约不一致）/ 旧 MISSING |
| `tables.json`（物理表格/行列/cell/表头层级/bbox/未决原因） | 无；LLM 直接自由输出 `specs.*` | `tables.json` + `boundary_decisions.json` ✅ | 新 IMPLEMENTED / 旧 MISSING |
| `candidates.json`（语义候选/原始值/标准化值/上下文） | `specs.electrical[].value/unit/condition` 扁平数组 | `candidates.json`（`raw_text` / `normalized_value` / `unit` / `column_role` / `role_source` / `bbox`）✅ | 新 IMPLEMENTED / 旧 MISSING |
| `evidence.json` | 无（`selected_pages` + `verification.status=model_unverified`） | **缺失**（G6-P1-002） | **两侧 MISSING** |
| `qc_report.json` | `metadata.core_validation` / `accept_status` / `core_sha256` | **缺失**（`tools/validate_evidence.py` 是外部只读校验器，不写 run 内 qc_report） | 新 MISSING / 旧 PARTIAL |

另外新方案多出 3 个非期望产物：`product.json`（占位）、`run_config.json`、
`boundary_decisions.json`；工作台 §5 未要求，需确认是否保留。

### 2.2 字段层（PDF 表格结构 → `ic-ex` Domain 模型）

以 Reviewer 给出的示例表 `Symbol | Parameter | Min | Typ | Max | Unit` 为基准：

| PDF 表格元素 | 旧方案 `IcPdfParser` | 新方案 Parser artifact | `ic-ex` Domain 目标 |
| --- | --- | --- | --- |
| 行标签 `VCC` / `Supply voltage` | `specs.electrical[].name`（自由文本） | `Candidate.column_role=SYMBOL` / `candidate_type=ROW_LABEL` | `Parameter.name` |
| `Min=4.5` | 塌缩进单个 `value`（如 `"4.5 to 5.5"`） | `ColumnRole.MIN` + `normalized_value` | `Parameter.min: str\|None` |
| `Typ=5.0` | 同上 | `ColumnRole.TYP` | `Parameter.typ: str\|None` |
| `Max=5.5` | 同上 | `ColumnRole.MAX` | `Parameter.max: str\|None` |
| `Unit=V` | `unit` 字符串（易与 value 合并） | `ColumnRole.UNIT` + `Candidate.unit` | `Parameter.unit: str\|None` |
| 测试条件 | `condition` 自由文本 | `ColumnRole.CONDITION` | `Parameter.conditions` |
| 单元格坐标 | 无 | `Cell.bbox` / `Candidate.bbox` | `Evidence.bbox` |
| 原文页码 | 无 | `Cell.page_number` / `Candidate.page_number` | `Evidence.page_number` |
| 表格归属 | 无 | `table_id` / `row_id` / `cell_id` | `Evidence.table_id/row_id/cell_id` |
| 单元格原文 | 无 | `raw_text` | `Evidence.raw_text` |
| 文档身份 | `metadata.pdf_hash` | `Document.sha256` | `Evidence.document_sha256`（Sha256Hex） |
| 适用型号 | `basic_info.mpn`（模型自报） | `Product.requested_mpn`（**占位**，`normalized_mpn=requested_mpn`） | `Parameter.applicable_mpn`（必填非空） |
| 封装维度 | `condition` 里的文字 | 无独立产物 | `Parameter.package` |
| 正式参数容器 | `specs.electrical[]` 数组 | **未产出** | `FormalParameterSet`（只收 `verified/audited`） |

**关键结论**：`src/icpdf/domain/candidate.py:13` 的 `ColumnRole` 已含
`MIN/TYP/MAX/UNIT/SYMBOL/CONDITION` 六个角色，`candidate_registry.py:60-89`
也把角色、bbox、页码、原文写进了每个 candidate。所以**结构上具备"靠拢 Domain"的基础**，
但 `pipeline.parse_pdf()` 止步于 candidate，**没有实例化 `Parameter` / `Evidence` /
`FormalParameterSet`**（G6-P1-002）。Gate 6A 必须验证的是「结构信息是否完整保留」，
而不是「参数是否已抽取」。

**两类典型错误的检测点**（对应 Reviewer 示例）：
- `5.0 V` 被简化成 `5.0` → `Cell Text Accuracy` + `Column Alignment Accuracy` 同时判失败；
- MIN/TYP/MAX 合并成一个值 → `Column Alignment Accuracy` 判失败，
  且 `tables.json` 中该表 `column_roles` 应仍为 3 个独立列，不得塌缩。

---

## 3. 历史解析痛点清单（真实证据，用于刻意放大样本）

以下痛点来自本仓库与旧项目的**真实文档/代码**，不是推测。样本清单的
`painpoint_amplification` 字段逐件标注了对应编号。

| 编号 | 痛点 | 证据 |
| --- | --- | --- |
| PAIN-01 | 跨页表格合并/衔接 | `docs/方案讨论.txt:239`「跨页表格合并」；`:311`「复杂表格（跨页、多层表头）」 |
| PAIN-02 | MIN/TYP/MAX 塌缩、单位错乱、跨表匹配 | `docs/检查错误清单.txt:8`「74AC11800DW 把推荐 MIN/NOM/MAX 串成 3 5 5.5V」「DRV10963 五款把推荐电压 2.1—5.5V 覆盖进绝对最大额定值」；`IcPdfParser/parse_datasheets.py:400-432` `ELEC_RULES_V3` 三条安全规则 |
| PAIN-03 | 多层表头、合并单元格、极端表头解析 | `docs/方案讨论.txt:239`「极端表头解析」；`:311`「多层表头」 |
| PAIN-04 | 多封装列只抽第一列 / 整条热阻参数漏掉 | `IcPdfParser/parse_datasheets.py` `SYSTEM_PROMPT` 规则 4e/4f/4g（原文「只抽第一列等于把另外几个封装的热阻/参数全部丢掉，这是数据造假」） |
| PAIN-05 | 多型号/变体参数串用 | `docs/检查错误清单.txt:10`「ADC12DL1500ACF 继承 2500 变体采样率」 |
| PAIN-06 | 跨页表头丢失、表头归属不明 | 同上 §PAIN-01 + `backstage/…修订版.md:259`「无法证明的边界、表头归属或参数条件必须保留 unresolved reason」 |
| PAIN-07 | 常规文本漏字/错序/字符完整性 | `configs/parser.yaml` `text_min_chars: 1`；`text_blocks.py:52` 逐 span/word 抽取 |
| PAIN-08 | 文本层缺失/乱码（OCR 需求） | Gate 0 预检字段 `has_text_layer`；`IcPdfParser/parse_datasheets.py:692 text_is_garbled()` |
| PAIN-09 | 特殊符号：`Rθ(JA)` vs `RθJA`、`±2000`、`µ`、上划线 | `IcPdfParser/qc/deterministic_extract.py::_thermal_norm()` 模块说明；`SYSTEM_PROMPT` 规则 4d（ESD `±2000` 不得写成 `+2000`）；`qc/symbols_overbar_scan.py` |
| PAIN-10 | 证据链缺失 / 分类器证据页 NONE | `docs/方案讨论.txt:311`「没有证据链（Evidence）」；`ds_parse_candidates_350_v2.csv` 中 26 件 `evidence_page_no=NONE` |
| PAIN-11 | EVM/板卡混入、器件身份错配 | `docs/检查错误清单.txt:7`「AFE7950 误成 AFE7950EVM；部分 EV/DEMO 板卡误成裸芯片」；Gate 1 `PATH_ALIAS_PROBE.md` 的 P2 路径依赖 |
| PAIN-12 | 板级指南被当成芯片手册、引脚/封装列混用 | `docs/检查错误清单.txt:9`「74ACT11020DR 用 20 脚而 D 封装应 14 脚；BQ24261RGET/BQ24262RGER 用 BGA 球位描述 24 脚 VQFN」；`:101` TPS2391EVM |

补充观察项（不占配额）：`IcPdfParser/qc/deterministic_extract.py` 模块说明记录
`find_tables` 会把 `0.23` 读成 `023.`（小数位融合，无法反推小数点）；
`docs/检查错误清单.txt` 74ACT11132D 行记录「参数名被写进数值端点」。
这两项并入 PAIN-02 / PAIN-09 的检查表。

**放大策略**：30 件中 4 件取自 `page_count >100`（PAIN-01/03）、4 件取自另一批
`>100`（PAIN-01/06）、4 件取双段命名（PAIN-04/05）、3 件取 `page_count<=10`
（PAIN-08/09）、2 件取 `evidence_page_no=NONE` 与 V022（PAIN-10/11/12）。
即 **17/30 件刻意落在痛点区**，远高于按页数均匀抽样的自然占比。
所有类型标签均为 `PROPOSED_PENDING_GOLD_CONFIRMATION`，须人工确认。

---

## 4. 30 件建议样本清单

文件：`GATE6A_SAMPLE_PROPOSAL.csv`（30 行 × 12 列），统计见 `GATE6A_SAMPLE_STATS.json`。
来源：`runs/stage_a_350/ds_parse_candidates_350_v2.csv`（350 件，
SHA-256 `040a0e78322089387f3237c0db2f487d37cd17d9de887ec9d5e647345ae05839`）。

| 建议配额 | 件数 | 抽样依据（只读清单字段） |
| --- | --- | --- |
| 普通文本型 Datasheet | 6 | `page_count` 11–30 且 `evidence_page_no != NONE` |
| 复杂参数表 | 6 | `page_count` 31–100 |
| 多级表头、合并单元格 | 5 | `page_count > 100` 前 5 |
| 多封装或多型号 | 4 | 文件名含 `__` 双段命名线索 |
| 跨页表格 | 4 | `page_count > 100` 随后 4 |
| 扫描型或复杂版面 | 3 | `page_count` 5–10（**清单无法判定扫描/无文本层，须人工确认**） |
| 边界或异常文档 | 2 | 1 件 `evidence_page_no=NONE` + 指定检查点 V022（疑似 EVM） |
| **合计** | **30** | |

抽样按 `pdf_sha256` 确定性定序，可复现；**SHA 只用于选样排序，执行阶段严格使用
`file_path` 原文寻址，禁止按 SHA 全盘搜索路径**（Gate 1 P2 `G1-P2-001` 硬约束）。

- `baseline_5=TRUE` 5 件：跨 5 个不同配额各 1 件（见 `GATE6A_SAMPLE_STATS.json`）。
- `legacy_reference=TRUE` 仅 1 件（V003）：本清单是全 350 件目的性抽样，
  与旧项目 `V001–V030` 不重合。旧项目 30 件残留只作历史参考，**成绩不混合**。
- 类型替换规则：Gold Set 人工确认若判定某件与建议配额不符，须提交
  `sample_substitution.csv` 记录原编号、新编号、理由，**经 Reviewer 批准后**替换，
  不得静默改写清单。

---

## 5. Gold Set 设计（格式草案，本轮不创建任何标注）

每件一个 `gold/<sample_no>.json`，另加 `gold/GOLD_MANIFEST.json`。
字段草案（逻辑结构，非可执行 Schema）：

```json
{
  "gold_version": "gate6a-gold/v0.1-draft",
  "sample_no": "V097",
  "document_sha256": "<64 hex，与 file_path 重算一致>",
  "file_path": "<候选清单原文>",
  "page_count": 52,
  "stratum_confirmed": "PENDING",
  "reviewer": "",
  "reviewed_at": "",
  "status": "DRAFT",
  "target_tables": [
    {
      "table_id": "gold-t01",
      "page_number": 12,
      "bbox": [x0, y0, x1, y1],
      "table_type": "electrical_characteristics",
      "header_levels": 2,
      "cross_page_group_id": null,
      "rows": [
        {"row_id": "r01", "cells": [
          {"cell_id": "c01", "column_id": 0, "text": "VCC",
           "bbox": [], "page_number": 12, "gold_column_role": "symbol"},
          {"cell_id": "c02", "column_id": 1, "text": "4.5",
           "bbox": [], "page_number": 12, "gold_column_role": "min"}
        ]}
      ]
    }
  ],
  "expected_candidates": [
    {"symbol": "VCC", "min": "4.5", "typ": "5.0", "max": "5.5",
     "unit": "V", "condition": "", "package": "", "applicable_mpn": ""}
  ],
  "evidence_anchors": [
    {"page_number": 12, "bbox": [], "raw_text": "4.5"}
  ],
  "pain_tags": ["PAIN-02"],
  "notes": ""
}
```

规则：

1. `status` 只能是 `DRAFT → CONFIRMED`；**只有 `CONFIRMED` 的条目才进入指标计算**。
2. Gold 由人工对照 PDF 原始页面填写，记录 `reviewer` / `reviewed_at`；
   禁止用 Parser 输出反填 Gold（会自我印证）。
3. `gold_column_role` 必须逐单元格给出 `symbol/min/typ/max/unit/condition/other`，
   这是 `Column Alignment Accuracy` 的唯一真值来源。
4. `bbox` 使用 `docs/DATA_CONTRACT.md` 冻结的 PDF page display 空间（pt，左上原点）。
5. `cross_page_group_id` 用于 `Cross-page Continuity`；无跨页填 `null`。
6. Gold 版本、逐件 SHA-256 写入 `GOLD_MANIFEST.json` 与 `SHA256SUMS.txt`；
   Gold 一旦 CONFIRMED 即冻结，变更须升版本号并留 diff。
7. **本轮不设通过门槛**：先建 Gold Set、统计各项基线，再由 Reviewer 确定阈值。

---

## 6. 评估指标（7 项，只定义口径，不设总分阈值）

| 指标 | 评价对象 | 计算口径（分子/分母） | 数据来源 |
| --- | --- | --- | --- |
| Table Recall | 目标参数表是否被发现 | Gold `target_tables` 中能在 `tables.json` 找到同页且 bbox 对应的表数 / Gold 目标表总数 | `tables.json` |
| Table Structure Accuracy | 行列与表头结构 | 行列数、表头层级、合并单元格归属全部与 Gold 一致的表数 / 已匹配表数 | `tables.json` + `boundary_decisions.json` |
| Cell Text Accuracy | 单元格文字逐字正确 | 与 Gold `text` 逐字一致的 cell 数 / Gold cell 总数（含 `±` `µ` `Rθ(JA)` 上划线） | `tables.json` |
| Column Alignment Accuracy | MIN/TYP/MAX/UNIT 对应正确 | `column_role` 与 Gold `gold_column_role` 一致的列数 / Gold 标注列总数；重点抓「三列合并」「丢单位」 | `candidates.json` |
| Candidate Recall | 关键参数表候选是否漏检 | Gold `expected_candidates` 中有对应 candidate 的条目数 / Gold 候选总数 | `candidates.json` |
| Evidence Localization Accuracy | 页码/坐标/原文可回溯 | `page_number` + `bbox` + `raw_text` 三项均能对回 PDF 原位置的 candidate 数 / 抽检 candidate 数 | `candidates.json` + `tools/validate_evidence.py` + 人工复核 |
| Cross-page Continuity | 跨页表格衔接 | Gold 中 `cross_page_group_id != null` 的组里，被正确衔接或**明确标 unresolved** 的组数 / 跨页组总数 | `tables.json` |

配套约束：

- 匹配判定阈值（bbox IoU、文本相似度容差）**本轮不给数值**，由 Reviewer 在看到基线分布后确定。
- 不设加权总分，不以「平均通过率」代替逐项结果；每项单独报 `numerator / denominator / value`。
- 逐件结果落 `per_item_metrics.csv`；`metrics.json` 的所有汇总数字必须能**只读逐件 CSV 盲重算**复现（沿用 Gate 1 硬条件 4）。
- 失败/异常件必须有一行逐件记录并写 `error_reason`，不得从分母中静默剔除。

---

## 7. 与 `ic-ex` 的对比方法（含 C1/C2/C3 切换）

1. 按 §1.3 由 Reviewer 指定口径；默认 C1。
2. 5 件基线子集（清单 `baseline_5=TRUE`）单独目录 `gate6a/baseline/`，
   与 30 件正式产物 `gate6a/runs/<run_id>/` **物理隔离**。
3. 每件独立 `RunStore` run_id（`RunStore.create()` 自动生成，已存在则拒绝覆盖）。
4. 基线产物冻结后生成 `baseline/SHA256SUMS.txt`；Gate 6B 修复后用同一 5 件重跑，
   逐指标出 `delta`，只报「提升/持平/回退」，不宣称「超越另一套系统」。
5. 若选 C2：旧项目残留只从 `runs/stage_a_350/gate2a/` 读取，目录仍带
   `LEGACY_PIPELINE_TRIAL` 标记，结果写入 `gate6a/legacy_comparison/`，
   且**只做参数级/文本级定性对照，不并入六维度 Parser 指标分母**。
6. 若选 C3：等 Reviewer 给出具体路径与入口后另出补充方案，本轮不启动。

---

## 8. 评估脚本方案（只给契约，本轮不实现、不执行）

拟新增（**均未创建**）：

| 拟建文件 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| `runs/gate6a/_benchmark.py` | 逐件驱动 + 指标计算 | `GATE6A_SAMPLE_PROPOSAL.csv` 的 `file_path`、Gold `CONFIRMED` 集合、独立 runs 根目录 | `per_item_metrics.csv`、`metrics.json`、`GATE6A_REPORT.md` |
| `runs/gate6a/_parser_worker.py` | 单件子进程隔离（对应 G6-P1-001 设计） | 单个 `file_path` + run_id | sentinel 包裹的 JSON 状态；崩溃/超时由父进程 `kill()` |
| `runs/gate6a/_gold_verify.py` | Gold 完整性 | `GOLD_MANIFEST.json` | Gold 版本、逐件 SHA、CONFIRMED 数量校验 |
| `runs/gate6a/_contract_check.py` | §2.1 七产物契约对齐 | 每件 run 目录 | `artifact_contract.csv`（7 件存在性 + 字段存在性） |
| `runs/gate6a/_metrics_verify.py` | 盲重算 | 只读 `per_item_metrics.csv` | 0 不一致校验结果 |
| `runs/gate6a/SHA256SUMS.txt` | 完整性 | 本目录全部交付件 | `sha256sum -c` 全 OK |

运行前提（**本轮均不满足，故不执行**）：

- 隔离 venv 装齐 `pyproject.toml` 声明的 `typer` / `pyyaml` / `rich` / `python-dotenv`
  （当前环境四项全缺，`python -m icpdf.cli` 与集成测试在 import 阶段即失败）；
- `GATE6A_SAMPLE_PROPOSAL.csv` 与 Gold Set 经 Reviewer 批准；
- 逐件子进程保护壳方案（G6-P1-001）获批或在脚本中以受控方式隔离；
- 明确 `cli.py parse` 命令**不调用 LLM**（已由源码核查确认：`pipeline.parse_pdf()`
  无 LLM SDK import，`extract` 仍占位）。

红线：评估脚本不得调用任何 LLM、不得写数据库、不得修改 `src/icpdf/`、
不得把 `LEGACY_PIPELINE_TRIAL` 残留计入 Parser 指标、不得自行判定 `CONTENT_QC`。

---

## 9. 只读边界与等待审批事项

本轮实际执行：只读 `git` / CSV / 源码 / 文档检索，生成方案与建议清单，
生成哈希清单与校验 JSON。**PDF 打开次数 0、Parser 调用 0、LLM 调用 0、
Gold 标注 0、依赖安装 0、数据库操作 0、代码改动 0、主项目 Git 提交 0。**

等待 Reviewer 确认：

1. §1.3 的对比口径选 C1 / C2 / C3；若 C3 请给具体路径与入口函数。
2. 30 件建议配额与具体编号（`GATE6A_SAMPLE_PROPOSAL.csv`）；
   特别是「扫描型或复杂版面」3 件无法由清单字段判定，需人工确认。
3. Gold Set 字段草案与 `DRAFT → CONFIRMED` 流程。
4. 7 项指标口径与「匹配判定阈值待基线后确定」的安排。
5. §2.1 中 `raw_extraction.json` 命名不一致、多出的 3 个产物是否保留。
6. Gate 6A 的独立目录、`Run ID` 前缀与审批令牌形式。

以上任一未确认前，Gate 6A 保持 `NOT_STARTED`；Gate 6B/6C/6D 与 320 件均不启动。
