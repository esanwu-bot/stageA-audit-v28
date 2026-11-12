# v3.2 —— 符号继承与 condition 归属下沉到物理行

**状态**：证据补交（对应 Reviewer 19:08 的两条意见）
**Parser 是否重跑**：**否**。`metrics.parser_rerun = false`，输入全部是 `runs/gate6a_replay_v2_postfix/` 的冻结产物。
**输入是否变动**：否。`v3_rows_parser.csv`（参数块组装结果）与上一版 **sha256 完全相同** —— 本轮只动判定层，没碰块组装。
**一对一消费是否变动**：否。`v3_parent_block_sharing.csv`、`v3_consumption_reassignments.csv` 与上一版**逐字节相同**，说明分配结果一行未动。

---

## 1. 指标：硬命中从 82 降到 66，这是收紧不是退步

| 指标 | v3（上一版） | v3.2（本版） | 变化 |
|---|---|---|---|
| Gold 行 | 105 | 105 | — |
| 定位行 `located_rows` | 104（99.05%） | 104（99.05%） | 不变 |
| 全字段一致 `exact_rows` | 89（84.76%） | 89（84.76%） | 不变 |
| **严格命中 `strict_hit_rows`** | **82（78.10%）** | **66（62.86%）** | **−16** |
| 软命中 `soft_hit_rows` | 7（6.67%） | 23（21.90%） | +16 |
| 其中 coarse 大块并集 | 7 | 7 | 不变 |
| 其中 符号无依据跨行继承 | 0 | **16** | +16 |
| `row_verified_hit_rows` | 82 | 66 | −16 |
| 敏感性参考：跨行借用也算通过 | — | 81（77.14%） | 仅参考 |

**82 → 66 的每一分都能对上**（`metrics.symbol_inheritance.strict_scope_breakdown`）：

```
判定作用域（全字段一致且非 coarse）  82
  ├─ 同一行直接命中                  62   ← 计入严格命中
  ├─ 无依据跨行继承（命中行非首行）    15   ← 本轮降级
  ├─ 无依据跨行继承（命中行为首行）     1   ← 本轮降级
  └─ 不适用（Gold 无符号，按值兜底）    4   ← 计入严格命中
严格命中 62 + 4 = 66
```

上一版把 82 全部算作硬命中，是因为**只校验了「符号挂上了这个块」，没校验「符号属于这一行」**。这正是 Reviewer 指出的漏洞。

> `exact_rows` 的含义本轮也澄清了：它是「值/单位/页码/符号在块级全过」，**含 coarse、含软命中**，所以等于 `严格 + 软 = 66 + 23 = 89`，不再等于硬命中。硬命中只能看 `strict_hit_rows`。断言脚本第 2 节守着这条。

---

## 2. 符号继承：只认三条证据通道

实现见 `evaluator_v3_1to1/_evaluate.py::classify_symbol_inheritance()`（L313）。判定顺序如下，任一成立才算「符号属于这一行」：

| # | 通道 | 判据 | 结果 |
|---|---|---|---|
| 1 | 文本 | 符号（归一化后）出现在 `matched_physical_row_id` 这一行的行文本里 | `同一行直接命中` |
| 2 | 几何 | 承载符号的**单元格 bbox** 纵向完整覆盖该行（`cell.y0 ≤ row.y0+0.5` 且 `cell.y1 ≥ row.y1−0.5`） | `跨行合并单元格继承` |
| 3 | 结构 | 表级 `merge_evidence` 里有一条同时提到承载行与命中行 | `跨行合并单元格继承` |
| — | 皆不成立 | 只能推断、不能证明 | `无依据跨行继承` → 降级为软命中 |

两条硬边界：

- **不把「块里有这个符号」当证据**。块是若干物理行的并集，用它判归属等于用答案挑行。
- **不把「这一列在这行没有单元格」当合并证据**。`reconstruction_status=partial` 时，缺格既可能是纵向合并、也可能是丢格，Parser 自己在 `uncertainty_reason` 里写的是后者。默认前者就是把丢格洗成合并。

### 2.1 一个必须自曝的判定缺陷（已修）

初版判定用 `symbol_regex()` 直接匹配**原始行文本**，而 `norm_symbol()` 会把符号归一成小写 —— `Tstg` 变成 `tstg`，再拿小写正则去搜 `Storage Temperature (T stg )` 必然搜不到。结果 9 行「符号明明就在这一行」被判成不在，硬命中一度掉到 57。

