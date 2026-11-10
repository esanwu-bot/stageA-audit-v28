# FIELD_MAPPING.csv 完整 46 行内容与逐项审查矩阵

来源：`gate6/FIELD_MAPPING.csv`（Gate 6 第一轮交付，未修改）。
本文件由 `_build_r2.py` 从该 CSV **逐行原样生成**，不含人工改写，
用于解决「46 行 × 7 列只能证明规模、不能证明映射正确」的问题。

**证据边界**：以下全部是**设计稿**，不是已实现代码；逐项判定是提交方自审，
不等于 Reviewer 已核准。`FIELD_MAPPING_REVIEW.csv` 给出六维逐行判定与待批项。

## 一、原文件完整性

| 项 | 值 |
| --- | --- |
| 路径 | `runs/stage_a_350/gate6/FIELD_MAPPING.csv` |
| SHA-256 | `4560132aded62121e83c5a33a486e4320b3c413a7b1aec949567af0b5f511116` |
| 数据行 | 46 |
| 列数 | 7（每行一致，已逐行校验） |
| BOM | 无 |
| 字段 | `legacy_field` / `legacy_example` / `domain_target` / `mapping_rule` / `forbidden_action` / `risk` / `verdict` |

## 二、46 行完整内容（原样）

| # | legacy_field | legacy_example | domain_target | mapping_rule | forbidden_action | risk | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | metadata.pdf_hash | 0e78a29e...f36c | Document.sha256 | 必须等于 RunStore.copy_source 对 source.pdf 重算的 SHA256Hex 64 位小写 hex;不一致即整件判失败 | 用文件名或清单里的字符串直接填入而不重算 | P0 | DIRECT_MAP |
| 2 | metadata.requested_mpn | DS90C387AVJD_NOPB | Product.requested_mpn | 直接映射为调用方请求的料号;与观测料号分开存储 | 用 basic_info.mpn 覆盖 requested_mpn | P0 | DIRECT_MAP |
| 3 | basic_info.mpn | DS90C387AVJD | identity_candidate (观察区) + 条件性 Product.normalized_mpn | 默认 normalized_mpn=requested_mpn;只有补齐含 kind/page_number/raw_text 的 identity_evidence 后才允许改写 normalized_mpn | 无证据时直接把模型输出写成 normalized_mpn | P0 | CONDITIONAL |
| 4 | basic_info.manufacturer | Texas Instruments | Product.manufacturer (可选 str) | 仅当存在页码与原文证据时写入;否则留在观察区 | 把模型自报厂商当成已验证身份 | P1 | CONDITIONAL |
| 5 | basic_info.category | Integrated Circuits (ICs) | unmapped_legacy | Domain 无自由分类字段;只保留只读观察 | 强行塞进 Product.product_type 或 Parameter.name | P2 | QUARANTINE |
| 6 | basic_info.subcategory | Programmable Oscillators | unmapped_legacy | 同上 | 伪造枚举值 | P2 | QUARANTINE |
| 7 | basic_info.description | 英文一句话描述 | unmapped_legacy | 不属于 formal parameter 容器 | 当作参数或证据 | P2 | QUARANTINE |
| 8 | basic_info.datasheet_url | 空串或 URL | run_config.provenance (只读) | 旧链 core_validation 把空 URL 判为溯源链断开 不得出包;新链同样记为缺陷 | 用猜测 URL 补齐 | P1 | QUARANTINE |
| 9 | basic_info.identity / identity_state | device / board | Product.identity_scope | 由确定性规则映射到 device/board/onboard_device/unknown | 按 identity_confidence 分数裁决 | P1 | CONDITIONAL |
| 10 | basic_info.identity_confidence | 0.95 | 不映射 | 契约第 6 条:置信度只是提示 不能替代证据检查 | 映射成 VerificationStatus.VERIFIED | P0 | DO_NOT_MAP |
| 11 | basic_info.identity_evidence | 列表 | Product.identity_evidence (条件性) | 须含 kind + page_number>=1 + raw_text 非空;bbox 可选;缺项不构造 | 缺页码或原文时伪造证据对象 | P0 | CONDITIONAL |
| 12 | specs.electrical[].name | VIH / RθJA / Rθ(JA) | Parameter.name | 保留原文字符串;同义归一只作为提示 不构成 canonical field | 擅自改写为自造 canonical id | P1 | DIRECT_MAP |
| 13 | specs.electrical[].value | 1.9 / 2.0 to 3.6 / ±2000 | Parameter.value (str\|None) | 原样保留字符串;范围与 ± 号不得规范化 | 把 5V 转成数字 5 并丢掉 V;把 0 to 0.55 折成 0.55 | P0 | DIRECT_MAP |
| 14 | specs.electrical[].unit | V / µA / °C/W | Parameter.unit (str\|None) | 原样保留;value 与 unit 已分列时不得拼接 | 合并后丢失单位 | P0 | DIRECT_MAP |
| 15 | specs.electrical[].condition | TA = 25°C; IOH = -50 µA | Parameter.conditions | 原样保留;含电压/电流/温度/封装变体条件 | 从 Features 或标题段落借条件拼到本行 | P0 | DIRECT_MAP |
| 16 | specs.electrical[] MIN/TYP/MAX 塌缩 | value=2.0 to 3.6; condition 追加 ; min=... max=... | Parameter.min / typ / max | 不得从塌缩字符串反推三列;三列只能从 candidates.json 中 column_role=min/typ/max 的绑定单元格取得;取不到就只填 value 原串 并在 conditions 留痕 | 用 TYP/NOM 顶替 MIN 或一律取 MAX | P0 | GAP_RESOLVE_FROM_CANDIDATES |
| 17 | specs.electrical[].table_id | (旧输出无此字段) | Parameter.table_id (NonEmptyStr 必填) | 必须由 candidates.json 的单元格绑定反查;反查不到整行 UNRESOLVED + unresolved_reason=legacy_has_no_table_id | 编造 table_id 或复用文件名 | P0 | GAP_RESOLVE_FROM_CANDIDATES |
| 18 | specs.electrical[].evidence_ids | (旧输出无此字段) | Parameter.evidence_ids | 只有 verified/audited 才必须非空;每个 id 指向含 bbox/raw_text/page_number 的 Evidence | 用 selected_pages 或 evidence_page_no 充当 evidence_id | P0 | GAP_RESOLVE_FROM_CANDIDATES |
| 19 | specs.electrical[].verification.status | model_unverified | Parameter.verification_status | 旧链所有行一律映射 UNRESOLVED 并附 unresolved_reason;UNVERIFIED 仅用于新链已产生候选但未做证据校验的状态 | 映射成 VERIFIED 或 AUDITED 进入 FormalParameterSet | P0 | DIRECT_MAP |
| 20 | specs.electrical[].verification.reason | 模型抽取 未经过逐格核验 | Parameter.unresolved_reason | 作为 UNRESOLVED 的原因原文保留 | 空理由 | P1 | DIRECT_MAP |
| 21 | specs.electrical[] 多封装列 | condition=New Chip; DCY (SOT-223) 4 PINS | 多个 Parameter + Parameter.package | 每个 (name/package/applicable_mpn/table_id/conditions) 组合出独立行 且 parameter_id 唯一 | 把多列压成一行 只抽第一列 | P0 | EXPAND |
| 22 | specs.electrical[].applicable_mpn | (旧输出无此字段) | Parameter.applicable_mpn (必填非空) | 优先取带证据的 ordering_info[].mpn;其次 basic_info.mpn 且须有 identity_evidence;都不满足则 UNRESOLVED + unresolved_reason=applicable_mpn_unresolved | 用 requested_mpn 冒充已证明的适用型号 | P0 | GAP_RESOLVE_FROM_CANDIDATES |
| 23 | specs.electrical[] | whole array | FormalParameterSet | 只接收 verification_status in {verified audited} 的行;构造期校验重复 parameter_id | 把 unresolved/quarantined 行塞进 formal 容器 | P0 | GATED |
| 24 | specs.absolute_max[] | VCC to GND | Parameter(category=ABSOLUTE_MAXIMUM) | 与 electrical 分家;应力额定值不得混入正常工作参数 | 把 PMAX/Tj/Tstg 写进 electrical | P0 | DIRECT_MAP |
| 25 | specs.thermal[] | Rθ(JA) / RθJC(top) | Parameter(category=THERMAL) | 保留原文名;可复用旧 _thermal_norm 做同义归并提示 但不得替代证据绑定 | 因括号写法不同而丢整条参数 | P1 | DIRECT_MAP |
| 26 | specs.esd[] | HBM ±2000 V | unmapped_legacy | ParameterCategory 无 ESD 枚举;本轮不映射 需契约升级评审 | 临时给枚举加值或塞进 OTHER 后宣称通过 | P1 | QUARANTINE |
| 27 | specs.package.type | 4-VDFN | Product.package / Parameter.package | 作为字符串保留 | 转成整数或代码 | P2 | DIRECT_MAP |
| 28 | specs.package.pins | 4 | (无 Domain 字段) | Domain 无 Pin 模型;进入 unmapped_legacy | 伪造 Pin 模型或写进 Parameter.value | P1 | QUARANTINE |
| 29 | specs.package.dimensions | 3.2mm x 2.5mm | unmapped_legacy | 无对应字段 | 当作电气参数 | P2 | QUARANTINE |
| 30 | specs.temperature.operating | -40°C to 85°C | Parameter(category=OTHER 或 THERMAL 需评审) | 原样保留范围字符串 不得拆成浮点上下界 | 把范围折成单值 | P1 | QUARANTINE |
| 31 | specs.temperature.storage | -65°C to 150°C | unmapped_legacy / 同上 | 同上 | 与 operating 混用 | P2 | QUARANTINE |
| 32 | specs.scope / pin_scope | device | Product.identity_scope | 由确定性规则映射 | 按模型自报 scope 直接改身份 | P1 | CONDITIONAL |
| 33 | pin_configuration[] | {"pin":1 "name":"NC"} | unmapped_legacy | Domain 无 Pin/Pinout 模型;不进 formal 容器 | 伪造模型或把 pin 号写进参数值 | P1 | QUARANTINE |
| 34 | ordering_info[] | 完整可订购料号 | applicable_mpn 的候选来源 (条件性) | 仅在有证据时用于 Parameter.applicable_mpn;多型号时须逐型号展开 | 把 ordering_info 整表当作已验证参数 | P1 | CONDITIONAL |
| 35 | alternatives[] | 替代料号 | unmapped_legacy | 不属于新契约 | 写入 formal 容器 | P2 | QUARANTINE |
| 36 | features / applications / seo / multi_language | 数组或文案 | unmapped_legacy | 只读隔离 不静默丢弃 也不伪造 Domain 字段 | 把文案数值当参数来源 | P1 | QUARANTINE |
| 37 | metadata.selected_pages | [1 2 3 4 5 6 7 8 11 12 13 14 16 17 21 22] | run_config.json 选页预算留痕 | 只证明送进模型的页集合 不是单条参数的来源页 | 映射成 Evidence.page_number | P0 | DO_NOT_MAP |
| 38 | 候选清单 evidence_page_no | NONE (V002 V017 V020) | 不映射 | 这是分类器证据页状态 与解析证据页是两套口径 | 把 NONE 写成 0 空串或猜测页码 | P0 | DO_NOT_MAP |
| 39 | metadata.confidence | 0.95 | 不映射 | 契约第 6 条 | 当作 VerificationStatus 或质量判据 | P0 | DO_NOT_MAP |
| 40 | metadata.model_version | qwen-flash | run_config.llm.model | 记录真实模型名;当前新项目 pipeline.py:186 写空串 需补齐 | 硬编码或用配置名冒充真实调用 | P1 | GAP_FILL |
| 41 | metadata.prompt_version | v3 | run_manifest.prompt_version | 新链须写自己的 prompt_version;当前 pipeline.py:187 写空串 | 沿用旧 v3 冒充新链版本 | P1 | GAP_FILL |
| 42 | metadata.parse_timestamp | 2026-11-10T18:43:08+08:00 | run_config.legacy_parse_timestamp | 是旧链事实 不是 Document.created_at;Document.created_at 必须由新链运行时生成且 timezone-aware | 覆盖 Document.created_at | P2 | QUARANTINE |
| 43 | metadata.core_validation / accept_status / core_sha256 / deterministic_extract | qc 结果 | qc_report.json (只读) | 作为 QC 与确定性抽取留痕 不进 Domain | 当作 Schema 校验通过证据 | P1 | QUARANTINE |
| 44 | legacy 空字符串 | value="" | Parameter.value=None 且 UNRESOLVED | 标记 unresolved_reason=legacy_value_empty | 当成 0 或有效空参数 | P0 | DIRECT_MAP |
| 45 | legacy 占位符字符串 | not_specified / - / — / NA / N/A | UNRESOLVED + unresolved_reason=source_cell_placeholder | 原串保留在只读观察区 | 转成 0 None 或跳过不记录 | P0 | DIRECT_MAP |
| 46 | legacy null 或缺失 key | 字段不存在 | UNRESOLVED + unresolved_reason=legacy_key_missing | 显式区分于空串与占位符 | 用默认数值补齐 | P0 | DIRECT_MAP |

