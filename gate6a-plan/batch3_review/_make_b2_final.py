# -*- coding: utf-8 -*-
"""B2 最终定稿 + v1.6 验证输入三件套（唯一真源：PM 签字的 xlsx）。

PM 2026-11-12 裁定
------------------
1. 过期草稿 notes 一律改成「人工已核对 PDF 原图并确认」；
   绝不能改 min/max/typ 核心数值和签名。
2. V003 的 VDDSHV5 condition 保留 `1.8V Operation`（p106 原文确有独立一行），
   不强改成 `VDD=1.8V`。
3. 机检要求 OK=30 / ERROR=0。

真源纪律
--------
只读 `Batch3_B2_ANNOTATED (1).xlsx`，同目录 Excel 另存的 .csv 不是真源。
原 15 列逐格照抄（仅 notes 按裁定改写），另追加 4 列：
  approved_by / entered_by / device_model / human_adjudication
与 B1 最终定稿的 19 列结构完全对齐。

7 行符号回填（Reviewer 第五轮，不再用裁定码）
--------------------------------------------
签字版里 V320 两行、V242 五行的 symbol 为空，符号被 VLM 塞进了 condition。
Reviewer 指出这不是「源头没有符号」，用 ACCEPTED_SOURCE_HAS_NO_SYMBOL
放行属于语义错配。现回到 PDF 原图把符号逐字提取回 symbol 列：

  V320 p12（DAC3482IRKDR__slas748f.pdf）
    行 11 `DACVDD, DIGVDD, CLKVDD`、行 24 `AVDD, PLLAVDD`
    表标题下方行 7 是全表条件 `over operating free-air temperature range
    (unless otherwise noted)(1)`，回填进 condition（去掉脚注编号）。
  V242 p6（ADS131B26QPHPRQ1__ads131b26-q1.pdf）
    行 7/11/14/17/20 分别是 `APWR to AGND` / `DPWR to DGND` /
    `AGND, AGNDy to DGND` / `AVDD to AGND` / `IOVDD to DGND`。
    该表只有 `see (1)` 脚注引用，没有具体测试条件，condition 留空。

保留原表的逗号 / `to` 写法，不改成 `符号1; 符号2`：分号不在 PDF 原文里，
会让 v1.6 的 check_symbol() 找不到符号。每个回填值都做
`nos(symbol) in nos(页文本)` 原文断言，非空 condition 同样断言。

授权链（封卷状态）：这 7 行由 WB 按原文回填，entered_by=WB_Agent；
PM 2026-11-12 10:05 授权并已在 Batch3_B2_FINAL_TO_SIGN.xlsx 的 7 个红格
补签 approved_by=wuxiaoxian。本脚本重跑时会从现有 Batch3_B2_FINAL.xlsx
读回这 7 处人工签名并原样保留，绝不代填、绝不自动补齐；
其余 23 行保持空白。reviewer 仍是 PM 对整表的签字，
human_adjudication 全部清空。

file_name 简写的处置（不改签字真源一格）
--------------------------------------
签字版里 3 件的 file_name 是简写，语料目录没有同名文件：
  ADC12QJ1600ALREP.pdf      → ADC12QJ1600ALREP__adc12qj1600-ep.pdf
  ADS54J40IRMPT.pdf         → ADS54J40IRMPT__ads54j40.pdf
  ADS131B26-Q1.pdf          → ADS131B26QPHPRQ1__ads131b26-q1.pdf
不改写 CSV，改为在 b2_pdfs/ 下按 CSV 原名建硬链接指向同一份 PDF 字节。
PDF 模式据此实算哈希，离线模式用 sidecar，三处 file_name 仍是签字原值。

产物
----
  Batch3_B2_SIGNED_original.xlsx        PM 签字原件副本（逐格未改）
  Batch3_B2_FINAL.csv / .xlsx           19 列最终定稿（验证器直接吃）
  Batch3_B2_notes_before_cleanup.txt    30 行原始 notes 留痕
  page_text_batch3_b2.json              页文本 + 溯源期望值
  Batch3_B2_PDF_PROVENANCE.csv          第三方溯源表
  b2_pdfs/                              6 份硬链接（本地验证环境，不入审计包）
"""
from __future__ import print_function

import argparse
import csv
import hashlib
import json
import os
import shutil
from collections import Counter, OrderedDict
from datetime import datetime
from pathlib import Path

