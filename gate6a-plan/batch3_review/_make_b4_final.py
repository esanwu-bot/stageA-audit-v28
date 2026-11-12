# -*- coding: utf-8 -*-
"""B4 定稿：从 PM 签字的 15 列 xlsx 生成 19 列 FINAL + 溯源 + 离线页文本。

与 B3 同一套口径，但有两条本轮特有的约束：

1. **notes 只清理 VLM 措辞，不动 PM 的裁定信息**：V130 那五行带着
   `【非白名单参数·需 PM 决定是否纳入】` 前缀，那是"这行要不要进 Gold"的依据，
   清成一句话就会丢掉；所以只把前缀后面的模型话术换成
   「人工已核对 PDF 原图并确认」。
2. **approved_by 一律留空**：签字件里没有这一列，PM 也没在这一轮填过。
   B1/B2/B3 的规矩是「只有 WB 代录入的行才由 PM 逐格补签 approved_by」，
   本轮没有代录入，所以不填 —— 不替人签字，也不假装签过。
   签字凭据是签字件本身（文件名 + SHA-256 记录在案）。
"""
from __future__ import print_function

import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import fitz
import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

import _make_b3_final as B3

HERE = Path(__file__).resolve().parent
SIGNED = HERE / "Batch3_B4_ANNOTATED.xlsx"
WORKING = HERE / "Gold_Set_v1.1_WORKING.csv"

OUT_CSV = HERE / "Batch3_B4_FINAL.csv"
OUT_XLSX = HERE / "Batch3_B4_FINAL.xlsx"
OUT_PROV = HERE / "Batch3_B4_PDF_PROVENANCE.csv"
OUT_SIDE = HERE / "page_text_batch3_b4.json"

FINAL_COLS = B3.FINAL_COLS
DEVICE_MODEL = {"V077": "AM1707", "V130": "CSD17505Q5A", "V290": "DS9638"}
SAMPLES = ["V077", "V130", "V290"]
EXPECT_ROWS = 14
FINAL_NOTE = "人工已核对 PDF 原图并确认"

SIGNED_COLS = ["sample_no", "file_name", "evidence_page", "table_title", "symbol",
               "parameter_name", "min_value", "typ_value", "max_value", "unit",
               "condition", "row_status", "notes", "reviewer", "confidence_score"]

# 本轮封卷登记。首次生成时为空 -> guard 返回 write；生成后把哈希填进来再跑一次，
# 必须全部 skip。之后任何字节变化都会被拦下。
SEALED_SHA_B4 = {
    "Batch3_B4_FINAL.csv":
        "2db19c9753f053dda83f4a110fc7099e55797fb22738c3f91b66e03c5c0f551d",
    "Batch3_B4_FINAL.xlsx":
        "972b23f79408da8a568409204db7f25f2ee595e08ef3fc8b602a6cfb6aea86c1",
    "page_text_batch3_b4.json":
        "43e42b3c831b2fcf1df5bb94eb0ca4332937e5af84d6976d671f981315f59aef",
    "Batch3_B4_ANNOTATED.xlsx":
        "cc1b2ae030ee93cecce22e42a9edbbd8888aa514b67c7573d7ca111427cbc7b2",
}

PREFIX_RX = re.compile(r"^【[^】]*】")


def cell_str(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def load_signed(path):
    ws = openpyxl.load_workbook(str(path), data_only=True).active
    vals = list(ws.values)
    hdr = [cell_str(x) for x in vals[0]]
    if hdr != SIGNED_COLS:
        raise SystemExit("签字件表头不是 15 列预期结构：%s" % hdr)
    rows = []
    for r in vals[1:]:
        if not any(x not in (None, "") for x in r):
            continue
        rows.append({k: cell_str(v) for k, v in zip(hdr, r)})
    if len(rows) != EXPECT_ROWS:
        raise SystemExit("签字件行数 %d，与预期 %d 不符" % (len(rows), EXPECT_ROWS))
    got = [r["sample_no"] for r in rows]
    if sorted(set(got)) != sorted(SAMPLES):
        raise SystemExit("签字件样本集合不符：%s" % sorted(set(got)))
    bad = [r["sample_no"] for r in rows if r["row_status"] != "CONFIRMED"]
    if bad:
        raise SystemExit("有行不是 CONFIRMED，不能封卷：%s" % bad)
    who = {r["reviewer"] for r in rows}
    if who != {"wuxiaoxian"}:
        raise SystemExit("签字人不是 PM 本人：%s" % who)
    return rows


def clean_notes(notes):
    """只把模型话术换成人工核对声明，保留 PM 需要看的前缀。"""
    m = PREFIX_RX.match(notes or "")
    prefix = m.group(0) if m else ""
    return prefix + FINAL_NOTE


def disk_info(file_name):
    """按台账的 file_path 找 PDF，实算哈希/页数/字节。"""
    work = {r["sample_no"]: r for r in
            csv.DictReader(open(WORKING, encoding="utf-8-sig"))}
    return work, work


def build_rows(signed, work):
    out, side = [], {}
    for r in signed:
        sno = r["sample_no"]
        meta = work[sno]
        path = Path(meta["file_path"])
        if not path.is_file():
            raise SystemExit("找不到 PDF：%s" % path)
        if path.name != r["file_name"]:
            raise SystemExit("台账文件名与签字件不一致：%s ≠ %s"
                             % (path.name, r["file_name"]))
        raw = path.read_bytes()
        digest = B3.sha(path)
        doc = fitz.open(str(path))
        npages = doc.page_count
        pages = {str(n): doc.load_page(n - 1).get_text("text")
                 for n in (1, int(r["evidence_page"]))}
        doc.close()
        if int(r["evidence_page"]) > npages:
            raise SystemExit("%s 证据页 %s 超过总页数 %d"
                             % (sno, r["evidence_page"], npages))
        node = {"sample_no": sno, "file_name": r["file_name"],
                "device_model": DEVICE_MODEL[sno], "sha256": digest,
                "page_count": npages, "size_bytes": len(raw), "pages": pages}
        side[sno] = node
        row = {k: r.get(k, "") for k in SIGNED_COLS}
        row["notes"] = clean_notes(r["notes"])
        row["approved_by"] = ""      # 不代签
        row["entered_by"] = ""
        row["human_adjudication"] = ""
        row["device_model"] = DEVICE_MODEL[sno]
        out.append(row)
    return out, side


def write_csv(path, rows):
    state = B3.guard_sealed(path, SEALED_SHA_B4)
    if state == "skip":
        return "未改写（封卷件哈希与登记一致，保留原字节）"
    tmp = path.with_name(path.name + ".wb_tmp")
    with open(tmp, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FINAL_COLS)
        w.writeheader()
        w.writerows(rows)
    B3.atomic_replace(tmp, path)
    return "已改写"


def write_xlsx(path, rows):
    state = B3.guard_sealed(path, SEALED_SHA_B4)
    if state == "skip":
        return "未改写（封卷件哈希与登记一致，保留原字节）"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "B4_FINAL"
    ws.append(FINAL_COLS)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="2F5597")
        c.alignment = Alignment(horizontal="center")
    for r in rows:
        ws.append([r.get(k, "") for k in FINAL_COLS])
    for ci, k in enumerate(FINAL_COLS, 1):
        width = {"parameter_name": 46, "notes": 40, "file_name": 40,
                 "human_adjudication": 26, "row_status": 14,
                 "table_title": 30, "condition": 30, "device_model": 16}.get(k, 14)
        ws.column_dimensions[get_column_letter(ci)].width = width
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    tmp = path.with_name(path.name + ".wb_tmp.xlsx")
    wb.save(str(tmp))
    B3.atomic_replace(tmp, path)
    return "已改写"


