# -*- coding: utf-8 -*-
"""把人工签字的 Batch 3 B1 定稿，变成 v1.6 验证器能吃的输入。

为什么要这层适配
------------------
v1.6 验证器是给 Batch 2 的 24 行 Gold 写的，它要求：
  * CSV 有 `device_model` 列（CSV ↔ sidecar 互校必需，缺字段即 ERROR，不许跳过）
  * `page_text.json` 的 samples 里有每个样本的 file_name / device_model / sha256 / page_count
  * `Batch2_PDF_PROVENANCE.csv` 里四项与 sidecar 完全一致
  * PDF 模式实算 SHA-256 与 sidecar 对

圈选台导出的草稿没有 device_model，也没有这批 PDF 的溯源记录。
**不能为了让报告变绿就关掉这些检查**——那正是我们封了七轮的 fail-open。
所以这里补的都是真实值：型号取 PDF 第 1 页标题行，SHA-256/页数从磁盘原件实算，
页文本从 PDF 逐页抽出。三处写同一份实测数据，PDF 模式再用原件复算一遍哈希。

真源约定（PM 2026-11-12 指定）
------------------------------
**只读 xlsx，不读 csv**。用户从 Excel 另存出来的那份 CSV 是 GBK 编码 + Tab 分隔，
属于 Excel 的导出格式，不是标注真源。xlsx 用 openpyxl 按单元格类型读，
数值不会被 Excel 的显示格式改写。

绝不改动签过字的字段
--------------------
原 15 列逐格照抄，只**追加** `device_model` 与 `human_adjudication` 两列；
后者留空——空符号要不要人工裁定，由人决定，机器不替人签。
"""
from __future__ import print_function

import argparse
import csv
import hashlib
import json
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

import fitz
import openpyxl

PREP = Path(__file__).resolve().parent

# 型号取自各 PDF 第 1 页的标题行，不是文件名猜的。
# V336 封面同时印 DS96F173MQML / DS96F175MQML，按文件名 DS96F173ME_883 选前者。
DEVICE_MODEL = {
    "V173": "SN74AHCT1G04",
    "V199": "CSD18504Q5A",
    "V304": "SN74CB3T3306",
    "V319": "TLV2354",
    "V336": "DS96F173MQML",
    "V345": "DAC63202W",
}

ORIG_COLS = [
    "sample_no", "file_name", "evidence_page", "table_title", "symbol",
    "parameter_name", "min_value", "typ_value", "max_value", "unit",
    "condition", "row_status", "notes", "reviewer", "confidence_score",
]
EXTRA_COLS = ["device_model", "human_adjudication"]


def read_xlsx(path):
    """按单元格读，保留用户签过字的所有值。"""
    wb = openpyxl.load_workbook(str(path), data_only=True)
    ws = wb.active
    raw = list(ws.values)
    hdr = [str(h or "").strip() for h in raw[0]]
    missing = [c for c in ORIG_COLS if c not in hdr]
    if missing:
        raise SystemExit("xlsx 缺列: %s" % missing)
    out = []
    for vals in raw[1:]:
        if not any(v is not None and str(v).strip() for v in vals):
            continue                       # 全空行跳过
        row = {}
        for k in ORIG_COLS:
            v = vals[hdr.index(k)]
            if v is None:
                row[k] = ""
            elif isinstance(v, float) and v.is_integer():
                row[k] = str(int(v))       # Excel 把 20 读成 20.0，别把 .0 写进 CSV
            else:
                row[k] = str(v).strip()
        out.append(row)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", required=True, help="人工签字的 xlsx（唯一真源）")
    ap.add_argument("--pdf-dir", required=True, help="PDF 语料目录")
    ap.add_argument("--out-prefix", default="Batch3_B1")
    args = ap.parse_args()

    src = Path(args.xlsx)
    pdf_dir = Path(args.pdf_dir)
    if not src.exists():
        raise SystemExit("找不到 xlsx: %s" % src)
    if not pdf_dir.is_dir():
        raise SystemExit("找不到 PDF 目录: %s" % pdf_dir)

    rows = read_xlsx(src)
    samples = OrderedDict()
    for r in rows:
        sno = r["sample_no"]
        if sno not in DEVICE_MODEL:
            raise SystemExit("未登记型号: %s（请按 PDF 封面标题行补 DEVICE_MODEL）" % sno)
        r["device_model"] = DEVICE_MODEL[sno]
        r["human_adjudication"] = ""
        samples.setdefault(sno, {"file_name": r["file_name"], "pages": set()})
        samples[sno]["pages"].add(1)                       # 型号核验要封面
        try:
            samples[sno]["pages"].add(int(r["evidence_page"]))
        except ValueError:
            raise SystemExit("%s 有非整数 evidence_page=%r" % (sno, r["evidence_page"]))

    # ---- 从 PDF 原件实算溯源，并抽页文本 ----
    side = OrderedDict()
    prov_rows = []
    for sno, meta in samples.items():
        p = pdf_dir / meta["file_name"]
        if not p.exists():
            raise SystemExit("PDF 缺失: %s" % p)
        raw = p.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        doc = fitz.open(str(p))
        npages = doc.page_count
        pages = {}
        for pno in sorted(meta["pages"]):
            if pno > npages:
                raise SystemExit("%s 的 evidence_page=%d 超出页数 %d" % (sno, pno, npages))
            pages[str(pno)] = doc.load_page(pno - 1).get_text("text")
        doc.close()

        node = OrderedDict([
            ("sample_no", sno),
            ("file_name", meta["file_name"]),
            ("device_model", DEVICE_MODEL[sno]),
            ("sha256", digest),
            ("page_count", npages),
            ("size_bytes", len(raw)),
            ("pages", pages),
        ])
        side[sno] = node
        prov_rows.append({k: node[k] for k in
                          ("sample_no", "file_name", "device_model",
                           "sha256", "page_count", "size_bytes")})
        print("  %-5s %-38s %3d 页  sha256=%s…" %
              (sno, meta["file_name"][:38], npages, digest[:16]))

    out_csv = PREP / ("%s_CONFIRMED.csv" % args.out_prefix)
    out_side = PREP / ("page_text_%s.json" % args.out_prefix.lower())
    out_prov = PREP / ("%s_PDF_PROVENANCE.csv" % args.out_prefix)

    # utf-8-sig：Excel 靠 BOM 判编码；GBK 那份导出不是真源，不要覆写它
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=ORIG_COLS + EXTRA_COLS)
        w.writeheader()
        w.writerows(rows)

    with open(out_prov, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(prov_rows[0]))
        w.writeheader()
        w.writerows(prov_rows)

    obj = OrderedDict([
        ("generated_at", datetime.now().astimezone().isoformat()),
        ("source_xlsx", str(src)),
        ("extractor", "_build_batch3_verify_inputs.py"),
        ("note", "型号取 PDF 第 1 页标题行；sha256/页数从磁盘原件实算；"
                 "页文本逐页抽取。验证器 PDF 模式会再用原件复算哈希。"),
        ("samples", side),
    ])
    out_side.write_text(json.dumps(obj, ensure_ascii=False, indent=2),
                        encoding="utf-8", newline="\n")

    print("\n签字行 %d 行 / %d 样本" % (len(rows), len(samples)))
    print("  %s" % out_csv.name)
    print("  %s" % out_prov.name)
    print("  %s" % out_side.name)
    print("\n复核命令：")
    print("  python validate_annotation.py --csv %s --page-text %s "
          "--provenance %s --pdf-dir <PDF>" %
          (out_csv.name, out_side.name, out_prov.name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
