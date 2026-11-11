# -*- coding: utf-8 -*-
"""标注辅助 #5：机检 —— 核对"你抄的值是否真的印在你填的那一页上"。

它做什么
--------
逐行检查 Batch1_Annotation.csv：
  1. `sample_no` 是否真实存在于 Gold_Set_v1.1_WORKING.csv（防编造样本）
  2. `evidence_page` 是否在 1..page_count 之间（防页码超出）
  3. 把该页的文字抽出来，核对 `min/typ/max` 的数值是否**真的出现在这一页**
  4. 核对 `symbol` 与 `unit` 是否也出现在这一页
  5. 行错位启发式：unit 列里出现数字、symbol 列像是数值、页码等于某个值
  6. 若该页抽不出文字（扫描件），**不判对错**，只标 CANNOT_VERIFY

找不到时给出建议页
------------------
某行的值在指定页找不到，脚本会扫全文档，列出"这些值实际出现在哪些页"，
直接告诉你页码该改成几。这是修页码最快的办法。

它不是什么
----------
* 不是 Parser。不 import `icpdf.parser.*`，不调用 `parse_pdf()`。
* 不修改你的 CSV，只出报告。
* 不判断参数设计对错——它只核对"字在不在那一页"。

用法
----
  python validate_annotation.py
  python validate_annotation.py --csv Batch1_Annotation.csv
  python validate_annotation.py --no-suggest      # 跳过全文搜页，快一些
"""
from __future__ import print_function

import argparse
import csv
import re
import sys
from pathlib import Path

PREP = Path(__file__).resolve().parent
WORKING = PREP / "Gold_Set_v1.1_WORKING.csv"
DEFAULT_ANNO = PREP / "Batch1_Annotation.csv"

MINUS = "-\u2212\u2013\u2014"          # 连字符/减号/短横/长横
SPACE_RE = re.compile(r"\s+")


def _unify(s):
    """统一微符号 / 减号 / 不换行空格。空白另行处理。"""
    if s is None:
        return ""
    t = str(s)
    t = t.replace("\u00b5", "u").replace("\u03bc", "u").replace("\u212b", "A")
    for ch in MINUS:
        t = t.replace(ch, "-")
    t = t.replace("\u00a0", " ")
    return t


def normalize(s):
    """压成「无空白」形式。仅用于 symbol / unit 这类不含空格的短串包含判断。"""
    return SPACE_RE.sub("", _unify(s))


def collapse(s):
    """压成「单空格分隔」形式 —— 数值核对必须用这个。

    为什么不能先删光空白：PDF 里 `0 to 1.75` 删空白后变 `0to1.750to3.75`，
    `1.75` 右侧紧跟 `0`，会被数值边界断言判成"找不到"；`6 16` 变 `616` 同理。
    保留空格才能保住数字之间的真实边界。
    """
    return SPACE_RE.sub(" ", _unify(s)).strip()


def num_pattern(val):
    """把 '4.5' / '-8' / '±0.5' / '4.5V' 变成宽松正则（配合 collapse 文本使用）。

    数字内部允许夹杂空白（应对 PDF 把 `1.75` 抽成 `1 . 75` 的情况），
    两侧不允许紧邻数字或小数点（避免 `4.5` 命中 `14.55`）。
    """
    v = collapse(val)
    m = re.search(r"-?\d+(?:\.\d+)?", v)
    if not m:
        return None
    core = m.group(0)
    # 有效位数差异不算错：PDF 印 4.50、表格填 4.5 是同一个数。
    # 先把尾零剥掉（4.50→4.5），再在正则末尾允许 0*（4.5 可命中 4.50）。
    if "." in core:
        core = core.rstrip("0").rstrip(".")
    body = r"\s*".join(re.escape(ch) for ch in core)
    return re.compile(r"(?<![\d.])" + body + r"0*(?![\d.])")


def page_texts(doc):
    texts = []
    for i in range(doc.page_count):
        texts.append(doc.load_page(i).get_text("text") or "")
    return texts


