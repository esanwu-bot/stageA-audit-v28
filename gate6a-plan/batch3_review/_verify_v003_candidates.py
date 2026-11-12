# -*- coding: utf-8 -*-
"""prescan3 加固后，用 V003 全书 282 页做真实 PDF 回归并留 stdout。

为什么单独一份：_test_core_order_and_header.py 全部用合成页，不依赖外部 PDF；
真实手册的候选页回归需要外部文件，两者分开，合成测试才能保持 SKIP=0。
"""
from __future__ import print_function

import argparse
import sys
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _build_batch3_interactive as I3

PDF = Path(r"E:\workspace\IcPdfParser\data\pdfs\AM2431BSDFHIALXR__am2431.pdf")
WANT = (101, 105, 106)
EXCLUDE = (14,)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default=str(PDF), help="V003 PDF 路径")
    args = ap.parse_args()
    pdf = Path(args.pdf)
    if not pdf.exists():
        print("FAIL 找不到 V003 PDF：%s" % pdf)
        return 1
    doc = fitz.open(str(pdf))
    print("V003 真实 PDF 回归：%s" % pdf.name)
    print("页数：%d" % doc.page_count)
    cand = I3.prescan3(doc, doc.page_count)
    print("加固后候选页：%s（%d 页）" % (cand, len(cand)))
    doc.close()

    ok = True
    for pno in WANT:
        hit = pno in cand
        print("%s p%d（第 6 章真表）%s" %
              ("PASS" if hit else "FAIL", pno, "保留" if hit else "被误杀"))
        ok = ok and hit
    for pno in EXCLUDE:
        hit = pno not in cand
        print("%s p%d（术语解释页）%s" %
              ("PASS" if hit else "FAIL", pno, "排除" if hit else "被误放行"))
        ok = ok and hit
    print("结论：%s" % ("全部通过" if ok else "未通过"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
