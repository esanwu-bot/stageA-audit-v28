# 分类器最小修订方案（设计文档）

**状态**：设计草案，待 Reviewer 审批
**适用版本**：`docclassifier-2.2.1` / `doc-classifier-v2`
**前置约束**：本轮**冻结代码**，`ICEX_WORKBENCH_ALLOW_PARSE=0`，不新增、不修改任何实现。本文只描述"应该怎么改"，不含实现。

---

## 0. 阅读约定：三类陈述必须分开

本文每条关键结论都标注类型，请按类型分配信任度：

| 标记 | 含义 | 证据要求 |
| --- | --- | --- |
| **【事实】** | 已观察、可复现。来自归档响应、代码只读复核或实测 | 必须给出可复现路径 |
| **【假设】** | 待验证。样本量不足，或依赖尚未检验的分布假设 | 必须写明"用什么验证、验证到什么程度才算成立" |
| **【推论】** | 设计判断。基于事实与假设推导出的"应该怎么改" | 必须写明前提；前提不成立则结论失效 |

**本文最重要的一条纪律**：不要把【假设】写成【事实】。上一轮 `DEFECT-001` 就犯了这个错——见 §1。

---

## 1. 更正声明（必须先读）

上一轮 `evm_probe/FINAL_VERDICT.md` 中 `DEFECT-001` 的「现象」是这样写的：

> 样本 A 的 PDF 元数据 Title 中同时包含了板载 IC 型号（ADC08xx0）和文档类型（Evaluation Module User's Guide）。规则 `DS_PRODUCT_MODEL_TITLE` 仅在字符串中匹配到了型号，就记了一票强 DS 证据……

**这个描述是错的。** 本轮做只读复核时发现它与实际触发链不符，现予更正：

**【事实】实际触发链**：`DS_PRODUCT_MODEL_TITLE` 匹配到的"型号"不是 `ADC08xx0`，而是**文档号 `SLAU715A`**。

复现方式（只读，不启动服务、不调用 Parser）：

```
read_head(A)                    → meta_title = "ADC08xx0 Evaluation Module User's Guide (Rev. A)"
parse_provenance(A 的文件名)     → document_subject_mpn = "slau715a"
_classify_worker 把 subject 传给 scan_pages  → mpn 参数实际是 "slau715a"
mpn_root("slau715a")            → "SLAU715A"
title_block 含 "SLAU715A"        → True   （首页第 2 行 "SLAU715A–February 2017–…"）
DEVICE_WORD_RE 命中              → "ADC"  （来自元数据标题里的 "ADC08xx0"）
⇒ DS_PRODUCT_MODEL_TITLE 记一票 STRONG
```

对照样本 B：`document_subject_mpn = "sluuaa7a"` → root `SLUUAA7A` **同样出现在标题块**，但 `DEVICE_WORD_RE` **无命中**（B 的标题是 "User's Guide for bq25570 Battery Charger Evaluation Module…"，`battery` / `charger` 都不在器件词表里）→ 规则**不触发**。

**为什么这个区别至关重要**：

- 原描述指向"元数据路径不可靠"，对应的修法是"给 metadata 降权"。
- 真实根因是"**文档号被当成了器件型号**"，对应的修法完全不同——降权 metadata 对这个缺陷**毫无作用**，因为文档号 `SLAU715A` 出现在**首页正文**（第 2 行），不在 metadata 里。

按原描述去改，会改错地方。这是本文存在的首要理由。

**处理建议**：`DEFECT-001` 的修订版已发布，见 `evm_probe/DEFECT-001_REVISED.md`（该文件显式推翻原版归因，并附只读复现日志 `61_defect001_repro.log`）。`FINAL_VERDICT.md` 正文保留原版原文不动，供审计对照；修订以 `DEFECT-001_REVISED.md` 为准，本文 §1 与其完全一致。

---

## 2. Q1 — `DS_PRODUCT_MODEL_TITLE` 的证据语义

### 2.1 三个证据平面必须先分清

**【事实】** 当前实现里，三个平面在代码中的实际归属：

| 平面 | 物理位置 | 代码中的 `EvidenceSource` | 是否进入 `title_block` |
| --- | --- | --- | --- |
| 元数据 | PDF `Title` / `Subject` 字段 | `METADATA` | 是（拼接在最前） |
| 首页标题区 | 第 1 页前 6 个非空行 | `FIRST_PAGE` | 是（拼接在后） |
| 正文 | 第 2 页及以后 | `BODY` | 否 |

