# -*- coding: utf-8 -*-
"""生成 33 件总清单（Batch3_MASTER_INVENTORY.csv / .txt）。

清单只做汇总与核对，不改任何已封卷文件：
  · 每件的状态、Gold 行数一律从既有 CSV 实算，不手填；
  · 排除理由照录原始记录，另用 reason_class 标注现行三类话术口径，
    避免"为了统一话术而改写历史记录"；
  · 分类口径按 Reviewer 2026-11-12 定稿的四分法（此前按 batch 分组，
    导致 V022 诊断件与 V328 排除件混在一张总账里对不上）：
        已定稿 Gold   24 件 = Batch2 6 + B1 6 + B2 6 + B3 4 + B4 2
        排除 Gold 候选 5 件 = V222 / V328 / V041 / V347 / V130
        SCAN 排除      3 件 = S01 / S02 / S03
        诊断件         1 件 = V022
    其中 V130 由 25 件口径移入排除候选：PM 2026-11-12 15:32 在签字定稿件上
    删除了该件全部 5 行（均为非白名单参数），B4 因此由 3 件降为 2 件。
  · 末尾硬断言：四类并集 = 33、各类件数 = 24/5/3/1、互不重叠、
    Gold 内部按批次拆分的件数也与 6+6+6+4+2 一致。
"""
from __future__ import print_function

import csv
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_CSV = HERE / "Batch3_MASTER_INVENTORY.csv"
OUT_TXT = HERE / "Batch3_MASTER_INVENTORY.txt"

PLAN = HERE / "Batch3_BATCH_PLAN.csv"
B1 = HERE / "Batch3_B1_RESIGNED.csv"
B2 = HERE / "Batch3_B2_FINAL.csv"
B3 = HERE / "Batch3_B3_FINAL.csv"
B4 = HERE / "Batch3_B4_FINAL.csv"
B2G = HERE / "Batch2_GOLD_v1.csv"
SCAN = HERE / "Batch3_SCAN_MANIFEST.csv"

COLS = ["category", "batch", "sample_no", "file_name", "role", "status",
        "gold_rows", "evidence_source", "reason_class", "note"]

# 四个分类（顺序即打印顺序，也是断言比对顺序）
CAT_GOLD = "已定稿 Gold"
CAT_EXCL = "排除 Gold 候选"
CAT_SCAN = "SCAN 排除"
CAT_DIAG = "诊断件"
CATEGORIES = [CAT_GOLD, CAT_EXCL, CAT_SCAN, CAT_DIAG]
EXPECT_COUNT = {CAT_GOLD: 24, CAT_EXCL: 5, CAT_SCAN: 3, CAT_DIAG: 1}
# Gold 内部按批次拆分，Reviewer 给的口径是 6+6+6+4+3；
# 第十三轮 PM 在签字件上删掉 V130 全部行，B4 由 3 件降为 2 件 → 6+6+6+4+2。
EXPECT_GOLD_BATCH = {"Batch2": 6, "B1": 6, "B2": 6, "B3": 4, "B4": 2}
# 排除候选必须是这五件，SCAN 必须是这三件 —— 写死以防分类又漂
EXPECT_EXCL = {"V222", "V328", "V041", "V347", "V130"}
EXPECT_SCAN = {"S01", "S02", "S03"}
EXPECT_DIAG = {"V022"}

# 现行三类排除话术（Reviewer 2026-11-12 定稿）
CLS_SMD = "版式不支持稳定还原行序"
CLS_SCAN = "电气特性页为扫描图"
CLS_NOLAYER = "全书无文本层"
CLS_NOTABLE = "文档内无标准参数表"
# 第四类：不是技术做不到，而是 PM 裁定不纳入（属范围决定，与上面三类不同）。
# 单列出来，免得跟「流程无能力」混为一谈，也免得下次又被当成漏件重提。
CLS_PM_CUT = "PM 裁定不纳入（非白名单参数，签字件已删除该件全部行）"

