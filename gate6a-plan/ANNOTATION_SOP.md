# Gate 6A Gold Set 标注 SOP

适用对象：标注员（`reviewer`）与复核人（`reviewer_2`）。
适用文件：`Gold_Set_Template.csv`、`Gold_Set_Template.candidates.csv`、
`Gold_Set_Template.column_roles.csv`。

一句话原则：**先用眼睛把 PDF 上的真值写死，再让 Parser 跑。顺序颠倒，全部作废。**

---

## 0. 开工前必须确认的三件事

1. **Parser 还没跑过**。本轮 Gate 6A 的 Gold 必须**先于** Parser 执行完成并 `CONFIRMED`。
   如果已经跑过，立刻停下并上报——这份 Gold 会被判为自我印证。
2. **模板当前全是 `DRAFT`，且没有任何预填的 Gold 内容。** 不要"参考"任何既有结果。
3. **手上要有 PDF 原件**，路径取自清单的 `file_path`，按原文寻址，
   **禁止按 SHA 全盘搜索**（Gate 1 `G1-P2-001` 硬约束）。

---

## 1. 三张表的分工

| 表 | 粒度 | 填什么 |
| --- | --- | --- |
| `Gold_Set_Template.csv` | 一行一个样本 | 身份、层名确认、状态、复核人、痛点覆盖、两个计数 |
| `Gold_Set_Template.candidates.csv` | 一行一个期望候选参数 | symbol / min / typ / max / unit / condition / package |
| `Gold_Set_Template.column_roles.csv` | 一行一个单元格 | 逐单元格列角色，Column Alignment 的唯一真值来源 |

三张表靠 `sample_no` 关联；明细表靠 `table_id` 与 `sample_no` 双重关联。

**目标表的完整几何（页码、bbox、表类型、跨页组）不写在 CSV 里**，
写进 JSON（见 §2），CSV 只保留标量与计数。

---

## 2. `gold_json_path` 怎么填

### 2.1 命名与位置

- 固定写成 `gold/<sample_no>.json`，例如 `V097` → `gold/V097.json`。
- 路径是**相对仓库根**的，不要写绝对路径，不要写反斜杠。
- 一个样本一个文件，**不允许**一个文件装多个样本，也不允许多个文件描述一个样本。

### 2.2 什么时候写这一列

按顺序：

1. 先打开 PDF，把该样本的 JSON **完整写好**并落盘；
2. 再回 `Gold_Set_Template.csv`，把 `gold_json_path` 填上；
3. 最后才把 `status` 从 `DRAFT` 改成 `CONFIRMED`。

**文件不存在就不许填这一列。** 这一列是"我去写过"的声明，
不是"我打算写"的计划。复核人会逐条校验文件存在性与 `sample_no` 一致性。

### 2.3 JSON 里必须有什么

沿用 `GATE6A_PARSER_BENCHMARK.md` §5 的结构，最小可用形态：

```
gold_version   固定填 gate6a-gold/v0.1
sample_no      与 CSV 严格一致
document_sha256  与 CSV 的 pdf_sha256 逐字符相同
file_path      照抄 CSV
page_count     与 CSV 一致
target_tables[]  每张表给 table_id / page_number / bbox / table_type /
                 header_levels / cross_page_group_id
rows[].cells[]   每个单元格给 cell_id / column_id / text / bbox /
                 page_number / gold_column_role
expected_candidates[]  symbol / min / typ / max / unit / condition /
                       package / applicable_mpn
evidence_anchors[]     page_number / bbox / raw_text
pain_tags[]      该件实际覆盖的 PAIN 编号
```

CSV 与 JSON 的对应关系：

| CSV 列 | 必须等于 JSON 里的 |
| --- | --- |
| `target_table_count` | `len(target_tables)` |
| `expected_candidate_count` | `len(expected_candidates)` 且等于 candidates 表该件行数 |
| `pain_coverage` | `pain_tags` 用分号分隔 |
| `pdf_sha256` | `document_sha256` |

**这四项对不上，该条不得 `CONFIRMED`。**

---

## 3. 页码怎么记

### 3.1 只用一种页码

- 一律用 **PDF 物理页序号，从 1 开始**（`doc.load_page(i)` 的 `i + 1`）。
- **不要**用页面上印的页码。手册常有封面、罗马数字前言，印刷页码与物理页相差好几页。
- 如果某一页同时有印刷页码，需要说明时写在 `notes` 里，**不得替换物理页号**。

### 3.2 跨页表怎么记

