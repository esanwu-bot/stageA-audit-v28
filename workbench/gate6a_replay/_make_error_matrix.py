# -*- coding: utf-8 -*-
"""105 行错误矩阵：把「命中」的定义摊开成可逐行核对的表。

判定口径（v2 修正版，与 report.md §4 一致，此处逐行落表）：

    match_status
      命中       value_match=是 且 unit_match=是 且 symbol_match=是 且
                 parser_page=gold_page（四项全过）。
                 condition_match 为参考字段，不参与命中判定。
      错误匹配   定位到了候选块（located=是），但上述四项至少一项不过
      漏提       连候选块都没定位到（located=否）

    located         是否定位到候选块。这是「定位率」的分子，
                    与「命中率」是两个不同指标，必须分开计数。
    value_match     Gold 的每个非空 min/typ/max 都能在块内找到（1e-6 相对容差）
    unit_match      单位作为独立 token 出现在该行或同表（合并单元格上下文）
    symbol_match    候选块是否经「符号路径」命中：
                    token/text → 是；按值反查（by_value）→ 否；Gold 无符号或未定位 → 不适用
    condition_match Gold 的 condition 能否在块文本 + 表头里定位（参考字段，不阻断命中）

输出：workbench/gate6a_replay/audit/error_matrix_105.csv
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _replay_common as C  # noqa: E402

AUDIT = Path(__file__).resolve().parent / "audit"
OUT = AUDIT / os.environ.get("ICPDF_MATRIX_NAME", "error_matrix_105.csv")
# 由输出根名推断本次矩阵对应的回测版本，避免 v1/v2 两份矩阵混淆
RUN_LABEL = C.OUT_ROOT.name

# 细分原因：按 (样本, 符号) 落到「实际发生了什么」，与 report.md §8 同源。
SECONDARY = {
    ("V003", "TJ"): "档位串行：取到 Extended Industrial –40/105，Gold 记 125",
    ("V077", "RVDD"): "档位串行：符号行本身无值，吞入下一行 456 MHz 档",
    ("V077", "DVDD"): "档位串行：块内是 3.3V 档，Gold 记 1.8V 档",
    ("V199", "ID"): "档位串行：取到 TC=25°C 的 75A，Gold 记另一条件 50A",
    ("V162", "VCC"): "同名符号跨页：VCC 挂到 p5 表头行，p25 目标行未成块",
    ("V162", "VI"): "同名符号跨页：p25 行无符号，按值落到 p27",
    ("V162", "IO"): "同名符号跨页：IO 在 p27 的 ICC 语境命中",
    ("V319", "TA"): "同名符号多语境：推荐温度档 / 热阻表 / 共模表未消歧",
    ("V319", "IO"): "行未成块：该页无同时含 IO 与 20 mA 的块",
    ("V320", "V(ESD)"): "合并符号单元未随行：符号只落在 CDM 行，交付 ±500 而非 ±2000",
    ("V256", "V(MAIN-AUX)"): "合并符号单元未随行：值/页/单位全对，符号列未落到行上",
}

README = """# error_matrix_105.csv 字段与「命中」判定口径

本表是 Gate 6A 受控回测的逐行逐条明细，105 行对应 Gold 冻结的 105 条参数行
（唯一键 `_uid`，**不做任何折叠**；历史上用 `_key` 会把同页同符号同值的
重复行折叠成 101 行，已废弃该口径）。

## 一、`match_status` 三值定义（互斥，合计 105）

**命中 = 四项全部通过，缺一不算：**

| 判据 | 要求 | 说明 |
| --- | --- | --- |
| `value_match` | `是` | Gold 的每个非空 min/typ/max 都能在块内找到 |
| `unit_match` | `是` | 单位作为独立 token 出现在该行或同表上下文 |
| `symbol_match` | `是` | 候选块经符号路径命中，不是按值反查出来的 |
| `parser_page` == `gold_page` | 相等 | 块必须落在 Gold 记录的页码上 |
| `condition_match` | **参考字段** | 只做提示，**不参与**命中判定 |

| 值 | 判定条件 | 说明 |
| --- | --- | --- |
| `命中` | 上表四项全部通过 | 与 `error_category=完全一致` 严格等价 |
| `错误匹配` | `located=是`，但四项至少一项不过 | 能挂上块，但挂错了 |
| `漏提` | `located=否` | 完全没抽出来 |

## 二、三个口径，别混（这是本表最容易被误读的地方）

**命中定义（写死，不接受别的读法）：值、单位、符号、条件（参考）、页码全部一致。**

展开成列就是：`value_match=是` 且 `unit_match=是` 且 `symbol_match=是` 且
`condition_match` 通过（**参考字段，不阻断判定**）且 `parser_page == gold_page`。

