#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gate 6A 建议样本清单生成器（只读 CSV，不打开 PDF、不跑解析）。

抽样只使用 ds_parse_candidates_350_v2.csv 中已存在的可观测字段：
sample_no / pdf_sha256 / file_path / page_count / evidence_page_no。
所有 proposed_stratum 都是**建议配额占位**，必须经人工 Gold Set 确认后方可生效。
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

STAGE = Path("E:/workspace/icpdf-extractor/runs/stage_a_350")
OUT = STAGE / "gate6_r2"
CAND = STAGE / "ds_parse_candidates_350_v2.csv"

# 与 30 件 LEGACY_PIPELINE_TRIAL 重叠的历史编号（仅作对照，不计成绩）
LEGACY_HAVE = {"V001", "V002", "V003", "V004", "V005", "V006", "V007",
               "V008", "V009", "V010", "V012"}


def page(r):
    return int(r["page_count"])


def by_sha(r):
    """确定性排序键：内容 SHA，不依赖文件名语义，且只用于选样、不用于寻址。"""
    return r["pdf_sha256"]


def main():
    rows = list(csv.DictReader(CAND.open(newline="", encoding="utf-8-sig")))
    assert len(rows) == 350
    by_no = {r["sample_no"]: r for r in rows}
    used: set[str] = set()
    picks: list[dict] = []

    def take(pool, n, stratum, basis, pain, note=""):
        pool = sorted([r for r in pool if r["sample_no"] not in used], key=by_sha)
        for r in pool[:n]:
            used.add(r["sample_no"])
            picks.append({
                "sample_no": r["sample_no"],
                "pdf_sha256": r["pdf_sha256"],
                "file_path": r["file_path"],
                "page_count": r["page_count"],
                "evidence_page_no": r["evidence_page_no"],
                "proposed_stratum": stratum,
                "selection_basis": basis,
                "painpoint_amplification": pain,
                "gold_status": "PROPOSED_PENDING_GOLD_CONFIRMATION",
                "baseline_5": "FALSE",
                "legacy_reference": "TRUE" if r["sample_no"] in LEGACY_HAVE else "FALSE",
                "notes": note,
            })

    # 1. 普通文本型 Datasheet：中等页数、分类器有证据页
    take([r for r in rows if 11 <= page(r) <= 30 and r["evidence_page_no"] != "NONE"],
         6, "普通文本型 Datasheet", "page_count 11-30 且 classifier evidence_page_no 非空，按 SHA 定序取 6",
         "PAIN-07 常规文本完整性")

    # 2. 复杂参数表：较长文档，表格密度预期更高
    take([r for r in rows if 31 <= page(r) <= 100], 6,
         "复杂参数表", "page_count 31-100，按 SHA 定序取 6",
         "PAIN-02 MIN/TYP/MAX 与单位列对齐")

    # 3. 多级表头 / 合并单元格：放大长文档中的多表结构
    take([r for r in rows if page(r) > 100], 5,
         "多级表头 / 合并单元格", "page_count >100 的前 5（按 SHA 定序）",
         "PAIN-01 跨页表格合并 / PAIN-03 多层表头")

    # 4. 多封装或多型号：文件名含双型号线索（仅为线索，不作裁决）
    multi = [r for r in rows if "__" in Path(r["file_path"]).name
             and len(Path(r["file_path"]).name.split("__")[0]) >= 8]
    take(multi, 4, "多封装或多型号", "文件名含 __ 双段命名线索，按 SHA 定序取 4",
         "PAIN-04 多封装列只抽第一列 / PAIN-05 变体参数串用")

    # 5. 跨页表格：其余超长文档
    take([r for r in rows if page(r) > 100], 4,
         "跨页表格", "page_count >100 的随后 4 件（按 SHA 定序）",
         "PAIN-01 跨页表格合并 / PAIN-06 表头跨页丢失")

    # 6. 扫描型或复杂版面：短文档，版面特殊性无法由清单判定，如实标注
    take([r for r in rows if page(r) <= 10], 3,
         "扫描型或复杂版面（待人工确认）",
         "page_count 5-10，仅作版面特殊线索；清单字段无法判定扫描/无文本层",
         "PAIN-08 文本层缺失或乱码 / PAIN-09 特殊符号上划线")

    # 7. 边界或异常文档：分类器证据页 NONE + 疑似 EVM 线索件
    take([r for r in rows if r["evidence_page_no"] == "NONE"], 1,
         "边界或异常文档", "evidence_page_no=NONE，按 SHA 定序取 1",
         "PAIN-10 分类器证据页缺失 / PAIN-11 EVM 板卡混入")
    # 追加指定检查点：V022 疑似 EVM（若尚未被选入）
    if "V022" not in used and "V022" in by_no:
        r = by_no["V022"]
        used.add("V022")
        picks.append({
            "sample_no": "V022", "pdf_sha256": r["pdf_sha256"],
            "file_path": r["file_path"], "page_count": r["page_count"],
            "evidence_page_no": r["evidence_page_no"],
            "proposed_stratum": "边界或异常文档",
            "selection_basis": "Gate 2a 指定检查点：疑似 EVM，检查是否含板载阻容参数",
            "painpoint_amplification": "PAIN-11 EVM 板卡混入 / PAIN-12 板级指南被当成芯片手册",
            "gold_status": "PROPOSED_PENDING_GOLD_CONFIRMATION",
            "baseline_5": "FALSE",
            "legacy_reference": "TRUE" if "V022" in LEGACY_HAVE else "FALSE",
            "notes": "指定检查点，替换须经 Reviewer 批准并记录理由",
        })

    assert len(picks) == 30, len(picks)

    # 5 件基线子集：跨 5 个不同配额各取 1 件，按 sample_no 定序
    seen_strata = set()
    for p in sorted(picks, key=lambda x: x["sample_no"]):
        if p["proposed_stratum"] not in seen_strata and len(seen_strata) < 5:
            seen_strata.add(p["proposed_stratum"])
            p["baseline_5"] = "TRUE"

    fields = ["sample_no", "pdf_sha256", "file_path", "page_count",
              "evidence_page_no", "proposed_stratum", "selection_basis",
              "painpoint_amplification", "gold_status", "baseline_5",
              "legacy_reference", "notes"]
    with (OUT / "GATE6A_SAMPLE_PROPOSAL.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(picks)

    stats = {
        "source_csv": str(CAND),
        "source_csv_sha256": hashlib.sha256(CAND.read_bytes()).hexdigest(),
        "population": 350,
        "proposed_n": len(picks),
        "quota": {
            "普通文本型 Datasheet": 6, "复杂参数表": 6,
            "多级表头 / 合并单元格": 5, "多封装或多型号": 4,
            "跨页表格": 4, "扫描型或复杂版面（待人工确认）": 3,
            "边界或异常文档": 2,
        },
        "quota_note": "第 7 类 2 行 = 1 行 NONE 抽样 + 1 行指定检查点 V022；"
                      "7 类合计 6+6+5+4+4+3+2 = 30，与建议配额一致",
        "baseline_5_count": sum(1 for p in picks if p["baseline_5"] == "TRUE"),
        "baseline_5_samples": [p["sample_no"] for p in picks if p["baseline_5"] == "TRUE"],
        "legacy_overlap_count": sum(1 for p in picks if p["legacy_reference"] == "TRUE"),
        "legacy_overlap_samples": [p["sample_no"] for p in picks if p["legacy_reference"] == "TRUE"],
        "pdf_opened": False,
        "parser_invoked": False,
        "llm_called": False,
        "gold_labels_created": False,
        "type_labels_are_proposals_only": True,
        "addressing_rule": "执行阶段必须严格使用 file_path 原文；SHA 只用于校验，禁止按 SHA 另找路径",
    }
    (OUT / "GATE6A_SAMPLE_STATS.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("[gate6a samples] n=%d baseline5=%d legacy_overlap=%d" % (
        len(picks), stats["baseline_5_count"], stats["legacy_overlap_count"]))
    for p in picks:
        print("  %-5s p%-4s %-28s %s" % (p["sample_no"], p["page_count"],
                                           p["proposed_stratum"][:26],
                                           "BASE" if p["baseline_5"] == "TRUE" else ""))


if __name__ == "__main__":
    main()
