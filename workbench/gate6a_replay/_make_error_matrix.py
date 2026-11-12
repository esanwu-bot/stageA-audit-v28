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

本表是 Gate 6A 受控回测的逐行逐条明细，$n 行对应 Gold 冻结的 $n 条参数行
（唯一键 `_uid`，**不做任何折叠**；历史上用 `_key` 会把同页同符号同值的
重复行折叠成 101 行，已废弃该口径）。

> **本表出自 evaluator v3（一对一消费匹配）**，不是 v2 的增量补丁。
> v3 相对 v2 只改了两件事：候选块/物理行**只能用一次**；`coarse` 行**不得计入严格命中**。
> Parser 一次都没有重跑，输入是 v2 冻结在盘上的 `per_sample/` 产物。

## 一、`match_status` 四值定义（互斥，合计 $n）

**严格命中 = 四项全部通过，且命中不落在大块里：**

| 判据 | 要求 | 说明 |
| --- | --- | --- |
| `value_match` | `是` | Gold 的每个非空 min/typ/max 都能在块内找到 |
| `unit_match` | `是` | 单位作为独立 token 出现在该行或同表上下文 |
| `symbol_match` | `是` 或 `不适用` | 候选块经符号路径命中，不是按值反查出来的 |
| `parser_page` == `gold_page` | 相等 | 块必须落在 Gold 记录的页码上 |
| `coarse` | `否` | 命中块跨度 < 5 行，或走的是 token 级匹配 |
| `condition_match` | **参考字段** | 只做提示，**不参与**命中判定 |

| 值 | 判定条件 | 说明 |
| --- | --- | --- |
| `严格命中` | 上表六行全部满足 | 「值/单位/符号/页码全对」且「能落到具体物理行」 |
| `软命中` | 同上，但 `coarse=是` | 值确实在解析结果里，但命中落在一个 ≥5 行的大块内，**无法逐行确认** |
| `错误匹配` | `located=是`，但字段至少一项不过 | 能挂上块，但挂错了 |
| `漏提` | `located=否` | 完全没抽出来 |

`软命中` 单独成类是本轮针对「软硬混算」的修正：v2 把这类行直接算进「完全一致」，
等于用一个大块的数值并集冒充逐行对上的证据。

## 二、四个口径，别混（这是本表最容易被误读的地方）

| 口径 | 定义 | 分子 | 分母 | 比率 |
| --- | --- | --- | --- | --- |
| **严格命中率** | 值 + 单位 + 符号 + 页码全过，且 `coarse=否` | **$strict** | $n | **$strict_rate** |
| 全字段一致（含软） | 同上但含 `coarse=是` | $exact_all | $n | $exact_rate |
| 命中率（保守口径） | 严格命中里再把 condition 当硬门（扣掉 $cond_blocked 行不可定位） | $conserv | $n | $conserv_rate |
| **定位率** | 只要定位到候选块即可，不看字段 | **$located** | $n | **$located_rate** |

> 保守口径说明：`condition_match=无` 的行（Gold 本就没写条件，$n 行里有 63 行）
> 不参与扣减——没有字段可卡；只有 `不可定位` 的 $cond_blocked 行会被扣掉。
> 若按「含软命中」的旧基数算，同一口径是 89 − 13 = 76（即历史上那个 72.38%）。

**99.05% 永远不可能是命中率** —— 它是定位率，分子 $located 里含 $mism 行错误匹配
和 $soft 行软命中。三个数逐层收窄：

```
定位           $located  / $n     $located_rate    挂上块就算
 ├─ 全字段一致     $exact_all  / $n     $exact_rate    值/单位/符号/页码全对
 │   ├─ 严格命中     $strict  / $n     $strict_rate    ← 本轮主口径
 │   └─ 软命中        $soft  / $n      6.67%    大块内命中，需人工复核
 └─ 错误匹配       $mism  / $n    $mism_rate
漏提                 $miss  / $n
```

### 2.1 $located 这个分子是怎么来的

```
v1（修复前）定位到候选块      $located_v1
  + V256 修复后新增定位         5   ← 就是 G088–G092 这五行
  ─────────────────────────────
v2/v3（修复后）定位到候选块   $located
```