**【事实】** `title_block` = 元数据 Title + 元数据 Subject + 首页前 6 个非空行，三者用空格拼成一个**单一字符串**。

这个拼接是问题的温床：拼接之后，**来源信息就丢了**。规则在 `title_block` 上做正则，无法区分"这个词来自出版方填的元数据"还是"来自 TI 排版的首页页眉"。样本 A 正是这样——"SLAU715A"来自首页页眉，"ADC"来自元数据标题，两者被拼进同一个字符串后一起满足了规则。

**【事实】一处内部不一致**：`DS_PRODUCT_MODEL_TITLE` 的规则声明里写的是 `EvidenceSource.FIRST_PAGE`，但它实际产出的命中记录是 `EvidenceSource.METADATA`。两者对不上。任何"按 `source` 字段做降权/门控"的修法，都会踩到这个不一致——**修之前必须先把它统一**。

### 2.2 现状机制（已观察事实，逐条可复现）

**【事实】** 规则触发需要同时满足三个条件：

| # | 条件 | 样本 A 的取值 |
| --- | --- | --- |
| 1 | 存在一个"根"，长度 ≥ 4 | `mpn_root(document_subject_mpn)` = `SLAU715A` |
| 2 | 该根**逐字**出现在 `title_block` 中（大小写不敏感） | `SLAU715A` 出现在首页第 2 行 |
| 3 | `title_block` 中任意位置命中器件描述词 | `ADC`（来自 `ADC08xx0`） |

**【事实】** 条件 1 用的根，来源是 `document_subject_mpn`——即文件名 `__` 后半段的**文档号**（`slau715a`），不是产品型号（`ADC08060EVM`）。函数名 `mpn_root()` 与实参语义不符：它剥的是 EVM 家族后缀，而传入的是文档号，文档号没有这类后缀，于是**原样返回**。

**【推论】** 这是**类型混淆**：一条名为 `PRODUCT_MODEL_TITLE`（产品型号标题）的规则，被喂了一个**文档编号**。文档号天然会出现在标题块（TI 每份文档首页都有 `SLAUxxx`/`SBAAxxx`），所以条件 2 几乎恒真；条件 3 只要标题里出现 `ADC`/`DAC`/`driver` 等任一子串就满足。**两个弱条件相乘，产出了一个 STRONG 结论。**

**【事实】** 条件 3 的匹配是子串匹配，不是词边界匹配。`ADC` 在 `ADC08xx0` 内部即被命中。

### 2.3 正反例：如何用"文档主语"语义区分

设计目标：**既抓出真正的 IC Datasheet（哪怕型号只出现在 metadata），又排掉 `<IC型号> Evaluation Module User's Guide` 这种陷阱。**

| 类型 | 样本 | 标题块内容 | 应判 | 依据（文档主语是谁） |
| --- | --- | --- | --- | --- |
| 正例 1：metadata 里就是主语型号 | 假设的 `ADS1299__ads1299.pdf`，Title = `ADS1299 Low-Noise ADC Datasheet` | 型号 + 器件类型 + 文档类型词 `Datasheet` | **应记 DS 证据** | 主语是 `ADS1299` 这颗芯片；`Datasheet` 明示本体类型 |
| 正例 2：主语型号 + 电气内容 | `CD4098BE-NG__cd4098b.pdf`（V002，实解析通过） | 型号 + 正文含电气章节 | **应记 DS 证据** | 主语是芯片，且有正文佐证 |
| **反例 1（本次缺陷）** | `ADC08060EVM__slau715a.pdf` | `ADC08xx0 Evaluation Module User's Guide` + `SLAU715A` | **不应记 DS 证据** | 主语是**评估板**；`ADC08xx0` 是**板上的器件**；`SLAU715A` 是**文档号** |
| 反例 2：文件名带 EVM 但本体是 DS | `CC2500EMK__cc2500.pdf`（V022） | `… 2.4 GHz RF Transceiver datasheet (Rev. C)` | **应判 DS**（不能因文件名判 EVM） | 主语是 `CC2500` 芯片；文件名前缀是采集噪声 |
| 反例 3：板级 Schematic 语境 | 任何 UG 里的 `Typical Application Schematic` | 含 Schematic 字样 | **不应据此判 EVM** | 这是被测 IC 的应用电路，不是整板原理图 |

