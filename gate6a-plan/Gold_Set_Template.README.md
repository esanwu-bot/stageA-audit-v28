# Gate 6A Gold Set 标注模板使用说明

本目录下的三个 CSV 是**人工标注载体**，不是评测结果。
它们把 `GATE6A_PARSER_BENCHMARK.md` §5 的嵌套 JSON Gold 结构拆成三张扁平表，
方便在 Excel / 文本编辑器里逐行填写，事后可无损折叠回原 JSON 结构。

| 文件 | 粒度 | 用途 |
| --- | --- | --- |
| `Gold_Set_Template.csv` | 一行一个样本（33 行） | 标量字段：样本身份、层名、状态、复核人、痛点覆盖、分母资格 |
| `Gold_Set_Template.candidates.csv` | 一行一个期望候选参数 | `expected_candidates`（symbol / min / typ / max / unit / condition / package） |
| `Gold_Set_Template.column_roles.csv` | 一行一个单元格 | 逐单元格 `gold_column_role`，是 Column Alignment Accuracy 的唯一真值来源 |

三张表用 `sample_no` 关联。`candidates` 与 `column_roles` 初始只有表头，
标注人按样本追加行。填写规则详见 `ANNOTATION_SOP.md`。

---

## 1. 33 行的构成

| `set_role` | 件数 | 来源 | `denominator_eligible` |
| --- | --- | --- | --- |
| `FORMAL` | 29 | 350 池内 | `TRUE` |
| `FORMAL_OUT_OF_POOL` | 3 | **池外**（S01 / S02 / S03） | `TRUE` |
| `DIAGNOSTIC_ONLY` | 1 | 池内（V022） | **`FALSE`** |
| **合计** | **33** | | 32 可计 + 1 永不进分母 |

分层共 8 层（括号内为件数）：普通文本型 Datasheet（6）、复杂参数表（6）、
多级表头 / 合并单元格（5）、多封装或多型号（4）、跨页表格（4）、
**短文档（9–10 页）（3）**、**扫描件（无文本层）（3）**、边界或异常文档（2）。

> **「短文档（9–10 页）」原名「扫描型或复杂版面」。**
> v1.1 依 Reviewer 裁定改名：该层 3 件（V130 / V290 / V347）实测
> `has_text_layer = TRUE`、9–10 页，是短文档而不是扫描件。沿用旧名会让读者
> 误以为 PAIN-08 已被覆盖。
>
> **「扫描件（无文本层）」是新增层，3 件全部来自 350 池之外。**
> 与本方案其余各层不同源，报告中必须单独列 `n=3`，不与池内层合并比较。

---

## 2. 哪些列可以改，哪些绝对不要动

`Gold_Set_Template.csv` 的列分成两段，分界线是 `painpoint_hypothesis`。

### 预填段（机器产生，只读）

| 列 | 含义 | 来源 |
| --- | --- | --- |
| `sample_no` | 样本编号 | 池内 30 件沿用 V 编号；池外 3 件为 S01–S03 |
| `set_role` | `FORMAL` / `FORMAL_OUT_OF_POOL` / `DIAGNOSTIC_ONLY` | 见 §1 |
| `diagnostic_only` | 是否只作诊断 | 仅 V022 为 `TRUE` |
| `denominator_eligible` | 是否允许进分母 | V022 `FALSE`，其余 `TRUE` |
| `pdf_sha256` | PDF 全文 SHA-256 | 池清单 / 扫描脚本实测 |
| `file_path` | 绝对路径 | 池清单 / 扫描脚本实测 |
| `page_count` | 页数 | 池清单 / PyMuPDF 实测 |
| `stratum_proposed` | 机器建议分层 | 层名修正版（含 v1.1 改名） |
| `text_layer_probe` | PyMuPDF 探针测得的 `has_text_layer` | 池清单 / 扫描实测 |
| `page1_text_chars` | 首页有效文本字符数（池外 3 件才有，均为 0） | 本次扫描 |
| `painpoint_hypothesis` | **分界线**，其上只读 | GATE6A_PLAN §1.2 |

改这些列会让样本与池清单脱钩，`SHA256SUMS.txt` 校验也会失败。

### 待填段（标注人填写）

| 列 | 取值 | 说明 |
| --- | --- | --- |
| `reviewer` | 姓名/工号 | 第一标注人 |
| `reviewer_2` | 姓名/工号 | 第二复核人。`baseline_5`（V097/V003/V011/V077/V022）**强制双人** |
| `reviewed_at` | ISO8601，如 `2026-11-12T09:30:00+08:00` | 填写时刻 |
| `status` | `DRAFT` → `CONFIRMED` | **只有 `CONFIRMED` 进入指标计算**，其余一律不计 |
| `stratum_confirmed` | 分层中文名，或 `OTHER:<说明>` | 人工裁定该件真实所属层 |
| `text_layer_verified` | `TRUE` / `FALSE` | 是否**实际打开 PDF** 确认有无文本层。**S01–S03 必须填 `FALSE`** |
| `pain_coverage` | `PAIN-02;PAIN-07` 分号分隔 | 该件**实际**覆盖到的痛点 |
| `target_table_count` | 整数 | 须等于 `candidates` 表中该件不同 `table_id` 数 |
| `expected_candidate_count` | 整数 | 须等于 `candidates` 表中该件行数 |
| `gold_json_path` | 相对路径，如 `gold/V097.json` | 必须**文件已存在**才许填，见 `ANNOTATION_SOP.md` §2 |
| `notes` | 自由文本 | 存疑点；`unresolved` 以 `UNRESOLVED:` 开头；两人分歧以 `CONFLICT:` 开头 |
| `exclude_from_metrics_reason` | 自由文本 | 为空表示计入分母；非空必须写清排除理由 |

