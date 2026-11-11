# -*- coding: utf-8 -*-
"""生成 Gate 6A Gold Set 人工标注模板（三个扁平 CSV）。

设计要点
--------
* `GATE6A_PARSER_BENCHMARK.md` §5 的 Gold 结构是嵌套 JSON（样本 → 表 → 行 → 单元格）。
  人工填写用嵌套 JSON 极易出错，因此这里拆成三个**扁平** CSV，一份一张表，
  一行一条记录，最后可无损折叠回 §5 的 JSON 结构。

      Gold_Set_Template.csv              一行一个样本（标量字段）
      Gold_Set_Template.candidates.csv   一行一个 expected_candidate
      Gold_Set_Template.column_roles.csv 一行一个单元格的 gold_column_role

* 「预填」列由机器产生，标注人**只读不改**；「待填」列一律留空。
  两者的分界写在 `Gold_Set_Template.README.md`。

* 严禁用 Parser 输出反填 Gold（自我印证）。本脚本不读任何 Parser 产物。

本轮（v1.1）三处裁定已落进数据
------------------------------
1. V130 / V290 / V347 的层名由「扫描型或复杂版面」改为「短文档（9–10 页）」。
   依据：三件 page_count 9–10、has_text_layer = TRUE，不是扫描件。
2. S01 / S02 / S03 正式列入「扫描件（无文本层）」层，
   set_role = FORMAL_OUT_OF_POOL，denominator_eligible = TRUE。
3. V022 保持 diagnostic_only = TRUE、denominator_eligible = FALSE，绝不进分母。
"""
from __future__ import print_function

import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(r"E:\workspace\icpdf-extractor")
PROPOSAL = ROOT / "runs/stage_a_350/gate6_r2/GATE6A_SAMPLE_PROPOSAL.csv"
POOL = ROOT / "runs/stage_a_350/ds_parse_candidates_350_v2.csv"
OUT = Path(__file__).resolve().parent
# 产出先落 build/，再回填 OUT/。
# 原因：OUT/ 下的 CSV 可能正被 WorkBuddy 预览面板或 Excel 独占打开，
# 直接写入会 PermissionError。回填失败时不静默跳过，逐项报告。
BUILD = OUT / "build"

SCAN_STRATUM = "扫描件（无文本层）"
SHORT_DOC_STRATUM = "短文档（9–10 页）"

# 层名修正：原提案把这三件记在「扫描型或复杂版面」层，实测是短文档而非扫描件。
# Reviewer 2026-11-11 裁定改名（GATE6A_PLAN.md v1.1 §1.3 / §1.4 缺口 1）。
STRATUM_RENAME = {
    "V130": SHORT_DOC_STRATUM,
    "V290": SHORT_DOC_STRATUM,
    "V347": SHORT_DOC_STRATUM,
}

RENAME_NOTE = ("；层名经 Reviewer 2026-11-11 修正：原提案记为「扫描型或复杂版面」，"
               "实测 page_count 9–10 且 has_text_layer=TRUE，属短文档而非扫描件")

# V022：Reviewer 裁定单列 diagnostic_only，绝不进任何指标分母
# （GATE6A_PLAN §1.4 缺口 2，v1.1 已确认）
DIAGNOSTIC_ONLY = {
    "V022": "Gate 6A 指定检查点：疑似 EVM 板卡手册，池内 v2 判为 DS_STRONG/IC_PARSE，"
            "类别自相矛盾；仅用于诊断 Parser 是否产出「看似合理的垃圾」，"
            "不参与任何指标分子分母（GATE6A_PLAN.md §1.4 缺口 2）",
}

SUPP_NOTE = ("350 池外补充件（同 SHA 别名 %d 个）；Reviewer 2026-11-11 批准正式列入"
             "「%s」层并计入分母（GATE6A_PLAN.md v1.1 §1.4 缺口 1 选项 2）；"
             "计入仍以 status = CONFIRMED 为前提")