**关键区分点不是"哪个平面"，而是"这个 token 在语义上指谁"。**

三个可操作的判据：

1. **文档号不是型号。** `SLAU`/`SBAU`/`SLAA`/`SBAA`/`SWRA` 等前缀是 TI 文档编号体系，`mpn_root` 遇到它们必须返回空，不得作为型号根。这是本次缺陷的**直接堵口**。
2. **文档类型词否决。** 若命中位置附近（同一标题块）出现 `Evaluation Module` / `User's Guide` / `EVM` / `Board`，则该次型号命中不得计为 DS 证据——因为标题已经自述了本体类型。
3. **主语归属判定。** 若型号根来自 `source_product_mpn`（文件名前缀）而文档号来自 `document_subject_mpn`（文件名后缀），二者不一致时，说明"这份文档讲的是板载器件、归属在板级资料里"，此时型号命中只能作**辅助**（MEDIUM），不能作 STRONG。

### 2.4 严禁一刀切禁用 metadata

**【推论】** 禁用 `source=metadata` 是错的，理由有三：

1. **会误伤真 Datasheet。** 大量正规 Datasheet 的型号**只在** metadata Title 里规范书写（`ADS1299 8-Channel 24-Bit ADC`），正文首页是排版图片或页眉噪声。禁用 metadata 等于把这批文档推向 `UNKNOWN`。
2. **打不到本次缺陷。** 触发本次命中的文档号 `SLAU715A` 来自**首页正文**，不是 metadata。禁用 metadata 对 A 无效（§1 已论证）。
3. **metadata 恰恰是最干净的结构化字段。** 它由出版方按规范填写，比正文 OCR 噪声低。问题不在"用了 metadata"，而在"用了却没校验语义"。

**【推论】** 正确方向是**给 metadata 增加语义校验**，而不是关闭它：

- metadata 命中 → 必须与正文证据**交叉验证**（同一型号在正文出现，或正文有电气章节）；
- metadata 命中 → 若同块含文档类型词，降为 MEDIUM；
- 文档号类 token → 无论来自哪个平面，一律不作为型号证据。

---

## 3. Q2 — EVM 板级证据的优先级

### 3.1 信号强弱定义（【事实】，取自现行实现）

| 信号 | 代码中的声明来源 | 声明强度 | 是否进 `board_strong` | 实际作用 |
| --- | --- | --- | --- | --- |
| `EVM_BOARD_SCHEMATIC` | 首页正文 | STRONG | **是** | 最强板级证据；能触发"板级压倒 IC 段落" |
| `EVM_BOARD_TITLE`（组 = `EVAL_MODULE`/`BOARD`/`DEV_KIT`） | 标题块 | STRONG | **是** | 板级主体标题，单独即可裁决 |
| `EVM_BOARD_TITLE`（组 = `USER_GUIDE`） | 标题块 | **MEDIUM** | **否** | 只作辅助；"User's Guide" 过于宽泛，芯片也可能有 |
| `DOCNUMBER_UG`（`SLAU`/`SBAU` 前缀） | 文件名 | MEDIUM | **否** | 仅提示；不参与 `board_strong` |
| `EVM_BOARD_TERMS`（Jumper/BOM/Test Points） | 首页正文 | MEDIUM | **否** | 需 ≥2 类组合才有效 |
| `DS_PRODUCT_MODEL_TITLE` | 标题块 | STRONG | —（DS 侧） | 与 `DS_DOCUMENT_TITLE` 同属 DS 标题级强证据 |

**【事实】** 裁决阶梯的关键顺序（这决定了 A 的命运）：

| 档 | 条件 | 结论 |
| --- | --- | --- |
| 档 5 | **两侧都有标题级 STRONG**（`board_strong` 且 `ds_title_strong`） | `UNKNOWN` + `conflict=true` ← **A 停在这里** |
| 档 1 | 仅 `board_strong` | `EVM` / high（并把 DS 命中写进 `rejected_rules`） |
| 档 3/4 | `ds_strong`（标题强证据 或 电气章节组合） | `DS_STRONG` |
| 档 2 | 仅 `board_body`（板级词 ≥2 类） | `EVM` / medium |
| 后续 | 仅 `USER_GUIDE` 组标题 | `UG` / medium |
| 档 6 | 无强证据 | `DS_WEAK` 或 `UNKNOWN`/`REVIEW` |

