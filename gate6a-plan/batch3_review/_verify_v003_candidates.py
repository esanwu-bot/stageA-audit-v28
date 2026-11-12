# -*- coding: utf-8 -*-
"""prescan3 加固后，用 V003 全书 282 页做真实 PDF 回归并留 stdout。

为什么单独一份：_test_core_order_and_header.py 全部用合成页，不依赖外部 PDF；
真实手册的候选页回归需要外部文件，两者分开，合成测试才能保持 SKIP=0。

本轮追加「13 页上下文链路证据」：把页级分类、上一页状态、表头指纹
相似度、最终放行链路逐页打印，并硬断言「只有 p102 / p106 两页走
指纹继承，其余 11 页走本页正常提取」——这是 PM 2026-11-12 的验收口径。
"""
from __future__ import print_function

import argparse
import sys
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _build_batch3_interactive as I3

PDF = Path(r"E:\workspace\IcPdfParser\data\pdfs\AM2431BSDFHIALXR__am2431.pdf")
# 13 页都是第 6 章真实参数表页：p101 AMR，p105/p106 ROC，
# p108~119 为 Electrical Characteristics / ROC 等真表（表头含
# PARAMETER / TEST CONDITIONS / MIN / TYP / MAX / UNIT）。
# 第五轮加固曾因阈值过紧把这 9 页误杀，现整表写进回归断言。
WANT = (101, 102, 105, 106, 108, 109, 110, 111, 112, 113, 115, 117, 119)
EXCLUDE = (14,)
INHERIT_PAGES = (102, 106)      # PM 指定：只有这两页允许走跨页指纹继承


def context_evidence(doc):
    """逐页打印「页级分类 → 表头指纹 → 上下文关联」真实链路。

    严格串行：本页 Stage 2 全部 extract 完（PageContext 随即释放 page），
    才访问上一页；STRONG / WEAK 页连上一页的 find_tables 都不调。
    """
    print("")
    print("=" * 122)
    print("13 页真实表的上下文链路证据（页级分类 → 表头指纹 → 上下文关联）")
    print("=" * 122)
    print("%-6s %-8s %-44s %-34s %8s  %s" %
          ("pno", "本页类别", "本页 Page_Title", "上一页类别/标题", "指纹sim", "放行链路"))
    print("-" * 122)
    inherit, local, geo_ok, text_ok, sig_total = [], [], True, True, 0
    for pno in WANT:
        pg = doc.load_page(pno - 1)
        cur = I3.PageContext(pg, pno)
        cur.extract_tables()
        prev = None
        if pno > 1:
            prev = I3.PageContext(doc.load_page(pno - 2), pno - 1)
            if cur.title_class == "NONE":
                prev.extract_tables()
        links = I3.link_context(cur, prev)
        allowed = [r for _, ok, r, _ in links if ok]
        if "INHERITED_TITLE_FINGERPRINT" in allowed:
            inherit.append(pno)
        if "LOCAL_TITLE" in allowed:
            local.append(pno)
        sims = ([I3.fingerprint_similarity(s.fp, ps.fp)
                 for s in cur.signatures for ps in prev.signatures]
                if prev is not None and prev.signatures else [])
        simtxt = ("%.2f" % max(sims)) if sims else "--"
        pstate = ("%s / %s" % (prev.title_class,
                               (prev.page_title or "(无)")[:21])
                  if prev is not None else "-")
        print("p%-5d %-8s %-44s %-34s %8s  %s" %
              (pno, cur.title_class, (cur.page_title or "(无)")[:42],
               pstate, simtxt, ",".join(allowed) or "(全拦)"))
        for s in cur.signatures:
            sig_total += 1
            if not I3._bbox_in_clip(s.bbox, cur.rect):
                geo_ok = False
            if s.text_hit < I3.TABLE_TEXT_MIN_HIT:
                text_ok = False
    print("-" * 122)
    checks = [
        (sorted(inherit) == list(INHERIT_PAGES),
         "恰好 2 页走指纹继承：%s（PM 指定 p102 / p106）" % inherit),
        (sorted(local) == [p for p in WANT if p not in INHERIT_PAGES],
         "11 页有本页独立标题，走 LOCAL_TITLE 正常提取：%s" % local),
        (sig_total >= 13 and geo_ok,
         "13 页共 %d 张表签名 bbox 全在本页 clip 内（隔离 2 / Y 轴越界）" % sig_total),
        (sig_total >= 13 and text_ok,
         "13 页表头词均在本页文本核到（隔离 3 / 跨页正文串入）"),
    ]
    ok = True
    for hit, msg in checks:
        print("%s %s" % ("PASS" if hit else "FAIL", msg))
        ok = ok and hit
    return ok


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
    extra = sorted(set(cand) - set(WANT))
    hit = not extra
    print("%s 候选页集合与 13 页真表清单一致，无多余页%s" %
          ("PASS" if hit else "FAIL", "" if hit else "：%s" % extra))
    ok = ok and hit

    ok = context_evidence(doc) and ok
    doc.close()
    print("结论：%s" % ("全部通过" if ok else "未通过"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
