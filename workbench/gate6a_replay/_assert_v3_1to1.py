# -*- coding: utf-8 -*-
"""v3 一对一匹配的不变量自检。

Reviewer 抓的是「假一对一」和「软硬混算」，所以这两点不能只写在文档里，
必须由断言守住。本脚本对 runs/gate6a_replay_v3_1to1/ 的落盘产物逐条校验，
任何一条不成立就非零退出。
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "runs" / "gate6a_replay_v3_1to1"

FAIL: list[str] = []
PASS = 0


def check(cond: bool, name: str, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print("  PASS  %-52s %s" % (name, detail))
    else:
        FAIL.append(name)
        print("  FAIL  %-52s %s" % (name, detail))


def load_csv(name: str) -> list[dict]:
    with open(OUT / name, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def main() -> int:
    m = json.loads((OUT / "metrics.json").read_text(encoding="utf-8"))
    detail = load_csv("eval_detail.csv")
    soft = load_csv("soft_hits.csv")
    share = load_csv("parent_block_sharing.csv")

    print("=== 1. 基数 ===")
    check(len(detail) == 105, "eval_detail 105 行", str(len(detail)))
    check(m["gold_rows"] == 105, "metrics.gold_rows == 105")
    check(m["samples"] == 24, "metrics.samples == 24")

    print("\n=== 2. 定位 / 严格 / 软 三层对账 ===")
    located = sum(1 for r in detail if r["located"] == "True")
    strict = sum(1 for r in detail if r["strict_hit"] == "True")
    softn = sum(1 for r in detail if r["soft_hit"] == "True")
    exact_all = sum(1 for r in detail if r["primary"] == "完全一致")
    check(located == m["located_rows"], "定位数一致", "%d" % located)
    check(strict == m["strict_hit_rows"], "严格命中数一致", "%d" % strict)
    check(softn == m["soft_hit_rows"], "软命中数一致", "%d" % softn)
    check(strict + softn == exact_all,
          "严格 + 软 == 全字段一致", "%d + %d = %d" % (strict, softn, exact_all))
    check(located + sum(1 for r in detail if r["located"] != "True") == 105,
          "定位 + 未定位 == 105")
    check(m["exact_rows"] == strict,
          "exact_rows 就是严格命中（已剔除 coarse）", "%d" % m["exact_rows"])

    print("\n=== 3. 硬/软互斥：coarse 一行都不许进严格命中 ===")
    bad = [r for r in detail if r["strict_hit"] == "True" and r["coarse"] == "True"]
    check(not bad, "严格命中里没有 coarse 行", "%d 行" % len(bad))
    both = [r for r in detail if r["strict_hit"] == "True" and r["soft_hit"] == "True"]
    check(not both, "同一行不同时是严格与软命中", "%d 行" % len(both))
    all_soft_coarse = [r for r in detail if r["soft_hit"] == "True" and r["coarse"] != "True"]
    check(not all_soft_coarse, "软命中必为 coarse", "%d 行" % len(all_soft_coarse))

    print("\n=== 4. 软命中清单与明细一致 ===")
    check(len(soft) == softn, "soft_hits.csv 行数 == 软命中数", "%d" % len(soft))
    sk = {(r["sample_no"], r["gold_key"]) for r in soft}
    dk = {(r["sample_no"], r["gold_key"]) for r in detail if r["soft_hit"] == "True"}
    check(sk == dk, "soft_hits.csv 与 eval_detail 的软命中集合相同")

    print("\n=== 5. 一对一消费：同一物理行绝不能被两条 Gold 行占用 ===")
    used = Counter((r["sample_no"], r["matched_physical_row_id"])
                   for r in detail if r["matched_physical_row_id"])
    dup = {k: v for k, v in used.items() if v > 1}
    check(not dup, "物理行占用唯一", "%d 个重复" % len(dup))
    check(len(used) == located, "占用物理行数 == 定位数",
          "%d == %d" % (len(used), located))

    print("\n=== 6. 物理行必须属于其父块的覆盖范围 ===")
    outside = []
    for r in detail:
        if not r["matched_physical_row_id"]:
            continue
        covered = set(r["block_covered_rows"].split("|"))
        if r["matched_physical_row_id"] not in covered:
            outside.append((r["sample_no"], r["matched_physical_row_id"]))
    check(not outside, "matched_physical_row_id 落在父块覆盖行内", "%d 例外" % len(outside))

    print("\n=== 7. 父块共用全部落在不同子行 ===")
    badshare = [r for r in share if r["all_distinct"] != "True"]
    check(not badshare, "共用父块无重复物理行", "%d 个父块共用" % len(share))
    check(len(share) == m["matching"]["parent_blocks_shared"],
          "共用父块数与 metrics 一致", str(len(share)))

    print("\n=== 8. 行级数值归属 ===")
    rv = sum(1 for r in detail if r["strict_hit"] == "True" and r["row_value_ok"] == "True")
    check(rv == m["row_verified_hit_rows"], "row_verified 数一致", "%d" % rv)
    fake = [r for r in detail if r["strict_hit"] == "True" and r["row_value_ok"] != "True"]
    check(not fake, "严格命中的值都落在被指派的物理行上", "%d 行仅在块级成立" % len(fake))

    print("\n=== 9. 归因与字段级统计 ===")
    att = Counter(r["primary"] for r in detail)
    check(sum(att.values()) == 105, "归因之和 == 105", str(sum(att.values())))
    check(dict(att) == m["attribution"], "归因分布与 metrics 一致")
    fl = m["field_level"]
    check(fl["page_ok"] == sum(1 for r in detail
                               if r["located"] == "True" and r["page_ok"] == "True"),
          "field_level.page_ok 一致")
    check(m["reference_only"]["condition_match"]
          == sum(1 for r in detail if r["located"] == "True" and r["cond_ok"] == "True"),
          "condition_match 为参考值且与明细一致")

    print("\n=== 10. 不再重跑 Parser ===")
    check(m.get("parser_rerun") is False, "metrics.parser_rerun == False")
    check(m["parser_root"].endswith("gate6a_replay_v2_postfix"),
          "输入指向 v2 冻结产物", m["parser_root"])

    print("\n" + ("全部 %d 项断言通过" % PASS if not FAIL
                  else "失败 %d 项：%s" % (len(FAIL), FAIL)))
    return 0 if not FAIL else 1


if __name__ == "__main__":
    raise SystemExit(main())
