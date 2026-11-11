# -*- coding: utf-8 -*-
"""生成"内容损坏、但哈希算得出且对得上"的 PDF 夹具，供 F3/N9 复现用。

为什么要单独造这份夹具
----------------------
普通的损坏 PDF（截断、乱码）哈希必然变，v1.5 也能靠哈希不符报错。
真正漏掉的是这样一种语料：**文件已经残了，但溯源表里的哈希被同步改成了残文件的哈希**。
此时三处互校全过、哈希全对，唯独 PDF 本身不能读——只算哈希的检查会在这里放过它。

这个脚本就造这份语料：
  1. 把一份真 PDF 截到 30%（fitz 仍能打开，但 page_count=0）；
  2. 把这个残文件的 SHA-256 写进 sidecar 和 provenance；
  3. 顺带生成只含该样本行的 CSV。

产物目录结构（可直接喂给 validate_annotation.py）：

  <out>/
    pdfs/<原文件名>          残 PDF
    page_text.json           sha256 已改成残文件哈希
    provenance.csv           同上
    v101.csv                 只含该样本的行

用法
----
  python _mk_corrupt_pdf_fixture.py --pdf-dir E:/workspace/IcPdfParser/data/pdfs --out /tmp/corrupt
  python validate_annotation.py --csv /tmp/corrupt/v101.csv --pdf-dir /tmp/corrupt/pdfs \\
         --page-text /tmp/corrupt/page_text.json --provenance /tmp/corrupt/provenance.csv

期望：v1.6 判 ERROR、退出码 1；v1.5 会落到 CANNOT_VERIFY、退出码 0（这就是 F3 的缺口）。
"""
from __future__ import print_function

import argparse
import copy
import csv
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_SAMPLE = "V101"
DEFAULT_CUT = 0.30


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf-dir", default=os.environ.get("ICPDF_PDF_DIR"),
                    help="真 PDF 所在目录（也可用 ICPDF_PDF_DIR）")
    ap.add_argument("--csv", default=str(HERE / "Batch2_GOLD_v1.csv"))
    ap.add_argument("--page-text", default=str(HERE / "page_text.json"))
    ap.add_argument("--provenance", default=str(HERE / "Batch2_PDF_PROVENANCE.csv"))
    ap.add_argument("--sample", default=DEFAULT_SAMPLE, help="挑哪个样本当受害者")
    ap.add_argument("--cut", type=float, default=DEFAULT_CUT, help="截断比例，默认 0.30")
    ap.add_argument("--out", required=True, help="产物目录")
    args = ap.parse_args()

    if not args.pdf_dir:
        print("需要 --pdf-dir 或 ICPDF_PDF_DIR")
        return 2
    pdf_dir = Path(args.pdf_dir)
    if not pdf_dir.is_dir():
        print("PDF 目录不存在: %s" % pdf_dir)
        return 2

    with open(args.csv, encoding="utf-8-sig", newline="") as fh:
        rd = csv.DictReader(fh)
        cols = rd.fieldnames
        rows = list(rd)
    picks = [r for r in rows if r["sample_no"] == args.sample]
    if not picks:
        print("CSV 里没有样本 %s" % args.sample)
        return 2
    fname = picks[0]["file_name"]

    src = pdf_dir / fname
    if not src.exists():
        print("找不到 PDF: %s" % src)
        return 2

    raw = src.read_bytes()
    keep = max(1024, int(len(raw) * args.cut))
    broken = raw[:keep]
    digest = hashlib.sha256(broken).hexdigest()

    out = Path(args.out)
    (out / "pdfs").mkdir(parents=True, exist_ok=True)
    (out / "pdfs" / fname).write_bytes(broken)

    side = copy.deepcopy(json.loads(Path(args.page_text).read_text(encoding="utf-8")))
    if args.sample not in (side.get("samples") or {}):
        print("sidecar 里没有样本 %s" % args.sample)
        return 2
    side["samples"][args.sample]["sha256"] = digest
    (out / "page_text.json").write_text(json.dumps(side, ensure_ascii=False),
                                        encoding="utf-8")

    with open(args.provenance, encoding="utf-8-sig", newline="") as fh:
        prd = csv.DictReader(fh)
        pcols = prd.fieldnames
        prows = list(prd)
    for r in prows:
        if r["sample_no"] == args.sample:
            r["sha256"] = digest
    with open(out / "provenance.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=pcols, lineterminator="\n")
        w.writeheader()
        w.writerows(prows)

    with open(out / ("%s.csv" % args.sample.lower()), "w",
              encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(picks)

    print("样本 %s / 文件 %s" % (args.sample, fname))
    print("原文件 %d 字节 → 残文件 %d 字节（截 %d%%）"
          % (len(raw), len(broken), int(args.cut * 100)))
    print("残文件 SHA-256: %s" % digest)
    print("已写入 sidecar 与 provenance 的 sha256 字段（刻意让它们对得上）")
    print("产物目录: %s" % out)
    print()
    print("复现命令：")
    print("  python validate_annotation.py --csv %s --pdf-dir %s \\"
          % (out / ("%s.csv" % args.sample.lower()), out / "pdfs"))
    print("         --page-text %s --provenance %s"
          % (out / "page_text.json", out / "provenance.csv"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
