# -*- coding: utf-8 -*-
"""把已生成的两份 Batch 3 圈选台，重新内联成修好导出名的前端。

为什么不重跑生成器：生成器会再调一遍 VLM、重画 29 张裁图，
而这次只是前端改了两行字符串，数据一格没动。用「同一份 CSV +
同一份修好的 _b2_app.js」重建 <script> 内容，产物与源码仍然完全同源，
且不碰任何标注结论。

用法：
  python _patch_b3_export_name.py --html Batch3_Viewer.html \
      --csv Batch3_DRAFT.csv --name Batch3_ANNOTATED
  python _patch_b3_export_name.py --html Batch3_B2_Viewer.html \
      --csv Batch3_B2_DRAFT.csv --name Batch3_B2_ANNOTATED
"""
from __future__ import print_function

import argparse
import csv
import json
import re
from pathlib import Path

import _build_batch2_interactive as I2

PREP = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--name", required=True, help="导出文件名（不含 .csv 后缀）")
    args = ap.parse_args()

    hp, cp = PREP / args.html, PREP / args.csv
    text = hp.read_text(encoding="utf-8")
    rows = list(csv.DictReader(open(cp, encoding="utf-8-sig")))

    js = ("window.B3_EXPORT_NAME=%s;\n" % json.dumps(args.name)
          + I2.build_js(rows))
    new, n = re.subn(r"(<script>)(.*?)(</script>)",
                     lambda m: m.group(1) + js + m.group(3),
                     text, flags=re.S)
    if n != 1:
        raise SystemExit("HTML 里 <script> 段数不是 1（实际 %d），拒绝改写" % n)

    # 回归断言：Bug 特征串必须消失，新名字必须出现，草稿行数不许变
    assert 'a.download = "Batch2_ANNOTATED.csv"' not in new, "硬编码还在"
    assert "a.download = EXPORT_NAME + \".csv\"" in new, "参数化没生效"
    assert "window.B3_EXPORT_NAME=%s;" % json.dumps(args.name) in new
    assert new.count('<img src="') == text.count('<img src="'), "图片引用数变了"
    m = re.search(r"const DRAFT = (\[.*?\]);", new, re.S)
    assert len(json.loads(m.group(1))) == len(rows), "注入行数与 CSV 不一致"

    hp.write_text(new, encoding="utf-8", newline="\n")
    print("%s → 导出名 %s.csv，草稿 %d 行，图片 %d 张，回归断言全过"
          % (hp.name, args.name, len(rows), new.count('<img src="')))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