修法：`symbol_regex()` 加 `re.IGNORECASE`（L237），并把三处匹配统一改成在 `norm_text()` 归一化后的文本上做。修复后 57 → 66，且这 9 行全部回到 `同一行直接命中`。

这不是放宽判据，是把「大小写/全半角/破折号」这类排版差异从证据判定里剔出去 —— 与 `norm_symbol` 的口径本来就该一致。

---

## 3. 16 行降级清单

CSV：`audit/symbol_inheritance_proof.csv`（20 行 = 16 行无依据 + 4 行无符号）。

| 样本 | 行数 | 符号 | 父块 | 现象 |
|---|---|---|---|---|
| V011 | 3 | VIH ×2、VIL ×1 | `p003-t01-r04/r07` | 符号在首行，数值在后续行 |
| V077 | 1 | CVDD | `p038-t01-r03` | 符号在 456 MHz 行，命中 375 MHz 行 |
| V101 | 6 | VIH ×2、VIL ×2、VOH ×2 | `p003-t01-r04/r07/r10` | 同 V011，块跨 3~6 行 |
| V146 | 1 | VOH | `p004-t01-r03` | 符号在首行，命中第二行 |
| V199 | 1 | PD | `p001-t03-r08` | 符号在首行，命中第二行 |
| V244 | 2 | CVDD | `p044-t01-r02` | 符号在 1.2V 行，命中 1.1V / 1.0V 行 |
| V320 | 2 | IOVDD、AVDD+PLLAVDD | `p012-t01-r04` | 两行符号与数值**互相错位** |
| 合计 | **16** | | | |

### 3.1 两种成因必须分开看

- **跨行借用（15 行）**：命中行在父块首行之后，符号只在更靠前的行。
- **行指派错位（1 行，V320 `053|iovdd`）**：命中行是父块首行 `r04`，但符号 `IOVDD` 属于 `r04`、数值 `-0.5/4` 同时也在 `r05`；分配器把 `AVDD, PLLAVDD` 那条 Gold 行给了 `r04`、把 `IOVDD` 给了 `r05`，两行**互换了**。`r04` 与 `r05` 的数值完全相同（都是 `–0.5 / 4 V`），排序键分不开，是分配器的已知弱点。这条不计入「跨行借用」，`is_parent_first_row` 列可直接区分。

### 3.2 为什么交了 20 行而不是 Reviewer 说的 1 行

Reviewer 的字面筛选是「`match_mode=text` 且命中行不是父块首行」。实测**只有 1 行**（V146 `079|voh`）。

但缺陷与 `match_mode` 无关 —— 15 条 `token` 模式的行同样在跨行借符号。只交 1 行，等于用筛选条件把 15 条问题藏起来。所以本表收录**全部需要做符号归属裁定的行**，并给出两列供复核者自行复现子集：

- `is_parent_first_row`：命中行是否父块首行（`False` = 非首行）
- `in_reviewer_filter`：是否命中字面筛选（全表恰好 1 行为 `True`）

```bash
# 复核者的字面口径：1 行
awk -F, 'NR==1 || $9=="True"' symbol_inheritance_proof.csv
# 非首行的全部：15 行
awk -F, 'NR==1 || ($8=="False" && $11=="无依据跨行继承")' symbol_inheritance_proof.csv
```

---

## 4. 一个必须承认的边界：文本续行线索存在，但不算证据

V011 的块是这样的（`rows_detail` 原样）：

```
p003-t01-r04  High Level Input V IH - - 2 1.5 - - 1.5 - 1.5 - V   [首行][承载符号]
p003-t01-r05  Voltage 4.5 3.15 - - 3.15 - 3.15 - V                [命中行]
p003-t01-r06  6 4.2 - - 4.2 - 4.2 - V
```

肉眼看得出：印刷版式里 `High Level Input Voltage` 是**一个纵向合并的参数名单元格**，`2 / 4.5 / 6` 是三行测试条件，Parser 把合并单元格的文字按行拆开落在了三行上（`High Level Input` + `Voltage` + `6`）。所以「符号属于第 2 行」在**语义上大概率成立**。

但这不是证据，是推断：

- 符号单元格 `V IH` 的 bbox 只覆盖 `r04`（CSV 的 `symbol_cell_y` / `symbol_row_y` 两列给了实测值）；
- 表级 `merge_evidence` 是 **0 条**，`reconstruction_status = partial`；
- 「文字被拆到下一行」既可能是合并单元格的文字分布，也可能是行切分把一句话切断了 —— 二者在 Parser 输出里长得一样。

