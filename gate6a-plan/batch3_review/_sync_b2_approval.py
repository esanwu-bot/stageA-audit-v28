# -*- coding: utf-8 -*-
"""封卷前：把 PM 在 Batch3_B2_FINAL.xlsx 上补签的授权链同步进 CSV。

真源纪律
--------
PM 2026-11-12 09:48 在 Excel 里直接编辑了 Batch3_B2_FINAL.xlsx 的
approved_by 列。该 xlsx 是授权链唯一真源；同目录 CSV 是派生产物。
本脚本绝不写回 xlsx，绝不增删人工签名，只做：

  1. 把签字版逐格未改地留痕为 Batch3_B2_FINAL_SIGNED_approval.xlsx；
  2. 把封卷前无签名版留痕为 Batch3_B2_FINAL_pre_approval.xlsx；
  3. 按签字版 19 列重建 CSV（UTF-8 BOM / LF），逐格断言 CSV == XLSX；
  4. 断言相对无签名版只有 approved_by 一列有变化，其余 18 列
     （含 min/max/typ、reviewer、symbol、condition、notes）一字未动；
  5. 断言每个非空 approved_by 都只能取 wuxiaoxian；
  6. 如实打印 approved_by 与 entered_by 的对齐情况，不做任何自动补齐。

不写 sidecar / provenance / 页文本，避免仅因授权链签字就扰动溯源哈希。
"""
from __future__ import print_function

import csv
import hashlib
import os
import shutil
from pathlib import Path

import openpyxl

PREP = Path(__file__).resolve().parent
SIGNED = PREP / "Batch3_B2_FINAL.xlsx"
SNAPSHOT = PREP / "Batch3_B2_FINAL_SIGNED_approval.xlsx"
PRE_APPROVAL = PREP / "Batch3_B2_FINAL_pre_approval.xlsx"
AUDIT_PREV = Path(
    r"E:\workspace\github\stageA-audit-v28\gate6a-plan\batch3_review"
    r"\Batch3_B2_FINAL.xlsx")
OUT_CSV = PREP / "Batch3_B2_FINAL.csv"
REVIEWER = "wuxiaoxian"