- 每一段（每页那部分）各自是一个 `rows[]` 段，靠同一个 `cross_page_group_id` 串起来。
- `cross_page_group_id` 无跨页时填 `null`，**不许留空**、不许填 `""`。
- 表头延续的那一页，`header_levels` 记**逻辑表头层数**，不是该页实际印了几行表头。

### 3.3 坐标系只有一套

`bbox` 一律用 `docs/DATA_CONTRACT.md` 冻结的 **PDF page display 空间（pt，左上原点）**。
`[x0, y0, x1, y1]`，必须是数字数组，不许写字符串。
截图量出来的像素坐标、换成 mm 的坐标，**一律不合规**。

---

## 4. 数值与单位怎么记

### 4.1 逐字抄，不许规范化

| 场合 | 必须写成 | 不许写成 |
| --- | --- | --- |
| 正负号 | `±0.5` | `+/-0.5`、`0.5` |
| 微 | `µA`（U+00B5） | `uA`、`μA`（U+03BC 也不行） |
| 欧姆 | `Ω` | `ohm`、`R` |
| 上划线/横线 | 保留原字形，如 `Rθ(JA)` 按原样 | `RthJA` |
| 上下标 | 抄成连续文本，不丢字符 | 省略下标 |
| 空格 | 保留 `1 000` 或 `1000` 的原始写法 | 自作主张加千分位 |

Cell Text Accuracy 直接吃这一条，抄错一个字符就是一次错。

### 4.2 值放哪一列

- `min` / `typ` / `max` **按 PDF 表头对位**，不要按"看起来像最小值"猜。
  表头只写一列数值（如 "Limits"）时，值放 `max` 还是 `min` 取决于表中语义，
  判不准就记 `unresolved`（见 §5）。
- 空单元格就留空字符串，**不要**用 `-`、`—`、`N/A` 填充。空与"没有该值"是两回事。
- 一个单元格里塞多个条件（如 `4.5 (VCC=5V)`）时：数值进 `min/typ/max`，
  条件进 `condition`，两者**都保留原文**。

### 4.3 单位单独一列

单位不写进数值列。`max = "5.5"`、`unit = "V"`。
若同一列内单位不一致（个别行是 mV），该行 `unit` 单独记 `mV`，
**不做换算**——换算会掩盖原表问题。

### 4.4 条件列

`condition` 抄原文（如 `TA = 25°C`、`VCC = 4.5V to 5.5V`）。
条件跨多行合并（单元格合并）时，把合并范围内的条件**逐行重复填入**，
不要只在首行写一次——否则候选匹配会认不出来。

---

## 5. 冲突与 `unresolved` 怎么处理

### 5.1 什么情况必须记 `unresolved`

出现下列任一情况，**不要猜**，记 `unresolved`：

1. 字形不可辨（扫描件糊、符号重叠、上下标丢失）；
2. 表头层级歧义，判不出某列是 `min` 还是 `max`；
3. 同一参数在文档不同页给出**互相矛盾**的值，且无版本/条件说明；
4. 单元格内容跨越表格边框，无法确定归属行；
5. 跨页表在续页缺少表头，无法确定列对齐；
6. 图内嵌表（表格是图片的一部分），文字只能靠肉眼读且存在多义。

### 5.2 怎么记

- 在 `Gold_Set_Template.csv` 的 `notes` **以 `UNRESOLVED:` 开头**写清原因，
  例如 `UNRESOLVED: 第 12 页 Table 3 第 4 列表头被水印遮挡，无法判定 min/max`。
- `status` **保持 `DRAFT`**，不得升 `CONFIRMED`。
- JSON 里对应条目照写，但把有争议字段留空字符串，且在 `notes` 字段同步写明。
- **不要**为了让条目"完整"而填一个自己都不信的值。填错比留空危害大得多。

### 5.3 `unresolved` 的统计地位

- `unresolved` **单列一栏，不进任何分子分母**；
- 但报告里**必须出现它的数量**，不允许隐去；
- 若 `unresolved` 占比 > 20%，视为 Gold 质量不足，触发软停止（`GATE6A_PLAN.md` §4.2）。

### 5.4 两人意见不一致怎么办

- `reviewer` 与 `reviewer_2` 结论不同的条目，**不得由任一方强行 `CONFIRMED`**；
- 按 `unresolved` 处理，并在 `notes` 写 `CONFLICT: reviewer 认为 X，reviewer_2 认为 Y`；
- 由第三人（或 Reviewer）裁定后，重开该条并升 `gold_version` 小版本号，保留 diff。

