# V256 崩溃证据：traceback、夹紧公式与单元格映射不变性

- 样本：`V256`（MPN `BQ79652-Q1`）
- PDF：`BQ79652PAPRQ1.pdf`
- 崩溃页：第 57 页
- 复现：`_run_one.py --sample V256`；证据脚本 `_v256_crash_evidence.py`

## 1. 真实 traceback（修复前，取自 `runs/gate6a_replay_v1/logs/V256.log`）

```
Traceback (most recent call last):
  File "...\workbench\gate6a_replay\_run_one.py", line 42, in main
    result = parse_pdf(args.pdf, args.mpn or Path(args.pdf).stem,
  File "...\src\icpdf\parser\pipeline.py", line 120, in parse_pdf
    detected, candidate_sets, contexts = detect_tables_with_evidence(
  File "...\src\icpdf\parser\table_detector.py", line 219, in detect_tables_with_evidence
    table = DetectedTable(
  File "...\site-packages\pydantic\main.py", line 280, in __init__
    validated_self = self.__pydantic_validator__.validate_python(data, self_instance=self)
pydantic_core._pydantic_core.ValidationError: 1 validation error for DetectedTable
  Value error, grid_ys must be strictly ascending [type=value_error,
  input_value={'page_number': 57, 'bbox'...49609375), 'n_rows': 10}, input_type=dict]
```

## 2. 夹紧公式与容差

定义在 `src/icpdf/parser/structure.py`，常量 `MIN_ROW_GAP_PT = 0.2`。

```python
gap = min(MIN_ROW_GAP_PT, (hi - lo) / (n - 1))   # n = len(ys)
out = [ys[0]]
for value in ys[1:]:
    floor = out[-1] + gap
    out.append(floor if value < floor else value)   # 只上推，不下拉
```

| 项 | 取值 | 为什么这么定 |
| --- | --- | --- |
| `MIN_ROW_GAP_PT` | **0.2 pt** | PDF 坐标 3 位小数，0.2pt 远大于浮点噪声（~1e-9）、又远小于最小字高（10pt 字号行高约 12pt），不会把正常相邻行推开 |
| `gap` 上限 | `(hi - lo) / (n - 1)` | 区域总高只有这么多时按均分收窄，保证最后一条边界不越出区域底边 `hi` |
| 方向 | 只上推、不下拉 | 保证 `out` 单调不减且 `out[i] >= ys[i]`，不会把一行往上拽，也就不会改变任何行与文字的包含关系 |
| 行序 | **不排序** | 排序会把行重排，`GridCell.row` 与 `cell_words` 的索引随之失效 |

本次实测：`n = 11`，`hi - lo = 135.04`，`(hi-lo)/(n-1) = 13.504`，故 `gap = 0.2`。

## 3. 第 57 页两个 region 的诊断

| region | source | n_rows | 修复前是否严格递增 | 修复前校验 | 修复后 lattice_adjusted | 修复后校验 |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | `text_alignment` | 10 | 否 | `ValueError: grid_ys must be strictly ascending` | True | `pass` |
| 1 | `text_alignment` | 8 | 是 | `pass` | False | `pass` |

## 4. `grid_ys` 逐位坐标对比（region 0，11 条边界）

| # | 修复前 | 修复后 | Δ | 是否变动 |
| --- | --- | --- | --- | --- |
| 0 | 500.456 | 500.456 | +0.000 | 不变 |
| 1 | 508.374 | 508.374 | +0.000 | 不变 |
| 2 | 513.699 | 513.699 | +0.000 | 不变 |
| 3 | 521.126 | 521.126 | +0.000 | 不变 |
| 4 | 529.291 | 529.291 | +0.000 | 不变 |
| 5 | 543.035 | 543.035 | +0.000 | 不变 |
| 6 | 533.715 | 543.235 | +9.520 | **变动** |
| 7 | 588.750 | 588.750 | +0.000 | 不变 |
| 8 | 571.507 | 588.950 | +17.443 | **变动** |
| 9 | 555.487 | 589.150 | +33.663 | **变动** |
| 10 | 635.496 | 635.496 | +0.000 | 不变 |

