# -*- coding: utf-8 -*-
"""生成 Gate 6A Gold Set 人工标注模板（三个扁平 CSV）。

设计要点
--------
* `GATE6A_PARSER_BENCHMARK.md` §5 的 Gold 结构是嵌套 JSON（样本 → 表 → 行 → 单元格）。
  人工填写用嵌套 JSON 极易出错，因此这里拆成三个**扁平** CSV，一份一张表，
  一行一条记录，最后可由 `_build_gold_json.py` 无损折叠回 §5 的 JSON 结构。

      Gold_Set_Template.csv              一行一个样本（标量字段）
      Gold_Set_Template.candidates.csv   一行一个 expected_candidate
      Gold_Set_Template.column_roles.csv 一行一个单元格的 gold_column_role

* 「预填」列由机器产生，标注人**只读不改**；「待填」列一律留空。
  两者的分界写在 `Gold_Set_Template.README.md`。

* 严禁用 Parser 输出反填 Gold（自我印证）。本脚本不读任何 Parser 产物。
"""
from __future__ import print_function

import csv
import json
import sys
from pathlib import Path

ROOT = Path(r"E:\workspace\icpdf-extractor")
PROPOSAL = ROOT / "runs/stage_a_350/gate6_r2/GATE6A_SAMPLE_PROPOSAL.csv"
POOL = ROOT / "runs/stage_a_350/ds_parse_candidates_350_v2.csv"
OUT = Path(__file__).resolve().parent

# V022：Reviewer 裁定单列 diagnostic_only，不进任何指标分母（GATE6A_PLAN §1.4 缺口 2）
DIAGNOSTIC_ONLY = {
    "V022": "Gate 6A 指定检查点：疑似 EVM 板卡手册，池内 v2 判为 DS_STRONG/IC_PARSE，"
            "类别自相矛盾；仅用于诊断 Parser 是否产出「看似合理的垃圾」，"
            "不参与任何指标分子分母（GATE6A_PLAN.md §1.4 缺口 2）",
}

MAIN_COLS = [
    # —— 预填（机器产生，标注人只读）——
    "sample_no",
    "set_role",
    "diagnostic_only",
    "pdf_sha256",
    "file_path",
    "page_count",
    "stratum_proposed",
    "text_layer_probe",
    "page1_text_chars",
    "painpoint_hypothesis",
    # —— 待填（标注人填写）——
    "reviewer",
    "reviewer_2",
    "reviewed_at",
    "status",
    "stratum_confirmed",
    "text_layer_verified",
    "pain_coverage",
    "target_table_count",
    "expected_candidate_count",
    "gold_json_path",
    "notes",
    "exclude_from_metrics_reason",
]

CAND_COLS = [
    "sample_no", "candidate_id", "symbol", "min", "typ", "max", "unit",
    "condition", "package", "applicable_mpn", "page_number",
    "evidence_raw_text", "notes",
]

ROLE_COLS = [
    "sample_no", "table_id", "cell_id", "column_id", "page_number",
    "text", "bbox", "gold_column_role", "notes",
]


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def load_pool_flags():
    """从 350 池清单取 has_text_layer / page_count，作为交叉校验。"""
    out = {}
    for r in read_csv(POOL):
        out[r["sample_no"]] = {
            "has_text_layer": r.get("has_text_layer", ""),
            "page_count": r.get("page_count", ""),
            "v2_predicted_class": r.get("v2_predicted_class", ""),
            "v2_predicted_route": r.get("v2_predicted_route", ""),
        }
    return out


def load_supplementary():
    """经 _select_supplementary.py 确定性选出的 3 件补充样本（PAIN-08 覆盖）。"""
    p = OUT / "selected_supplementary.json"
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8")).get("selected", [])


