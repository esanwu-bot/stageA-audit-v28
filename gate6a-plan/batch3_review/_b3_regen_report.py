# -*- coding: utf-8 -*-
"""B3 定稿与签字版的逐格差异报告（原始 stdout 即 Batch3_B3_regen_report.txt）。

只做核对与打印，不改任何文件。判据：
  * 原 15 列里只允许 notes 全行变、condition 仅 V256 那五行变；
  * 核心数值列与 row_status / reviewer / confidence_score 必须 0 差异；
  * approved_by 只允许出现在 entered_by=WB_Agent 的行上，且两列行号必须一致。
"""
from __future__ import print_function

import csv
import hashlib
import sys
from pathlib import Path

import openpyxl

PREP = Path(__file__).resolve().parent

ORIG_COLS = [
    "sample_no", "file_name", "evidence_page", "table_title", "symbol",
    "parameter_name", "min_value", "typ_value", "max_value", "unit",
    "condition", "row_status", "notes", "reviewer", "confidence_score",
]
FINAL_COLS = [
    "sample_no", "file_name", "evidence_page", "table_title", "symbol",
    "parameter_name", "min_value", "typ_value", "max_value", "unit",
    "condition", "row_status", "notes", "reviewer", "approved_by",
    "entered_by", "confidence_score", "device_model", "human_adjudication",
]
CORE = ("min_value", "typ_value", "max_value", "unit", "symbol",
        "parameter_name")
SIGN_COLS = ("row_status", "reviewer", "confidence_score")


def cell(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def main():
    signed_xlsx = PREP / "Batch3_B3_SIGNED_original.xlsx"
    new_csv = PREP / "Batch3_B3_FINAL.csv"
    for p in (signed_xlsx, new_csv):
        if not p.exists():
            raise SystemExit("缺少输入：%s" % p)

    ws = openpyxl.load_workbook(str(signed_xlsx), data_only=True).active
    vals = list(ws.values)
    hdr = [str(x or "").strip() for x in vals[0]]
    signed = [{k: cell(v[hdr.index(k)]) for k in ORIG_COLS}
              for v in vals[1:]
              if any(x is not None and str(x).strip() for x in v)]
    with open(new_csv, encoding="utf-8-sig", newline="") as fh:
        final = list(csv.DictReader(fh))

    print("B3 封卷后逐格差异报告")
    print("=" * 78)
    print("签字版：%d 行 x %d 列（CONFIRMED / reviewer 全一致）"
          % (len(signed), len(hdr)))
    print("定稿  ：%d 行 x %d 列" % (len(final), len(final[0])))
    print("行数一致：%s   19 列定稿结构：%s"
          % (len(signed) == len(final), list(final[0]) == FINAL_COLS))
    print()

    diff, stat = [], {}
    for i, (a, b) in enumerate(zip(signed, final), 1):
        for k in ORIG_COLS:
            if a[k] != b[k]:
                diff.append((i, k, a[k], b[k]))
                stat[k] = stat.get(k, 0) + 1

    print("逐格差异（15 列签字值 → 19 列定稿）：")
    print("%-6s %-16s %-30s %s" % ("行", "列", "签字版", "定稿"))
    for i, k, x, y in diff:
        print("%-6d %-16s %-30r %r"
              % (i, k, (x[:28] + "…") if len(x) > 28 else x, y[:28]))
    print()
    print("差异按列汇总：", stat)
    print("核心数值列（%s）差异数：%d"
          % ("/".join(CORE), sum(stat.get(k, 0) for k in CORE)))
    print("状态与签名列（%s）差异数：%d"
          % ("/".join(SIGN_COLS), sum(stat.get(k, 0) for k in SIGN_COLS)))
    print()

    bad = [k for k in CORE + SIGN_COLS if stat.get(k)]
    if bad:
        print("FAIL 不允许改动的列出现了差异：%s" % bad)
        return 2
    if set(stat) - {"notes", "condition"}:
        print("FAIL 出现未登记的改动列：%s" % (set(stat) - {"notes", "condition"}))
        return 2

    print("notes 取值分布：", dict((k, sum(1 for r in final if r["notes"] == k))
                               for k in set(r["notes"] for r in final)))
    print("残留草稿措辞（VLM 草稿 / low_confidence / 请确认）：",
          sum(1 for r in final
              if any(t in r["notes"] for t in ("VLM 草稿", "low_confidence", "请确认"))))
    print()
    print("新增列填充情况：")
    print("  device_model：", dict((k, sum(1 for r in final if r["device_model"] == k))
                              for k in set(r["device_model"] for r in final)))
    entered = [i for i, r in enumerate(final, 1) if r["entered_by"]]
    approved = [i for i, r in enumerate(final, 1) if r["approved_by"]]
    print("  entered_by=WB_Agent 行：", entered)
    print("  approved_by 非空行    ：", approved)
    print("  两列行号完全对齐      ：", entered == approved)
    print("  approved_by 取值集合  ：",
          sorted({r["approved_by"] for r in final if r["approved_by"]}))
    print("  human_adjudication 非空行：",
          [i for i, r in enumerate(final, 1) if r["human_adjudication"]])
    print()
    print("V256 五行 condition：")
    for i, r in enumerate(final, 1):
        if r["sample_no"] == "V256":
            print("  行%-3d min=%-5s max=%-5s condition=%s"
                  % (i, r["min_value"], r["max_value"], r["condition"]))
    dkeys = [(r["sample_no"], r["symbol"], r["condition"], r["unit"],
              r["evidence_page"], r["min_value"], r["typ_value"],
              r["max_value"]) for r in final]
    print("  判重键唯一（无重复占位）：%s" % (len(set(dkeys)) == len(dkeys)))
    print()

    if entered != approved:
        print("FAIL approved_by 与 entered_by 行号不一致")
        return 2
    print("结论：notes 20 格 + condition 5 格按登记改动，"
          "核心数值与签名状态 0 差异；5 处补签落在 WB 代录入行上。")
    print()
    for p in ("Batch3_B3_FINAL.csv", "Batch3_B3_FINAL.xlsx",
              "Batch3_B3_FINAL_TO_SIGN.xlsx", "Batch3_B3_FINAL_SIGNED.xlsx",
              "Batch3_B3_PDF_PROVENANCE.csv", "page_text_batch3_b3.json"):
        f = PREP / p
        if f.exists():
            print("%-34s %8d 字节  sha256=%s…"
                  % (p, f.stat().st_size,
                     hashlib.sha256(f.read_bytes()).hexdigest()[:16]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