## 三、Reviewer 六项重点的逐行判定

机器可读版见 `FIELD_MAPPING_REVIEW.csv`（46 行，与本节一一对应）。

### 3.1 源字段与目标字段是否一一对应

- `1:1_VERBATIM`：逐字映射，不改写。
- `1:1_CONDITIONAL`：一对一但需证据条件成立。
- `1:1_ENUM`：一对一但需枚举/状态判定，**规则待批**。
- `1:N_EXPAND` / `1:N_CONDITIONAL`：一行拆多行（多封装/多型号）。
- `N:1_ENUM`：多行归并到一个枚举字段，须共用同一套确定性规则。
- `GAP_FROM_CANDIDATES`：旧输出缺该字段，须由 `candidates.json` 绑定单元格反查，**不得凭空生成**。
- `GATED_CONTAINER` / `GAP_FILL` / `QUARANTINE` / `NONE_NO_MAP`：不进 formal 容器。

### 3.2 单位转换规则

**本设计不做单位换算**，只做原文保留：

- R-U1：`value` 与 `unit` 在旧输出中已分列 → 分别写入 `Parameter.value` / `Parameter.unit`，不得合并。
- R-U2：出现 `"5V"` 这类合并串 → 整串保留到 `value`，`unit=None`，
  并标记 `unit_normalization_required` 进 `unresolved_reason`；**禁止**转成数字 5 丢掉 V。
