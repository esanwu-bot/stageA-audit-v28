# -*- coding: utf-8 -*-
"""忠实性校验：只用 v2 冻结产物重算，必须精确复现 v2 的 104 / 89 / 7。

这不是重跑 Parser。输入是 runs/gate6a_replay_v2_postfix/per_sample/<sno>/
下的 tables.json 与 candidates.json —— Parser 已经跑完、冻结在盘上的产物。
本脚本只重跑**评估器侧**的块组装与匹配，用来证明：

  1. 冻结产物足以重建候选择集，块数与块内容与冻结的 param_blocks 零漂移；
  2. 在旧匹配逻辑下，重算结果与 v2 的指标逐项相等。

有了这条基线，v3 新算法的任何数值变化才能被归因到「一对一消费」这一项改动，
而不是「换了一批输入」。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUN = REPO / "runs" / "gate6a_replay_v2_postfix"
# 让 _replay_common.OUT_ROOT 指向 v2 冻结目录，load_run 只读不写
os.environ["ICPDF_REPLAY_OUT"] = str(RUN)

EVAL_DIR = REPO / "workbench" / "gate6a_replay" / "audit" / "evaluator_v2_final"
sys.path.insert(0, str(EVAL_DIR))
import _evaluate as E  # noqa: E402
import _replay_common as C  # noqa: E402

# 审计包里的 _replay_common 用 parents[2] 定位仓库根，但快照被挪到
# audit/evaluator_v2_final/ 之后深度多了一层，直接跑会指向
# workbench/gate6a_replay/。这里显式校正，v3 版本已改为逐级向上探测。
C.REPO = REPO
C.PREP = REPO / "workbench" / "_gate6a_prep"
C.LEDGER = C.PREP / "Gold_Set_v1.1_WORKING.csv"
C.GOLD_SOURCES = [
    ("Batch2", C.PREP / "Batch2_GOLD_v1.csv"),
    ("B1", C.PREP / "Batch3_B1_RESIGNED.csv"),
    ("B2", C.PREP / "Batch3_B2_FINAL.csv"),
    ("B3", C.PREP / "Batch3_B3_FINAL.csv"),
    ("B4", C.PREP / "Batch3_B4_FINAL.csv"),
]
C.BASELINE_ROOT = REPO / "runs" / "gate6a_replay_v1"


def main() -> int:
    print("OUT_ROOT =", C.OUT_ROOT)
    assert C.OUT_ROOT == RUN.resolve(), "OUT_ROOT 未指向 v2 冻结目录"

    gold = C.load_gold()
    by_sample: dict[str, list[dict]] = {}
    for g in gold:
        by_sample.setdefault(g["sample_no"], []).append(g)

    print("Gold 行 %d / 样本 %d" % (len(gold), len(by_sample)))
    print()

    # ---- 1. 块组装零漂移 ----
    drift, checked = [], 0
    all_details = []
    for sno in sorted(by_sample):
        tables, cands = E.load_run(sno)
        blocks = E.build_blocks(sno, tables, cands)
        frozen = json.loads(
            (RUN / "per_sample_json" / ("%s.json" % sno)).read_text(encoding="utf-8"))
        fz = frozen["param_blocks"]
        checked += 1

        if len(blocks) != len(fz):
            drift.append("%s 块数 %d != 冻结 %d" % (sno, len(blocks), len(fz)))
            continue
        for a, b in zip(blocks, fz):
            if a["block_id"] != b["block_id"]:
                drift.append("%s block_id %s != %s" % (sno, a["block_id"], b["block_id"]))
                break
            if sorted(a["symbols"]) != sorted(b["symbols"]):
                drift.append("%s/%s symbols 不一致" % (sno, a["block_id"]))
                break
            if [round(x, 9) for x in a["numbers"]] != [round(x, 9) for x in b["numbers"]]:
                drift.append("%s/%s numbers 不一致" % (sno, a["block_id"]))
                break
            if int(a["n_rows"]) != int(b["n_rows"]):
                drift.append("%s/%s n_rows %s != %s" % (sno, a["block_id"], a["n_rows"], b["n_rows"]))
                break
            if a["text"] != b["text"]:
                drift.append("%s/%s text 不一致" % (sno, a["block_id"]))
                break
            if a["cond_source"] != b["cond_source"]:
                drift.append("%s/%s cond_source 不一致" % (sno, a["block_id"]))
                break
            if sorted(a["table_units"]) != sorted(b["table_units"]):
                drift.append("%s/%s table_units 不一致" % (sno, a["block_id"]))
                break

        all_details.extend(E.eval_gold_row(g, blocks) for g in by_sample[sno])

    print("=== 1. 块组装零漂移 ===")
    print("  比对样本数 :", checked)
    if drift:
        print("  !! 发现漂移 %d 处：" % len(drift))
        for d in drift[:10]:
            print("     -", d)
        return 1
    print("  结果       : 全部一致（block_id / symbols / numbers / n_rows / text / cond_source / table_units）")

    # ---- 2. 旧匹配逻辑数值复现 ----
    n = len(all_details)
    hit = sum(1 for d in all_details if d["hit"])
    exact = sum(1 for d in all_details if d["primary"] == "完全一致")
    coarse = sum(1 for d in all_details if d["hit"] and d["coarse"])
    coarse_exact = sum(1 for d in all_details if d["coarse"] and d["primary"] == "完全一致")

    print()
    print("=== 2. 旧匹配逻辑数值复现（对照 v2 metrics.json）===")
    v2 = json.loads((RUN / "metrics.json").read_text(encoding="utf-8"))
    checks = [
        ("Gold 行数",       n,             v2["gold_rows"]),
        ("定位(hit_rows)",  hit,           v2["hit_rows"]),
        ("exact_rows",      exact,         v2["exact_rows"]),
        ("coarse_hits",     coarse,        v2["coarse_hits"]),
    ]
    ok = True
    for name, got, want in checks:
        flag = "OK " if got == want else "!! "
        ok &= (got == want)
        print("  %s%-18s 重算 %-5s v2 冻结 %-5s" % (flag, name, got, want))
    print("  %s%-18s %-6s（v2 未单列，本次新算）" % ("— ", "coarse 且完全一致", coarse_exact))

    if ok:
        print()
        print("基线确立：冻结产物足够重建 v2 的全部指标，重算无漂移。")
        print("v3 的任何数值变化都可归因于「一对一消费」这一项改动。")
        return 0
    print()
    print("!! 复现失败，不能继续。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