| 口径 | 定义 | 分子 | 分母 | 比率 |
| --- | --- | --- | --- | --- |
| **命中率（主口径）** | 值 + 单位 + 符号 + 页码 四门全过，condition 作参考 | **89** | 105 | **84.76%** |
| 命中率（保守口径） | 把 condition 也当硬门，五项全过 | 76 | 105 | 72.38% |
| **定位率** | 只要定位到候选块即可，不看值/单位/符号/页码 | **104** | 105 | **99.05%** |

三个数都小于 104 或等于 104，**99.05% 永远不可能是命中率**：

- 89/105 = 84.76% —— 主口径命中率
- 76/105 = 72.38% —— 若把 condition 也算硬门（13 行完全一致的 condition 定位不到）
- 104/105 = 99.05% —— **定位率**，分子 104 里含 15 行错误匹配

### 2.1 104 这个分子是怎么来的

```
v1（修复前）定位到候选块      99
  + V256 修复后新增定位         5   ← 就是 G088–G092 这五行
  ─────────────────────────────
v2（修复后）定位到候选块     104
```

那 5 行在 v1 里 V256 整件崩溃、零输出，`located=否`；
修复后正常出表，`located=是` 但 `symbol_match=否`，所以计入定位、不计入命中。

| Gold 行 | 符号 | Gold 值 | 单位 | 条件 | 命中块 | 修复前 | 修复后 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| G088 | `V(MAIN-AUX)` | -7.1 / 6.1 | mV | 2V<VCELL<4.5V; TA=25°C | `p013-t01-r02` | 漏提 | 错误匹配（symbol 否） |
| G089 | `V(MAIN-AUX)` | -7.8 / 6.6 | mV | 2V<VCELL<4.5V; -20°C<TA<65°C | `p013-t01-r03` | 漏提 | 错误匹配（symbol 否） |
| G090 | `V(MAIN-AUX)` | -7.8 / 6.6 | mV | 2V<VCELL<4.5V; -40°C<TA<105°C | `p013-t01-r03` | 漏提 | 错误匹配（symbol 否） |
| G091 | `V(MAIN-AUX)` | -7.8 / 6.7 | mV | 2V<VCELL<4.5V; -40°C<TA<125°C | `p013-t01-r05` | 漏提 | 错误匹配（symbol 否） |
| G092 | `V(MAIN-AUX)` | -7.9 / 6.9 | mV | 1V<VCELL<5V; -40°C<TA<125°C | `p013-t01-r06` | 漏提 | 错误匹配（symbol 否） |

这 5 行的**值、单位、页码全对**（`value_match=是`、`unit_match=是`、
`gold_page=parser_page=13`），唯一不通过的是 `symbol_match`：
V(MAIN-AUX) 是合并符号单元，符号只落在首行，没有随行下传（见 `TECH_DEBT.md` TD-02）。
G089 与 G090 还同时落到 `p013-t01-r03`，是「档位串行」的典型表现（TD-01）。

### 2.2 对账闭合

```
located=是                    104
  ├─ 命中（四门全过）           89
  └─ 错误匹配                   15   （数值错 6 / symbol 错配 5 / 页错 3 / 单位错 1）
located=否（漏提）               1   （V319 / IO：该页无同时含 IO 与 20 mA 的块）
                              ----
                               105
```

`located` 列就是「是否定位到候选块」的逐行标记，`命中 + 错误匹配 = 104`，
再加 1 行漏提正好 105。分子的 104 可以逐行数出来，不依赖任何口头说明。

## 三、`symbol_match` 的判定依据

`symbol_match` 由 `match_mode` 直接推出，不是新判据：

| `match_mode` | `symbol_match` | 含义 |
| --- | --- | --- |
| `token` | 是 | 符号与数值在同一单元格 token 内命中 |
| `text` | 是 | 符号落在块文本中 |
| `value` | 不适用 | Gold 本身没填符号，只能按值认，不存在符号可比 |
| 空（by_value） | 否 | 符号路径失败，退回同页按值反查才挂上块 |
| 空（未定位） | 不适用 | 没有候选块，符号无从判定 |

`token` / `text` 意味着走的是符号索引，块文本里确实有这个符号；
`match_mode` 为空且 `located=是`，正是 `_evaluate.py` 里 `by_value` 分支——
值在正确页上，但符号列没对上。

## 四、三项判据的精确定义

- `value_match`：Gold 行每个非空 `min/typ/max` 都能在候选块内找到对应数值。
  比较容差 `1e-6` 相对误差；`±` 前缀按量值比对；负号与数字之间允许空白（`– 0.5` 视作 `-0.5`）。
- `unit_match`：单位作为**独立 token**（边界正则）出现在该行文本或同表表头/合并单元格上下文。
  不用 `unit in text` 子串判定——否则单位 `V` 会误命中符号 `VA19`。