def main():
    proposal = read_csv(PROPOSAL)
    pool = load_pool_flags()
    supp = load_supplementary()

    rows = []
    for r in proposal:
        sno = r["sample_no"]
        flags = pool.get(sno, {})
        is_diag = sno in DIAGNOSTIC_ONLY
        rows.append({
            "sample_no": sno,
            "set_role": "DIAGNOSTIC_ONLY" if is_diag else "FORMAL",
            "diagnostic_only": "TRUE" if is_diag else "FALSE",
            "pdf_sha256": r["pdf_sha256"],
            "file_path": r["file_path"],
            "page_count": r["page_count"],
            "stratum_proposed": r["proposed_stratum"],
            "text_layer_probe": flags.get("has_text_layer", ""),
            "page1_text_chars": "",          # 由扫描脚本按需补；350 池未逐件存
            "painpoint_hypothesis": r["painpoint_amplification"],
            "reviewer": "",
            "reviewer_2": "",
            "reviewed_at": "",
            "status": "DRAFT",
            "stratum_confirmed": "PENDING",
            "text_layer_verified": "",
            "pain_coverage": "",
            "target_table_count": "",
            "expected_candidate_count": "",
            "gold_json_path": "",
            "notes": r.get("notes", ""),
            "exclude_from_metrics_reason":
                DIAGNOSTIC_ONLY.get(sno, ""),
        })

    # 补充样本（350 池外，PAIN-08 覆盖）
    for c in supp:
        rows.append({
            "sample_no": c["sample_no"],
            "set_role": "SUPPLEMENTARY",
            "diagnostic_only": "FALSE",
            "pdf_sha256": c["sha256"],
            "file_path": c["file_path"],
            "page_count": c["page_count"],
            "stratum_proposed": "扫描型或复杂版面（实测无文本层，band=%s）" % c["band"],
            "text_layer_probe": "FALSE",
            "page1_text_chars": c["page1_text_chars"],
            "painpoint_hypothesis": "PAIN-08 文本层缺失或乱码",
            "reviewer": "", "reviewer_2": "", "reviewed_at": "",
            "status": "DRAFT",
            "stratum_confirmed": "PENDING",
            "text_layer_verified": "",
            "pain_coverage": "",
            "target_table_count": "",
            "expected_candidate_count": "",
            "gold_json_path": "",
            "notes": "350 池外补充件（同 SHA 别名 %d 个）；须 Reviewer 批准突破"
                     "抽样约束后方可计入分母（GATE6A_PLAN.md §1.4 缺口 1 选项 2）"
                     % c["alias_count"],
            "exclude_from_metrics_reason": "",
        })

    main_csv = OUT / "Gold_Set_Template.csv"
    with open(main_csv, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=MAIN_COLS)
        w.writeheader()
        w.writerows(rows)

    # 30 件候选清单（正式版）：在原提案基础上补 diagnostic_only / set_role 两列，
    # 并把 V022 的去留写死，避免下游再各自解释。
    cand_cols = [
        "sample_no", "set_role", "diagnostic_only", "pdf_sha256", "file_path",
        "page_count", "evidence_page_no", "proposed_stratum", "selection_basis",
        "painpoint_amplification", "gold_status", "baseline_5",
        "legacy_reference", "v2_predicted_class", "v2_predicted_route",
        "has_text_layer", "d_prime_change_hit", "notes",
    ]
    with open(OUT / "GATE6A_SAMPLE_CANDIDATES_30.csv", "w",
              encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cand_cols)
        w.writeheader()
        for r in proposal:
            sno = r["sample_no"]
            flags = pool.get(sno, {})
            w.writerow({
                "sample_no": sno,
                "set_role": "DIAGNOSTIC_ONLY" if sno in DIAGNOSTIC_ONLY else "FORMAL",
                "diagnostic_only": "FALSE" if sno not in DIAGNOSTIC_ONLY else "TRUE",
                "pdf_sha256": r["pdf_sha256"],
                "file_path": r["file_path"],
                "page_count": r["page_count"],
                "evidence_page_no": r["evidence_page_no"],
                "proposed_stratum": r["proposed_stratum"],
                "selection_basis": r["selection_basis"],
                "painpoint_amplification": r["painpoint_amplification"],
                "gold_status": r["gold_status"],
                "baseline_5": r["baseline_5"],
                "legacy_reference": r["legacy_reference"],
                "v2_predicted_class": flags.get("v2_predicted_class", ""),
                "v2_predicted_route": flags.get("v2_predicted_route", ""),
                "has_text_layer": flags.get("has_text_layer", ""),
                "d_prime_change_hit": "FALSE",   # GATE6A_PLAN §1.4 缺口 3 实测 0 命中
                "notes": r.get("notes", ""),
            })

    for name, cols in (("Gold_Set_Template.candidates.csv", CAND_COLS),
                       ("Gold_Set_Template.column_roles.csv", ROLE_COLS)):
        with open(OUT / name, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            # 空表：表头即契约，标注人按样本追加行

    print("Gold_Set_Template.csv rows=%d (formal=%d, diagnostic_only=%d, supplementary=%d)"
          % (len(rows),
             sum(1 for r in rows if r["set_role"] == "FORMAL"),
             sum(1 for r in rows if r["set_role"] == "DIAGNOSTIC_ONLY"),
             sum(1 for r in rows if r["set_role"] == "SUPPLEMENTARY")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