**注意档 5 在档 1 之前。** 只要 DS 侧出现**任何**标题级 STRONG，板级证据就再也拿不到裁决权——即使板级证据更充分。这是"冲突优先于裁决"的设计，本身是保守的、正确的；但它把**误报的代价放大**了：一条虚假 DS 强证据，就能让一份证据充分的 EVM 掉进人工池。

### 3.2 A 为什么冲突（精确链条，【事实】）

```
board_strong     = True   ← EVM_BOARD_TITLE「Evaluation Module」(STRONG)
ds_title_strong  = True   ← DS_PRODUCT_MODEL_TITLE（虚假：文档号 SLAU715A 被当作型号根）
                          ↓
                    档 5 触发 → UNKNOWN / REVIEW / conflict=true
```

**【推论】这不是"两个合理证据对撞"，而是"一个真证据 + 一个假证据对撞"。** 表面看是分类器谨慎，实质是规则产生了噪声。把 A 的困境描述成"证据冲突"会误导修法——修法不该是"让分类器更会权衡冲突"，而该是"别产生这条假证据"。

### 3.3 没有 `EVM_BOARD_SCHEMATIC` 时，靠 `EVM_BOARD_TITLE` + `DOCNUMBER_UG` 能否直接判 EVM？

**【事实】** 回答分两半，取决于 `EVM_BOARD_TITLE` 命中的是哪个组：

| 情形 | `board_strong` | 结果 |
| --- | --- | --- |
| 命中组是 `EVAL_MODULE` / `BOARD` / `DEV_KIT`（STRONG） | **True** | **能直接判 `EVM` / high**（走档 1），不需要 SCHEMATIC，也不需要 `DOCNUMBER_UG` |
| 仅命中组是 `USER_GUIDE`（MEDIUM） | **False** | 不能。会落到后续档，最终多半是 `UG` / medium |

**【事实】** `DOCNUMBER_UG` **不参与** `board_strong` 的构成，它在实现里只用于 `board_body` 的补充条件。所以"`EVM_BOARD_TITLE` + `DOCNUMBER_UG` 组合能否判 EVM"这个问题本身有个前提错误：`DOCNUMBER_UG` 在这条路径上不提供裁决力。

**【事实】** 回到样本 A：它命中的 `EVM_BOARD_TITLE` 是 `Evaluation Module`，属 `EVAL_MODULE` 组，**STRONG**。也就是说——

> **A 本来就已经满足 `board_strong`。只要那条虚假的 `DS_PRODUCT_MODEL_TITLE` 不存在，A 会直接落到档 1，判为 `EVM` / high，全程不需要 `EVM_BOARD_SCHEMATIC`。**

**【推论】** 这直接推翻了我上一轮报告里的建议 2（"板级覆盖条件不应只认 SCHEMATIC，应放宽"）。那个建议是**误诊**：覆盖规则从来没有"只认 SCHEMATIC"，`EVM_BOARD_TITLE` 一直在 `board_strong` 里。A 的问题不在板级证据不足，而在 DS 侧多了一条假证据。

**因此本方案的核心判断是：只需修一条规则，不需要动板级证据的强弱体系。** 这是"最小修订"的实际含义。

**【假设】** 若把 A 的假 DS 证据去掉后，A 判为 `EVM` / high——这个预测**尚未实测**（本轮冻结，未跑分类器）。验证方式见 §5 矩阵的 A 行：必须实测确认 `doc_type=EVM`、`confidence=high`、`route=QUARANTINE`。若实测落到 `UG`/medium，说明还有别的因素，本方案的因果链需要修正。

---

## 4. Q3 — `AMBIGUOUS` 与 `NON_DATASHEET` 的运维分流

### 4.1 两类的本质差异（【事实】）

| | `NON_DATASHEET` | `AMBIGUOUS` |
| --- | --- | --- |
| 触发条件 | 分类器**明确**判定为非 Datasheet 本体（如 `doc_type=EVM`） | 证据冲突，或无足够证据支持任何一侧 |
| 典型 `doc_type` | `EVM` / `UG` / `AN` | `UNKNOWN` |
| 典型 `route` | `QUARANTINE` | `REVIEW` |
| `evidence_conflict` | `false` | 可能 `true` |
| `confidence` | `medium` / `high` | `low` |
| 语义 | "我知道它是什么，它不是 Datasheet" | "我不知道它是什么" |
| 本轮样本 | **B** | **A** |

