# -*- coding: utf-8 -*-
"""对 3 件补充样本做逐页全量文本层核验（不是抽样）。

扫描阶段为了 11,355 份的吞吐，9 页以上的文档只抽样 8 页。
但真正要进评测的这 3 件必须给出**逐页**结论，否则「无文本层」只是抽样推断。

本脚本对每件逐页统计：字符数、图像块数、图像覆盖面积比。
判定：
  - 全部页字符数 < 20            -> IMAGE_ONLY_CONFIRMED
  - 有任何一页字符数 >= 20        -> MIXED_TEXT_LAYER（不可作为 PAIN-08 样本）

只读，不调用 Parser，不调用大模型。
"""
from __future__ import print_function

import json
import sys
from pathlib import Path

PREP = Path(__file__).resolve().parent
TEXT_MIN = 20


def probe_full(path):
    import fitz
    doc = fitz.open(path)
    try:
        pages = []
        for i in range(doc.page_count):
            page = doc.load_page(i)
            text = (page.get_text("text") or "").strip()
            imgs = page.get_images(full=True) or []
            # 图像覆盖面积比：用 get_image_info() 拿绘制实例的真实 bbox。
            # 不用 get_text("dict") 的 type==1 块——嵌入型 XObject 在那里拿不到 bbox，
            # 会错误地算出 0.0，把"有图"误报成"无图"。
            area = 0.0
            n_drawn = 0
            try:
                parea = abs(page.rect.width * page.rect.height) or 1.0
                for info in page.get_image_info():
                    x0, y0, x1, y1 = info["bbox"]
                    area += abs((x1 - x0) * (y1 - y0))
                    n_drawn += 1
                area = round(min(area / parea, 1.0), 4)
            except Exception:                                    # noqa: BLE001
                area = -1.0
            pages.append({
                "page": i + 1,
                "chars": len(text),
                "image_objects": len(imgs),
                "image_draw_instances": n_drawn,
                "image_area_ratio": area,
            })
        return {
            "page_count": doc.page_count,
            "is_encrypted": bool(doc.is_encrypted or doc.needs_pass),
            "pages": pages,
        }
    finally:
        doc.close()


def main():
    sel = json.loads((PREP / "selected_supplementary.json").read_text(encoding="utf-8"))
    out = []
    for s in sel["selected"]:
        print("checking %s %s ..." % (s["sample_no"], s["file_name"]), flush=True)
        r = probe_full(s["file_path"])
        maxc = max(p["chars"] for p in r["pages"])
        min_area = min(p["image_area_ratio"] for p in r["pages"])
        verdict = ("IMAGE_ONLY_CONFIRMED" if maxc < TEXT_MIN
                   else "MIXED_TEXT_LAYER")
        out.append({
            "sample_no": s["sample_no"],
            "file_name": s["file_name"],
            "sha256": s["sha256"],
            "page_count": r["page_count"],
            "pages_probed": len(r["pages"]),
            "is_encrypted": r["is_encrypted"],
            "max_chars_per_page": maxc,
            "total_chars": sum(p["chars"] for p in r["pages"]),
            "min_image_area_ratio": min_area,
            "verdict": verdict,
            "pages": r["pages"],
        })

    overall = all(r["verdict"] == "IMAGE_ONLY_CONFIRMED" for r in out)
    doc = {
        "method": "PyMuPDF 逐页 get_text('text')；阈值 20 字符，与 Gate 1 一致",
        "parser_invoked": False,
        "llm_called": False,
        "overall": "PASS" if overall else "FAIL",
        "samples": out,
    }
    (PREP / "full_page_textlayer_verify.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")

    print()
    print("overall:", doc["overall"])
    for r in out:
        print("  %s %-40s pages=%2d probed=%2d maxchars=%3d totalchars=%4d minImgArea=%.2f  %s"
              % (r["sample_no"], r["file_name"], r["page_count"],
                 r["pages_probed"], r["max_chars_per_page"], r["total_chars"],
                 r["min_image_area_ratio"], r["verdict"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
