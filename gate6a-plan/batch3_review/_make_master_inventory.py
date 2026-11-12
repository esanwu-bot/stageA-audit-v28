# -*- coding: utf-8 -*-
"""生成 33 件总清单（Batch3_MASTER_INVENTORY.csv / .txt）。

清单只做汇总与核对，不改任何已封卷文件：
  · 每件的状态、Gold 行数一律从既有 CSV 实算，不手填；
  · 排除理由照录原始记录，另用 reason_class 标注现行三类话术口径，
    避免"为了统一话术而改写历史记录"；
  · 末尾做三条硬断言：33 件各出现一次、行数合计、无未归类项。
"""
from __future__ import print_function

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_CSV = HERE / "Batch3_MASTER_INVENTORY.csv"
OUT_TXT = HERE / "Batch3_MASTER_INVENTORY.txt"

PLAN = HERE / "Batch3_BATCH_PLAN.csv"
B1 = HERE / "Batch3_B1_RESIGNED.csv"
B2 = HERE / "Batch3_B2_FINAL.csv"
B3 = HERE / "Batch3_B3_FINAL.csv"
B4 = HERE / "Batch3_B4_DRAFT.csv"
B2G = HERE / "Batch2_GOLD_v1.csv"
SCAN = HERE / "Batch3_SCAN_MANIFEST.csv"

COLS = ["batch", "sample_no", "file_name", "role", "status",
        "gold_rows", "evidence_source", "reason_class", "note"]

# 现行三类排除话术（Reviewer 2026-11-12 定稿）
CLS_SMD = "版式不支持稳定还原行序"
CLS_SCAN = "电气特性页为扫描图"
CLS_NOLAYER = "全书无文本层"
CLS_NOTABLE = "文档内无标准参数表"

# 已封卷件里记录的原始理由，照录不改写
B3_REASON = {
    "V328": "29 页中 12 页无文本层、前 12 页有连续 4 页空白；无 OCR 能力，无法建立 Gold",
    "V222": "9 页全为封装/板图/卷带资料，0.05 MIN/MAX 是机械尺寸标注，无电气参数表",
}
# 各件在本轮的实情不同，备注不能一句话套三件
B4_NOTE = {
    "V077": "CVDD/RVDD 按 375·456 MHz 分行绑定，DVDD 锚 1.8V I/O；待 PM 点选",
    "V130": "5 行均非白名单参数（MOSFET 击穿/阈值/导通电阻/漏电/栅电荷），待 PM 决定是否纳入",
    "V290": "VIL 两行按温度档绑定（0~70°C / −55~125°C）；II 条件待 PM 定夺",
}
B4_REASON = {
    "V347": "版式不支持稳定还原行序，当前流程无法建立可验证 Gold；需 SMD 专用规则后重评",
    "V041": "电气特性页为扫描图；当前 Gate6A 流程无可用 OCR 取证路径，无法建立可验证 Gold",
}