**【推论】** 二者在安全上等价（都不进 Parser），在**信息量**上不等价。把它们混在一个池子里，会让"分类器明确判否"的文档被"分类器说不清"的文档拖慢处置——B 本可自动丢弃，却要排在 A 后面等人工。

### 4.2 建议的流转规则

| 状态 | 处置 | 是否可自动 | 可否进 Parser |
| --- | --- | --- | --- |
| `DATASHEET`（`DS_STRONG` + 8 项白名单全过） | 进 Parser | 是 | **是**（唯一入口） |
| `NON_DATASHEET`（`doc_type ∈ {EVM, UG, AN, SMD}`） | 归档隔离，记录 `rejected_rules`，**不进复核队列** | 是 | 否 |
| `AMBIGUOUS`（`doc_type=UNKNOWN` 且 `conflict=true`） | 进人工复核队列，标注冲突双方 | 否 | 否 |
| `UNKNOWN`（`conflict=false`，纯证据不足） | 进人工复核队列，标注"证据不足"而非"冲突" | 否 | 否 |
| `OCR` / 读失败 | 进重跑或 OCR 队列，**不是**复核队列 | 部分 | 否 |

**【推论】** `AMBIGUOUS` 与 `UNKNOWN`（无冲突）也应分开排队：前者需要"裁决冲突"，后者需要"补充证据"，处理动作不同。

### 4.3 硬约束：人工复核**绝对不能**自动放行 Parser

**【事实】** 系统内已有一道全局不变量：

> `route == IC_PARSE` **当且仅当** `doc_type == DS_STRONG`

任何违反都会直接抛异常，不是返回错误码。这意味着：**只要人工复核的结果不是"重新分类为 `DS_STRONG`"，就不可能进入 Parser。**

**【推论】** 基于此，人工复核的流转必须遵守四条：

1. **人工复核不直接改 `doc_type`。** 复核结论只能是"维持隔离"或"触发重新分类"，不得由复核界面直接把标签改成 `DS_STRONG` 并放行——否则等于绕过分类器，把不变量架空。
2. **人工复核不得跳过 8 项白名单。** 即使人工认定"这是 Datasheet"，也必须重新走一遍 `route` / `doc_type` / `classification_status` / `read_status` / `source_hash_status` / `ic_datasheet_extraction` / `evidence_conflict` / `source_sha256` 的校验，全部通过才允许进 Parser。
3. **人工复核的结论必须留痕。** 谁、何时、基于什么证据、把哪份文档从哪个状态改到哪个状态，必须可审计。当前 `review_status=pending` 字段已存在，但没有记录复核人与依据。
4. **复核不改变"已发生的事实"。** 原始响应、`rejected_rules`、`evidence_pages` 不得被复核动作覆写——复核只能追加记录。

**【推论】** 一句话：**人工复核只能把文档"退回"或"重跑"，不能把文档"放行"。** 放行的唯一路径是重新经过分类器并满足全部白名单条件。

---

## 5. Q4 — 验证矩阵

修复后必须全表通过才可合入。每行注明"验证什么缺陷/风险"。

### 5.1 必测样本