# 已封卷件里记录的原始理由，照录不改写
B3_REASON = {
    "V328": "29 页中 12 页无文本层、前 12 页有连续 4 页空白；无 OCR 能力，无法建立 Gold",
    "V222": "9 页全为封装/板图/卷带资料，0.05 MIN/MAX 是机械尺寸标注，无电气参数表",
}
# 各件在本轮的实情不同，备注不能一句话套三件。
# 注意：V130 的 5 条 condition 与 V290 的 II 条件是 WB 按原图补录、PM 尚未复核，
# 所以这里不能再写"已封卷"——封卷登记已撤销，等补签后重新登记。
B4_NOTE = {
    "V077": ("5 行；CVDD/RVDD 按 375·456 MHz 分行绑定，DVDD 锚 1.8V I/O；"
             "PM 2026-11-12 15:32 逐格补签 approved_by"),
    "V290": ("3 行（VIH / VIL×2）；VIL 两行按温度档绑定；"
             "II 一行由 PM 在签字件上删除，VIH 原表本就无条件是事实"),
}
B4_REASON = {
    "V347": "版式不支持稳定还原行序，当前流程无法建立可验证 Gold；需 SMD 专用规则后重评",
    "V041": "电气特性页为扫描图；当前 Gate6A 流程无可用 OCR 取证路径，无法建立可验证 Gold",
    "V130": ("PM 2026-11-12 15:32 在签字定稿件上删除该件全部 5 行："
             "BVDSS / VGS(th) / RDS(on) / IDSS / IGSS 均为非白名单参数，不作 Gold 背书"),
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
            rec.update(category=CAT_GOLD, role="Gold", status="已定稿",
                       gold_rows=c1.get(sno, 0),
                       evidence_source="Batch3_B1_RESIGNED.csv",
                       note="PM 签字定稿，v1.6 机检通过")
        elif batch == "B2":
            rec.update(category=CAT_GOLD, role="Gold", status="已定稿",
                       gold_rows=c2.get(sno, 0),
                       evidence_source="Batch3_B2_FINAL.csv",
                       note="PM 签字定稿，v1.6 机检通过")
        elif batch == "B3":
            if sno in c3:
                rec.update(category=CAT_GOLD, role="Gold", status="已定稿",
                           gold_rows=c3[sno],
                           evidence_source="Batch3_B3_FINAL.csv",
                           note="PM 补签 5 处，已封卷（commit 92f170c）")
            else:
                rec.update(category=CAT_EXCL, role="Gold", status="EXCLUDED",
                           gold_rows=0,
                           evidence_source="INDEX.md §15",
                           reason_class=CLS_SCAN if sno == "V328" else CLS_NOTABLE,
                           note=B3_REASON.get(sno, "未进 Gold"))
        elif batch == "B4":
            if sno in c4:
                rec.update(category=CAT_GOLD, role="Gold", status="已定稿",
                           gold_rows=c4[sno],
                           evidence_source="Batch3_B4_FINAL.csv",
                           note=B4_NOTE.get(sno, "PM 已签字，v1.6 机检 OK=14"))
            else:
                rec.update(category=CAT_EXCL, role="Gold", status="EXCLUDED",
                           gold_rows=0,
                           evidence_source="Batch3_B4_Viewer.html"
                                           if sno != "V130"
                                           else "Batch3_B4_FINAL.xlsx",
                           reason_class=(CLS_SMD if sno == "V347"
                                         else CLS_PM_CUT if sno == "V130"
                                         else CLS_SCAN),
                           note=B4_REASON.get(sno, "未进 Gold"))
        elif batch == "SCAN":
            s = scan.get(sno, {})
            rec.update(category=CAT_SCAN, role="SCAN", status="EXCLUDED",
                       gold_rows=0,
                       evidence_source="Batch3_SCAN_MANIFEST.csv",
                       reason_class=CLS_NOLAYER,
                       note="%s 页，sha256=%s…" % (s.get("page_count", "?"),
                                                  (s.get("sha256") or "")[:16]))
        elif batch == "DONE":
            rec.update(category=CAT_GOLD, role="Gold", status="已完成",
                       gold_rows=cdone.get(sno, 0),
                       evidence_source="Batch2_GOLD_v1.csv",
                       note="Batch 2 已定稿（24 行 Gold）")
        else:
            rec.update(category="", role="?", status="未归类")
        out.append(rec)

    # 第 33 件：V022 是 Gate 6A 指定检查点，不参与 Gold 分母
    out.append({"category": CAT_DIAG, "batch": "DIAG", "sample_no": "V022",
                "file_name": "CC2500EMK__cc2500.pdf",
                "role": "DIAGNOSTIC_ONLY", "status": "不参与 Gold",
                "gold_rows": 0, "evidence_source": "Gold_Set_v1.1_WORKING.csv",
                "reason_class": "",
                "note": "指定检查点：EVM 板卡手册，仅用于诊断 Parser 是否产出"})

    out.sort(key=lambda r: (CATEGORIES.index(r["category"])
                            if r["category"] in CATEGORIES else 99,
                            r["batch"], r["sample_no"]))

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

    # 断言 1：每件都必须落在四个分类之一，四类并集 = 全表
    bad_cat = [r["sample_no"] for r in out if r["category"] not in CATEGORIES]
    assert not bad_cat, "存在四类之外的分类：%s" % bad_cat
    cnt = Counter(r["category"] for r in out)
    assert set(cnt) == set(CATEGORIES), "四类没有同时出现：%s" % dict(cnt)
    for cat in CATEGORIES:
        assert cnt[cat] == EXPECT_COUNT[cat], (
            "分类「%s」件数 %d，与预期 %d 不符"
            % (cat, cnt[cat], EXPECT_COUNT[cat]))
    assert sum(cnt.values()) == 33, "四类合计不是 33：%d" % sum(cnt.values())

    # 断言 2：互不重叠（每件只能有一个分类，靠唯一性 + 单值字段保证，
    # 这里显式再核一遍四类的样本集合两两无交集）
    sets = {c: {r["sample_no"] for r in out if r["category"] == c}
            for c in CATEGORIES}
    for i, a in enumerate(CATEGORIES):
        for b in CATEGORIES[i + 1:]:
            dup = sets[a] & sets[b]
            assert not dup, "分类「%s」与「%s」重叠：%s" % (a, b, sorted(dup))

    # 断言 3：具体到件，分类不能漂
    assert sets[CAT_EXCL] == EXPECT_EXCL, "排除候选集合不符：%s" % sorted(sets[CAT_EXCL])
    assert sets[CAT_SCAN] == EXPECT_SCAN, "SCAN 排除集合不符：%s" % sorted(sets[CAT_SCAN])
    assert sets[CAT_DIAG] == EXPECT_DIAG, "诊断件集合不符：%s" % sorted(sets[CAT_DIAG])

    # 断言 4：Gold 内部按批次 6+6+6+4+3
    gold_batch = Counter(("Batch2" if r["batch"] == "DONE" else r["batch"])
                         for r in out if r["category"] == CAT_GOLD)
    for b, n in EXPECT_GOLD_BATCH.items():
        assert gold_batch.get(b, 0) == n, (
            "Gold 里 %s 批次 %d 件，与预期 %d 不符" % (b, gold_batch.get(b, 0), n))

    total = sum(int(r["gold_rows"]) for r in out)
    assert total == sum(c1.values()) + sum(c2.values()) + sum(c3.values()) \
        + sum(c4.values()) + sum(cdone.values()), "行数合计与各批 CSV 不符"

    lines = []
    lines.append("Gate 6A · 33 件总清单（四分类口径）")
    lines.append("=" * 76)
    for cat in CATEGORIES:
        lines.append("")
        lines.append("【%s】%d 件" % (cat, cnt[cat]))
        lines.append("-" * 76)
        for r in out:
            if r["category"] != cat:
                continue
            lines.append("  %-5s %-32s %-8s %-4s %s" % (
                r["sample_no"], r["file_name"][:32], r["status"],
                r["gold_rows"] if r["gold_rows"] else "-", r["note"][:38]))
    lines.append("")
    lines.append("-" * 76)
    lines.append("合计：%d 件 = %s" % (
        sum(cnt.values()), " + ".join("%s %d" % (c, cnt[c]) for c in CATEGORIES)))
    lines.append("Gold 内部批次：%s（合计 %d）" % (
        " + ".join("%s %d" % (b, gold_batch[b]) for b in
                   ["Batch2", "B1", "B2", "B3", "B4"]), cnt[CAT_GOLD]))
    lines.append("Gold 行数合计：%d" % total)
    for name, d in (("B1", c1), ("B2", c2), ("B3", c3), ("B4", c4),
                    ("Batch2 Gold v1", cdone)):
        lines.append("  %-16s %2d 件 %3d 行" % (name, len(d), sum(d.values())))
    OUT_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    print("\n".join(lines))
    print()
    print("清单：%s（%d 字节）" % (OUT_CSV.name, OUT_CSV.stat().st_size))
    print("断言：四类并集 33、24/5/3/1、互不重叠、Gold 批次 6+6+6+4+2、"
          "行数合计 %d 与各批 CSV 一致" % total)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
