# Gate 6A Gold Set 标注模板使用说明

本目录下的三个 CSV 是**人工标注载体**，不是评测结果。
它们把 `GATE6A_PARSER_BENCHMARK.md` §5 的嵌套 JSON Gold 结构拆成三张扁平表，
方便在 Excel / 文本编辑器里逐行填写，事后可无损折叠回原 JSON 结构。

| 文件 | 粒度 | 用途 |
| --- | --- | --- |
| `Gold_Set_Template.csv` | 一行一个样本 | 标量字段：样本身份、分层确认、状态、复核人、痛点覆盖 |
| `Gold_Set_Template.candidates.csv` | 一行一个期望候选参数 | `expected_candidates`（symbol / min / typ / max / unit / condition / package） |
| `Gold_Set_Template.column_roles.csv` | 一行一个单元格 | 逐单元格 `gold_column_role`，是 Column Alignment Accuracy 的唯一真值来源 |

三张表用 `sample_no` 关联。`candidates` 与 `column_roles` 初始只有表头，
标注人按样本追加行即可。

---

## 1. 哪些列可以改，哪些绝对不要动

`Gold_Set_Template.csv` 的列分成两段，分界线是 `painpoint_hypothesis`。

### 预填段（机器产生，只读）

| 列 | 含义 | 来源 |
| --- | --- | --- |
| `sample_no` | 样本编号 | 350 池清单 |
| `set_role` | `FORMAL` / `DIAGNOSTIC_ONLY` / `SUPPLEMENTARY` | 见 §2 |
| `diagnostic_only` | 是否不进任何指标分母 | 见 §2 |
| `pdf_sha256` | PDF 全文 SHA-256 | 池清单，已重算一致 |
| `file_path` | 绝对路径 | 池清单原文 |
| `page_count` | 页数 | 池清单 |
| `stratum_proposed` | 机器建议分层 | GATE6A_PLAN §1.3 |
| `text_layer_probe` | PyMuPDF 探针测得的 `has_text_layer` | 池清单 `has_text_layer` |
| `page1_text_chars` | 首页有效文本字符数（补充样本才有） | 本次扫描 |
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
| `text_layer_verified` | `TRUE` / `FALSE` | 是否**实际打开 PDF** 确认有无文本层。这一列是 PAIN-08 是否真被覆盖的唯一凭证 |
| `pain_coverage` | `PAIN-02;PAIN-07` 分号分隔 | 该件**实际**覆盖到的痛点，事后据此统计"哪些 PAIN 真被测了" |
| `target_table_count` | 整数 | 该件 Gold 目标表总数，须等于 `candidates` 表中该件不同 `table_id` 数 |
| `expected_candidate_count` | 整数 | 该件期望候选参数条数，须等于 `candidates` 表中该件行数 |
| `gold_json_path` | 相对路径 | 折叠后的 `gold/<sample_no>.json` 路径 |
| `notes` | 自由文本 | 存疑点、边界判定理由 |
| `exclude_from_metrics_reason` | 自由文本 | 为空表示计入分母；非空必须写清排除理由 |

---

## 2. 三类样本的角色，不要混用

### `FORMAL`（默认）

进入指标分母。准确率分母 = 该类中 `status=CONFIRMED` 的件数。

### `DIAGNOSTIC_ONLY`

**V022 已被单独标记**（`CC2500EMK__cc2500.pdf`，99 页）。

原因：池内 `v2_predicted_class = DS_STRONG`、`route = IC_PARSE`，即分类器判它是
Datasheet；但 Gate 2a 的人工怀疑是 EVM 板卡手册。这是**分类器与人工判断不一致**的样本。
它的作用只有一条：检验 Parser 在一个**可能本不该被解析**的文档上，
是否会产生"看似合理的垃圾结果"。

它**不参与任何指标的分子或分母**。填它的 Gold 时仍要填全，但 `exclude_from_metrics_reason`
必须保留原文，不得清空。

### `SUPPLEMENTARY`

来自 350 池**之外**的补充件，用于覆盖 PAIN-08（文本层缺失/乱码）。
补充件突破"从 350 池抽样"的约束，须 Reviewer 明确批准后才可计入分母；
未获批前 `status` 保持 `DRAFT`，且不进入任何指标。

---

## 3. 三个必须守住的禁区

1. **禁止用 Parser 输出反填 Gold。** 一旦反填，指标就是自我印证，全部作废。
   Gold 只能由人对照 PDF 原始页面填写。
2. **`bbox` 坐标系只有一套。** 用 `docs/DATA_CONTRACT.md` 冻结的 PDF page display
   空间（单位 pt，原点左上）。换算过或截过图的坐标一律不合规。
3. **`CONFIRMED` 即冻结。** 冻结后再改必须升 `gold_version` 并留 diff，
   不得原地静默修改。

---

## 4. 填写示例（仅示意格式，不要写进模板）

`Gold_Set_Template.csv` 一行：

```
V097,FORMAL,FALSE,3e5c...9a,52,复杂参数表,TRUE,,PAIN-07 常规文本完整性,
张三,李四,2026-11-12T09:30:00+08:00,CONFIRMED,复杂参数表,TRUE,PAIN-07;PAIN-02,4,37,gold/V097.json,合并单元格判定存疑,,
```

对应的 `Gold_Set_Template.candidates.csv` 一行：

```
V097,c0001,VCC,4.5,5.0,5.5,V,,SOT-23,CC2500,12,4.5,
```

对应的 `Gold_Set_Template.column_roles.csv` 一行：

```
V097,gold-t01,c0001,0,12,VCC,"[72.0,540.5,110.3,553.2]",symbol,
```

`Gold_Set_Template.candidates.csv` 的 `table_id` 与 `column_roles` 的 `table_id`
必须能对上，否则折叠回 JSON 时会被判为孤儿行并拒收。

---

## 5. 折叠回 JSON

标注完成后运行 `_build_gold_json.py`（同一目录，随本轮交付），它按 §5 结构折叠，
并做五项校验：`target_table_count` / `expected_candidate_count` 与明细行数一致、
`table_id` 无孤儿、`gold_column_role` 取值合法、`pdf_sha256` 与池清单一致、
`status=CONFIRMED` 的件必须有 `reviewer` 与 `reviewer_2`。

校验不过则拒绝产出，不静默降级。
