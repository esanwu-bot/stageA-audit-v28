# -*- coding: utf-8 -*-
"""口径对照：把「修正前」与「修正后」的评估结果逐行对齐，分清责任。

Reviewer 要的是能分清「Parser 真错」与「评估器自己没对齐」。做法不是靠叙述，
而是**同一批落盘产物、两套口径各评一遍**，再按 Gold 稳定键逐行 diff：

    ICPDF_EVAL_LEGACY=1 python _evaluate.py     -> legacy_eval_detail.csv
    python _evaluate.py                         -> eval_detail.csv

本脚本只读这两个 CSV，产出：
    calibration_diff.csv   逐行差异（含翻正/仍错/恶化）
    calibration_diff.md    可直接粘进报告的表格
"""
from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _replay_common as C  # noqa: E402

OLD = C.OUT_ROOT / "legacy_eval_detail.csv"
NEW = C.OUT_ROOT / "eval_detail.csv"
OUT_CSV = C.OUT_ROOT / "calibration_diff.csv"
OUT_MD = C.OUT_ROOT / "calibration_diff.md"

# 每条行的处置分类
FIXED = "评估器修正后翻正"          # 旧口径判错 -> 新口径完全一致
STILL = "仍不一致（Parser 侧问题）"  # 两套口径都没到完全一致
WORSE = "口径调整后变差"            # 旧对 -> 新错（必须为 0）
UNCHANGED = "两套口径一致（已正确）"


def load(path: Path) -> dict[str, dict]:
    assert path.is_file(), "缺口径产物：%s" % path
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return {r["gold_key"]: r for r in csv.DictReader(fh)}


def main() -> int:
    old, new = load(OLD), load(NEW)
    assert set(old) == set(new), "两套口径的 Gold 行集合不一致"

    rows, kinds = [], Counter()
    for key in new:
        o, n = old[key], new[key]
        op, np_ = o["primary"], n["primary"]
        if op == np_ == "完全一致":
            kind = UNCHANGED
        elif np_ == "完全一致":
            kind = FIXED
        elif op == "完全一致":
            kind = WORSE
        else:
            kind = STILL
        kinds[kind] += 1
        rows.append({
            "sample_no": n["sample_no"], "symbol": n["symbol"],
            "gold_page": n["gold_page"], "min": n["min"], "typ": n["typ"],
            "max": n["max"], "unit": n["unit"],
            "legacy_primary": op, "final_primary": np_, "kind": kind,
            "legacy_mode": o.get("match_mode", ""), "final_mode": n.get("match_mode", ""),
            "legacy_block": o.get("matched_block_id", ""),
            "final_block": n.get("matched_block_id", ""),
            "final_block_rows": n.get("block_rows", ""),
            "final_missing": n.get("missing_values", ""),
            "gold_key": key,
        })

    rows.sort(key=lambda r: ({"评估器修正后翻正": 0, "仍不一致（Parser 侧问题）": 1,
                              "口径调整后变差": 2}.get(r["kind"], 3),
                             r["sample_no"], r["symbol"]))
    C.write_csv_lf(OUT_CSV, rows,
                   ["sample_no", "symbol", "gold_page", "min", "typ", "max", "unit",
                    "legacy_primary", "final_primary", "kind", "legacy_mode",
                    "final_mode", "legacy_block", "final_block",
                    "final_block_rows", "final_missing", "gold_key"])

    # 逐行纠正的方向统计：旧 -> 新
    moves = Counter("%s -> %s" % (r["legacy_primary"], r["final_primary"])
                    for r in rows if r["kind"] == FIXED)

    lines = ["# 评估口径对照（修正前 vs 修正后）", "",
             "同一批 Parser 落盘产物，仅评估口径不同。", "",
             "| 分类 | 行数 |", "|---|---|"]
    for k in (FIXED, STILL, WORSE, UNCHANGED):
        lines.append("| %s | %d |" % (k, kinds[k]))
    lines += ["", "## 翻正方向（旧口径 -> 新口径）", "", "| 迁移 | 行数 |", "|---|---|"]
    for k, v in moves.most_common():
        lines.append("| %s | %d |" % (k, v))
    lines += ["", "## 逐行明细（仅列有变化的行）", "",
              "| 样本 | 符号 | 页 | Gold(min/typ/max/unit) | 旧口径 | 新口径 | 分类 | 命中块 |",
              "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r["kind"] == UNCHANGED:
            continue
        g = "/".join(x for x in (r["min"], r["typ"], r["max"]) if x) + "/" + r["unit"]
        lines.append("| %s | `%s` | %s | %s | %s | %s | %s | %s |" % (
            r["sample_no"], r["symbol"], r["gold_page"], g,
            r["legacy_primary"], r["final_primary"], r["kind"],
            r["final_block"] or "—"))
    OUT_MD.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))

    print("逐行对照：%d 行" % len(rows))
    for k in (FIXED, STILL, WORSE, UNCHANGED):
        print("  %-22s %d" % (k, kinds[k]))
    print("翻正方向：" + "，".join("%s %d" % (k, v) for k, v in moves.most_common()))
    print("产物：%s / %s" % (OUT_CSV.name, OUT_MD.name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