那 5 行在 v1 里 V256 整件崩溃、零输出，`located=否`；
修复后正常出表，`located=是` 但 `symbol_match=否`，所以计入定位、不计入命中。

**v3 又把它们的物理行归属修正了**（这是「一对一消费」的直接结果）：

| Gold 行 | Gold 值 | 条件 | v2 命中块 | v3 命中块 | v3 物理行 |
| --- | --- | --- | --- | --- | --- |
| G088 | -7.1 / 6.1 | 2V<VCELL<4.5V; TA=25°C | `p013-t01-r02` | `p013-t01-r02` | `r02` |
| G089 | -7.8 / 6.6 | 2V<VCELL<4.5V; -20°C<TA<65°C | `p013-t01-r03` | `p013-t01-r03` | `r03` |
| G090 | -7.8 / 6.6 | 2V<VCELL<4.5V; -40°C<TA<105°C | `p013-t01-r03` ⚠ | `p013-t01-r04` | `r04` |
| G091 | -7.8 / 6.7 | 2V<VCELL<4.5V; -40°C<TA<125°C | `p013-t01-r05` | `p013-t01-r05` | `r05` |
| G092 | -7.9 / 6.9 | 1V<VCELL<5V; -40°C<TA<125°C | `p013-t01-r06` | `p013-t01-r06` | `r06` |

⚠ 是 v2 的缺陷：G089 与 G090 值完全相同（-7.8 / 6.6），各条独立扫全池时
`max()` 取第一个最大项，两行都落在单行块 `p013-t01-r03` 上，等于**同一个物理行被消费两次**。
v3 让块/行只能用一次，G090 顺位落到 `p013-t01-r04`——而 r04 的文本正是
`-40°C<TA<105°C`，与 G090 的条件吻合。**注意：分配时完全没有使用 condition**，
condition 只是事后佐证，不是输入。

这 5 行的**值、单位、页码全对**，唯一不通过的是 `symbol_match`：
V(MAIN-AUX) 是合并符号单元，符号只落在首行，没有随行下传（见 `TECH_DEBT.md` TD-02）。

### 2.2 对账闭合

```
located=是                       $located
  ├─ 全字段一致                   $exact_all
  │    ├─ 严格命中（coarse=否）    $strict
  │    └─ 软命中  （coarse=是）      $soft
  └─ 错误匹配                      $mism   （数值错 6 / symbol 错配 5 / 页错 3 / 单位错 1）
located=否（漏提）                  $miss   （V319 / IO：该页无同时含 IO 与 20 mA 的块）
                               ----
                                 $n
```

`严格命中 + 软命中 + 错误匹配 = $located`，再加 $miss 行漏提正好 $n。
每个数都能逐行数出来，不依赖任何口头说明。

## 三、`matched_physical_row_id`：父块与子行的区分

`parser_output_id` 是**父块** id（块首行的行 id），一个块可能吞并 2~8 行。
只有 `matched_physical_row_id` 才说明这条 Gold 行**具体落在哪一行**。

- 单行块：两者相同。
- 多行父块：不同，且同一父块被多条 Gold 行引用时，子行必须**互不相同**。
  本表由 `_assert_v3_1to1.py` 断言：「同一物理行被占用两次」的行数必须为 0，
  实际 $dup_rows 行。
- `block_covered_rows` 列出父块覆盖的全部物理行，可直接核对子行确实在其中。

## 四、`symbol_match` 的判定依据

`symbol_match` 由 `match_mode` 直接推出，不是新判据：

| `match_mode` | `symbol_match` | 含义 |
| --- | --- | --- |
| `token` | 是 | 符号与数值在同一单元格 token 内命中 |
| `text` | 是 | 符号落在块文本中 |
| `value` | 不适用 | Gold 本身没填符号，只能按值认，不存在符号可比 |
| `by_value_symbol` | 否 | 符号路径失败，退回同页按值反查才挂上块 |
| （未定位） | 不适用 | 没有候选块，符号无从判定 |

v2 把 `by_value_symbol` 这一支留成空字符串，统计时混进 `none` 里分不清；
v3 显式命名，因此 v3 的 `match_mode` 里没有空值。