### 一处已预填的例外

`stratum_confirmed` 对以下 6 件**已预先填写**，标注人不必再改：

- V130 / V290 / V347 → `短文档（9–10 页）`（依据：`page_count` 9–10、`has_text_layer=TRUE`）
- S01 / S02 / S03 → `扫描件（无文本层）`（依据：70 页逐页 0 字符、图像覆盖 1.00）

其余 27 件的 `stratum_confirmed` 仍为 `PENDING`，须看 PDF 后确认。

---

## 3. 三类样本的角色，不要混用

### `FORMAL`（29 件）

池内抽样，进指标分母。准确率分母 = 该类中 `status=CONFIRMED` 的条目数。

### `FORMAL_OUT_OF_POOL`（3 件，S01–S03）

来自 350 池**之外**的真实无文本层件，用于覆盖 PAIN-08。
Reviewer 2026-11-11 已批准正式列入并**准备计入分母**。

三条义务：

1. `denominator_eligible = TRUE`，但**当前全部 `DRAFT`，此刻不进任何分母**；
2. 只有 `status = CONFIRMED` 后才计入；
3. 报告里必须**单列 `n=3`**，注明「池外补充，不可与池内层直接比较」。

它们突破了"从 350 池抽样"的约束，这一点必须写进报告，不能含糊成"33 件抽样"。

### `DIAGNOSTIC_ONLY`（1 件，V022）

`CC2500EMK__cc2500.pdf`，99 页。

原因：池内 `v2_predicted_class = DS_STRONG`、`route = IC_PARSE`，分类器判它是
Datasheet；但 Gate 2a 的人工怀疑是 EVM 板卡手册。这是**分类器与人工判断不一致**的样本。
作用只有一条：检验 Parser 在**可能本不该被解析**的文档上，是否产生"看似合理的垃圾结果"。

`denominator_eligible = FALSE`，**不参与任何指标的分子或分母**。
填入 `exclude_from_metrics_reason` 的原文**不得清空**。

---

## 4. 三个必须守住的禁区

1. **禁止用 Parser 输出反填 Gold。** 一旦反填，指标就是自我印证，全部作废。
   Gold 只能由人对照 PDF 原始页面填写，且必须**先于** Parser 执行完成。
2. **`bbox` 坐标系只有一套。** 用 `docs/DATA_CONTRACT.md` 冻结的 PDF page display
   空间（单位 pt，原点左上）。换成像素或 mm 一律不合规。
3. **`CONFIRMED` 即冻结。** 冻结后再改必须升 `gold_version` 并留 diff，
   不得原地静默修改。

---

## 5. 填写示例（仅示意格式，不要写进模板）

`Gold_Set_Template.csv` 一行：

```
V097,FORMAL,FALSE,TRUE,3e5c...9a,E:\...\V097.pdf,52,复杂参数表,TRUE,,PAIN-07 常规文本完整性,
张三,李四,2026-11-12T09:30:00+08:00,CONFIRMED,复杂参数表,TRUE,PAIN-07;PAIN-02,4,37,gold/V097.json,,,
```

`Gold_Set_Template.candidates.csv` 一行：

```
V097,c0001,VCC,4.5,5.0,5.5,V,,SOT-23,CC2500,12,4.5,
```

`Gold_Set_Template.column_roles.csv` 一行：

```
V097,gold-t01,c0001,0,12,VCC,"[72.0,540.5,110.3,553.2]",symbol,
```

`candidates` 与 `column_roles` 的 `table_id` 必须能对上，否则折叠回 JSON 时
会被判为孤儿行并拒收。

---

## 6. 折叠回 JSON 前的五项校验

标注完成后折叠时，以下五项任一不过即拒绝产出，不静默降级：

1. `target_table_count` / `expected_candidate_count` 与明细行数一致；
2. `table_id` 无孤儿行；
3. `gold_column_role` 取值在 `symbol/min/typ/max/unit/condition/other` 之内；
4. `pdf_sha256` 与池清单一致；
5. `status = CONFIRMED` 的件必须有 `reviewer`；`baseline_5` 还必须有 `reviewer_2`。

`denominator_eligible = FALSE` 的件（仅 V022）折叠时必须带
`exclude_from_metrics_reason` 非空，否则拒收。