- `symbol_match`：见上表，由 `match_mode` 推出。
- `condition_match`：Gold 的 `condition` 能否在块文本 + 表头里定位。
  无 condition 记 `无`；能定位记 `可定位`；有 condition 但定位不到记 `不可定位`。
  **这是参考字段**：它记录「条件能不能定位」，但不参与命中判定，
  因为条件是自然语言描述，定位不到往往只是措辞差异，不足以否定整行。

## 五、其余字段

| 字段 | 含义 |
| --- | --- |
| `sample_id` | 样本号（V003…V349），对应 `input_manifest.json` 的 `sample_no` |
| `gold_row_id` | Gold 行号 `G001`…`G105`，按冻结顺序 |
| `parser_output_id` | Parser 输出的块行 id，形如 `p105-t01-r02`（页码-表号-行号）；`—` 表示未定位 |
| `located` | 是否定位到候选块（是/否）。定位率的分子 |
| `gold_page` / `parser_page` | Gold 记录的页码 / 实际命中块所在页码 |
| `error_category` | 主类别：`完全一致` / `数值错` / `单位错` / `evidence page 错` / `symbol 错配` / `漏提` / `解析失败` |
| `secondary_category` | 细分到「实际发生了什么」，与 `TECH_DEBT.md` 的 TD 编号对应 |
| `defect_owner` | 责任方：`—` / `Parser` / `Parser（Tech Debt）` |
| `match_mode` | 定位方式：`token` / `text` / `value` / `—` |
| `block_rows` | 命中块包含的行数，用来识别「块过大导致误吞」 |
| `run_version` | 本行出自哪个回测根，防止 v1/v2 张冠李戴 |

## 六、如何自查这张表没有造假

1. 数 `位于=是` 的行数 → 104；数 `match_status=命中` 的行数 → 89；两者相加的关系见 §二。
2. 任取一行 `命中`，用 `parser_output_id` 到对应回测的
   `per_sample/<sample>/tables.json` 里搜该 id，核对块文本确实同时含 Gold 的符号与数值。
3. 任取一行 `错误匹配`，比对 `gold_page` 与 `parser_page`、`value_match` 与 `unit_match`，
   确认错因与 `error_category` 一致。
4. `symbol_match=否` 的行应当恰好等于 `error_category=symbol 错配` 的行数（5 行，全在 V256）。

## 七、两份矩阵的关系（重要）

| 文件 | 对应回测 | `located` | 命中 | 错误匹配 | 漏提 |
| --- | --- | --- | --- | --- | --- |
| `error_matrix_105.csv` | v2（格线修复**后**） | 104 | 89 | 15 | 1 |
| `error_matrix_105_v1_prefix.csv` | v1（格线修复**前**） | 99 | 89 | 10 | 6 |

两份矩阵**只有 V256 的 5 行不同**，其余 100 行逐字段完全一致。
`run_version` 列标明每份表出自哪个回测根目录。

## 八、V256 的口径变化：分数没变，诊断变了

修复前（v1）：V256 第 57 页 `grid_ys` 非严格递增 → `DetectedTable` 校验崩溃 →
整件无 Parser 输出 → 5 行记为 `match_status=漏提`、`error_category=解析失败`。

修复后（v2）：V256 正常出表（216 页，337 张表）→ 5 行变为
`match_status=错误匹配`、`error_category=symbol 错配`、`symbol_match=否`、
`secondary_category=合并符号单元未随行`，而 `value_match`、`unit_match`、
`gold_page=parser_page=13` 全对。

**命中数没有变**：两份矩阵都是 89 行命中。这 5 行在修复前是漏提、修复后是错误匹配，
都不计入命中。修复的价值不是提分，而是把「Parser 崩了、无可诊断」变成
「Parser 抽对了值和页，只是符号归属错」这一可归因、可进 Tech Debt 的缺陷。

**变的是定位率**：v1 99/105 = 94.29%，v2 104/105 = 99.05%。