所以判 `无依据跨行继承`。这是 Parser 侧的可追溯性缺口（未记录纵向合并），不是评估器编出来的问题；我们把它记成待办而不是把它算成通过。

**敏感性**：若 Reviewer 认为「父块内符号在更靠前的行」可以接受，硬命中为 **81/105 = 77.14%**（`metrics.symbol_inheritance.strict_if_cross_row_accepted`）。我们不用这个数当主指标，但把它算好放在那里，避免「藏一个更宽松的口径」。

---

## 5. V077 逐条（Reviewer 点名）

| Gold 行 | 符号 | condition | 命中行 | condition 归属 | 硬命中 | 主归因 |
|---|---|---|---|---|---|---|
| `097` | CVDD | `375 MHz version` | `p038-t01-r04` | **条件在命中行** | ✗ | 完全一致（因符号降级） |
| `098` | CVDD | `456 MHz version` | `p038-t01-r03` | **条件在命中行** | ✓ | 完全一致 |
| `099` | RVDD | `375 MHz version` | `p038-t01-r06` | 条件未定位 | ✗ | 数值错 |
| `100` | RVDD | `456 MHz version` | `p038-t01-r05` | **条件在命中行** | ✓ | 完全一致 |
| `101` | DVDD | `Supply voltage, I/O, 1.8V` | `p038-t01-r07` | 条件未定位 | ✗ | 数值错 |

- `097`：命中行原文 `375 MHz version 1.14 1.2 1.32 V` —— condition **就在这一行**，不再是「父块里出现过就算过」。降级原因只有一个：符号 `CVDD` 只在 `r03`（456 MHz 行），`r04` 自己没有符号。
- `099`：`375 MHz` 的条件在指派到的 `r06` 上找不到。这不是 condition 判定失手，是**行指派本身错了** —— `r06` 的原文是 `Supply voltage, I/O, 1.8V (USB0_VDDA18, USB1_VDDA18) 1.71 1.8 1.89 V`，与 `1.14/1.2/1.32` 无关，所以主归因本来就是「数值错」。condition 未定位是**结果**，不是原因。
- `101`：同理，命中行是 `3.3V` 那行，Gold 要的是 `1.8V` 那行 → 数值错 + condition 未定位。

结论：V077 五条里，`097` 是「条件对、符号借」，`098/100` 干净通过，`099/101` 是行指派错误。**没有一条是「父块里出现过就放行」。**

---

## 6. V256 逐条（Reviewer 点名）

| Gold 行 | condition | 命中行 | condition 归属 | 证据（命中行原文，节选） |
|---|---|---|---|---|
| `087` | `2V<VCELL<4.5V; TA=25°C` | `p013-t01-r02` | **条件在命中行** | `2V<V CELL <4.5V; T A =25 o C -7.1 6.1 mV` |
| `088` | `2V<VCELL<4.5V; -20°C<TA<65°C` | `p013-t01-r03` | **条件在命中行** | `Main - AUX measurement during 2V<V CELL <4.5V; -20 o C<T A <65 o C -7.8 6.6 mV` |
| `089` | `2V<VCELL<4.5V; -40°C<TA<105°C` | `p013-t01-r04` | **条件在命中行** | `V VCELL and OVDAC Reference 2V<V CELL <4.5V; -40 o C<T A <105 o C -7.8 6.6 mV` |
| `090` | `2V<VCELL<4.5V; -40°C<TA<125°C` | `p013-t01-r05` | **条件在命中行** | `(MAIN-AUX) diagnostic. Same input voltage to both ADC under same T ; 2V<V CELL <4.5V; -40 o C<T A <125 o C -7...` |
| `091` | `1V<VCELL< 5V; -40°C<TA<125°C` | `p013-t01-r06` | **条件在命中行** | `A 1V<V CELL < 5V; -40 o C<T A <125 o C -7.9 6.9 mV` |

5/5 落在**物理行**上，逐条给出原文。这五行是「同一符号、五行、条件各不相同、其中 2/3 行 MIN/MAX 完全相同（−7.8/6.6）」的最难情形 —— 靠块级文本根本分不开，只有行级归属才能对上。

注意口径差异：这 5 行在 `error_matrix_105.csv` 里是「错误匹配（symbol_match=否）」，在 v3.2 里 `strict_hit=False` 且 `soft_hit=False`（`primary` 不是「完全一致」）。两份产物口径不同但结论一致 —— **都不算命中**。V256 修复的价值是「从整件崩溃变成可归因」，不是提分，这一点没变。

---

## 7. condition 四层拆分