## 五、三项判据的精确定义

- `value_match`：Gold 行每个非空 `min/typ/max` 都能在候选块内找到对应数值。
  比较容差 `1e-6` 相对误差；`±` 前缀按量值比对；负号与数字之间允许空白（`– 0.5` 视作 `-0.5`）。
- `unit_match`：单位作为**独立 token**（边界正则）出现在该行文本或同表表头/合并单元格上下文。
  不用 `unit in text` 子串判定——否则单位 `V` 会误命中符号 `VA19`。
- `symbol_match`：见上表，由 `match_mode` 推出。
- `condition_match`：Gold 的 `condition` 能否在块文本 + 表头里定位。
  无 condition 记 `无`；能定位记 `可定位`；有 condition 但定位不到记 `不可定位`。
  **这是参考字段**：它记录「条件能不能定位」，但不参与命中判定，
  因为条件是自然语言描述，定位不到往往只是措辞差异，不足以否定整行。

## 六、其余字段

| 字段 | 含义 |
| --- | --- |
| `sample_id` | 样本号（V003…V349），对应 `input_manifest.json` 的 `sample_no` |
| `gold_row_id` | Gold 行号 `G001`…`G105`，按冻结顺序 |
| `parser_output_id` | 父块 id，形如 `p105-t01-r02`（页码-表号-行号）；`—` 表示未定位 |
| `matched_physical_row_id` | 实际占用的**物理行** id；多行父块下与上一个字段不同 |
| `located` | 是否定位到候选块（是/否）。定位率的分子 |
| `strict_hit` / `soft_hit` | 严格命中 / 软命中标记，互斥 |
| `gold_page` / `parser_page` | Gold 记录的页码 / 实际命中块所在页码 |
| `error_category` | 主类别：`完全一致` / `数值错` / `单位错` / `evidence page 错` / `symbol 错配` / `漏提` / `解析失败` |
| `secondary_category` | 细分到「实际发生了什么」，与 `TECH_DEBT.md` 的 TD 编号对应 |
| `defect_owner` | 责任方：`—` / `Parser` / `Parser（Tech Debt）` |
| `match_mode` | 定位方式：`token` / `text` / `value` / `by_value_symbol` |
| `block_rows` | 命中父块包含的行数，用来识别「块过大导致误吞」 |
| `run_version` | 本行出自哪个回测根，防止 v1/v2/v3 张冠李戴 |

## 七、如何自查这张表没有造假

1. 数 `located=是` 的行数 → $located；数 `match_status=严格命中` → $strict；
   数 `match_status=软命中` → $soft；三者与 $mism、$miss 的关系见 §2.2。
2. 数 `严格命中` 行里 `coarse=是` 的个数 → **必须是 0**。这是「软硬分离」的硬断言。
3. 任取一行 `严格命中`，用 `matched_physical_row_id` 到对应回测的
   `per_sample/<sample>/tables.json` 里定位该行，核对值确实在这一行上，
   而不只是在这个块的并集里。
4. `symbol_match=否` 的行应当恰好等于 `error_category=symbol 错配` 的行数（5 行）。
5. 有 `matched_physical_row_id` 的行，其 `(sample_id, matched_physical_row_id)` 组合必须唯一。

## 八、V256 的口径变化：分数没变，诊断和归属变了

修复前（v1）：V256 第 57 页 `grid_ys` 非严格递增 → `DetectedTable` 校验崩溃 →
整件无 Parser 输出 → 5 行记为 `match_status=漏提`、`error_category=解析失败`。

修复后：V256 正常出表（216 页，337 张表）→ 5 行变为
`match_status=错误匹配`、`error_category=symbol 错配`、`symbol_match=否`、
`secondary_category=合并符号单元未随行`，而 `value_match`、`unit_match`、
`gold_page=parser_page=13` 全对。

**命中数没有变**：v1/v2/v3 的「全字段一致」都是 $exact_all 行。
这 5 行在修复前是漏提、修复后是错误匹配，都不计入命中。
修复的价值不是提分，而是把「Parser 崩了、无可诊断」变成
「Parser 抽对了值和页，只是符号归属错」这一可归因、可进 Tech Debt 的缺陷。

