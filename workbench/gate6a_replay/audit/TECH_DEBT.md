# Gate 6A Tech Debt 台账（Parser 已知语义缺陷）

记录时间：2026-11-12
适用版本：Gate 6A 首次受控回测所用 Parser（`src/icpdf/parser/`）
处置决策：**本轮不修复**，按 Reviewer 与项目方一致意见，留待引入 LLM / Agent 纠偏阶段处理。

这四类问题都不是「评估器口径」问题，而是 Parser 在结构重建与符号归属上的真实缺陷。
它们已被错误矩阵（`audit/error_matrix_105.csv`）逐行钉住，具备可复现样本，
后续任何修复都能用同一张矩阵做回归。

---

## TD-01 档位串行：同一列参数值错行归属

**现象**：表内某列的参数值在纵向上连续排列，但每行的符号（parameter name）只出现在首行，
Parser 把「值 → 符号」按行带一一对应后，第 2 行及以后的值被挂到了错误的符号上，
或直接判为无符号孤儿块。

**可复现样本**：
- `V256` 第 13 页 table 01：`-7.1 / 6.1 mV` 被归到 `p013-t01-r02`，
  `-7.9 / 6.9 mV` 被归到 `p013-t01-r06`，而 Gold 期望的行是中间那几行。
  值、单位、页码全部正确，**只有 symbol 错**。

**表现在指标上**：`match_status = 错误匹配`，`value_match/unit_match = True`，
`condition_match = False`，`error_category = symbol 错配`。

**受影响行数**：4 行（V003/TJ、V077/RVDD、V077/DVDD、V199/ID）。

**修复方向（未来）**：
1. 结构性做法：识别「符号列存在行跨度（row_span > 1）」时，把该符号视为覆盖整个跨度段，
   段内每行值共享该符号并按下标顺序配对。
2. Agent 做法：把该页的 block 序列 + 符号列 + 值列交给 LLM，让它输出
   `(symbol, value)` 配对表，Parser 只做校验与坐标回填。

**为何本轮不修**：修它需要动「符号 → 行」的归属模型，会影响全部 24 件的输出，
违背本次「除 V256 外输出不变」的硬边界。

---

## TD-02 合并单元格：跨行单元格未随行下传

**现象**：表头或参数名列存在合并单元格（一行文字纵向跨多行），
Parser 在按 `grid row` 拆行时，只把文字留在首行，后续行成为空单元格，
导致这些行的 symbol 缺失。

**可复现样本**：
- `V256` 第 57 页（双栏版式）右侧跨行单元格，正是导致行带 top/bottom 交错、
  `(prev_bottom + cur_top)/2` 产出倒序格线的直接原因。
  本轮已用几何夹紧手段（`_monotonic_lattice`）让 Parser 不再崩溃，
  但**合并语义本身仍未下传**，跨行单元格覆盖的行依然缺 symbol。

**表现在指标上**：`match_status = 漏提` 或 `错误匹配`，
`error_category = symbol 错配` / `漏提`。

**受影响行数**：6 行（V320/V(ESD) 1 行 + V256/V(MAIN-AUX) 5 行）。

**修复方向（未来）**：在 `structure.py` 的 `select_row_cells()` 之上加一层
「跨行符号下传」（carry-down），对 `row_span > 1` 的单元格，
把文本复制到其覆盖的每一行的同列，并打标记 `inherited=True` 以便审计区分原始/继承。

---

## TD-03 同名抢匹配：同页同名符号跨表/跨页抢匹配

**现象**：同一份 PDF 里同一符号名（如 `VDD_CORE`、`TA`）在多处出现，
且带不同条件（不同温度、不同测试条件）。评估与 Parser 的候选池按符号名索引，
先命中的块会被后一条 Gold 行重复消费，或者一条 Gold 行抢到了另一个条件下的块。

**可复现样本**：错误矩阵中 `secondary_category = 同名符号跨页` 的行。

**表现在指标上**：`match_status = 错误匹配`，`value_match = False`，
`parser_page` 与 `gold_page` 不同页。

**受影响行数**：5 行（3 行跨页 + 2 行多语境），见 `error_matrix_105.csv` 中
`secondary_category` 以「同名符号」开头的行。

**修复方向（未来）**：
1. Parser 侧：在符号之外补充「条件指纹」（同行的温度/电压/测试条件 token），
   候选键改为 `(symbol, condition_fingerprint)`。
2. Agent 侧：把同页所有同名符号块与全部 Gold 行一次性交给 LLM 做**全局最优配对**
   （匈牙利算法或直接让它输出配对矩阵），而不是逐行贪心。

**为何本轮不修**：条件指纹的抽取规则本身需要领域判断，硬编码规则会引入新的误判。

---

## TD-04 同格未拆分：一格多参数值未拆成多行

**现象**：一个单元格里塞了多个参数值（用 `/`、`,`、换行分隔），
Parser 把它当作一个整体 token，评估时 `numbers_in()` 只能取出首个或全部数值但无法一一对齐，
Gold 侧则是拆开的多行。

**可复现样本**：`V256` 的 `-7.1 / 6.1 mV` 这类写法（min/typ 或 dual-channel 值同格）。

**表现在指标上**：`match_status = 错误匹配`，`value_match = False`。

**修复方向（未来）**：在 `logical_assembly` 之后加一步「单元格值拆分」，
按 `/` 与换行切分，拆出的子值继承同坐标但加 `sub_index`，
再由上层决定是合并成一行多列还是展开成多行。

---

## 附：本轮已修复、不计入 Debt 的问题

| 问题 | 性质 | 处置 |
| --- | --- | --- |
| V256 第 57 页倒序格线导致 `DetectedTable` 校验崩溃 | 结构层真实缺陷（几何） | **已修**：`_monotonic_lattice()` 夹紧 + `lattice_adjusted` 上报，见 `audit/v256_crash_evidence.md` |
| 评估器四类硬伤（下划线符号、脚注尾标、分离负号、整格 token） | 评估口径缺陷 | **已修**：见 `audit/evaluator_flips_39.csv`，39 行翻正 |
| 单位判定用 `unit in text` 造成 `V` 命中 `VA19` | 评估口径缺陷 | **已修**：改为边界正则 |
| 块页码取首格页码导致跨页误判 | 评估口径缺陷 | **已修**：改为取单元格自身页码 |
| Gold 唯一键用 `_key` 折叠重复行（105→101） | 评估口径缺陷 | **已修**：改用 `_uid` |

---

## 回归约束（未来修 Debt 时必须满足）

1. `audit/error_matrix_105.csv` 的 105 行必须全部重算，`命中` 数不得下降。
2. `workbench/gate6a_replay/_assert_boundaries.py` 的 25 项断言必须全 PASS。
3. `tests/unit/test_structure_lattice.py` 的 5 项必须全 PASS（尤其
   `test_ascending_lattice_is_returned_verbatim`，它守的是「不破坏既有样本」）。
4. 任何改动都必须重新生成 v1↔v2 逐件 sha256 对照，证明影响面可控。