import fitz
import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

PREP = Path(__file__).resolve().parent
PDF_DIR = Path(r"E:\workspace\IcPdfParser\data\pdfs")
LINK_DIR = PREP / "b2_pdfs"
SRC_XLSX = Path(r"D:\Documents\Downloads\Batch3_B2_ANNOTATED (1).xlsx")

OUT_CSV = PREP / "Batch3_B2_FINAL.csv"
OUT_XLSX = PREP / "Batch3_B2_FINAL.xlsx"
SIGNED_COPY = PREP / "Batch3_B2_SIGNED_original.xlsx"
NOTES_BEFORE = PREP / "Batch3_B2_notes_before_cleanup.txt"
OUT_SIDE = PREP / "page_text_batch3_b2.json"
OUT_PROV = PREP / "Batch3_B2_PDF_PROVENANCE.csv"

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

# 型号取 PDF 第 1 页封面原文；V003 封面只印族名 AM243x，另有一行
# "AM2434, AM2432, AM2431"，故取能核到的 AM2431。
DEVICE_MODEL = {
    "V038": "ADC12QJ1600-EP",
    "V320": "DAC3482",
    "V346": "ADS54J40",
    "V242": "ADS131B26-Q1",
    "V003": "AM2431",
    "V011": "CD54HC123F3A",
}

# 简写 → 语料目录实际文件名（按前缀实测，精确指定，不做模糊猜）
ALIAS = {
    "ADC12QJ1600ALREP.pdf": "ADC12QJ1600ALREP__adc12qj1600-ep.pdf",
    "ADS54J40IRMPT.pdf": "ADS54J40IRMPT__ads54j40.pdf",
    "ADS131B26-Q1.pdf": "ADS131B26QPHPRQ1__ads131b26-q1.pdf",
}

FINAL_NOTE = "人工已核对 PDF 原图并确认"
REVIEWER = "wuxiaoxian"
ENTERED_BY = "WB_Agent"
V003_COND = "1.8V Operation"

# key = (sample_no, 签字版里被错放进 condition 的原值)
# value = (回到 PDF 原图后应填的 symbol, 真正的测试条件)
V320_COND = "over operating free-air temperature range (unless otherwise noted)"
SYMBOL_BACKFILL = {
    ("V320", "DACVDD, DIGVDD, CLKVDD"): ("DACVDD, DIGVDD, CLKVDD", V320_COND),
    ("V320", "AVDD, PLLAVDD"): ("AVDD, PLLAVDD", V320_COND),
    ("V242", "APWR to AGND"): ("APWR to AGND", ""),
    ("V242", "DPWR to DGND"): ("DPWR to DGND", ""),
    ("V242", "AGND, AGNDy to DGND"): ("AGND, AGNDy to DGND", ""),
    ("V242", "AVDD to AGND"): ("AVDD to AGND", ""),
    ("V242", "IOVDD to DGND"): ("IOVDD to DGND", ""),
}

import sys
sys.path.insert(0, str(PREP))
from validate_annotation import nos   # 与 v1.6 用同一个归一化函数做原文断言


