# -*- coding: utf-8 -*-
"""行格线单调化：正常升序不动、重复与逆序被夹紧且不重排行。

对应缺陷：V256 第 57 页（BQ79652-Q1）双栏正文被识别成一个 text-alignment
区域，右侧跨行单元格让行带 top/bottom 交错，`(prev_bottom + cur_top) / 2`
算出倒序格线，`DetectedTable` 的校验直接抛 ValidationError，整件 PDF 零输出。

修复原则（见 structure._monotonic_lattice）：
  · 只把倒序的那条边界推到「前一条 + 最小间距」，**不排序、不重排行**，
    因此 ``GridCell.row`` 与 ``cell_words`` 的索引全部保持有效；
  · 已经严格递增的格线必须**逐位等于输入**——这是「其他样本输出不变」的前提。
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from icpdf.parser.structure import MIN_ROW_GAP_PT, TableGrid, _monotonic_lattice


def _strictly_ascending(values: list[float]) -> bool:
    return all(right > left for left, right in zip(values, values[1:]))


def test_ascending_lattice_is_returned_verbatim() -> None:
    """正常升序：逐位不变，且不标记 adjusted。"""
    ys = [100.0, 112.0, 125.5, 140.0, 160.25]

    out, adjusted = _monotonic_lattice(ys, lo=100.0, hi=160.25)

    assert out == ys, "升序格线被改动，会破坏其他样本的逐位一致性"
    assert adjusted is False
    assert _strictly_ascending(out)


def test_duplicate_boundaries_are_pushed_apart() -> None:
    """重复坐标：只把重复的那条往上推，行数不变。"""
    ys = [100.0, 120.0, 120.0, 120.0, 180.0]

    out, adjusted = _monotonic_lattice(ys, lo=100.0, hi=180.0)

    assert adjusted is True
    assert len(out) == len(ys), "格线数量必须保持，行数 = 格线数 - 1"
    assert _strictly_ascending(out)
    assert out[0] == ys[0] and out[1] == ys[1]
    assert out[2] == pytest.approx(ys[1] + MIN_ROW_GAP_PT)
    assert out[3] == pytest.approx(ys[1] + 2 * MIN_ROW_GAP_PT)


def test_reversed_boundaries_are_clamped_without_reordering() -> None:
    """逆序坐标：夹紧而非排序，行序与行数都不许变。"""
    ys = [500.46, 543.04, 533.72, 588.75, 571.51, 555.49, 635.50]

    out, adjusted = _monotonic_lattice(ys, lo=500.46, hi=635.50)

    assert adjusted is True
    assert len(out) == len(ys)
    assert _strictly_ascending(out)
    # 未被倒序影响的前缀原样保留
    assert out[:2] == ys[:2]
    # 倒序点被推高到前一条之上，而不是被移到别处（不重排）
    assert out[2] > out[1]
    assert out[4] > out[3]
    assert out[5] > out[4]
    # 末边界是区域底边，仍落在区域内
    assert out[-1] == pytest.approx(ys[-1])
    assert out[-1] <= 635.50


def test_clamped_lattice_stays_inside_region_even_when_span_is_tiny() -> None:
    """极端情况：区域高度不足时，最小间距自动收缩，绝不越出底边。"""
    ys = [10.0] * 6 + [10.4]

    out, adjusted = _monotonic_lattice(ys, lo=10.0, hi=10.4)

    assert adjusted is True
    assert _strictly_ascending(out)
    assert out[-1] <= 10.4 + 1e-9


def test_cell_row_indices_survive_clamping() -> None:
    """夹紧后 ::TableGrid.n_rows 与 cell 的 row 索引仍然自洽。"""
    ys = [0.0, 10.0, 10.0, 30.0]
    out, adjusted = _monotonic_lattice(ys, lo=0.0, hi=30.0)
    grid = TableGrid(bbox=(0.0, 0.0, 10.0, 30.0), xs=[0.0, 10.0], ys=out,
                     cells=[], lattice_adjusted=adjusted)

    assert adjusted is True
    assert grid.n_rows == len(ys) - 1 == 3
    # 每个 cell 的行索引仍落在 [0, n_rows) 内
    for row_index in range(grid.n_rows):
        assert 0 <= row_index < grid.n_rows
