# -*- coding: utf-8 -*-
"""比对 PM 手工编辑后的 Batch3_B4_FINAL.xlsx 与上一版 CSV（14 行）的差异。"""
import csv
import sys

import openpyxl

sys.stdout.reconfigure(encoding="utf-8")

CSV = "Batch3_B4_FINAL.csv"
XLSX = "Batch3_B4_FINAL.xlsx"


def norm(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return "%g" % v
    if isinstance(v, int):
        return "%g" % float(v)
    return str(v).strip()


def main():
    old = list(csv.DictReader(open(CSV, encoding="utf-8-sig")))
    ws = openpyxl.load_workbook(XLSX, data_only=True).active
    vals = list(ws.values)
    hdr = [str(x) for x in vals[0]]
    new = [{h: norm(r[i]) for i, h in enumerate(hdr)} for r in vals[1:]]

    print("CSV  %d 行 × %d 列" % (len(old), len(old[0])))
    print("XLSX %d 行 × %d 列" % (len(new), len(hdr)))
    print()

    key = lambda r: (r["sample_no"], r["symbol"],
                     norm(r["min_value"]), norm(r["typ_value"]),
                     norm(r["max_value"]), r["unit"])
    print("=== XLSX 保留的 8 行，与 CSV 同键行逐列比对 ===")
    oldmap = {}
    for r in old:
        oldmap.setdefault(key(r), []).append(r)
    diff = 0
    for r in new:
        k = key(r)
        if k not in oldmap:
            print("  !! 该行在 CSV 里找不到同键：%s" % (k,))
            continue
        o = oldmap[k].pop(0)
        for c in hdr:
            a, b = norm(o.get(c)), r.get(c, "")
            if c in ("min_value", "typ_value", "max_value"):
                if a.replace(" ", "") == b.replace(" ", ""):
                    continue
            if a != b:
                diff += 1
                print("  %-5s %-8s %-14s %r -> %r"
                      % (r["sample_no"], r["symbol"], c, a, b))
    print("差异格数：%d" % diff)
    print()

    print("=== CSV 里有、XLSX 里没有的行（= 被删掉的） ===")
    left = [r for rs in oldmap.values() for r in rs]
    seen = set()
    for r in left:
        k = key(r)
        if k in seen:
            continue
        seen.add(k)
        cnt = sum(1 for x in left if key(x) == k)
        print("  删 %-5s %-8s %s/%s/%s %-3s ×%d  cond=%r"
              % (r["sample_no"], r["symbol"], r["min_value"] or "-",
                 r["typ_value"] or "-", r["max_value"] or "-", r["unit"],
                 cnt, r["condition"]))
    print()
    print("=== 签字列 ===")
    for c in ("reviewer", "approved_by", "entered_by", "row_status"):
        vals_c = {r.get(c, "") for r in new}
        print("  %-12s 取值集合=%s" % (c, sorted(vals_c)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