FINAL_COLS = [
    "sample_no", "file_name", "evidence_page", "table_title", "symbol",
    "parameter_name", "min_value", "typ_value", "max_value", "unit",
    "condition", "row_status", "notes", "reviewer", "approved_by",
    "entered_by", "confidence_score", "device_model", "human_adjudication",
]


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cell(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def read_xlsx(path):
    ws = openpyxl.load_workbook(str(path), data_only=True, read_only=True).active
    vals = list(ws.values)
    hdr = [str(x or "").strip() for x in vals[0]]
    assert hdr == FINAL_COLS, "%s 表头与 19 列定稿不一致：%r" % (path.name, hdr)
    rows = []
    for v in vals[1:]:
        if not any(x is not None and str(x).strip() for x in v):
            continue
        rows.append({k: cell(v[i]) for i, k in enumerate(FINAL_COLS)})
    assert len(rows) == 30, "%s 应为 30 行，实际 %d" % (path.name, len(rows))
    return rows


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert rows and list(rows[0]) == FINAL_COLS, "%s 表头异常" % path.name
    return [{k: (r.get(k) or "") for k in FINAL_COLS} for r in rows]


def atomic_copy(src, dst):
    tmp = dst.with_name(dst.name + ".wb_tmp")
    shutil.copy2(str(src), str(tmp))
    try:
        os.replace(str(tmp), str(dst))
    except PermissionError:
        if dst.exists() and sha(dst) == sha(src):
            tmp.unlink()
            return "跳过（目标被占用，字节一致）"
        raise SystemExit("目标被占用且内容不一致，拒绝静默跳过：%s" % dst)
    finally:
        if tmp.exists():
            tmp.unlink()
    return "留痕"


def main():
    for p in (SIGNED, AUDIT_PREV, OUT_CSV):
        if not p.is_file():
            raise SystemExit("缺少输入文件：%s" % p)

    print("签字版 xlsx : %s  %d 字节  sha256=%s" %
          (SIGNED.name, SIGNED.stat().st_size, sha(SIGNED)[:16]))
    print("封卷前 xlsx : %s  %d 字节  sha256=%s" %
          (AUDIT_PREV.name, AUDIT_PREV.stat().st_size, sha(AUDIT_PREV)[:16]))

    signed = read_xlsx(SIGNED)
    prev = read_xlsx(AUDIT_PREV)
    prev_csv = read_csv(OUT_CSV)

    # 封卷前 CSV 与封卷前 xlsx 必须同源（第五轮状态自证）
    assert prev == prev_csv, "第五轮 CSV 与 xlsx 不同源，拒绝继续"
    assert not any(r["approved_by"] for r in prev), \
        "封卷前版本应无 approved_by，现场与预期不符"

    # 授权链之外 18 列逐格未变
    diffs = []
    for i, (a, b) in enumerate(zip(signed, prev), 1):
        for k in FINAL_COLS:
            if a[k] != b[k]:
                diffs.append((i, k, b[k], a[k]))
    changed_cols = {d[1] for d in diffs}
    assert changed_cols <= {"approved_by"}, \
        "除 approved_by 外还有列被改动：%s" % sorted(changed_cols)
    assert changed_cols == {"approved_by"}, \
        "签字版与封卷前版本完全相同，没有检测到人工签字"
    assert len(diffs) == 7, "approved_by 变化应为 7 处，实际 %d" % len(diffs)

    bad = [(i, v) for i, a, b, v in diffs if v != REVIEWER]
    assert not bad, "approved_by 出现非 PM 本人签名：%r" % bad
    assert all(r["reviewer"] == REVIEWER for r in signed)
    assert all(r["row_status"] == "CONFIRMED" for r in signed)
    assert not any(r["human_adjudication"] for r in signed)
    assert not any(not r["symbol"].strip() for r in signed)

    # 留痕（签字版逐格未改；封卷前版本供 Reviewer 反查差异）
    print("\n留痕：%s %s" % (SNAPSHOT.name, atomic_copy(SIGNED, SNAPSHOT)))
    print("留痕：%s %s" % (PRE_APPROVAL.name, atomic_copy(AUDIT_PREV, PRE_APPROVAL)))
    assert sha(SNAPSHOT) == sha(SIGNED), "签字版留痕字节不一致"
    assert sha(PRE_APPROVAL) == sha(AUDIT_PREV), "封卷前留痕字节不一致"

    # 重建 CSV，逐格断言与签字版 xlsx 同源
    tmp = OUT_CSV.with_name(OUT_CSV.name + ".wb_tmp")
    with open(tmp, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FINAL_COLS)
        w.writeheader()
        w.writerows(signed)
    try:
        os.replace(str(tmp), str(OUT_CSV))
    except PermissionError:
        raise SystemExit("CSV 被占用，请关闭 Excel/预览后重跑：%s" % OUT_CSV)
    finally:
        if tmp.exists():
            tmp.unlink()
    assert read_csv(OUT_CSV) == signed, "CSV 与签字版 xlsx 不同源"

    print("\n--- approved_by 差异（封卷前 -> PM 签字版）---")
    for i, k, old, new in diffs:
        print("  数据行%-3d %-5s %-30s | %r -> %r" %
              (i, signed[i - 1]["sample_no"], signed[i - 1]["symbol"][:30],
               old, new))

    ap = {i for i, r in enumerate(signed, 1) if r["approved_by"]}
    eb = {i for i, r in enumerate(signed, 1) if r["entered_by"]}
    print("\n--- 授权链对齐情况（如实打印，不自动补齐）---")
    print("  approved_by 非空行（%d）：%s" % (len(ap), sorted(ap)))
    print("  entered_by=WB_Agent 行（%d）：%s" % (len(eb), sorted(eb)))
    print("  两者交集（%d）：%s" % (len(ap & eb), sorted(ap & eb)))
    print("  已签 approved_by 但非代录入行（%d）：%s" %
          (len(ap - eb), sorted(ap - eb)))
    print("  代录入但缺 approved_by（%d）：%s" %
          (len(eb - ap), sorted(eb - ap)))
    for i in sorted(eb - ap):
        r = signed[i - 1]
        print("    行%-3d %-5s symbol=%r" % (i, r["sample_no"], r["symbol"]))
    print("\n结论：CSV 已与 PM 签字版 xlsx 同源；"
          "除 7 处 approved_by 外 18 列逐格未变；xlsx 未被本脚本写回。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
