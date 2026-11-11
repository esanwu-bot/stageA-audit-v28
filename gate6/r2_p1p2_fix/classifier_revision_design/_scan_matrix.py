"""方案 A / B / D / E / F 全量对照扫描（只读，多进程版 v2）。

一次 PDF 文本抽取，五个判定：
  A  BEFORE       : cand = document_subject_mpn or mpn   （当前生产代码）
  B  R1' naive    : cand = source_product_mpn or ""      （上一轮被推翻的方案）
  D  guard_only   : cand = A 的参数，标题块命中 EVM_BOARD_TITLE 时抑制该规则
  E  demote       : cand = A 的参数，无条件移除该规则（= 降级出 DS_STRONG_RULES）
  F  source+guard : cand = B 的参数，标题块命中 EVM_BOARD_TITLE 时抑制该规则

性能说明（v2）：`scan_pages` 只依赖候选型号，A/D/E 共用 cand_a 的一次调用，
B/F 共用 cand_b 的一次调用；每份 PDF 因此只做 2 次 `scan_pages` + 5 次 `_decide_matrix`，
再按 CPU 核数并行。v1 是 5 次 `scan_pages` + 单进程，实测 8.2%/9min，已废弃。

输出：_impact_matrix/matrix.jsonl + summary.json
复现：py -3.13 workbench/_classifier_revision/_scan_matrix.py
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

DATA_DIR = Path(r"E:\workspace\IcPdfParser\data\pdfs")
OUT_DIR = Path(__file__).resolve().parent / "_impact_matrix"
JSONL = OUT_DIR / "matrix.jsonl"
SUMMARY = OUT_DIR / "summary.json"

RULE = "DS_PRODUCT_MODEL_TITLE"
BOARD = "EVM_BOARD_TITLE"
VARIANTS = ("B", "D", "E", "F")

_fitz = None
_decide_matrix = None
_scan_pages = None
_scan_filename = None
_parse_provenance = None
_DEFAULT_FIRST_PAGES = 3


def _init():
    global _fitz, _decide_matrix, _scan_pages, _scan_filename, _parse_provenance
    global _DEFAULT_FIRST_PAGES
    import pymupdf as fitz

    from icpdf.classification.classifier import DEFAULT_FIRST_PAGES, _decide_matrix as dm
    from icpdf.classification.rules import parse_provenance, scan_filename, scan_pages

    _fitz = fitz
    _decide_matrix = dm
    _scan_pages = scan_pages
    _scan_filename = scan_filename
    _parse_provenance = parse_provenance
    _DEFAULT_FIRST_PAGES = DEFAULT_FIRST_PAGES


def _mpn_from_name(name: str) -> str:
    stem = Path(name).stem
    return stem.split("__", 1)[0] if "__" in stem else stem


def _other_strong(hits) -> str:
    tags = []
    for h in hits:
        if h.rule_id == RULE:
            continue
        if getattr(h, "strength", None) is not None and h.strength.value == "strong":
            tags.append(h.rule_id if not h.group else "%s/%s" % (h.rule_id, h.group))
    groups = {h.group for h in hits if h.rule_id == "DS_ELECTRICAL_SECTIONS" and h.group}
    if len(groups) >= 2 and (groups & {"SECTION_ELECTRICAL", "SECTION_ABSMAX", "SECTION_PINS"}):
        tags.append("ds_combo(%s)" % "|".join(sorted(groups)))
    return ";".join(sorted(set(tags))) if tags else "(none)"


def _pack(hits, pe, cand, filename, provenance) -> dict:
    dec = _decide_matrix(hits, pe, "OK", cand, filename, provenance)
    return {
        "cand": cand,
        "fired": any(h.rule_id == RULE for h in hits),
        "doc_type": dec.doc_type.value,
        "confidence": dec.confidence.value,
        "route": dec.route.value,
        "conflict": dec.conflict,
        "other_strong": _other_strong(hits),
    }


def _without_rule(hits):
    return [h for h in hits if h.rule_id != RULE]


def _work(name: str):
    path = DATA_DIR / name
    try:
        doc = _fitz.open(str(path))
        pages = [doc[j].get_text()
                 for j in range(min(_DEFAULT_FIRST_PAGES, doc.page_count))]
        mt = doc.metadata.get("title") or ""
        ms = doc.metadata.get("subject") or ""
        doc.close()
    except Exception:
        return (None, True)

    try:
        mpn = _mpn_from_name(name)
        pv = _parse_provenance(name)
        cand_a = pv.document_subject_mpn or mpn
        cand_b = pv.source_product_mpn or ""

        base = list(_scan_filename(name, mpn))
        page_a, pe_a = _scan_pages(pages, mt, ms, cand_a, None)
        if cand_b == cand_a:
            page_b, pe_b = page_a, pe_a
        else:
            page_b, pe_b = _scan_pages(pages, mt, ms, cand_b, None)

        board_a = any(h.rule_id == BOARD for h in page_a)
        board_b = any(h.rule_id == BOARD for h in page_b)

        a = _pack(base + list(page_a), pe_a, cand_a, name, pv)
        b = _pack(base + list(page_b), pe_b, cand_b, name, pv)
        e = _pack(base + _without_rule(page_a), pe_a, cand_a, name, pv)
        d = _pack(base + (_without_rule(page_a) if board_a else list(page_a)),
                  pe_a, cand_a, name, pv)
        f = _pack(base + (_without_rule(page_b) if board_b else list(page_b)),
                  pe_b, cand_b, name, pv)
    except Exception:
        print("ERR %s\n%s" % (name, traceback.format_exc()), file=sys.stderr)
        return (None, True)

    variants = {"B": b, "D": d, "E": e, "F": f}
    key = lambda x: (x["fired"], x["doc_type"], x["route"])  # noqa: E731
    if all(key(v) == key(a) for v in variants.values()):
        return (None, False)

    row = {
        "filename": name,
        "source_product_mpn": pv.source_product_mpn,
        "document_subject_mpn": pv.document_subject_mpn,
        "A_before": a,
    }
    for k in VARIANTS:
        row[k] = variants[k]
    return (row, False)


def _classify(row: dict):
    """把一行归入四类关注事件，返回 (transitions, focus_items)。"""
    a = row["A_before"]
    out = {}
    for k in VARIANTS:
        v = row[k]
        if (v["fired"], v["doc_type"], v["route"]) == (a["fired"], a["doc_type"], a["route"]):
            continue
        if v["doc_type"] == a["doc_type"] and v["route"] == a["route"]:
            continue
        t = "%s/%s -> %s/%s" % (a["doc_type"], a["route"], v["doc_type"], v["route"])
        kind = None
        if a["doc_type"] == "EVM" and v["doc_type"] != "EVM":
            kind = "evm_lost"
        elif a["route"] != "IC_PARSE" and v["route"] == "IC_PARSE":
            kind = "leak_to_parser"
        elif a["doc_type"] == "DS_STRONG" and v["doc_type"] != "DS_STRONG":
            kind = "ds_demoted"
        out[k] = (t, kind, {"file": row["filename"], "t": t,
                            "kind": kind, "other_strong": a["other_strong"]})
    return out


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(f for f in os.listdir(DATA_DIR) if f.lower().endswith(".pdf"))
    total = len(files)
    workers = min(8, os.cpu_count() or 4)
    print("population = %d  workers = %d" % (total, workers), flush=True)

    counts = {k: {"diff": 0, "type": 0} for k in VARIANTS}
    transitions = {k: {} for k in VARIANTS}
    focus = {k: [] for k in VARIANTS}
    rows = []
    n_open_err = 0
    done = 0

    with Pool(workers, initializer=_init) as pool:
        for row, err in pool.imap_unordered(_work, files, chunksize=20):
            done += 1
            if err:
                n_open_err += 1
            if row is not None:
                rows.append(row)
                a = row["A_before"]
                for k in VARIANTS:
                    v = row[k]
                    if (v["fired"], v["doc_type"], v["route"]) != (
                            a["fired"], a["doc_type"], a["route"]):
                        counts[k]["diff"] += 1
                for k, (t, kind, item) in _classify(row).items():
                    counts[k]["type"] += 1
                    transitions[k][t] = transitions[k].get(t, 0) + 1
                    if kind:
                        focus[k].append(item)
            if done % 1000 == 0:
                print("  .. %d/%d rows=%d" % (done, total, len(rows)), flush=True)

    rows.sort(key=lambda r: r["filename"])
    with open(JSONL, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    payload = {
        "population": total,
        "workers": workers,
        "open_errors": n_open_err,
        "rows_any_diff": len(rows),
        "variant_legend": {
            "A": "BEFORE: cand = document_subject_mpn or mpn",
            "B": "R1' naive: cand = source_product_mpn or ''",
            "D": "guard_only: A 参数 + 板级标题存在时抑制 DS_PRODUCT_MODEL_TITLE",
            "E": "demote: A 参数 + 无条件移除该规则",
            "F": "source+guard: B 参数 + 板级标题存在时抑制",
        },
        "per_variant": {
            k: {
                "diff_key": counts[k]["diff"],
                "doc_type_or_route_changed": counts[k]["type"],
                "transitions": dict(sorted(transitions[k].items(), key=lambda kv: -kv[1])),
                "evm_lost": sum(1 for x in focus[k] if x["kind"] == "evm_lost"),
                "leak_to_parser": sum(1 for x in focus[k] if x["kind"] == "leak_to_parser"),
                "ds_demoted": sum(1 for x in focus[k] if x["kind"] == "ds_demoted"),
                "examples": focus[k][:60],
            } for k in VARIANTS
        },
    }
    SUMMARY.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("DONE total=%d open_err=%d rows=%d" % (total, n_open_err, len(rows)), flush=True)
    for k in VARIANTS:
        p = payload["per_variant"][k]
        print("  %s type_changed=%d evm_lost=%d leak=%d ds_demoted=%d" % (
            k, p["doc_type_or_route_changed"], p["evm_lost"], p["leak_to_parser"],
            p["ds_demoted"]), flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    raise SystemExit(main())
