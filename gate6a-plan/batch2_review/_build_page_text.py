# -*- coding: utf-8 -*-
"""把证据页的原文抽成 page_text.json，让机检脚本脱离 PDF 也能跑。

只抽需要的页：第 1 页（核对型号）+ CSV 里出现的 evidence_page。
不整本抄，一是包体积，二是没必要——机检只对这几页负责。
"""
import csv
import datetime
import json
from pathlib import Path

import fitz

PREP = Path(__file__).resolve().parent
PDF_DIR = Path(r"E:\workspace\IcPdfParser\data\pdfs")
GS = PREP / "Batch2_GOLD_v1.csv"
OUT = PREP / "page_text.json"


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
           "note": "只含第 1 页与 CSV 中出现的 evidence_page，供 validate_annotation.py 离线核对",
           "corpus_dir_at_build": str(PDF_DIR),
           "samples": {}}

    for sno, meta in need.items():
        doc = fitz.open(str(PDF_DIR / meta["file"]))
        pages = {}
        for p in sorted(meta["pages"], key=int):
            pages[p] = doc.load_page(int(p) - 1).get_text("text") or ""
        out["samples"][sno] = {"file_name": meta["file"], "device_model": meta["model"],
                               "page_count": doc.page_count, "pages": pages}
        print("%s %-40s 页数 %-3d 收录 p%s" % (sno, meta["file"], doc.page_count,
                                              ",".join(sorted(pages, key=int))))
        doc.close()

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("写出 %s  %.1f KB" % (OUT.name, OUT.stat().st_size / 1024))


if __name__ == "__main__":
    main()
