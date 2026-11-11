# -*- coding: utf-8 -*-
"""从扫描结果中按确定性规则选出 Gate 6A 补充样本（PAIN-08 覆盖）。

选样规则（与 GATE6A_PLAN.md §1.5「层内按 pdf_sha256 确定性升序取前 N 件，
可盲复现」保持同一口径，不另立标准）：

  1. 先按 pdf_sha256 去重（同一文档常以多个料号命名重复入库，
     不去重会把同一份扫描件的多个别名当成多个样本，虚增覆盖度）。
  2. 按 page_count 分三档：1-10 / 11-30 / 31-100。
  3. 每档内按 pdf_sha256 十六进制升序排序，取第一件。
  4. 三档各出 1 件，合计 3 件。

为什么分档而不是只取最短：页数决定了"能不能承载一张参数表"。
只取最短件会得到 1 页的封面扫描，无法检验任何表格行为，
PAIN-08 就退化成"打开就失败"的空测。

产出：
  IMAGE_ONLY_CANDIDATES.csv  全部去重后的无文本层候选（62 件），供 Reviewer 复核
  selected_supplementary.json 最终 3 件 + 选样规则 + 排除理由
"""
from __future__ import print_function

import csv
import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
BANDS = [("BAND_A_1_10", 1, 10), ("BAND_B_11_30", 11, 30), ("BAND_C_31_100", 31, 100)]


def main():
    summary = json.loads((OUT / "scan_summary.json").read_text(encoding="utf-8"))
    cands = summary["candidates"]

    # 1. 按 sha256 去重，保留文件名字典序最小者作为代表
    by = {}
    aliases = {}
    for r in cands:
        sha = r["sha256"]
        prev = by.get(sha)
        if prev is None or r["name"] < prev["name"]:
            by[sha] = r
        aliases.setdefault(sha, []).append(r["name"])
    uniq = sorted(by.values(), key=lambda r: r["sha256"])

    # 全部去重候选写入 CSV
    cols = ["sha256", "representative_name", "alias_count", "alias_names",
            "page_count", "size_bytes", "page1_chars", "sample_pages",
            "sample_chars", "path", "selected_as"]
    picks = {}
    for band, lo, hi in BANDS:
        sub = [r for r in uniq if lo <= r["page_count"] <= hi]
        sub.sort(key=lambda r: r["sha256"])
        if sub:
            picks[sub[0]["sha256"]] = band

    with open(OUT / "IMAGE_ONLY_CANDIDATES.csv", "w",
              encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in uniq:
            w.writerow({
                "sha256": r["sha256"],
                "representative_name": r["name"],
                "alias_count": len(aliases[r["sha256"]]),
                "alias_names": ";".join(sorted(aliases[r["sha256"]])),
                "page_count": r["page_count"],
                "size_bytes": r["size_bytes"],
                "page1_chars": r["page1_chars"],
                "sample_pages": r["sample_pages"],
                "sample_chars": r["sample_chars"],
                "path": r["path"],
                "selected_as": picks.get(r["sha256"], ""),
            })

    order = [b[0] for b in BANDS]
    chosen = sorted((r for r in uniq if r["sha256"] in picks),
                    key=lambda r: order.index(picks[r["sha256"]]))
    out = {
        "purpose": "PAIN-08（文本层缺失或乱码）覆盖：350 池内无真扫描件，需池外补充",
        "stratum": "扫描件（无文本层）",
        "selection_rule": [
            "按 pdf_sha256 去重（同一文档多料号别名视为一件）",
            "按 page_count 分档 1-10 / 11-30 / 31-100",
            "档内按 pdf_sha256 十六进制升序取首件",
            "三档各 1 件，合计 3 件",
        ],
        "scan_source": {
            "corpus": summary["corpus"],
            "total_pdf": summary["total_pdf"],
            "image_only_found": len(cands),
            "unique_after_dedup": len(uniq),
            "text_threshold_chars": summary["text_threshold_chars"],
            "sample_pages_cap": summary["sample_pages_cap"],
            "elapsed_sec": summary["elapsed_sec"],
        },
        "selected": [
            {
                "sample_no": "S%02d" % (i + 1),
                "band": picks[r["sha256"]],
                "stratum": "扫描件（无文本层）",
                "sha256": r["sha256"],
                "file_name": r["name"],
                "file_path": r["path"],
                "page_count": r["page_count"],
                "size_bytes": r["size_bytes"],
                "page1_text_chars": r["page1_chars"],
                "sampled_pages": r["sample_pages"],
                "sampled_chars": r["sample_chars"],
                "alias_count": len(aliases[r["sha256"]]),
                "in_350_pool": False,
                "in_d_prime_change_set": False,
            }
            for i, r in enumerate(chosen)
        ],
        "constraint_break_notice":
            "这 3 件位于 350 池之外，突破了「从 350 池抽样」的约束。"
            "依 GATE6A_PLAN.md §1.4 缺口 1 选项 2，Reviewer 已于 2026-11-11 批准"
            "将其正式列入 Gold Set「扫描件（无文本层）」层并计入分母；"
            "计入仍以 status = CONFIRMED 为前提（未 CONFIRMED 不进任何分母）。",
        "approval": {
            "approved_by": "Reviewer",
            "approved_at": "2026-11-11",
            "scope": "列入 Gold Set 扫描件层，准备计入分母",
            "plan_ref": "GATE6A_PLAN.md v1.1 §1.3 / §1.4 缺口 1",
        },
        "parser_invoked": False,
        "llm_called": False,
    }
    (OUT / "selected_supplementary.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")

    print("unique_candidates=%d selected=%d" % (len(uniq), len(chosen)))
    for s in out["selected"]:
        print("  %s %-10s %-42s pages=%2d" % (
            s["sample_no"], s["band"], s["file_name"], s["page_count"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
