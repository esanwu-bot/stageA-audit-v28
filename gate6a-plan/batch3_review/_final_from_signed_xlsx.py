# -*- coding: utf-8 -*-
"""从 PM 手工签字后的 Batch3_B4_FINAL.xlsx 重建 B4 定稿的下游产物。

为什么单独写这一版：
  第十三轮 PM 直接在 19 列定稿件上删行并逐格补签 approved_by，
  这份 xlsx 本身就是**签字件本体**。旧链路（ANNOTATED → FINAL）会按
  ANNOTATED 的 14 行重造，把 PM 的删除与签名一起覆盖掉，因此不能再走。

本脚本把已签 xlsx 当唯一事实源，只做「向下游派生」，绝不反向写回：
  · 导出 Batch3_B4_FINAL.csv（19 列，与 xlsx 逐格同源）
  · 重建 page_text_batch3_b4.json（只含仍在 Gold 里的样本）
  · 重建 Batch3_B4_PDF_PROVENANCE.csv（实算 sha256 / 页数 / 字节）

一切以断言收口：签名列、行数、样本集合、列序、CSV↔XLSX 同源。
"""
from __future__ import print_function

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

import fitz
import openpyxl

import _make_b3_final as B3

HERE = Path(__file__).resolve().parent
SIGNED_XLSX = HERE / "Batch3_B4_FINAL.xlsx"
WORKING = HERE / "Gold_Set_v1.1_WORKING.csv"

OUT_CSV = HERE / "Batch3_B4_FINAL.csv"
OUT_PROV = HERE / "Batch3_B4_PDF_PROVENANCE.csv"
OUT_SIDE = HERE / "page_text_batch3_b4.json"

# PM 2026-11-12 15:32:56 保存的签字件。此后只要字节再变，本脚本就停下，
# 不许拿一份来历不明的定稿件往下派生。
SIGNED_SHA = "685caff0da9c568658057c5b2d1a4949abea506589de12846709e78d984bd28e"

EXPECT_ROWS = 8
EXPECT_SAMPLES = {"V077", "V290"}
DROPPED = {"V130"}          # 本轮被 PM 删除的样本，留档说明用
DEVICE_MODEL = {"V077": "AM1707", "V290": "DS9638"}
SIGNER = "wuxiaoxian"


