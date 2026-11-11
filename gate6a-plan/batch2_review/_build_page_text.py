# -*- coding: utf-8 -*-
"""把证据页原文与 PDF 溯源信息写进 page_text.json，让机检脚本脱离 PDF 也能跑。

溯源三件事，缺一不可：
  sha256      —— 锁死"这份手册是哪一份"，别人拿到语料能对上是同一文件；
  page_count  —— 证明 evidence_page 没越界；
  size_bytes  —— 顺手记下，便于发现文件被替换过。

只抽需要的页：第 1 页（核对型号）+ CSV 里出现的 evidence_page。
不整本抄，一是包体积，二是没必要——机检只对这几页负责。
"""
import csv
import datetime
import hashlib
import json
from pathlib import Path

import fitz

PREP = Path(__file__).resolve().parent
PDF_DIR = Path(r"E:\workspace\IcPdfParser\data\pdfs")
GS = PREP / "Batch2_GOLD_v1.csv"
OUT = PREP / "page_text.json"


def sha256_of(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(chunk), b""):
            h.update(blk)
    return h.hexdigest()


def main():
    with open(GS, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    need = {}
    for r in rows:
        need.setdefault(r["sample_no"], {"file": r["file_name"], "model": r["device_model"],
                                         "pages": {"1"}})
        need[r["sample_no"]]["pages"].add(str(int(r["evidence_page"])))

    out = {"generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
           "extractor": "PyMuPDF page.get_text('text')",
           "note": "只含第 1 页与 CSV 中出现的 evidence_page，供 validate_annotation.py 离线核对；"
                   "sha256/page_count/size_bytes 用于溯源",
           "corpus_dir_at_build": str(PDF_DIR),
           "samples": {}}

    for sno in sorted(need):
        meta = need[sno]
        path = PDF_DIR / meta["file"]
        digest = sha256_of(path)
        doc = fitz.open(str(path))
        pages = {}
        for p in sorted(meta["pages"], key=int):
            pages[p] = doc.load_page(int(p) - 1).get_text("text") or ""
        out["samples"][sno] = {
            "sample_no": sno,
            "file_name": meta["file"],
            "device_model": meta["model"],
            "sha256": digest,
            "page_count": doc.page_count,
            "size_bytes": path.stat().st_size,
            "pages": pages,
        }
        print("%s %-42s p%-3d %8d B  sha256 %s…" %
              (sno, meta["file"], doc.page_count, path.stat().st_size, digest[:16]))
        doc.close()

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("写出 %s  %.1f KB" % (OUT.name, OUT.stat().st_size / 1024))


if __name__ == "__main__":
    main()