**变的是定位率**：v1 $located_v1/105 = 94.29%，v2/v3 $located/105 = $located_rate。

**v3 再改的是行归属**：G089/G090 从共用 `p013-t01-r03`
变成 `r03` / `r04` 两个不同物理行，符号错配的性质没变，但「两条 Gold 行抢一个物理行」
这个假命中的形态被消除了。

证据见 `v256_crash_evidence.md` 与 `parser_v1_v2_diff.md`。

## 九、两份矩阵的关系

| 文件 | 对应回测 | `located` | 全字段一致 | 严格命中 | 软命中 | 错误匹配 | 漏提 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `error_matrix_105.csv` | v3（一对一消费） | $located | $exact_all | $strict | $soft | $mism | $miss |
| `error_matrix_105_v1_prefix.csv` | v1（格线修复**前**） | $located_v1 | 89 | — | — | 10 | 6 |

v1 那份早于「软硬分离」，没有严格/软两列（记 `—`）。
两份矩阵在 V256 的 5 行上不同，其余 100 行逐字段一致。
`run_version` 列标明每份表出自哪个回测根目录。
"""


def write_readme() -> None:
    # 只有写主矩阵时才刷新口径说明，避免 v1 复跑把说明改成 v1 口径
    if OUT.name == "error_matrix_105.csv":
        (AUDIT / "error_matrix_105_README.md").write_text(README, encoding="utf-8")


def owner(primary: str, status: str, secondary: str = "") -> str:
    if primary == "解析失败":
        return "Parser（格线崩溃，已在 v2 修复并复跑）"
    if status == "软命中":
        return "Parser（大块合并，需人工复核）"
    if secondary:
        return "Parser（Tech Debt）"
    if status == "严格命中":
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
    return "否"                   # by_value_symbol 分支：符号路径失败


def is_exact_all(row: dict, located: bool, sym: str) -> bool:
    """全字段一致（含软命中）= 值 + 单位 + 符号 + 页码 四项全过。condition 不参与。"""
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
        exact_all = is_exact_all(r, located, sym)
        # v3 的严格命中已在评估器侧剔除 coarse；这里再独立复算一次，双向对齐
        strict = exact_all and r["coarse"] != "True"
        soft = exact_all and r["coarse"] == "True"

        # 交叉校验：新口径的「全字段一致」必须与评估器 primary 严格等价，
        # 严格/软两列必须与评估器自身判定一致，否则说明两套口径打架。
        if exact_all != (r["primary"] == "完全一致"):
            raise SystemExit(
                "口径冲突：%s/%s 新口径全字段一致=%s，但评估器 primary=%s；"
                "请先核对 eval_detail。" % (r["sample_no"], gold_row_id,
                                            exact_all, r["primary"]))
        if strict != (r["strict_hit"] == "True") or soft != (r["soft_hit"] == "True"):
            raise SystemExit(
                "口径冲突：%s/%s 矩阵复算 严格=%s/软=%s，"
                "评估器记为 严格=%s/软=%s。"
                % (r["sample_no"], gold_row_id, strict, soft,
                   r["strict_hit"], r["soft_hit"]))

        if strict:
            status = "严格命中"
        elif soft:
            status = "软命中"
        elif located:
            status = "错误匹配"
        else:
            status = "漏提"

        sec = "" if exact_all else SECONDARY.get((r["sample_no"], r["symbol"]), "")
        if r["primary"] == "解析失败":
            sec = "建表校验崩溃 grid_ys 非严格递增（第 57 页），整件无输出"

        rows.append({
            "sample_id": r["sample_no"],
            "gold_row_id": gold_row_id,
            "parser_output_id": r["matched_block_id"] or "—",
            "matched_physical_row_id": r.get("matched_physical_row_id") or "—",
            "match_status": status,
            "located": "是" if located else "否",
            "strict_hit": "是" if strict else "否",
            "soft_hit": "是" if soft else "否",
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
            "defect_owner": owner(r["primary"], status, sec),
            "match_mode": r["match_mode"] or "—",
            "block_rows": r["block_rows"] or "0",
            "run_version": RUN_LABEL,
        })
    return rows


COLUMNS = ["sample_id", "gold_row_id", "parser_output_id",
           "matched_physical_row_id", "match_status", "located",
           "strict_hit", "soft_hit", "value_match", "unit_match",
           "symbol_match", "condition_match", "gold_page", "parser_page",
           "error_category", "secondary_category", "defect_owner",
           "match_mode", "block_rows", "run_version"]


def write_readme(vals: dict) -> None:
    from string import Template
    text = Template(README).substitute(**vals)
    (AUDIT / "error_matrix_105_README.md").write_text(text, encoding="utf-8")


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

    strict = st["严格命中"]
    soft = st["软命中"]
    mism = st["错误匹配"]
    miss = st["漏提"]
    exact_all = strict + soft
    loc_y = loc["是"]

    # ---- 自洽断言：任何一条不成立就拒绝出表 ----
    assert sum(st.values()) == 105, st
    assert strict + soft + mism == loc_y, (st, loc)
    assert loc_y + loc["否"] == 105
    assert strict + soft == sum(1 for r in rows if r["error_category"] == "完全一致")
    assert sym["否"] == sum(1 for r in rows
                            if r["error_category"] == "symbol 错配")
    # 软硬分离的核心断言：严格命中里不得出现 coarse 行
    assert not any(r["match_status"] == "严格命中" and r["block_rows"] != "0"
                   and int(r["block_rows"]) >= 5 and r["match_mode"] != "token"
                   for r in rows), "严格命中里混入了 coarse 行"
    # 物理行不得被两条 Gold 行同时占用
    used = Counter((r["sample_id"], r["matched_physical_row_id"])
                   for r in rows if r["matched_physical_row_id"] != "—")
    assert max(used.values(), default=0) == 1, "有物理行被多条 Gold 行占用"

    v1 = list(csv.DictReader(open(AUDIT / "error_matrix_105_v1_prefix.csv",
                                  encoding="utf-8-sig", newline="")))
    located_v1 = sum(1 for r in v1 if r["located"] == "是")

    n = 105
    vals = {
        "n": n, "strict": strict, "soft": soft, "mism": mism, "miss": miss,
        "located": loc_y, "located_v1": located_v1, "exact_all": exact_all,
        # 保守口径：严格命中里把 condition 也当硬门。
        # 「无 condition」的行不算被卡（没有可卡的字段），只有「不可定位」才扣。
        "conserv": sum(1 for r in rows
                       if r["match_status"] == "严格命中"
                       and r["condition_match"] != "不可定位"),
        "cond_blocked": sum(1 for r in rows
                            if r["match_status"] == "严格命中"
                            and r["condition_match"] == "不可定位"),
        "dup_rows": sum(1 for v in used.values() if v > 1),
        "strict_rate": "%.2f%%" % (strict * 100.0 / n),
        "soft_rate": "%.2f%%" % (soft * 100.0 / n),
        "exact_rate": "%.2f%%" % (exact_all * 100.0 / n),
        "located_rate": "%.2f%%" % (loc_y * 100.0 / n),
        "mism_rate": "%.2f%%" % (mism * 100.0 / n),
    }
    vals["conserv_rate"] = "%.2f%%" % (vals["conserv"] * 100.0 / n)
    write_readme(vals)

    print("错误矩阵 %d 行 -> %s" % (len(rows), OUT.name))
    print("  match_status :", dict(st))
    print("  located      :", dict(loc),
          "→ 定位率 %.2f%%" % (loc_y * 100.0 / n))
    print("  symbol_match :", dict(sym))
    print("  严格命中率   : %d/%d = %.2f%%" % (strict, n, strict * 100.0 / n))
    print("  软命中       : %d/%d = %.2f%%（已从严格命中剔除）"
          % (soft, n, soft * 100.0 / n))
    print("  对账         : 严格 %d + 软 %d + 错误匹配 %d = located %d；+ 漏提 %d = %d"
          % (strict, soft, mism, loc_y, miss, n))
    print("  error_category:", dict(Counter(r["error_category"] for r in rows)))
    print("  口径说明 -> audit/error_matrix_105_README.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
