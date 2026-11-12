# -*- coding: utf-8 -*-
"""SCAN 批登记表：纯扫描件（无文本层）逐件留痕，标 EXCLUDED 并附溯源。

为什么要单独一张表：SCAN 三件不跑 VLM、不进 Gold，但"为什么不进"必须可复核。
只写一句 EXCLUDED 是结论，不是证据；这张表把 sha256 / 页数 / 无文本层页数
都从磁盘实算出来，Reviewer 拿同一份 PDF 就能复现。

判据（与 _build_batch3_interactive.py 的 `if not panes` 分支一致）：
  * 全书每一页 get_text("text").strip() 都为空 → 无文本层，无法建 Gold；
  * 只要有任意一页有文字，就不该用这套理由排除（说明另有问题，须人工看）。

产物：Batch3_SCAN_MANIFEST.csv（utf-8-sig，Excel 直开）
"""
from __future__ import print_function

import csv
import hashlib
import sys
from pathlib import Path

import fitz

PREP = Path(__file__).resolve().parent
WORKING = PREP / "Gold_Set_v1.1_WORKING.csv"
OUT = PREP / "Batch3_SCAN_MANIFEST.csv"

SCAN_SAMPLES = ["S01", "S02", "S03"]
# Reviewer 2026-11-12 定稿话术：全书无文本层用这一句，不可与其他两类混用
REASON = ("EXCLUDED: 全书无文本层；当前 Gate6A 流程无可用 OCR 取证路径，"
          "无法建立可验证 Gold")
COLS = [
    "sample_no", "file_name", "sha256", "page_count", "size_bytes",
    "blank_pages", "text_layer_pages", "verdict", "reason", "device_model",
    "reviewer",
]


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    reg = {r["sample_no"]: r for r in
           csv.DictReader(open(WORKING, encoding="utf-8-sig"))}
    rows = []
    for sno in SCAN_SAMPLES:
        if sno not in reg:
            raise SystemExit("样本不在册：%s" % sno)
        p = Path(reg[sno]["file_path"])
        if not p.is_file():
            raise SystemExit("找不到 PDF：%s" % p)
        raw = p.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        doc = fitz.open(str(p))
        n = doc.page_count
        blank = sum(1 for i in range(n)
                    if not doc.load_page(i).get_text("text").strip())
        doc.close()
        if blank != n:
            # 有文本层就不能用「无 OCR」这套理由排除，宁可报错让人看
            raise SystemExit(
                "FAIL %s 有 %d/%d 页存在文本层，不能按「无 OCR 能力」排除"
                % (sno, n - blank, n))
        rows.append({
            "sample_no": sno,
            "file_name": p.name,
            "sha256": digest,
            "page_count": n,
            "size_bytes": len(raw),
            "blank_pages": blank,
            "text_layer_pages": 0,
            "verdict": "EXCLUDED",
            "reason": REASON,
            "device_model": "",      # 无文本层，型号需人工从图面确认
            "reviewer": "",
        })
        print("  %-4s %-42s %3d 页  全 %d 页无文本层  sha256=%s…"
              % (sno, p.name[:42], n, blank, digest[:16]))

    tmp = OUT.with_name(OUT.name + ".tmp")
    with open(tmp, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    tmp.replace(OUT)

    # 落盘后回读断言：行数、被判 EXCLUDED 的件数、理由原文
    back = list(csv.DictReader(open(OUT, encoding="utf-8-sig")))
    assert len(back) == len(SCAN_SAMPLES), "行数不符：%d" % len(back)
    assert all(r["verdict"] == "EXCLUDED" for r in back)
    assert all(r["reason"] == REASON for r in back)
    assert all(r["text_layer_pages"] == "0" for r in back)
    print("\nSCAN 登记表：%d 件，全部 EXCLUDED，理由「%s」" % (len(back), REASON))
    print("  溯源列：sha256 / page_count / size_bytes / blank_pages 均从磁盘实算")
    print("  产物：%s（%d 字节）" % (OUT.name, OUT.stat().st_size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