修复前完整序列：

```
[500.456, 508.374, 513.699, 521.126, 529.291, 543.035, 533.715, 588.75, 571.507, 555.487, 635.496]
```

修复后完整序列：

```
[500.456, 508.374, 513.699, 521.126, 529.291, 543.035, 543.235, 588.75, 588.95, 589.15, 635.496]
```

倒序点共 **3** 处：第 6 位 543.035 → 533.715；第 8 位 588.75 → 571.507；第 9 位 571.507 → 555.487

夹紧把这三处推到 `前一位 + 0.2`，其余 8 条边界逐位不变。

## 5. 单元格映射不变性（region 0）

| 检查项 | 结果 |
| --- | --- |
| 单元格数（修复前 / 修复后） | 26 / 26 |
| `(text, row, column)` 三元组序列完全一致 | **True** |
| 每行单元格数分布完全一致 | **True** |
| 出现位移的单元格数 | 0 |
| 其中 `top` 被改动的 | 0 |
| 其中 `left` 被改动的 | 0 |
| 其中 `right` 被改动的 | 0 |

**没有出现错误切分或错误合并的直接判据**：

1. 单元格总数不变（26 = 26），排除「一格被拆成两格」或「两格并成一格」；
2. 每行单元格数分布不变，排除「某行的格被挪到相邻行」；
3. `(text, row, column)` 逐格对齐不变，排除「文字换了归属」；
4. `left` / `right` 零改动，排除「列边界被牵连」——夹紧只动 y，不动 x。

为什么连 `top` / `bottom` 都是 0 改动：单元格 bbox 由**词框并集**得出，不依赖 `ys`；行归属由「词落在哪条带」决定，而夹紧只把边界推移到空白间隔里，没有任何一个词因此跨带。所以这次修复是「格线合法了、单元格一个没动」，而不是「把单元格挪到新格线上」。

逐格位移明细（仅列出发生位移的单元格）：

| # | row | col | 文本 | 修复前 bbox | 修复后 bbox | Δ(top,bottom) |
| --- | --- | --- | --- | --- | --- | --- |
| — | — | — | 无位移 | — | — | — |

## 6. 影响面：24 件 2701 张表里只有 1 张触发夹紧

扫描 `runs/gate6a_replay_v2_postfix/per_sample/*/tables.json` 的 `uncertainty_reason` 字段（`_status()` 会把夹紧事实写进这里）：

| 项 | 值 |
| --- | --- |
| 样本数 | 24 |
| 表总数 | 2701 |
| 触发夹紧的表 | **1** |

触发明细：

- `V256` / `p057-t01`（第 57 页，10 行）

换句话说，这个修复对 **99.96%** 的表是严格恒等变换，只在唯一一张双栏版式表上生效。

确定性：同一口径连跑两遍，输出逐位一致 = **True**。

## 7. 结论

1. 倒序格线来自 `(prev_bottom + cur_top) / 2` 在**双栏版式**上的失效：
   第 57 页左右两栏被识别成一个 `text_alignment` 区域，右侧跨行单元格让行带上下交错。
   这是**结构层**的问题。
2. `DetectedTable` 的 `grid_ys must be strictly ascending` 校验是**正确的**——
   它拦住了一个真实的几何错误，不是误报。因此修复放在 `structure.py`，没有放宽校验。
3. 修复只把倒序边界上推到「前一位 + 0.2pt」，不排序、不重排行，
   单元格的 `(text, row, column)` 映射逐格不变（见 §5）。
4. 夹紧事实通过 `TableGrid.lattice_adjusted` 上报，`_status()` 据此降级为 `PARTIAL`
   并写明原因，几何修复不被静默吞掉。