def rows_of(path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def count_by_sample(rows):
    out = {}
    for r in rows:
        out[r["sample_no"]] = out.get(r["sample_no"], 0) + 1
    return out


def main():
    plan = rows_of(PLAN)
    plan_by = {r["sample_no"]: r for r in plan}
    c1, c2, c3, c4 = (count_by_sample(rows_of(p)) for p in (B1, B2, B3, B4))
    cdone = count_by_sample(rows_of(B2G))
    scan = {r["sample_no"]: r for r in rows_of(SCAN)}

    out = []
    for r in plan:
        sno, batch = r["sample_no"], r["batch"]
        rec = {k: "" for k in COLS}
        rec.update({"batch": batch, "sample_no": sno,
                    "file_name": r["file_name"], "gold_rows": 0})

        if batch == "B1":
            rec.update(role="Gold", status="已定稿",
                       gold_rows=c1.get(sno, 0),
                       evidence_source="Batch3_B1_RESIGNED.csv",
                       note="PM 签字定稿，v1.6 机检通过")
        elif batch == "B2":
            rec.update(role="Gold", status="已定稿",
                       gold_rows=c2.get(sno, 0),
                       evidence_source="Batch3_B2_FINAL.csv",
                       note="PM 签字定稿，v1.6 机检通过")
        elif batch == "B3":
            if sno in c3:
                rec.update(role="Gold", status="已定稿",
                           gold_rows=c3[sno],
                           evidence_source="Batch3_B3_FINAL.csv",
                           note="PM 补签 5 处，已封卷（commit 92f170c）")
            else:
                rec.update(role="Gold", status="EXCLUDED", gold_rows=0,
                           evidence_source="INDEX.md §15",
                           reason_class=CLS_SCAN if sno == "V328" else CLS_NOTABLE,
                           note=B3_REASON.get(sno, "未进 Gold"))
        elif batch == "B4":
            if sno in c4:
                rec.update(role="Gold", status="待签字",
                           gold_rows=c4[sno],
                           evidence_source="Batch3_B4_DRAFT.csv",
                           note=B4_NOTE.get(sno, "待 PM 点选"))
            else:
                rec.update(role="Gold", status="EXCLUDED", gold_rows=0,
                           evidence_source="Batch3_B4_Viewer.html",
                           reason_class=CLS_SMD if sno == "V347" else CLS_SCAN,
                           note=B4_REASON.get(sno, "未进 Gold"))
        elif batch == "SCAN":
            s = scan.get(sno, {})
            rec.update(role="SCAN", status="EXCLUDED", gold_rows=0,
                       evidence_source="Batch3_SCAN_MANIFEST.csv",
                       reason_class=CLS_NOLAYER,
                       note="%s 页，sha256=%s…" % (s.get("page_count", "?"),
                                                  (s.get("sha256") or "")[:16]))
        elif batch == "DONE":
            rec.update(role="Gold", status="已完成", gold_rows=cdone.get(sno, 0),
                       evidence_source="Batch2_GOLD_v1.csv",
                       note="Batch 2 已定稿（24 行 Gold）")
        else:
            rec.update(role="?", status="未归类")
        out.append(rec)

    # 第 33 件：V022 是 Gate 6A 指定检查点，不参与 Gold 分母
    out.append({"batch": "DIAG", "sample_no": "V022",
                "file_name": "CC2500EMK__cc2500.pdf",
                "role": "DIAGNOSTIC_ONLY", "status": "不参与 Gold",
                "gold_rows": 0, "evidence_source": "Gold_Set_v1.1_WORKING.csv",
                "reason_class": "",
                "note": "指定检查点：EVM 板卡手册，仅用于诊断 Parser 是否产出"})

    out.sort(key=lambda r: (r["batch"], r["sample_no"]))

    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(out)

    # ---------------- 硬断言 ----------------
    snos = [r["sample_no"] for r in out]
    assert len(snos) == 33, "件数不是 33：%d" % len(snos)
    assert len(set(snos)) == 33, "样本号重复：%s" % (
        [x for x in set(snos) if snos.count(x) > 1])
    assert not any(r["status"] == "未归类" for r in out), "有未归类项"
    total = sum(int(r["gold_rows"]) for r in out)
    assert total == sum(c1.values()) + sum(c2.values()) + sum(c3.values()) \
        + sum(c4.values()) + sum(cdone.values()), "行数合计与各批 CSV 不符"

    lines = []
    lines.append("Gate 6A · 33 件总清单（Batch 1–4 + SCAN + 诊断件）")
    lines.append("=" * 72)
    cur = None
    for r in out:
        if r["batch"] != cur:
            cur = r["batch"]
            lines.append("")
            lines.append("[%s]" % cur)
        lines.append("  %-5s %-34s %-12s %-4s %s" % (
            r["sample_no"], r["file_name"][:34], r["status"],
            r["gold_rows"] if r["gold_rows"] else "-", r["note"][:40]))
    lines.append("")
    lines.append("-" * 72)
    lines.append("件数：%d（Gold 参与件 %d + SCAN 3 + 诊断件 1）"
                 % (len(out), len(out) - 4))
    lines.append("Gold 行数合计：%d" % total)
    for name, d in (("B1", c1), ("B2", c2), ("B3", c3), ("B4", c4),
                    ("Batch2 Gold v1", cdone)):
        lines.append("  %-16s %2d 件 %3d 行" % (name, len(d), sum(d.values())))
    OUT_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    print("\n".join(lines))
    print()
    print("清单：%s（%d 字节）" % (OUT_CSV.name, OUT_CSV.stat().st_size))
    print("断言：33 件唯一、无未归类、行数合计 %d 与各批 CSV 一致" % total)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
