# -*- coding: utf-8 -*-
"""Gate 6A 标注前的四项机器自检，结果写入 selfcheck.json。

1. 30 件正式样本与 D' 193 条变化集是否无交集（GATE6A_PLAN §1.4 缺口 3 复核）
2. 30 件正式样本是否全部 has_text_layer = TRUE（缺口 1 的前提事实）
3. 3 件补充样本是否确认不在 350 池、不在 D' 变化集
4. 模板三张表的行数与 set_role 计数是否自洽

只读，不调用 Parser，不调用大模型。
"""
from __future__ import print_function

import csv
import json
import sys
from pathlib import Path

ROOT = Path(r"E:\workspace\icpdf-extractor")
PREP = Path(__file__).resolve().parent
POOL = ROOT / "runs/stage_a_350/ds_parse_candidates_350_v2.csv"
PROPOSAL = ROOT / "runs/stage_a_350/gate6_r2/GATE6A_SAMPLE_PROPOSAL.csv"
DPRIME = ROOT / "workbench/_classifier_revision/_d_prime/regression.jsonl"


def read_csv(p):
    with open(p, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def basename(p):
    return str(p).replace("/", "\\").split("\\")[-1]


def main():
    checks = {}

    pool = {r["sample_no"]: r for r in read_csv(POOL)}
    proposal = read_csv(PROPOSAL)
    dprime = [json.loads(l) for l in
              DPRIME.read_text(encoding="utf-8").splitlines() if l.strip()]
    dprime_names = {basename(r.get("filename", "")) for r in dprime}

    # 1. 正式样本 × D' 变化集
    hits = []
    for r in proposal:
        n = basename(r["file_path"])
        if n in dprime_names or r["pdf_sha256"] in {
                x.get("sha256") for x in dprime if x.get("sha256")}:
            hits.append({"sample_no": r["sample_no"], "name": n})
    checks["d_prime_intersection"] = {
        "formal_samples": len(proposal),
        "d_prime_change_records": len(dprime),
        "intersection_count": len(hits),
        "intersection": hits,
        "verdict": "PASS" if not hits else "FAIL",
        "meaning": "0 命中即 D' 不改变这 30 件的分类结论，样本集不会因 D' 上线失效",
    }

    # 2. 350 池 has_text_layer 分布 + 30 件取值
    dist = {}
    for r in pool.values():
        dist[r.get("has_text_layer", "")] = dist.get(
            r.get("has_text_layer", ""), 0) + 1
    formal_vals = {}
    for r in proposal:
        v = pool.get(r["sample_no"], {}).get("has_text_layer", "MISSING")
        formal_vals[v] = formal_vals.get(v, 0) + 1
    checks["text_layer_of_pool"] = {
        "pool_350_distribution": dist,
        "formal_30_distribution": formal_vals,
        "verdict": "PASS" if set(formal_vals) == {"TRUE"} else "FAIL",
        "meaning": "350 池内不存在真扫描件，故 PAIN-08 必须靠池外补充",
    }

    # 3. 补充样本排除性核查
    sel = json.loads((PREP / "selected_supplementary.json").read_text(encoding="utf-8"))
    pool_sha = {r["pdf_sha256"] for r in pool.values()}
    pool_name = {basename(r["file_path"]) for r in pool.values()}
    supp_rows = []
    for s in sel["selected"]:
        supp_rows.append({
            "sample_no": s["sample_no"],
            "file_name": s["file_name"],
            "in_350_pool_by_sha": s["sha256"] in pool_sha,
            "in_350_pool_by_name": s["file_name"] in pool_name,
            "in_d_prime_change_set": s["file_name"] in dprime_names,
            "page1_text_chars": s["page1_text_chars"],
            "sampled_chars": s["sampled_chars"],
        })
    ok = all(not r["in_350_pool_by_sha"] and not r["in_350_pool_by_name"]
             and not r["in_d_prime_change_set"]
             and r["page1_text_chars"] == 0 and r["sampled_chars"] == 0
             for r in supp_rows)
    checks["supplementary_exclusion"] = {
        "rows": supp_rows,
        "verdict": "PASS" if ok else "FAIL",
        "meaning": "3 件均在 350 池外、D' 变化集外，且实测抽样页文本为 0 字符",
    }

    # 4. 模板自洽（v1.1：33 行 = 29 池内 + 3 池外 + 1 诊断）
    tpl = read_csv(PREP / "Gold_Set_Template.csv")
    role = {}
    for r in tpl:
        role[r["set_role"]] = role.get(r["set_role"], 0) + 1
    diag = [r["sample_no"] for r in tpl if r["diagnostic_only"] == "TRUE"]
    elig = {}
    for r in tpl:
        elig[r["denominator_eligible"]] = elig.get(r["denominator_eligible"], 0) + 1
    expected_role = {"FORMAL": 29, "FORMAL_OUT_OF_POOL": 3, "DIAGNOSTIC_ONLY": 1}
    expected_elig = {"TRUE": 32, "FALSE": 1}
    ok4 = (role == expected_role and elig == expected_elig
           and diag == ["V022"])
    checks["template_consistency"] = {
        "rows": len(tpl),
        "set_role_counts": role,
        "denominator_eligible_counts": elig,
        "diagnostic_only_samples": diag,
        "expected_set_role": expected_role,
        "expected_denominator_eligible": expected_elig,
        "verdict": "PASS" if ok4 else "FAIL",
        "meaning": "33 = 29 池内 + 3 池外扫描件 + 1 诊断；可计 32、永不进分母 1",
    }

    overall = all(v.get("verdict") == "PASS" for v in checks.values())
    out = {
        "generated_at_note": "由 _selfcheck.py 生成",
        "overall": "PASS" if overall else "FAIL",
        "checks": checks,
        "parser_invoked": False,
        "llm_called": False,
    }
    (PREP / "selfcheck.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")

    print("overall:", out["overall"])
    for k, v in checks.items():
        print("  %-26s %s" % (k, v["verdict"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