def write_json(path, obj):
    state = B3.guard_sealed(path, SEALED_SHA_B4)
    if state == "skip":
        return "未改写（封卷件哈希与登记一致，保留原字节）"
    tmp = path.with_name(path.name + ".wb_tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2),
                   encoding="utf-8", newline="\n")
    B3.atomic_replace(tmp, path)
    return "已改写"


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


def main():
    if not SIGNED.exists():
        raise SystemExit("找不到签字件：%s" % SIGNED)
    signed_sha = B3.sha(SIGNED)
    rows_signed = load_signed(SIGNED)
    work, _ = disk_info(None)
    rows, side = build_rows(rows_signed, work)

    for r in rows:
        print("  %-5s p%-3s %-9s %-6s/%-6s/%-6s %-5s cond=%-30s notes=%s" % (
            r["sample_no"], r["evidence_page"], r["symbol"][:9], r["min_value"],
            r["typ_value"], r["max_value"], r["unit"], r["condition"][:30],
            r["notes"][:34]))

    s_csv = write_csv(OUT_CSV, rows)
    s_xlsx = write_xlsx(OUT_XLSX, rows)
    write_prov(OUT_PROV, side)
    obj = {"generated_at": datetime.now().astimezone().isoformat(),
           "source_xlsx": "Batch3_B4_ANNOTATED.xlsx",
           "source_sha256": signed_sha,
           "extractor": "_make_b4_final.py",
           "note": "notes 已清为「%s」，保留【非白名单参数】前缀；"
                   "approved_by 留空，签字凭据为签字件本身" % FINAL_NOTE,
           "samples": side}
    s_side = write_json(OUT_SIDE, obj)

    # ---- 落盘后逐格断言 ----
    vals = list(openpyxl.load_workbook(str(OUT_XLSX), data_only=True).active.values)
    if [str(x or "") for x in vals[0]] != FINAL_COLS:
        raise SystemExit("FINAL.xlsx 表头不是 19 列定稿结构")
    with open(OUT_CSV, encoding="utf-8-sig", newline="") as fh:
        csv2 = list(csv.DictReader(fh))
    if not len(csv2) == len(vals) - 1 == EXPECT_ROWS:
        raise SystemExit("CSV/XLSX 行数不一致：%d / %d" % (len(csv2), len(vals) - 1))
    for ri, r in enumerate(csv2, 1):
        for ci, k in enumerate(FINAL_COLS):
            if str(vals[ri][ci] or "") != (r.get(k) or ""):
                raise SystemExit("xlsx/CSV 不同源：行%d 列%s" % (ri, k))
    if any(r["approved_by"] for r in csv2):
        raise SystemExit("approved_by 非空：本轮不代签，必须为空")
    for r in csv2:
        if not r["notes"].endswith(FINAL_NOTE) or "VLM" in r["notes"]:
            raise SystemExit("notes 未清理干净：%s %r" % (r["sample_no"], r["notes"]))
        if not r["device_model"]:
            raise SystemExit("device_model 为空：%s" % r["sample_no"])

    print()
    print("B4 定稿：%d 行 / %d 样本 / %d 列" % (len(csv2), len(side), len(FINAL_COLS)))
    print("  签字件：%s（SHA-256 %s…）" % (SIGNED.name, signed_sha[:16]))
    print("  device_model：" + "，".join("%s=%s" % kv for kv in DEVICE_MODEL.items()))
    print("  notes：" + "；".join(sorted({r["notes"] for r in csv2})))
    print("  approved_by / entered_by / human_adjudication 全空（不代签）")
    print("  CSV 写入：%s" % s_csv)
    print("  xlsx 写入：%s" % s_xlsx)
    print("  sidecar 写入：%s" % s_side)
    return 0


if __name__ == "__main__":
    sys.exit(main())