def cell(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def load_signed():
    path = SIGNED_XLSX
    if not path.is_file():
        raise SystemExit("找不到定稿签字件：%s" % path)
    got = B3.sha(path)
    if got != SIGNED_SHA:
        raise SystemExit(
            "定稿签字件字节与登记不一致，拒绝派生：\n  登记 %s\n  实际 %s\n"
            "（若 PM 又改过，请先确认改动内容并把新哈希登记到 SIGNED_SHA）"
            % (SIGNED_SHA, got))
    wb = openpyxl.load_workbook(str(path), data_only=True)
    if len(wb.sheetnames) != 1:
        raise SystemExit("签字件应只有 1 个工作表，实际 %s" % wb.sheetnames)
    ws = wb.active
    vals = list(ws.values)
    hdr = [cell(x) for x in vals[0]]
    if hdr != B3.FINAL_COLS:
        raise SystemExit("签字件不是 19 列定稿结构：%s" % hdr)
    rows = []
    for r in vals[1:]:
        if not any(x not in (None, "") for x in r):
            continue
        rows.append({k: cell(v) for k, v in zip(hdr, r)})
    wb.close()

    if len(rows) != EXPECT_ROWS:
        raise SystemExit("签字件 %d 行，与预期 %d 不符" % (len(rows), EXPECT_ROWS))
    snos = {r["sample_no"] for r in rows}
    if snos != EXPECT_SAMPLES:
        raise SystemExit("签字件样本集合不符：%s（应 %s）"
                         % (sorted(snos), sorted(EXPECT_SAMPLES)))
    if snos & DROPPED:
        raise SystemExit("被 PM 删除的样本又出现在定稿件里：%s" % sorted(snos & DROPPED))

    bad = [r["sample_no"] for r in rows if r["row_status"] != "CONFIRMED"]
    if bad:
        raise SystemExit("有行不是 CONFIRMED，不能定稿：%s" % bad)
    for col in ("reviewer", "approved_by"):
        wrong = [r["sample_no"] for r in rows if r[col] != SIGNER]
        if wrong:
            raise SystemExit("%s 不是 %s 本人签的：%s" % (col, SIGNER, wrong))
    if any(r["entered_by"] for r in rows):
        raise SystemExit("entered_by 非空：本轮 WB 未代录入任何行")

    # 条件完整性：V077 五行与 V290 两行 VIL 必须有 condition；
    # V290 VIH 原表本就没有条件，允许为空，但不是漏填。
    lack = [r["symbol"] for r in rows
            if r["sample_no"] in ("V077",) and not r["condition"].strip()]
    if lack:
        raise SystemExit("V077 有行缺 condition：%s" % lack)
    vil = [r for r in rows if r["sample_no"] == "V290" and r["symbol"] == "VIL"]
    if len(vil) != 2 or not all(r["condition"].strip() for r in vil):
        raise SystemExit("V290 VIL 两行的温度档条件不全：%s"
                         % [r["condition"] for r in vil])
    return rows


def build_side(rows):
    work = {r["sample_no"]: r for r in
            csv.DictReader(open(WORKING, encoding="utf-8-sig"))}
    side = {}
    for sno in sorted({r["sample_no"] for r in rows}):
        meta = work.get(sno)
        if not meta:
            raise SystemExit("台账里找不到 %s" % sno)
        path = Path(meta["file_path"])
        if not path.is_file():
            raise SystemExit("找不到 PDF：%s" % path)
        names = {r["file_name"] for r in rows if r["sample_no"] == sno}
        if len(names) != 1:
            raise SystemExit("%s 的 file_name 在同一件里不一致：%s" % (sno, names))
        fname = names.pop()
        if path.name != fname:
            raise SystemExit("台账文件名与定稿件不一致：%s ≠ %s" % (path.name, fname))
        raw = path.read_bytes()
        pages_needed = sorted({1} | {int(r["evidence_page"])
                                     for r in rows if r["sample_no"] == sno})
        doc = fitz.open(str(path))
        npages = doc.page_count
        if max(pages_needed) > npages:
            raise SystemExit("%s 证据页超过总页数 %d" % (sno, npages))
        pages = {str(n): doc.load_page(n - 1).get_text("text")
                 for n in pages_needed}
        doc.close()
        side[sno] = {"sample_no": sno, "file_name": fname,
                     "device_model": DEVICE_MODEL[sno],
                     "sha256": B3.sha(path), "page_count": npages,
                     "size_bytes": len(raw), "pages": pages}
    return side


def write_csv(path, rows):
    tmp = path.with_name(path.name + ".wb_tmp")
    with open(tmp, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=B3.FINAL_COLS)
        w.writeheader()
        w.writerows(rows)
    data = tmp.read_bytes()
    # 定稿 CSV 沿用既有口径：BOM + CRLF（与 B3/B4 历史定稿一致，Excel 直接双击可读）。
    # 这里做正向校验：每个换行都必须是 CRLF，不允许混入裸 LF。
    if data.count(b"\r\n") != data.count(b"\n"):
        raise SystemExit("CSV 换行不统一（混有裸 LF），拒绝落盘")
    B3.atomic_replace(tmp, path)


def write_prov(path, side):
    rows = [{"sample_no": s, "file_name": v["file_name"],
             "device_model": v["device_model"], "sha256": v["sha256"],
             "page_count": v["page_count"], "size_bytes": v["size_bytes"]}
            for s, v in sorted(side.items())]
    tmp = path.with_name(path.name + ".wb_tmp")
    with open(tmp, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    B3.atomic_replace(tmp, path)


def write_json(path, obj):
    tmp = path.with_name(path.name + ".wb_tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2),
                   encoding="utf-8", newline="\n")
    B3.atomic_replace(tmp, path)


def main():
    rows = load_signed()
    side = build_side(rows)

    write_csv(OUT_CSV, rows)
    write_prov(OUT_PROV, side)
    obj = {"generated_at": datetime.now().astimezone().isoformat(),
           "source_xlsx": SIGNED_XLSX.name,
           "source_sha256": SIGNED_SHA,
           "extractor": "_final_from_signed_xlsx.py",
           "note": ("事实源为 PM 2026-11-12 15:32:56 手工签字定稿件："
                    "删除 V130 全部 5 行与 V290 II 1 行，8 行逐格补签 approved_by"),
           "samples": side}
    write_json(OUT_SIDE, obj)

    # ---- 落盘后逐格断言：CSV 必须与签字 xlsx 同源 ----
    ws = openpyxl.load_workbook(str(SIGNED_XLSX), data_only=True).active
    vals = list(ws.values)
    with open(OUT_CSV, encoding="utf-8-sig", newline="") as fh:
        back = list(csv.DictReader(fh))
    if not len(back) == len(vals) - 1 == EXPECT_ROWS:
        raise SystemExit("CSV/XLSX 行数不一致：%d / %d" % (len(back), len(vals) - 1))
    for ri, r in enumerate(back, 1):
        for ci, k in enumerate(B3.FINAL_COLS):
            if cell(vals[ri][ci]) != (r.get(k) or ""):
                raise SystemExit("CSV 与签字 xlsx 不同源：行%d 列%s" % (ri, k))

    print("B4 定稿（以 PM 签字件为源）：%d 行 / %d 样本 / %d 列"
          % (len(back), len(side), len(B3.FINAL_COLS)))
    print("  签字件：%s（SHA-256 %s…，%d 字节）"
          % (SIGNED_XLSX.name, SIGNED_SHA[:16], SIGNED_XLSX.stat().st_size))
    for sno in sorted(side):
        n = sum(1 for r in back if r["sample_no"] == sno)
        print("    %-5s %-22s %d 行  %s" % (sno, side[sno]["file_name"], n,
                                            side[sno]["device_model"]))
    print("  已由 PM 删除：%s（V130 五行 + V290 II 一行，共 6 行）"
          % "/".join(sorted(DROPPED)) + " + V290 II")
    print("  approved_by：8/8 = %s" % SIGNER)
    print("  CSV    %d 字节  %s" % (OUT_CSV.stat().st_size, B3.sha(OUT_CSV)))
    print("  xlsx   %d 字节  %s（未改写，签字件原字节）"
          % (SIGNED_XLSX.stat().st_size, SIGNED_SHA))
    print("  sidecar %d 字节" % OUT_SIDE.stat().st_size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