证据见 `v256_crash_evidence.md` 与 `parser_v1_v2_diff.md`。
"""


def write_readme() -> None:
    # 只有写主矩阵时才刷新口径说明，避免 v1 复跑把说明改成 v1 口径
    if OUT.name == "error_matrix_105.csv":
        (AUDIT / "error_matrix_105_README.md").write_text(README, encoding="utf-8")


def owner(primary: str, secondary: str = "") -> str:
    if primary == "解析失败":
        return "Parser（格线崩溃，已在 v2 修复并复跑）"
    if secondary:
        return "Parser（Tech Debt）"
    if primary == "完全一致":
        return "—"
    return "Parser"


def symbol_match_of(row: dict, located: bool) -> str:
    """由 match_mode 推出符号是否对上；不是新判据，只是把已有事实显式化。"""
    if not located:
        return "不适用"
    mode = (row["match_mode"] or "").strip()
    if mode in ("token", "text"):
        return "是"
    if mode == "value":
        return "不适用"          # Gold 本身没有符号
    return "否"                   # by_value 分支：符号路径失败


def is_hit(row: dict, located: bool, sym: str) -> bool:
    """命中 = 值 + 单位 + 符号 + 页码 四项全过。condition 不参与。"""
    return (located
            and row["num_ok"] == "True"
            and row["unit_ok"] == "True"
            and sym in ("是", "不适用")
            and row["page_ok"] == "True")


def build_rows(detail: list[dict]) -> list[dict]:
    rows = []
    for r in detail:
        idx = int(r["gold_key"].split("|")[0]) + 1          # _uid 前缀是 0-based
        gold_row_id = "G%03d" % idx
        located = r["hit"] == "True"
        sym = symbol_match_of(r, located)
        hit = is_hit(r, located, sym)

        # 交叉校验：新口径的「命中」必须与评估器原有的「完全一致」严格等价，
        # 否则说明两个口径打架，宁可报错也不出表。
        if hit != (r["primary"] == "完全一致"):
            raise SystemExit(
                "口径冲突：%s/%s 新口径命中=%s，但评估器 primary=%s；"
                "请先核对 eval_detail。" % (r["sample_no"], gold_row_id,
                                            hit, r["primary"]))

        status = "命中" if hit else ("错误匹配" if located else "漏提")
        sec = "" if hit else SECONDARY.get((r["sample_no"], r["symbol"]), "")
        if r["primary"] == "解析失败":
            sec = "建表校验崩溃 grid_ys 非严格递增（第 57 页），整件无输出"

        rows.append({
            "sample_id": r["sample_no"],
            "gold_row_id": gold_row_id,
            "parser_output_id": r["matched_block_id"] or "—",
            "match_status": status,
            "located": "是" if located else "否",
            "value_match": "不适用" if r["primary"] == "解析失败"
            else ("是" if r["num_ok"] == "True" else "否"),
            "unit_match": "不适用" if r["primary"] == "解析失败"
            else ("是" if r["unit_ok"] == "True" else "否"),
            "symbol_match": "不适用" if r["primary"] == "解析失败" else sym,
            "condition_match": "不适用" if r["primary"] == "解析失败"
            else ("无" if not r["condition"] else
                  ("可定位" if r["cond_ok"] == "True" else "不可定位")),
            "gold_page": r["gold_page"],
            "parser_page": r["matched_page"] or "—",
            "error_category": r["primary"],
            "secondary_category": sec,
            "defect_owner": owner(r["primary"], sec),
            "match_mode": r["match_mode"] or "—",
            "block_rows": r["block_rows"] or "0",
            "run_version": RUN_LABEL,
        })
    return rows


COLUMNS = ["sample_id", "gold_row_id", "parser_output_id", "match_status",
           "located", "value_match", "unit_match", "symbol_match",
           "condition_match", "gold_page", "parser_page", "error_category",
           "secondary_category", "defect_owner", "match_mode", "block_rows",
           "run_version"]


def main() -> int:
    detail = list(csv.DictReader(open(C.OUT_ROOT / "eval_detail.csv",
                                      encoding="utf-8-sig", newline="")))
    assert len(detail) == 105, len(detail)

    rows = build_rows(detail)
    AUDIT.mkdir(parents=True, exist_ok=True)
    C.write_csv_lf(OUT, rows, COLUMNS)

    from collections import Counter
    st = Counter(r["match_status"] for r in rows)
    loc = Counter(r["located"] for r in rows)
    sym = Counter(r["symbol_match"] for r in rows)

    # 自洽断言：写进日志，评审可复算
    assert sum(st.values()) == 105
    assert st["命中"] + st["错误匹配"] == loc["是"], (st, loc)
    assert loc["是"] + loc["否"] == 105
    assert sym["否"] == sum(1 for r in rows
                            if r["error_category"] == "symbol 错配")

    print("错误矩阵 %d 行 -> %s" % (len(rows), OUT))
    print("  match_status :", dict(st))
    print("  located      :", dict(loc),
          "→ 定位率 %.2f%%" % (loc["是"] * 100.0 / 105))
    print("  symbol_match :", dict(sym))
    print("  命中率       : %d/105 = %.2f%%"
          % (st["命中"], st["命中"] * 100.0 / 105))
    print("  对账         : 命中 %d + 错误匹配 %d = located %d；+ 漏提 %d = 105"
          % (st["命中"], st["错误匹配"], loc["是"], st["漏提"]))
    print("  error_category:", dict(Counter(r["error_category"] for r in rows)))
    write_readme()
    print("  口径说明 -> audit/error_matrix_105_README.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