MAIN_COLS = [
    # —— 预填（机器产生，标注人只读）——
    "sample_no",
    "set_role",
    "diagnostic_only",
    "denominator_eligible",
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

# 候选清单（33 件全集）的列
LIST_COLS = [
    "sample_no", "set_role", "diagnostic_only", "denominator_eligible",
    "in_350_pool", "pdf_sha256", "file_path", "page_count",
    "evidence_page_no", "stratum", "selection_basis",
    "painpoint_amplification", "gold_status", "baseline_5",
    "legacy_reference", "v2_predicted_class", "v2_predicted_route",
    "has_text_layer", "d_prime_change_hit", "notes",
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
    """经 _select_supplementary.py 确定性选出的 3 件池外扫描件。"""
    p = OUT / "selected_supplementary.json"
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8")).get("selected", [])


def main():
    proposal = read_csv(PROPOSAL)
    pool = load_pool_flags()
    supp = load_supplementary()

    rows = []
    list_rows = []

    for r in proposal:
        sno = r["sample_no"]
        flags = pool.get(sno, {})
        is_diag = sno in DIAGNOSTIC_ONLY
        stratum = STRATUM_RENAME.get(sno, r["proposed_stratum"])
        renamed = sno in STRATUM_RENAME
        # 层名已由 Reviewer 裁定的件，stratrum_confirmed 一并预填，
        # 避免标注人再去猜；其余件仍要求人看 PDF 后确认。
        confirmed = stratum if renamed else "PENDING"
        note = r.get("notes", "") + (RENAME_NOTE if renamed else "")

        rows.append({
            "sample_no": sno,
            "set_role": "DIAGNOSTIC_ONLY" if is_diag else "FORMAL",
            "diagnostic_only": "TRUE" if is_diag else "FALSE",
            "denominator_eligible": "FALSE" if is_diag else "TRUE",
            "pdf_sha256": r["pdf_sha256"],
            "file_path": r["file_path"],
            "page_count": r["page_count"],
            "stratum_proposed": stratum,
            "text_layer_probe": flags.get("has_text_layer", ""),
            "page1_text_chars": "",
            "painpoint_hypothesis": r["painpoint_amplification"],
            "reviewer": "",
            "reviewer_2": "",
            "reviewed_at": "",
            "status": "DRAFT",
            "stratum_confirmed": confirmed,
            "text_layer_verified": "",
            "pain_coverage": "",
            "target_table_count": "",
            "expected_candidate_count": "",
            "gold_json_path": "",
            "notes": note,
            "exclude_from_metrics_reason": DIAGNOSTIC_ONLY.get(sno, ""),
        })

        list_rows.append({
            "sample_no": sno,
            "set_role": "DIAGNOSTIC_ONLY" if is_diag else "FORMAL",
            "diagnostic_only": "TRUE" if is_diag else "FALSE",
            "denominator_eligible": "FALSE" if is_diag else "TRUE",
            "in_350_pool": "TRUE",
            "pdf_sha256": r["pdf_sha256"],
            "file_path": r["file_path"],
            "page_count": r["page_count"],
            "evidence_page_no": r["evidence_page_no"],
            "stratum": stratum,
            "selection_basis": r["selection_basis"],
            "painpoint_amplification": r["painpoint_amplification"],
            "gold_status": r["gold_status"],
            "baseline_5": r["baseline_5"],
            "legacy_reference": r["legacy_reference"],
            "v2_predicted_class": flags.get("v2_predicted_class", ""),
            "v2_predicted_route": flags.get("v2_predicted_route", ""),
            "has_text_layer": flags.get("has_text_layer", ""),
            "d_prime_change_hit": "FALSE",
            "notes": note,
        })

    # 池外补充件：正式列入扫描件层，准备计入分母
    for c in supp:
        rows.append({
            "sample_no": c["sample_no"],
            "set_role": "FORMAL_OUT_OF_POOL",
            "diagnostic_only": "FALSE",
            "denominator_eligible": "TRUE",
            "pdf_sha256": c["sha256"],
            "file_path": c["file_path"],
            "page_count": c["page_count"],
            "stratum_proposed": SCAN_STRATUM,
            "text_layer_probe": "FALSE",
            "page1_text_chars": c["page1_text_chars"],
            "painpoint_hypothesis": "PAIN-08 文本层缺失或乱码",
            "reviewer": "", "reviewer_2": "", "reviewed_at": "",
            "status": "DRAFT",
            "stratum_confirmed": SCAN_STRATUM,
            "text_layer_verified": "",
            "pain_coverage": "",
            "target_table_count": "",
            "expected_candidate_count": "",
            "gold_json_path": "",
            "notes": SUPP_NOTE % (c["alias_count"], SCAN_STRATUM),
            "exclude_from_metrics_reason": "",
        })

        list_rows.append({
            "sample_no": c["sample_no"],
            "set_role": "FORMAL_OUT_OF_POOL",
            "diagnostic_only": "FALSE",
            "denominator_eligible": "TRUE",
            "in_350_pool": "FALSE",
            "pdf_sha256": c["sha256"],
            "file_path": c["file_path"],
            "page_count": c["page_count"],
            "evidence_page_no": "N/A",
            "stratum": SCAN_STRATUM,
            "selection_basis": "池外补充：11,355 全量扫描命中无文本层件，"
                               "按 %s 分档、档内 SHA 升序取首件" % c["band"],
            "painpoint_amplification": "PAIN-08 文本层缺失或乱码",
            "gold_status": "PROPOSED_PENDING_GOLD_CONFIRMATION",
            "baseline_5": "FALSE",
            "legacy_reference": "FALSE",
            "v2_predicted_class": "N/A（无文本层，未经分类器判别）",
            "v2_predicted_route": "N/A",
            "has_text_layer": "FALSE",
            "d_prime_change_hit": "FALSE",
            "notes": "同 SHA 别名 %d 个；70 页逐页核验 0 字符" % c["alias_count"],
        })

    BUILD.mkdir(parents=True, exist_ok=True)

    outputs = {
        "Gold_Set_Template.csv": MAIN_COLS,
        "GATE6A_SAMPLE_CANDIDATES.csv": LIST_COLS,
        "Gold_Set_Template.candidates.csv": CAND_COLS,
        "Gold_Set_Template.column_roles.csv": ROLE_COLS,
    }
    written = {}
    for name, cols in outputs.items():
        path = BUILD / name
        with open(path, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            if name == "Gold_Set_Template.csv":
                w.writerows(rows)
            elif name == "GATE6A_SAMPLE_CANDIDATES.csv":
                w.writerows(list_rows)
            # 两张明细表只写表头：表头即契约，标注人按样本追加行
        written[name] = path

    # 回填 OUT/：被占用的文件不静默跳过，逐项报告
    print("--- 回填 %s ---" % OUT)
    for name in outputs:
        src, dst = BUILD / name, OUT / name
        try:
            dst.write_bytes(src.read_bytes())
            print("  OK      %s" % name)
        except PermissionError:
            print("  LOCKED  %s（构建产物在 build/，本次未回填）" % name)

    role = Counter(r["set_role"] for r in rows)
    strat = Counter(r["stratum_proposed"] for r in rows)
    elig = Counter(r["denominator_eligible"] for r in rows)
    print("Gold_Set_Template.csv rows=%d" % len(rows))
    print("  set_role            : %s" % dict(role))
    print("  denominator_eligible: %s" % dict(elig))
    print("  stratum             :")
    for k, v in strat.most_common():
        print("      %2d  %s" % (v, k))
    print("GATE6A_SAMPLE_CANDIDATES.csv rows=%d" % len(list_rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