`baseline_5`（V097 / V003 / V011 / V077 / V022）**强制双人**，
其余件建议双人，单人件必须在 `notes` 注明原因。

---

## 6. 扫描件（S01 / S02 / S03）的特殊处理

这三件**没有文本层**（逐页 0 字符、图像覆盖 100%），因此：

1. **不可能用文本抽取辅助**，只能靠眼睛看渲染图。请放大到 300% 以上再抄。
2. `text_layer_verified` 填 **`FALSE`** —— 这一列问的是"有没有文本层"，
   实测没有，就必须填 FALSE。填 TRUE 会被机检直接判错。
3. `stratum_confirmed` 已是 `扫描件（无文本层）`，**不要改**。
4. 若整页图像分辨率不足以致无法辨读，**整件记 `unresolved`**，
   `notes` 写 `UNRESOLVED: 全页扫描分辨率不足，字符不可辨`，
   不得凭上下文推测填值。
5. 这类件在 Parser 侧很可能整体失败。**失败不等于 Gold 错**：
   Gold 照实写，Parser 失败记 `error_reason` 并留在分母里（`GATE6A_PLAN.md` §3.1 硬约束 3）。

---

## 7. V022 的特殊处理

V022 是 `diagnostic_only = TRUE`、`denominator_eligible = FALSE`。

- 仍要**完整填 Gold**（它要用来诊断"Parser 会不会产出看似合理的垃圾"）；
- 但 `exclude_from_metrics_reason` **必须保留原文不得清空**；
- 它的分数**不与其余样本合并统计**，报告中单列。

---

## 8. 收工前自检（逐条打勾）

1. 每个 `CONFIRMED` 的 `gold_json_path` 文件真实存在，内容能被 JSON 解析。
2. `document_sha256` 与 CSV 的 `pdf_sha256` 逐字符相同。
3. `target_table_count` = 该件 `target_tables` 条数 = `column_roles` 表里不同 `table_id` 数。
4. `expected_candidate_count` = `candidates` 表该件行数。
5. `column_roles` 里每个 `table_id` 都能在 `candidates` 或 JSON 的 `target_tables` 找到，
   **无孤儿行**。
6. `gold_column_role` 取值只在 `symbol/min/typ/max/unit/condition/other` 之内。
7. 所有 `bbox` 是 4 个数字的数组，且落在页面尺寸范围内。
8. `unresolved` 条目数已统计，并在报告里出现。
9. `reviewer` / `reviewed_at` 已填；`baseline_5` 的 `reviewer_2` 已填。
10. 没有一条 Gold 的文本与 Parser 输出逐字雷同到可疑程度（自查是否误用了 Parser 结果）。

---

## 9. 一次完整填写示例（示意，勿写入模板）

样本 `V097`，PDF 第 12 页有一张电气特性表：

1. 打开 PDF，跳第 12 页，量出表格 bbox，写 `gold/V097.json`：
   `target_tables[0].table_id = "gold-t01"`、`page_number = 12`、
   `table_type = "electrical_characteristics"`、`header_levels = 2`、
   `cross_page_group_id = null`。
2. 抄第一行：`symbol = "VCC"`、`min = "4.5"`、`typ = "5.0"`、`max = "5.5"`、`unit = "V"`。
3. `candidates` 表加一行：`V097,c0001,VCC,4.5,5.0,5.5,V,,SOT-23,CC2500,12,4.5,`
4. `column_roles` 表加两行：
   `V097,gold-t01,c0001,0,12,VCC,"[72.0,540.5,110.3,553.2]",symbol,`
   `V097,gold-t01,c0002,1,12,4.5,"[118.0,540.5,150.2,553.2]",min,`
5. 回主表填：`target_table_count = 1`、`expected_candidate_count = 1`、
   `pain_coverage = PAIN-02`、`gold_json_path = gold/V097.json`、
   `reviewer = 张三`、`reviewed_at = 2026-11-12T09:30:00+08:00`、`status = CONFIRMED`。

若第 4 行某列表头被遮挡判不出 min/max：
`notes` 写 `UNRESOLVED: 第 12 页 Table 3 第 4 列表头被水印遮挡`，`status` 保持 `DRAFT`。

---

## 10. 绝对禁止的四件事

1. **用 Parser 输出反填 Gold**（自我印证，整批作废）。
2. **为了让数字好看而改 Gold**。
3. **把 `unresolved` 悄悄删掉或改成 `CONFIRMED`**。
4. **在 `CONFIRMED` 之后原地改内容**（必须升 `gold_version` 并留 diff）。
