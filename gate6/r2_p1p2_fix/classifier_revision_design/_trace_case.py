"""单样本判定轨迹导出（只读）。

用途：把某一份 PDF 在 A/B/D/E/F 五个方案下的命中证据与最终判定完整落成 JSON，
便于逐条复核「为什么这份文件被送进 Parser」。

**这不是 HTTP 响应**。它直接调用生产 `_decide_matrix`，绕过 `_classify_worker`
进程边界、超时与上传链路，性质是纯函数级模拟。

用法：py -3.13 workbench/_classifier_revision/_trace_case.py <文件名>
输出：_impact_matrix/trace_<stem>.json
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from icpdf.classification.classifier import (  # noqa: E402
    DEFAULT_FIRST_PAGES,
    _decide_matrix,
)
from icpdf.classification.rules import (  # noqa: E402
    parse_provenance,
    scan_filename,
    scan_pages,
)

DATA_DIR = Path(r"E:\workspace\IcPdfParser\data\pdfs")
OUT_DIR = Path(__file__).resolve().parent / "_impact_matrix"

RULE = "DS_PRODUCT_MODEL_TITLE"
BOARD = "EVM_BOARD_TITLE"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _hit(h) -> dict:
    return {
        "rule_id": h.rule_id,
        "group": h.group,
        "strength": getattr(h.strength, "value", str(h.strength)),
        "confidence": getattr(h.confidence, "value", str(h.confidence)),
        "source": getattr(h.source, "value", str(h.source)),
        "page": h.page,
        "matched_text": h.matched_text,
    }


def _decide(hits, pe, cand, filename, pv) -> dict:
    dec = _decide_matrix(hits, pe, "OK", cand, filename, pv)
    return {
        "doc_type": dec.doc_type.value,
        "route": dec.route.value,
        "confidence": dec.confidence.value,
        "semantic": getattr(dec.semantic, "value", str(dec.semantic)),
        "status": getattr(dec.status, "value", str(dec.status)),
        "conflict": dec.conflict,
        "rejected_rules": [getattr(r, "rule_id", str(r)) for r in (dec.rejected or [])],
    }


def main(name: str) -> int:
    import pymupdf as fitz

    path = DATA_DIR / name
    doc = fitz.open(str(path))
    pages = [doc[j].get_text() for j in range(min(DEFAULT_FIRST_PAGES, doc.page_count))]
    meta_title = doc.metadata.get("title") or ""
    meta_subject = doc.metadata.get("subject") or ""
    page_count = doc.page_count
    doc.close()

    mpn = Path(name).stem.split("__", 1)[0] if "__" in Path(name).stem else Path(name).stem
    pv = parse_provenance(name)
    cand_a = pv.document_subject_mpn or mpn
    cand_b = pv.source_product_mpn or ""

    base = list(scan_filename(name, mpn))
    page_a, pe_a = scan_pages(pages, meta_title, meta_subject, cand_a, None)
    page_b, pe_b = (page_a, pe_a) if cand_b == cand_a else scan_pages(
        pages, meta_title, meta_subject, cand_b, None)
    board_a = any(h.rule_id == BOARD for h in page_a)
    board_b = any(h.rule_id == BOARD for h in page_b)
    no_rule = lambda hs: [h for h in hs if h.rule_id != RULE]  # noqa: E731

    plans = {
        "A": (cand_a, page_a, pe_a),
        "B": (cand_b, page_b, pe_b),
        "D": (cand_a, no_rule(page_a) if board_a else page_a, pe_a),
        "E": (cand_a, no_rule(page_a), pe_a),
        "F": (cand_b, no_rule(page_b) if board_b else page_b, pe_b),
    }

    variants = {}
    for key, (cand, page_hits, pe) in plans.items():
        hits = base + list(page_hits)
        variants[key] = {
            "candidate_passed_to_scan_pages": cand,
            "ds_product_model_title_fired": any(h.rule_id == RULE for h in hits),
            "board_title_present": any(h.rule_id == BOARD for h in page_hits),
            "hits": [_hit(h) for h in hits],
            "decision": _decide(hits, pe, cand, name, pv),
        }

    payload = {
        "evidence_kind": "pure_function_simulation",
        "not_an_http_response": (
            "本文件直接调用生产 _decide_matrix 生成，未经 _classify_worker 进程、"
            "未经过上传链路与超时控制，不是 /api/parse 或 /api/process 的响应体。"),
        "generated_by": "workbench/_classifier_revision/_trace_case.py",
        "sample": {
            "filename": name,
            "pdf_sha256": _sha256(path),
            "page_count": page_count,
            "pages_read": min(DEFAULT_FIRST_PAGES, page_count),
            "metadata_title": meta_title,
            "metadata_subject": meta_subject,
            "filename_mpn": mpn,
            "provenance_document_subject_mpn": pv.document_subject_mpn,
            "provenance_source_product_mpn": pv.source_product_mpn,
            "provenance": pv.model_dump(mode="json"),
        },
        "variants": variants,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / ("trace_%s.json" % Path(name).stem)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("written", out)
    for k, v in variants.items():
        d = v["decision"]
        print("  %s cand=%-14s %s/%s  fired=%s" % (
            k, v["candidate_passed_to_scan_pages"] or "''",
            d["doc_type"], d["route"], v["ds_product_model_title_fired"]))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    raise SystemExit(main(sys.argv[1]))
