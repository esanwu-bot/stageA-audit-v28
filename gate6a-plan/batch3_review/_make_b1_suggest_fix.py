# -*- coding: utf-8 -*-
"""按 PDF 原文给出 B1 定稿的「建议修正版」，绝不代签。

v1.6 验证器在签字版上跑出 2 个 ERROR + 1 个 SUSPECT，三处都核过 PDF 原文，
确认是数据问题而不是验证器误判：

  行8  V304  p5 / II / Input current / max=-50 mA
        → -50 只在 p4，p5 一个都没有。p4 原文是
          `IIK | Control input clamp current | VIN < 0 | -50 | mA`。
          建议：页码改 4、symbol 改 IIK、参数名/条件按原文、保留 -50。

  行20 V173  p4 / IO / Continuous output current
        → min=`V_O = 0 to V_CC` 不是数值，是 p4 原文里夹在参数名与 ±25 之间的
          **测试条件**。建议：移到 condition，min 留空。

  行22 V345  p4 空 symbol
        → p4 原文该行只有 `Current into any pin except...` 和 -10 / 10 / mA，
          确实没印符号。按 Batch 2 先例填 ACCEPTED_SOURCE_HAS_NO_SYMBOL。

签字纪律
--------
这 3 行被机器改过，**原 reviewer 签名一律撤销**，row_status 退回
DRAFT_AWAITING_HUMAN_CONFIRM。机器无权替人确认，更不能留着签名改数据。
其余 20 行原样不动（含签名）。原签字版文件也不动，供对照。
"""
from __future__ import print_function

import csv
from pathlib import Path

PREP = Path(__file__).resolve().parent
SRC = PREP / "Batch3_B1_CONFIRMED.csv"
OUT = PREP / "Batch3_B1_SUGGESTED_FIX.csv"

ADJ = "ACCEPTED_SOURCE_HAS_NO_SYMBOL"
TAG = "机器按 PDF 原文建议修正，待人确认并重新签字"

# 行号按 CSV 数据行计（从 1 开始），与验证器报告的「行N」相差 1（报告含表头）
FIXES = {
    7: {   # 验证器报告「行8」
        "evidence_page": "4",
        "symbol": "IIK",
        "parameter_name": "Control input clamp current",
        "condition": "VIN < 0",
        "why": "p5 无 -50；p4 原文 IIK / Control input clamp current / VIN < 0 / -50 mA",
    },
    19: {  # 验证器报告「行20」
        "min_value": "",
        "condition": "VO = 0 to VCC",
        "why": "V_O = 0 to V_CC 是测试条件不是 min 值，p4 原文夹在参数名与 ±25 之间",
    },
    21: {  # 验证器报告「行22」
        "human_adjudication": ADJ,
        "why": "p4 该行确实没印符号，按 Batch 2 先例填裁定码（需人签）",
    },
}


def main():
    rows = list(csv.DictReader(open(SRC, encoding="utf-8-sig")))
    cols = list(rows[0].keys())
    changed = []
    for i, r in enumerate(rows, 1):
        if i not in FIXES:
            continue
        fix = FIXES[i]
        before = {k: r.get(k, "") for k in ("evidence_page", "symbol", "parameter_name",
                                            "min_value", "condition", "human_adjudication")}
        for k, v in fix.items():
            if k != "why":
                r[k] = v
        r["notes"] = (r.get("notes", "") + "；" + TAG + "：" + fix["why"]).strip("；")
        # 撤销签名：机器改过的行不能留着人的名字
        r["reviewer"] = ""
        r["row_status"] = "DRAFT_AWAITING_HUMAN_CONFIRM"
        changed.append((i, r["sample_no"], before, fix["why"]))

    with open(OUT, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    print("建议修正版: %s（%d 行）" % (OUT.name, len(rows)))
    for i, sno, before, why in changed:
        print("  行%-3d %-5s %s" % (i, sno, why))
        print("        原: %s" % {k: v for k, v in before.items() if v})
    print("\n撤销签名 %d 行；保留原签名 %d 行" %
          (len(changed), sum(1 for r in rows if r["reviewer"].strip())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