def load_working():
    with open(WORKING, encoding="utf-8-sig", newline="") as fh:
        return {r["sample_no"]: r for r in csv.DictReader(fh)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(DEFAULT_ANNO))
    ap.add_argument("--no-suggest", action="store_true")
    args = ap.parse_args()

    anno_path = Path(args.csv)
    if not anno_path.exists():
        print("找不到标注文件: %s" % anno_path)
        return 2

    with open(anno_path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    if not rows:
        print("标注文件还是空的（只有表头）。填完再跑本脚本。")
        return 0

    working = load_working()
    import fitz

    docs = {}
    texts = {}
    verdicts = []

    for idx, r in enumerate(rows, start=2):        # 2 = 表头后的第一行
        sno = (r.get("sample_no") or "").strip()
        problems = []
        notes = []

        if sno == "EXAMPLE":
            verdicts.append(("SKIP", idx, sno, ["示例行，跳过"]))
            continue

        if sno not in working:
            verdicts.append(("ERROR", idx, sno, ["sample_no 不在清单里"]))
            continue

        meta = working[sno]
        path = Path(meta["file_path"])
        if not path.exists():
            verdicts.append(("ERROR", idx, sno, ["PDF 文件不存在"]))
            continue

        if sno not in docs:
            docs[sno] = fitz.open(str(path))
            texts[sno] = page_texts(docs[sno])
            working[sno]["_texts"] = texts[sno]
        tl = texts[sno]

        total_pages = len(tl)
        try:
            page = int(str(r.get("evidence_page") or "").strip())
        except ValueError:
            verdicts.append(("ERROR", idx, sno, ["evidence_page 不是整数"]))
            continue

        if not (1 <= page <= total_pages):
            problems.append("evidence_page=%d 超出范围 1..%d" % (page, total_pages))
            verdicts.append(("ERROR", idx, sno, problems))
            continue

        ptext_flat = normalize(tl[page - 1])       # 无空白，用于 symbol/unit
        ptext_coll = collapse(tl[page - 1])        # 单空格，用于数值
        if len(ptext_flat) < 20:
            # 扫描件：抽不出文字，无法机检
            verdicts.append(("CANNOT_VERIFY", idx, sno,
                             ["第 %d 页抽不出文字（扫描件），需人工复看" % page]))
            continue

        # --- 数值核对 ---
        checked = 0
        missing = []
        for col in ("min_value", "typ_value", "max_value"):
            val = (r.get(col) or "").strip()
            if not val:
                continue
            rx = num_pattern(val)
            if rx is None:
                continue
            checked += 1
            if not rx.search(ptext_coll):
                missing.append(col)
                # 全文搜页，给出建议
                if not args.no_suggest:
                    where = [i + 1 for i, t in enumerate(tl)
                             if rx.search(collapse(t))]
                    if where:
                        notes.append("%s=%s 不在 p%d，但出现在 p%s"
                                     % (col, val, page,
                                        ",".join(str(x) for x in where[:6])))
                    else:
                        notes.append("%s=%s 全文都找不到，可能抄错或字形特殊"
                                     % (col, val))

        if checked == 0:
            rs = (r.get("row_status") or "").strip()
            if not (rs.startswith("UNRESOLVED") or rs.startswith("EXCLUDED")
                    or rs.startswith("DRAFT")):
                problems.append("三个数值列全空，但 row_status 不是 UNRESOLVED/EXCLUDED")

        if missing:
            problems.append("这些数值在本页找不到: %s" % ",".join(missing))

        # --- symbol / unit 核对 ---
        sym = (r.get("symbol") or "").strip()
        if sym:
            if normalize(sym) not in ptext_flat:
                problems.append("symbol=%s 在本页找不到" % sym)

        unit = (r.get("unit") or "").strip()
        if unit:
            if normalize(unit) not in ptext_flat:
                problems.append("unit=%s 在本页找不到" % unit)

        # --- 错位启发式 ---
        if re.fullmatch(r"[\d.]+", unit or ""):
            problems.append("unit 列是纯数字（%s），疑似列错位" % unit)
        if re.fullmatch(r"[\d.]+", sym or ""):
            problems.append("symbol 列是纯数字（%s），疑似列错位" % sym)
        vals = [(r.get(c) or "").strip() for c in
                ("min_value", "typ_value", "max_value")]
        present = [v for v in vals if v]
        # 只在"整行仅有一个数值、且该数值恰好等于页码"时提示：
        # 这是行列错位的典型形态；若一行有两三个数值，页码撞上其中一个纯属巧合
        # （例如第 6 页上正好有个 6），不该报错。
        if len(present) == 1 and present[0] == str(page):
            notes.append("evidence_page 与唯一数值相同（%d），"
                         "可能只是巧合，请确认是否行列错位" % page)

        # --- row_status 规范 ---
        rs = (r.get("row_status") or "").strip()
        if not rs:
            problems.append("row_status 为空")
        elif rs.startswith("UNRESOLVED") and len(rs) <= len("UNRESOLVED:"):
            problems.append("UNRESOLVED 必须写明原因")
        elif rs.startswith("EXCLUDED") and len(rs) <= len("EXCLUDED:"):
            problems.append("EXCLUDED 必须写明原因")

        verdict = "ERROR" if problems else ("SUSPECT" if notes else "OK")
        verdicts.append((verdict, idx, sno, problems + notes))

    for d in docs.values():
        d.close()

    # --- 输出 ---
    order = {"ERROR": 0, "SUSPECT": 1, "CANNOT_VERIFY": 2, "OK": 3, "SKIP": 4}
    counts = {}
    for v, _, _, _ in verdicts:
        counts[v] = counts.get(v, 0) + 1

    print("=" * 74)
    print("标注机检报告  %s" % anno_path.name)
    print("=" * 74)
    for v in sorted(verdicts, key=lambda x: (order.get(x[0], 9), x[1])):
        verdict, idx, sno, msgs = v
        if verdict == "OK" and not msgs:
            print("[OK      ] 行%-4d %-6s" % (idx, sno))
            continue
        print("[%-9s] 行%-4d %-6s" % (verdict, idx, sno))
        for m in msgs:
            print("            - %s" % m)

    print()
    print("统计: " + "  ".join("%s=%d" % (k, counts[k])
                             for k in ("OK", "SUSPECT", "ERROR",
                                       "CANNOT_VERIFY", "SKIP") if k in counts))
    if counts.get("ERROR"):
        print()
        print("有 ERROR，先修这些再谈 CONFIRMED。")
        return 1
    print()
    print("无 ERROR。SUSPECT 需人工再看一眼；CANNOT_VERIFY 是扫描件，只能人眼核。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