| # | 角色 | 样本 | 期望结果 | 验证什么 |
| --- | --- | --- | --- | --- |
| V1 | **缺陷复现** | `ADC08060EVM__slau715a.pdf`（A） | `doc_type=EVM`、`route=QUARANTINE`、`confidence=high`、`evidence_conflict=false` | `DEFECT-001` 已修复；文档号不再被当作型号 |
| V2 | **对照（不得回退）** | `BQ25570EVM-206__sluuaa7a.pdf`（B） | 维持 `doc_type=EVM`、`route=QUARANTINE`、`confidence=high`；5 条 `DS_ELECTRICAL_SECTIONS` 仍被 `overridden_by_board_evidence` 否决 | 修复未破坏原有的板级覆盖逻辑 |
| V3 | **防误伤：真 Datasheet，型号在 metadata** | `ADS1299` 类：metadata Title 含型号 + `Datasheet` | `doc_type=DS_STRONG`、`route=IC_PARSE` | metadata 未被一刀切禁用；真 Datasheet 不被推向 `UNKNOWN` |
| V4 | **防误伤：真 Datasheet，EVM 式文件名** | `CC2500EMK__cc2500.pdf`（V022，99 页） | `doc_type=DS_STRONG`、`route=IC_PARSE` | 文件名噪声不得压过正文证据 |
| V5 | **防误伤：真 Datasheet，EVM 式文件名** | `DRV8262VEVM__drv8262.pdf`（V164，65 页） | `doc_type=DS_STRONG` | 同上，覆盖 `VEVM` 后缀变体 |
| V6 | **防误伤：真 Datasheet，EMU 式文件名** | `CC31XXEMUBOOST__cc3100.pdf`（V255，45 页） | `doc_type=DS_STRONG` | 同上，覆盖 `EMUBOOST` 变体 |
| V7 | **防误伤：已实测解析通过的 Datasheet** | `CD4098BE-NG__cd4098b.pdf`（V002，17 页/7 表） | `doc_type=DS_STRONG` | 回归基线；此样本曾在真实探针中成功解析 |

### 5.2 假 UG / 边界场景

| # | 场景 | 构造 / 选取方式 | 期望结果 | 验证什么 |
| --- | --- | --- | --- | --- |
| E1 | **假 UG（真 DS）**：标题含 `User's Guide` 但正文是 Datasheet | 从数据集中选 metadata Subject=`User's Guide` 且正文含 `Absolute Maximum Ratings` + `Pin Configuration` 的样本（**待选取，见 §6 假设 H3**） | `doc_type=DS_STRONG` 或至少 `DS_WEAK`/`REVIEW`，**不得判 EVM** | `USER_GUIDE` 组只给 MEDIUM 的设计是否足够；UG 词不得单独判 EVM |
| E2 | **假 EVM（真 DS）**：文件名带 `EVM`，本体是 Datasheet | V4/V5/V6 已覆盖 | 判 DS | 文件名不得凌驾正文 |
| E3 | **文档号出现在首页但无器件词** | 构造：标题块含 `SLAU715A`，但无 `ADC`/`DAC`/`driver` 等 | **不触发** `DS_PRODUCT_MODEL_TITLE` | 验证条件 3 的独立性；也说明当前 B 为何不触发 |
| E4 | **文档号 + 器件词都在，但本体是 EVM** | A 的变体：换一份 UG，标题含 `SLAUxxx` 且含 `ADC` | 判 `EVM` | 修复后的主路径 |
| E5 | **真 Datasheet 但标题含 `Evaluation Module`** | 如 V022 的 p86 订购表提到 `Evaluation Module` | **不得判 EVM** | 防止修复矫枉过正；正文弱提及不能压过 DS 强证据 |
| E6 | **型号在 metadata 与正文不一致** | 构造：metadata 写 `ADC08xx0`，正文写 `ADC08060` | 应有明确归因（记哪一方），不得静默丢弃 | 交叉验证逻辑的边界行为 |
| E7 | **`title_block` 为空**（无 metadata、首页无文本） | 构造或选扫描件 | 走 `NO_TEXT_LAYER` / OCR 路径，**不得**因规则未触发而误判 | 空输入下的 fail-closed |
| E8 | **NVM 近似串**：`ADC_NVM_IMAGE` | 已有守卫用例 | `EVM_FILENAME_SUFFIX` 被 `nvm_guard` 否决并留痕 | 修复不得破坏既有守卫 |

### 5.3 通过判据

**【推论】** 修复可合入需同时满足：

1. V1 从 `AMBIGUOUS` 转为 `EVM`/high（**这是唯一的功能性目标**）；
2. V2–V8 全部维持原结论，**零回退**；
3. E1–E8 全部符合期望；
4. 全表 `assert_route_invariant` 无异常（`route == IC_PARSE ⟺ doc_type == DS_STRONG`）；
5. 修复前后 `rejected_rules` 的语义不变——被否决的证据仍要留痕，不能因为改了规则就消失。

---

## 6. 待验证假设清单（必须显式登记）

