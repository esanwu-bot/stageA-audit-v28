"""从 probe_record.json 派生 safety_matrix.csv（不手填任何数值）。

判定档位（档位名取自 classifier._decide_matrix 的分支注释）从「决胜证据」反推：
* ``EVM_BOARD_SCHEMATIC`` 命中      → 档 1（板级 STRONG 证据）
* ``EVM_BOARD_TITLE`` 的决胜组命中  → 档 1
* 两者皆无但 EVM_BOARD_TERMS ≥2 类  → 档 2（只有板级词汇，MEDIUM）
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
DECISIVE_GROUPS = {"EVAL_MODULE", "EVAL_BOARD", "DEV_KIT"}
BOARD_TERM_MIN_GROUPS = 2

rows = json.loads((OUT / "probe_record.json").read_text(encoding="utf-8"))["results"]


def classify_tier(r: dict) -> tuple[str, str]:
    """返回 (档位, 决胜证据说明)。"""
    matched = [m for m in (r.get("matched_rules") or []) if isinstance(m, dict)]
    ids = [m.get("rule_id") for m in matched]
    has_schematic = "EVM_BOARD_SCHEMATIC" in ids
    # 板级标题的组名只能从 rejected 的 reason 括号里读到（evidence 序列化未带 group）
    reason_groups: set[str] = set()
    for x in (r.get("rejected_rules") or []):
        m = re.search(r"overridden by board (?:evidence|terms) \(([^)]*)\)", x.get("reason", ""))
        if m:
            reason_groups |= {g.strip() for g in m.group(1).split("/")}
    title_hits = [m for m in matched if m.get("rule_id") == "EVM_BOARD_TITLE"]
    title_texts = ", ".join(sorted({str(m.get("matched_text")) for m in title_hits}))
    schematic_texts = ", ".join(sorted({str(m.get("matched_text")) for m in matched
                                        if m.get("rule_id") == "EVM_BOARD_SCHEMATIC"}))
    term_texts = sorted({str(m.get("matched_text")) for m in matched
                         if m.get("rule_id") == "EVM_BOARD_TERMS"})

    decisive_title = bool(reason_groups & DECISIVE_GROUPS)
    if has_schematic:
        return "档 1（board_strong）", "EVM_BOARD_SCHEMATIC: %s" % schematic_texts
    if title_hits and decisive_title:
        return "档 1（board_strong）", "EVM_BOARD_TITLE(%s): %s" % (
            "/".join(sorted(reason_groups & DECISIVE_GROUPS)), title_texts)
    if len(term_texts) >= BOARD_TERM_MIN_GROUPS:
        return "档 2（board_body，MEDIUM）", "EVM_BOARD_TERMS %d 类: %s" % (
            len(term_texts), "/".join(term_texts))
    return "其它", "（未能反推，需人工复核）"


def d_prime_effect(r: dict) -> tuple[int, str]:
    """D' 实际抑制了几条 DS_PRODUCT_MODEL_TITLE。"""
    n = 0
    for x in (r.get("rejected_rules") or []):
        if x.get("rule_id") == "DS_PRODUCT_MODEL_TITLE":
            n += 1
    if n:
        return n, "生效：抑制 %d 条 DS_PRODUCT_MODEL_TITLE" % n
    if any(m.get("rule_id") == "DS_PRODUCT_MODEL_TITLE"
           for m in (r.get("matched_rules") or []) if isinstance(m, dict)):
        return 0, "命中但因前提不成立未抑制"
    return 0, "未参与（文档中无 DS_PRODUCT_MODEL_TITLE 命中）"


HEADER = [
    "样本", "文件名", "PDF_SHA256", "HTTP", "service_status", "decision",
    "doc_type", "route", "confidence", "evidence_conflict", "semantic_type",
    "classification_status", "read_status", "source_hash_status",
    "sha256_matches_upload", "admit_to_parser",
    "parser_call_count", "parse_worker_started", "parser_stages_seen",
    "判定档位", "决胜板级证据",
    "D_prime_抑制条数", "D_prime_参与情况",
    "档1_抑制DS_ELECTRICAL_SECTIONS条数",
    "离线D_prime对照", "离线一致",
]

with (OUT / "safety_matrix.csv").open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(HEADER)
    for r in rows:
        tier, why = classify_tier(r)
        dn, dnote = d_prime_effect(r)
        n_elec = sum(1 for x in (r.get("rejected_rules") or [])
                     if x.get("rule_id") == "DS_ELECTRICAL_SECTIONS")
        exp = r.get("offline_expect") or {}
        if exp.get("D_prime"):
            exp_txt = "%s/%s/%s/conflict=%s" % tuple(exp["D_prime"])
        else:
            exp_txt = "不在 193 条变化集（A 与 D' 相同）"
        w.writerow([
            r["id"], r["filename"], r["source_sha256"], r["http_status"],
            r["service_status"], r["decision"], r["doc_type"], r["route"],
            r["confidence"], r["evidence_conflict"], r["semantic_type"],
            r["classification_status"], r["read_status"], r["source_hash_status"],
            r["sha256_matches_upload"], r["admit_to_parser"],
            r["parser_call_count"], r["parse_worker_started"],
            "|".join(r["parser_stages_seen"] or []) or "(empty)",
            tier, why, dn, dnote, n_elec, exp_txt,
            "N/A" if r.get("offline_match") is None else r["offline_match"],
        ])

print("safety_matrix.csv 已生成，%d 行" % len(rows))
for r in rows:
    tier, why = classify_tier(r)
    dn, dnote = d_prime_effect(r)
    print("  %s %-8s %s/%s/%s/%s  %s  D'=%s %s" % (
        r["id"], r["decision"], r["doc_type"], r["route"], r["confidence"],
        r["evidence_conflict"], tier, dn, why[:60]))