实现见 `cond_attribution()`（L417）。四层互斥，优先级 `row > header > block > unresolved`：

| 层级 | 字段 | 判据 |
|---|---|---|
| 1 | `condition_row_match` | 条件文本出现在 `matched_physical_row_id` **这一行**里 |
| 2 | `condition_header_match` | 条件在表头，且能按 `column_id` 对齐到命中行有取值的列 |
| 3 | `condition_block_match` | 只在父块其他行 / 表题表头出现（`condition_evidence` 给出位置） |
| 4 | `condition_unresolved` | 三处都找不到 |

实测分布（31 条带 condition 的已定位行）：

| 归属 | 行数 | 说明 |
|---|---|---|
| 条件在命中行 | 12 | 行级可证 |
| 条件在表头且按列对齐 | 0 | 本批 Gold 的 condition 没有落在 `header_cells` 里的 |
| 条件仅在父块他行 | 2 | 都是 V320 的**整表条件** `over operating free-air temperature range (unless otherwise noted)`，出现在表题文本、无列可对齐 |
| 条件未定位 | 17 | 见下 |

`condition_match`（旧字段，87/104）保留在 `metrics.condition_attribution.reference_only` 下，明确标为参考值，**不进任何命中率**。

17 条未定位里有三类，不能混为一谈：

1. **行指派错了**（V077 `099/101`）：条件在正确的那一行，只是没被指派到 —— 根因是分配，不是 condition。
2. **列头条件没进 `header_cells`**（V101 `000/001` 的 `HC, VCC=2V`）：这类条件印在**分组子列头**上，Parser 的 `header_cells` 没覆盖到那一层。属 Parser 表头建模缺口。
3. **章节标题被当条件**（V003 `070/071` 的 `6.1 Absolute Maximum Ratings`）：Gold 的 condition 字段混进了表题，本就不是行级条件。

第 2 类是可以修的（把分组子列头也纳入 `header_cells`），但它属 Parser 改动，不在本轮授权范围内，只登记。

---

## 8. 复算方法

```bash
# 1) 重算（只读冻结产物，不跑 Parser）
py -3.13 workbench/gate6a_replay/audit/evaluator_v3_1to1/_evaluate.py
# 输出：定位 104（99.05%）  硬命中 66（62.86%）  软命中 23（21.90%）

# 2) 37 项不变量断言（含本轮新增的符号配平与 condition 四层互斥）
py -3.13 workbench/gate6a_replay/_assert_v3_1to1.py
# -> 全部 37 项断言通过

# 3) 确定性：两个不同 PYTHONHASHSEED 下 8 个产物 sha256 全同
ICPDF_REPLAY_OUT=/tmp/det_a PYTHONHASHSEED=1     py -3.13 .../_evaluate.py
ICPDF_REPLAY_OUT=/tmp/det_b PYTHONHASHSEED=98765 py -3.13 .../_evaluate.py
```

本轮新增/加强的断言（`_assert_v3_1to1.py` 第 3、10、11 节）：

- 非 coarse 的软命中**必须**是无依据符号继承（挡住「用别的理由混进软命中」）
- 严格命中里**不许**出现无依据跨行继承
- `82 = 62 + 15 + 1 + 4` 必须配平
- `strict_if_cross_row_accepted == 严格 + 跨行借用`（敏感性数字也要自洽）
- condition 四层之和 == 带 condition 的行数，且同一行只能落一层

---

## 9. 本轮没做的事（避免被读成「已解决」）

1. **没有改 Parser**，也没有重跑。`merge_evidence` 为空是 Parser 侧问题，本轮只登记不修。
2. **没有改一对一分配算法**。V320 `053/055` 的互换仍在，只在本文件与 CSV 里标成「行指派错位」。改分配会牵动全部指标，须单独授权。
3. **没有把 `header_cells` 扩到分组子列头**，所以 V101 的 `HC, VCC=2V` 仍判未定位。
4. **81/105 只是敏感性参考**，不是主指标。若 Reviewer 采纳这个口径，主指标会随之改，但那是裁定，不是我们自行选择。

---

## 10. 与上一版的关系

`eval_v3_1to1.md` 记录的是 v3（一对一消费 + 硬软分离）的首次交付，其中 82/78.10% 是**当时**的硬命中数。本文件是它的修订层：一对一消费与块组装两件事完全没动（两份 CSV 逐字节相同可证），只把「符号归属」和「condition 归属」下沉到物理行，硬命中因此从 82 修正为 66。**引用时请用 66，不要再用 82。**