def cell(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_signed_xlsx(path):
    ws = openpyxl.load_workbook(str(path), data_only=True).active
    vals = list(ws.values)
    hdr = [str(x or "").strip() for x in vals[0]]
    missing = [c for c in ORIG_COLS if c not in hdr]
    if missing:
        raise SystemExit("签字 xlsx 缺列：%s" % missing)
    rows = []
    for v in vals[1:]:
        if not any(x is not None and str(x).strip() for x in v):
            continue
        rows.append({k: cell(v[hdr.index(k)]) for k in ORIG_COLS})
    return rows


def ensure_link(real, link):
    if link.exists():
        if sha(link) != sha(real):
            raise SystemExit("硬链接目录里已有同名但字节不同的文件：%s" % link)
        return "复用"
    try:
        os.link(str(real), str(link))
        return "硬链接"
    except OSError:
        shutil.copy2(str(real), str(link))
        if sha(link) != sha(real):
            raise SystemExit("复制后字节不一致：%s" % link)
        return "复制（os.link 不可用，已校验字节一致）"


def atomic_replace(tmp, dst):
    try:
        os.replace(str(tmp), str(dst))
    except PermissionError:
        raise SystemExit("目标被占用且需要改写，请关闭 Excel/预览后重跑：%s" % dst)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def main():
    # 干净解压包里也能跑：默认路径只对本机有效，用 --xlsx / --pdf-dir 覆盖。
    # 输出固定写脚本所在目录，不依赖任何外部绝对路径。
    global SRC_XLSX, PDF_DIR
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", default=str(SRC_XLSX),
                    help="PM 签字的 xlsx（唯一真源）")
    ap.add_argument("--pdf-dir", default=str(PDF_DIR),
                    help="PDF 语料目录")
    args = ap.parse_args()
    SRC_XLSX, PDF_DIR = Path(args.xlsx), Path(args.pdf_dir)
    if not SRC_XLSX.exists():
        raise SystemExit("找不到 PM 签字 xlsx：%s" % SRC_XLSX)
    if not PDF_DIR.is_dir():
        raise SystemExit("找不到 PDF 语料目录：%s" % PDF_DIR)

    # 授权链保护：PM 已在定稿 xlsx 上补签 approved_by，重跑本脚本不得抹掉。
    # 只认 19 列定稿结构；读不到就按「无签名」处理并在结尾如实提示。
    approval = []
    if OUT_XLSX.exists():
        awb = openpyxl.load_workbook(str(OUT_XLSX), data_only=True,
                                     read_only=True)
        avals = list(awb.active.values)
        ahdr = [str(x or "").strip() for x in avals[0]]
        awb.close()
        if ahdr == FINAL_COLS:
            ai = ahdr.index("approved_by")
            for v in avals[1:]:
                if not any(x is not None and str(x).strip() for x in v):
                    continue
                approval.append(cell(v[ai]))
        if approval and len(approval) != 30:
            raise SystemExit("现有定稿 approved_by 行数异常：%d" % len(approval))
    for v in approval:
        assert v in ("", REVIEWER), \
            "现有定稿 approved_by 出现非 PM 签名：%r" % v

    signed = read_signed_xlsx(SRC_XLSX)
    assert len(signed) == 30, "签字版应为 30 行，实际 %d" % len(signed)
    assert all(r["row_status"] == "CONFIRMED" for r in signed)
    assert all(r["reviewer"] == REVIEWER for r in signed)

    # 签字原件留痕（逐格未改，供 Reviewer 反查）
    if not SIGNED_COPY.exists() or sha(SIGNED_COPY) != sha(SRC_XLSX):
        tmp = SIGNED_COPY.with_name(SIGNED_COPY.name + ".wb_tmp")
        shutil.copy2(str(SRC_XLSX), str(tmp))
        atomic_replace(tmp, SIGNED_COPY)

    # 原始 notes 留痕：V003 的 3.3V Operation / EN DASH / AMR 勿混等排查线索不能丢
    lines = [
        "B2 签字版原始 notes（清理前全文留痕）",
        "真源：Batch3_B2_SIGNED_original.xlsx（PM 签字原件副本，逐格未改）",
        "清理后统一为：%s" % FINAL_NOTE,
        "=" * 72,
    ]
    for i, r in enumerate(signed, 1):
        lines.append("物理行%-3d %-5s %-12s | %s" %
                     (i, r["sample_no"], r["symbol"] or "(空)", r["notes"]))
    lines.append("=" * 72)
    for k, v in Counter(r["notes"] for r in signed).items():
        lines.append("%2d 行 | %s" % (v, k))
    NOTES_BEFORE.write_text("\n".join(lines) + "\n", encoding="utf-8",
                            newline="\n")

    # ---- 生成 19 列定稿 ----
    rows = []
    backfilled = []
    for i, s in enumerate(signed):
        r = {k: s[k] for k in ORIG_COLS}
        r["notes"] = FINAL_NOTE
        r["approved_by"] = approval[i] if approval else ""
        r["entered_by"] = ""
        r["device_model"] = DEVICE_MODEL.get(s["sample_no"], "")
        r["human_adjudication"] = ""
        if not r["symbol"]:
            key = (s["sample_no"], s["condition"])
            if key not in SYMBOL_BACKFILL:
                raise SystemExit("第 %d 行空符号未按 PDF 原图登记：%r" % (i + 1, key))
            sym, cond = SYMBOL_BACKFILL[key]
            r["symbol"] = sym
            r["condition"] = cond
            r["entered_by"] = ENTERED_BY
            backfilled.append((i + 1, s["sample_no"], s["condition"], sym, cond))
        rows.append(r)

    assert len(backfilled) == 7, "符号回填应为 7 行，实际 %d" % len(backfilled)
    assert all(r["symbol"].strip() for r in rows), "定稿里仍有空 symbol"
    assert not any(r["human_adjudication"] for r in rows), \
        "符号已回填，不应再留 ACCEPTED_SOURCE_HAS_NO_SYMBOL 裁定码"

    # 逐格断言：原 15 列里只有 notes / symbol / condition 三列允许改，
    # 且 symbol / condition 只允许在登记的 7 行里改。
    backfill_lines = {x[0] for x in backfilled}
    for i, (a, b) in enumerate(zip(signed, rows), 1):
        allowed = {"notes"}
        if i in backfill_lines:
            allowed |= {"symbol", "condition"}
        for k in ORIG_COLS:
            if k in allowed:
                continue
            assert a[k] == b[k], "行%d 列%s 被改动：%r → %r" % (i, k, a[k], b[k])
    v003 = [r for r in rows if r["sample_no"] == "V003" and
            r["symbol"] == "VDDSHV5"]
    assert len(v003) == 1 and v003[0]["condition"] == V003_COND, \
        "V003 的 VDDSHV5 condition 未按 PM 裁定保留 %s" % V003_COND
    assert all(r["notes"] == FINAL_NOTE for r in rows)
    assert not any("low_confidence" in r["notes"].lower() for r in rows)

    # ---- 硬链接验证环境 + 溯源 ----
    LINK_DIR.mkdir(exist_ok=True)
    samples = OrderedDict()
    for r in rows:
        sno, fname = r["sample_no"], r["file_name"]
        if sno not in DEVICE_MODEL:
            raise SystemExit("未登记型号：%s" % sno)
        assert r["device_model"] == DEVICE_MODEL[sno]
        samples.setdefault(sno, {"file_name": fname, "pages": set()})
        samples[sno]["pages"].add(1)
        try:
            samples[sno]["pages"].add(int(r["evidence_page"]))
        except ValueError:
            raise SystemExit("%s 的 evidence_page 非整数：%r" %
                             (sno, r["evidence_page"]))

    side, prov_rows = OrderedDict(), []
    print("PDF 溯源（按签字版 file_name 建硬链接，字节与语料原件一致）：")
    for sno, meta in samples.items():
        fname = meta["file_name"]
        real = PDF_DIR / ALIAS.get(fname, fname)
        if not real.exists():
            raise SystemExit("语料缺失：%s（签字名 %s）" % (real, fname))
        link = LINK_DIR / fname
        how = ensure_link(real, link)
        raw = real.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        doc = fitz.open(str(real))
        npages = doc.page_count
        pages = {}
        for pno in sorted(meta["pages"]):
            if pno > npages:
                raise SystemExit("%s 的 evidence_page=%d 超出页数 %d" %
                                 (sno, pno, npages))
            pages[str(pno)] = doc.load_page(pno - 1).get_text("text")
        doc.close()
        # PM 裁定 2 的原文断言：p106 确实有独立一行 1.8V Operation
        if sno == "V003":
            p106 = pages.get("106", "")
            assert any(ln.strip() == V003_COND for ln in p106.splitlines()), \
                "p106 原文找不到独立行 %r，拒绝保留该 condition" % V003_COND
        # 7 行符号回填：每个符号、每个非空测试条件都必须能在本页原文核到
        if sno in ("V320", "V242"):
            ptxt = "\n".join(pages.values())
            for lineno, bsno, oldcond, sym, cond in backfilled:
                if bsno != sno:
                    continue
                assert nos(sym) in nos(ptxt), \
                    "行%d 符号 %r 在 %s 证据页原文找不到" % (lineno, sym, sno)
                if cond:
                    assert nos(cond) in nos(ptxt), \
                        "行%d 测试条件 %r 在 %s 证据页原文找不到" % (lineno, cond, sno)

        node = OrderedDict([
            ("sample_no", sno),
            ("file_name", fname),
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
        print("  %-5s %-38s %3d 页  %-16s sha256=%s…" %
              (sno, fname[:38], npages, how, digest[:16]))

    # ---- 落盘 ----
    tmp_csv = OUT_CSV.with_name(OUT_CSV.name + ".wb_tmp")
    with open(tmp_csv, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FINAL_COLS)
        w.writeheader()
        w.writerows(rows)
    atomic_replace(tmp_csv, OUT_CSV)

    tmp_prov = OUT_PROV.with_name(OUT_PROV.name + ".wb_tmp")
    with open(tmp_prov, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(prov_rows[0]))
        w.writeheader()
        w.writerows(prov_rows)
    atomic_replace(tmp_prov, OUT_PROV)

    obj = OrderedDict([
        ("generated_at", datetime.now().astimezone().isoformat()),
        ("source_xlsx", "Batch3_B2_SIGNED_original.xlsx"),
        ("extractor", "_make_b2_final.py"),
        ("note", "file_name 沿用 PM 签字原值；3 件简写名通过 b2_pdfs/ 硬链接"
                 "指向语料原件同一字节。sha256/页数从磁盘实算，页文本逐页抽取，"
                 "验证器 PDF 模式会再复算一次哈希。"),
        ("samples", side),
    ])
    tmp_side = OUT_SIDE.with_name(OUT_SIDE.name + ".wb_tmp")
    tmp_side.write_text(json.dumps(obj, ensure_ascii=False, indent=2),
                        encoding="utf-8", newline="\n")
    atomic_replace(tmp_side, OUT_SIDE)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "B2_FINAL"
    ws.append(FINAL_COLS)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="2F5597")
        c.alignment = Alignment(horizontal="center")
    for r in rows:
        ws.append([r.get(k, "") for k in FINAL_COLS])
    for ci, k in enumerate(FINAL_COLS, 1):
        width = {"parameter_name": 42, "notes": 60, "file_name": 40,
                 "human_adjudication": 34, "row_status": 16,
                 "table_title": 32, "approved_by": 16,
                 "entered_by": 15, "condition": 32}.get(k, 15)
        ws.column_dimensions[get_column_letter(ci)].width = width
    green = PatternFill("solid", fgColor="E2EFDA")
    for lineno, _, _, _, _ in backfilled:
        for k in ("symbol", "condition", "entered_by"):
            ws.cell(row=lineno + 1, column=FINAL_COLS.index(k) + 1).fill = green
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    tmp_xlsx = OUT_XLSX.with_name(OUT_XLSX.name + ".wb_tmp")
    wb.save(str(tmp_xlsx))
    atomic_replace(tmp_xlsx, OUT_XLSX)

    # 落盘后逐格断言 CSV == XLSX
    vals = list(openpyxl.load_workbook(str(OUT_XLSX), data_only=True).active.values)
    assert [str(x or "") for x in vals[0]] == FINAL_COLS
    with open(OUT_CSV, encoding="utf-8-sig", newline="") as fh:
        csv2 = list(csv.DictReader(fh))
    assert len(csv2) == len(vals) - 1 == 30
    for ri, r in enumerate(csv2, 1):
        for ci, k in enumerate(FINAL_COLS):
            assert str(vals[ri][ci] or "") == (r.get(k) or ""), \
                "xlsx/CSV 不同源：行%d 列%s" % (ri, k)

    print("\nB2 最终定稿：%d 行 / %d 样本 / %d 列" %
          (len(rows), len(samples), len(FINAL_COLS)))
    print("  notes 全部为：%s" % FINAL_NOTE)
    print("  V003 VDDSHV5 condition 保留：%s（p106 原文断言通过）" % V003_COND)
    print("  按 PDF 原图回填符号 %d 行（不再使用裁定码）：" % len(backfilled))
    for lineno, sno, oldcond, sym, cond in backfilled:
        print("    行%-3d %-5s %-26s → symbol=%-26r condition=%r"
              % (lineno, sno, oldcond, sym, cond))
    print("  7 行逐字段原文断言通过；entered_by=WB_Agent")
    n_ap = sum(1 for v in approval if v)
    print("  approved_by：从现有定稿原样保留 %d 处 PM 补签，其余 %d 行保持空白"
          % (n_ap, 30 - n_ap))
    print("  其余 23 行原 15 列除 notes 外逐格未变；reviewer / row_status 未动")
    print("\n复核命令：")
    print("  python validate_annotation.py --csv %s --page-text %s "
          "--provenance %s --pdf-dir %s" %
          (OUT_CSV.name, OUT_SIDE.name, OUT_PROV.name, LINK_DIR.name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
