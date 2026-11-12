# -*- coding: utf-8 -*-
"""隔离三种效应：v2 原始选择 / v3 无消费排序 / v3 一对一消费。

目的：一对一消费到底改了几行，必须与「我实现里的排序细节」分开算。
否则会把排序差异算到「消费」头上，等于夸大或掩盖改动范围。
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
os.environ.setdefault("ICPDF_PARSER_ROOT", str(REPO / "runs" / "gate6a_replay_v2_postfix"))
os.environ.setdefault("ICPDF_REPLAY_OUT", str(REPO / "runs" / "gate6a_replay_v3_1to1"))

sys.path.insert(0, str(REPO / "workbench" / "gate6a_replay" / "audit" / "evaluator_v3_1to1"))
import _evaluate as E  # noqa: E402
import _replay_common as C  # noqa: E402


def load_csv(p):
    with open(p, encoding="utf-8-sig", newline="") as fh:
        return {r["gold_key"]: r for r in csv.DictReader(fh)}


def main() -> int:
    v2 = load_csv(REPO / "runs" / "gate6a_replay_v2_postfix" / "eval_detail.csv")
    v3 = load_csv(REPO / "runs" / "gate6a_replay_v3_1to1" / "eval_detail.csv")

    gold = C.load_gold()
    by_sample = defaultdict(list)
    for g in gold:
        by_sample[g["sample_no"]].append(g)

    # 无消费版：每行独立取最优 (块,行)，不做占用
    noconsume = {}
    for sno in sorted(by_sample):
        tables, cands = E.load_run(sno)
        blocks = E.build_blocks(sno, tables, cands)
        for g in by_sample[sno]:
            need = [C.as_number(g.get(k)) for k in ("min_value", "typ_value", "max_value")]
            need = [x for x in need if x is not None]
            cs = E.candidates_for(g, blocks)
            if not cs:
                noconsume[g["_uid"]] = ""
                continue
            best = min(c["tier"] for c in cs)
            pairs = [(c["tier"], c["block"], i, r) for c in cs if c["tier"] == best
                     for i, r in enumerate(c["block"]["rows_detail"])]
            pairs.sort(key=lambda p: (-E._row_cover(p[3], need)[0],
                                      -E._row_cover(p[3], need)[1],
                                      p[1]["n_rows"], p[1]["order"], p[2]))
            noconsume[g["_uid"]] = pairs[0][1]["block_id"] if pairs else ""

    ranking_diff, consumption_diff = [], []
    for k in v2:
        b2 = v2[k]["matched_block_id"]
        b3 = v3[k]["matched_block_id"]
        bn = noconsume.get(k, "")
        if b2 != bn:
            ranking_diff.append((k, v2[k]["sample_no"], b2, bn))
        if bn != b3:
            consumption_diff.append((k, v3[k]["sample_no"], bn, b3))

    print("=== A. v2 原始 vs v3 无消费排序（排序细节差异）===  %d 行" % len(ranking_diff))
    for k, s, a, b in ranking_diff:
        print("   %s/%s  v2=%s  noconsume=%s" % (s, k[:3], a or "—", b or "—"))
    print()
    print("=== B. 无消费 vs 一对一消费（真正的消费效应）===  %d 行" % len(consumption_diff))
    for k, s, a, b in consumption_diff:
        print("   %s/%s  noconsume=%s  consumed=%s" % (s, k[:3], a or "—", b or "—"))
    print()
    print("=== C. v2 vs v3 直接比对（A∪B 的合并效果）===")
    tot = 0
    for k in v2:
        if v2[k]["matched_block_id"] != v3[k]["matched_block_id"]:
            tot += 1
            print("   %s/%s  v2=%s  v3=%s  primary %s -> %s"
                  % (v3[k]["sample_no"], k[:3],
                     v2[k]["matched_block_id"] or "—",
                     v3[k]["matched_block_id"] or "—",
                     v2[k]["primary"], v3[k]["primary"]))
    print("   合计 %d 行" % tot)

    # 反向：v2 里有多少块被多行共用，其中单行块被重复占用的有几个
    shared = defaultdict(list)
    for r in v2.values():
        if r["matched_block_id"]:
            shared[(r["sample_no"], r["matched_block_id"])].append(r)
    multi = {k: v for k, v in shared.items() if len(v) > 1}
    single_dup = {k: v for k, v in multi.items() if len({r["block_rows"] for r in v}) == 1
                  and v[0]["block_rows"] == "1"}
    print()
    print("v2 被多行共用的块：%d 个；其中父块只有 1 行却容纳 >1 条 Gold 行的：%d 个"
          % (len(multi), len(single_dup)))
    for k, v in single_dup.items():
        print("   %s / %s  <- %d 行" % (k[0], k[1], len(v)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