- R-U3：`±2000`、`-40°C to 85°C`、`0 to 0.55` 等符号/范围原样保留，不做浮点化。
- R-U4：`unit` 本身是字符串，`µA` / `°C/W` / `dBFS/Hz` 不得归一化成 `uA` / `C/W`。
- R-U5：若未来要引入单位换算表，须作为**独立契约版本**提交审批；本轮不含任何换算表。

### 3.3 MIN/TYP/MAX 是否独立保留

- Domain 有独立 `min` / `typ` / `max`（`str | None`）。
- 旧链在 `ELEC_RULES_V3` 下把三列塌缩进单个 `value`（如 `"2.0 to 3.6"`），
  并在 `condition` 追加 `; min=..., max=...`。**禁止**从塌缩串反推三列。
- 三列唯一合法来源是 `candidates.json` 中 `column_role = min/typ/max` 的绑定单元格；
  取不到就只保留 `value` 原串，并在 `conditions` 留痕，三列留 `None`。
- 第 16 行即该规则；该规则**待 Reviewer 批准**，未批准前不得实现。

### 3.4 多封装参数保持封装维度

- 旧 `condition` 含 `New Chip; DCY (SOT-223) 4 PINS` 等变体文字。
- 每个 `(name, package, applicable_mpn, table_id, conditions)` 组合生成独立 `Parameter`，
  `parameter_id` 唯一；`Parameter.package` 另存封装字符串。
