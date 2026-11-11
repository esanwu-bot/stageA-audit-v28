# -*- coding: utf-8 -*-
"""从 page_text.json 生成 PDF 溯源表（样本 → 文件 → SHA-256 → 页数）。

数据只有一份源头（page_text.json 里的 sha256/page_count/size_bytes），
这里只做"摊平成表格"，不重新算哈希，避免两处口径打架。
"""
import csv
import json
from pathlib import Path

PREP = Path(__file__).resolve().parent
SRC = PREP / "page_text.json"
OUT_CSV = PREP / "Batch2_PDF_PROVENANCE.csv"

COLS = ["sample_no", "device_model", "file_name", "sha256", "page_count", "size_bytes"]


def load():
    d = json.loads(SRC.read_text(encoding="utf-8"))
    rows = []
    for sno in sorted(d["samples"]):
        s = d["samples"][sno]
        rows.append({
            "sample_no": sno,
            "device_model": s.get("device_model", ""),
            "file_name": s.get("file_name", ""),
            "sha256": s.get("sha256", ""),
            "page_count": s.get("page_count", ""),
            "size_bytes": s.get("size_bytes", ""),
        })
    return d, rows


def main():
    d, rows = load()
    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print("写出 %s  %d 行" % (OUT_CSV.name, len(rows)))
    for r in rows:
        print("  %-5s %-18s %-42s p%-3s %s" %
              (r["sample_no"], r["device_model"], r["file_name"],
               r["page_count"], r["sha256"][:16] + "…"))
    return rows


if __name__ == "__main__":
    main()