| ID | 假设 | 当前证据 | 如何验证 | 不成立会怎样 |
| --- | --- | --- | --- | --- |
| **H1** | 去掉 A 的虚假 DS 证据后，A 会判 `EVM`/high | 【推论】基于档 5→档 1 的代码路径推导，**未实测** | §5 V1 实测 | 若落到 `UG`/medium，说明另有因素，本方案因果链需重写 |
| **H2** | TI 的 EVM 用户指南普遍采用「`<板载IC型号> Evaluation Module User's Guide`」命名 | 【事实】仅 2 份样本：A 符合；B 是「`User's Guide for bq25570 … Evaluation Module`」，格式不同 | 在 350 份清单中统计 metadata Title 的命名模式分布 | 若只是 A 的特例，`DEFECT-001` 应降级为个案，不必改规则体系 |
| **H3** | 数据集中存在"标题含 User's Guide 但本体是 Datasheet"的样本 | 【事实】未确认存在 | 全量扫描 metadata Subject/Title 与正文 `Absolute Maximum Ratings` 的组合 | E1 无法执行，该项验证缺失，需以构造样本替代并标注 |
| **H4** | 文档号（`SLAU`/`SBAU`/`SBAA`/`SWRA`）出现在首页标题区是 TI 文档的普遍特征 | 【事实】A 一份；B 的 `SLUUAA7A` 也出现 | 抽样 30 份 TI 文档统计命中率 | 若命中率低，则"文档号当型号"是低频缺陷，优先级可降 |
| **H5** | `DEVICE_WORD_RE` 的子串匹配会系统性误触发 | 【事实】A 中 `ADC` 在 `ADC08xx0` 内命中 | 用型号清单跑一遍，统计有多少型号内部含器件词子串 | 若普遍，需改为词边界匹配；若罕见，可只修文档号问题 |
| **H6** | 修复 `DS_PRODUCT_MODEL_TITLE` 不会影响真 Datasheet 的召回 | 【推论】 | §5 V3–V7 实测 | 若 V3 回退，说明该规则对真 Datasheet 是必要证据，需改为"降权"而非"禁用" |

---

## 7. 风险与回滚

**【推论】** 三种可能的修法及各自风险：

| 方案 | 做法 | 风险 | 回滚难度 |
| --- | --- | --- | --- |
| **R1（推荐）** | 文档号类根直接返回空，不得作为型号根 | 低。只堵一条明确的语义错误，不动强弱体系 | 低（单点） |
| **R2** | 标题块含文档类型词时，型号命中降为 MEDIUM | 中。可能让真 Datasheet 掉出 `DS_STRONG`（见 H6） | 中 |
| **R3** | 元数据路径整体降权 | **不推荐**。打不到本次缺陷（§1），且误伤真 Datasheet（§2.4） | — |

**【推论】** 建议先落 R1，实测 V1–V8；只有 R1 不足以让 V1 通过时，才叠加 R2。**不要一次改两条**，否则无法归因。

---

## 8. 不在本方案范围内

- 不修改 `parse_pdf` 或任何 Parser 逻辑。
- 不修改 Workbench 的 `ICEX_CLASSIFY_ONLY` 哨兵（已独立验证通过）。
- 不调整 8 项白名单与 `assert_route_invariant`。
- 不重构 `title_block` 的拼接方式（虽然它是问题温床，但改动面过大，应单独立项）。
- 不处理 `DEFECT-001` 之外的分类缺陷。

---

## 9. 附录：证据索引

| 结论 | 证据位置 |
| --- | --- |
| A 的命中明细与冲突 | `evm_probe/10_A_response.json` → `classification.matched_rules` / `gate_reasons` |
| B 的覆盖裁决 | `evm_probe/20_B_response.json` → `classification.rejected_rules`（`overridden_by_board_evidence`） |
| 安全字段与哈希链 | `evm_probe/60_safety_matrix.md` |
| 最终裁定（含待更正的 `DEFECT-001`） | `evm_probe/FINAL_VERDICT.md` |
| V002/V022 文档级核验 | `doc_verify/GOLD_V022_AND_EVM_CANDIDATES.md` |
| 哨兵三层拦截 | `classify_only_guard/GUARD_REPORT.md` |

**本文所有"事实"均可通过只读方式复现**：读取归档 JSON、只读打开 PDF、阅读 `src/icpdf/classification/` 源码。**无需启动服务，无需调用 `classify_one()`，无需触碰 Parser。**