- 禁止把多列压成一行、禁止只抽第一列；同参数不同封装不是重复行。
- 第 21 行 `EXPAND_PER_VARIANT`、第 34 行 `1:N_CONDITIONAL` 覆盖该维度。

### 3.5 Evidence 缺失时是否明确进入隔离状态

- 旧输出无 `table_id` / `bbox` / 单元格原文，故**所有旧参数行默认 `UNRESOLVED`**。
- `UNRESOLVED` 必须带 `unresolved_reason`；`FormalParameterSet` 构造期拒绝非 formal 状态。
- 证据不足的行写入设想的 `parameters_unresolved.json`（**设计，未实现**），
  不进 formal 容器；不得用 `selected_pages`、`evidence_page_no=NONE`、
  `identity_confidence`、`metadata.confidence` 充当证据。
- 第 17/18/22/23 行是主要闸门；第 37/38/39 行明确禁止三类伪证据。

### 3.6 未经批准的默认值或隐式转换（如实列出，不声明为零）

本设计**存在显式默认值**，全部标为 `needs_reviewer_approval=YES`，未经批准不得实现：

| 编号 | 默认值 / 判定 | 涉及行 | 风险 |
| --- | --- | --- | --- |
| D-01 | `normalized_mpn = requested_mpn` | 3 | 若无身份证据，会把请求值当观测值 |
| D-02 | 旧参数行一律 `UNRESOLVED` | 19, 44, 45, 46 | 保守但需确认不会掩盖可验证行 |
| D-03 | 空串 → `None` + `UNRESOLVED` | 44 | 空串与占位符语义差异需确认 |
| D-04 | 占位符 → `UNRESOLVED` + `source_cell_placeholder` | 45 | 同上 |
| D-05 | 缺 key → `UNRESOLVED` + `legacy_key_missing` | 46 | 同上 |
| D-06 | 类别枚举 `ELECTRICAL/ABSOLUTE_MAXIMUM/THERMAL/OTHER` | 24, 25, 30, 32 | 枚举归属需评审 |
| D-07 | `identity_scope` 的 device/board/onboard_device/unknown 规则 | 9, 32 | 须单一规则源 |
| D-08 | `FormalParameterSet` 只接收 `{verified, audited}` | 23 | 沿用 Domain 现有定义，需确认 |
| D-09 | `requested_mpn` 的取值来源 | 2 | 须指定来自清单/驱动哪个字段 |
| D-10 | ESD / Pin / Ordering / SEO 全部进 `unmapped_legacy` | 26, 28, 33, 36 等 | 不扩枚举、不临时造模型 |

**不存在**的隐式转换（明确保证）：无单位换算、无字符串转数值、无范围折叠、
无占位符转 0/None、无页码推测、无 candidate_id/table_id 编造、无置信度转状态。

## 四、本轮不做什么

- 不修改 `FIELD_MAPPING.csv`（保持 Gate 6 第一轮字节不变）。
- 不实现任何映射代码、不写 `legacy_adapter.py`、不改 Domain 模型。
- 不把本节判定称为「已通过审核」；待 Reviewer 逐项给出关闭条件。
