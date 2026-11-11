# -*- coding: utf-8 -*-
"""Gate 6A 补充样本：在真实语料池中定位"无文本层 / 纯图像"PDF。

约束（Reviewer 明令）：
  - 绝不调用 icpdf Parser，不启动解析流水线，不写 workbench/runs 产物。
  - 只用 PyMuPDF(MuPDF) 做只读文本层探测，与 Gate 1 已有的
    runs/_gate1_pdf_probe.py 同一判定口径（首段有效文本 >= 20 字符视为有文本层）。

两段式判定，避免"首页是封面图、后页有文本"被误判为纯图像：
  段 1：探测首页有效文本字符数。
  段 2：仅对段 1 判为无文本层的文件，追加抽样最多 8 个跨页（首/尾/等距），
        汇总全文抽样字符数。只有"抽样总字符 < 20"才进入纯图像候选。

输出：
  scan_all.jsonl    —— 每份文件一行（page1 探测结果）
  candidates.jsonl  —— 纯图像候选（含 sha256）
  scan_summary.json —— 汇总统计
"""
from __future__ import print_function

import glob
import hashlib
import json
import os
import sys
import time
from multiprocessing import Pool

CORPUS = r"E:\workspace\IcPdfParser\data\pdfs"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

TEXT_MIN = 20          # 与 Gate 1 探针一致
MAX_SAMPLE_PAGES = 8   # 段 2 抽样页上限


def _page_texts(doc, idxs):
    out = []
    for i in idxs:
        try:
            out.append(doc.load_page(i).get_text("text") or "")
        except Exception:                                  # noqa: BLE001
            out.append("")
    return out


def probe_one(path):
    rec = {
        "path": path,
        "name": os.path.basename(path),
        "size_bytes": 0,
        "valid": "FALSE",
        "page_count": 0,
        "encrypted": "NOT_CHECKED",
        "page1_chars": -1,
        "sample_pages": 0,
        "sample_chars": -1,
        "image_only": "UNDETERMINED",
        "err": "",
    }
    try:
        rec["size_bytes"] = os.path.getsize(path)
    except OSError:
        pass
    try:
        import fitz
        doc = fitz.open(path)
        try:
            enc = bool(doc.is_encrypted or doc.needs_pass)
            rec["encrypted"] = "TRUE" if enc else "FALSE"
            rec["page_count"] = int(doc.page_count)
            rec["valid"] = "TRUE"
            if enc or doc.page_count == 0:
                # 加密件无法读文本层，不进入纯图像候选（另列处理）
                rec["image_only"] = "EXCLUDED_ENCRYPTED" if enc else "EXCLUDED_EMPTY"
                return rec
            # 段 1：首页
            t1 = _page_texts(doc, [0])[0]
            rec["page1_chars"] = len(t1.strip())
            if rec["page1_chars"] >= TEXT_MIN:
                rec["image_only"] = "FALSE"
                return rec
            # 段 2：跨页抽样
            n = doc.page_count
            if n <= MAX_SAMPLE_PAGES:
                idxs = list(range(n))
            else:
                step = (n - 1) / float(MAX_SAMPLE_PAGES - 1)
                idxs = sorted({int(round(i * step)) for i in range(MAX_SAMPLE_PAGES)})
            texts = _page_texts(doc, idxs)
            total = sum(len(t.strip()) for t in texts)
            rec["sample_pages"] = len(idxs)
            rec["sample_chars"] = total
            rec["image_only"] = "TRUE" if total < TEXT_MIN else "FALSE"
        finally:
            doc.close()
    except Exception as exc:                               # noqa: BLE001
        rec["err"] = type(exc).__name__
        rec["valid"] = "FALSE"
    return rec


def sha256_of(path):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()


def main():
    files = sorted(glob.glob(os.path.join(CORPUS, "*.pdf")))
    print("corpus=%s total_pdf=%d" % (CORPUS, len(files)), flush=True)
    t0 = time.time()
    recs = []
    with Pool(processes=8) as pool:
        for i, rec in enumerate(pool.imap_unordered(probe_one, files, chunksize=16), 1):
            recs.append(rec)
            if i % 1000 == 0:
                el = time.time() - t0
                print("  %d/%d  %.1fs  (%.2f ms/file)" % (
                    i, len(files), el, el / i * 1000), flush=True)

    recs.sort(key=lambda r: r["name"])
    all_path = os.path.join(OUT_DIR, "scan_all.jsonl")
    with open(all_path, "w", encoding="utf-8", newline="\n") as fh:
        for r in recs:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    cands = [r for r in recs if r["image_only"] == "TRUE"]
    for r in cands:
        r["sha256"] = sha256_of(r["path"])

    cand_path = os.path.join(OUT_DIR, "candidates.jsonl")
    with open(cand_path, "w", encoding="utf-8", newline="\n") as fh:
        for r in cands:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    def cnt(key, val):
        return sum(1 for r in recs if r[key] == val)

    summary = {
        "corpus": CORPUS,
        "total_pdf": len(files),
        "elapsed_sec": round(time.time() - t0, 1),
        "text_threshold_chars": TEXT_MIN,
        "sample_pages_cap": MAX_SAMPLE_PAGES,
        "counts": {
            "valid_true": cnt("valid", "TRUE"),
            "valid_false": cnt("valid", "FALSE"),
            "encrypted_true": cnt("encrypted", "TRUE"),
            "image_only_true": cnt("image_only", "TRUE"),
            "image_only_false": cnt("image_only", "FALSE"),
            "excluded_encrypted": cnt("image_only", "EXCLUDED_ENCRYPTED"),
            "excluded_empty": cnt("image_only", "EXCLUDED_EMPTY"),
        },
        "candidates": [
            {"name": r["name"], "path": r["path"], "sha256": r["sha256"],
             "page_count": r["page_count"], "size_bytes": r["size_bytes"],
             "page1_chars": r["page1_chars"], "sample_pages": r["sample_pages"],
             "sample_chars": r["sample_chars"]}
            for r in cands
        ],
        "parser_invoked": False,
        "llm_called": False,
        "run_artifacts_written": False,
    }
    with open(os.path.join(OUT_DIR, "scan_summary.json"), "w",
              encoding="utf-8", newline="\n") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)

    print("done elapsed=%.1fs image_only=%d" % (
        time.time() - t0, len(cands)), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
