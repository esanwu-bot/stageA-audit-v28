# -*- coding: utf-8 -*-
"""Gold Set 草稿打字员 —— 只用 fitz 词级坐标 + 正则，绝不调用 Parser。

为什么不用 fitz 的 find_tables
------------------------------
实测 V319 p6 的 find_tables 把 `MIN TYP MAX` 三列合并成一个单元格，
`1 5` 挤在一起，多温度组（VDD=3V / VDD=5V 各一组 MIN/TYP/MAX）完全分不开。
用它填值等于瞎猜列。故改用词级坐标自己算。

列归属规则（本脚本的核心，可审计）
----------------------------------
这些手册的数值**右对齐到列右边界**。实测 V319 p6 表头：
  MIN@339-353  TYP@372-387  MAX@399-417  MIN@429-443  TYP@461-477  MAX@489-507
数值 1@383-387 的右边界 387 与 TYP 的 387 重合 → 属 TYP 组 1；
数值 5@413-417 的右边界 417 与 MAX 的 417 重合 → 属 MAX 组 1。
因此：把每个数值的 x1 与各表头的 x1 比对，取容差内最近者。

宁可交白卷也不猜
----------------
以下情形一律不填值、标 UNRESOLVED，把判断权交回人手：
  * 数值数量少于/多于可归位数量，或有数值对不上任何列（容差外）
  * 同一行出现 `to` 范围（如 `-65 to 150`）且列归属不唯一
  * 找不到表头行、找不到参数名
  * 一行的几个数值挤进同一列

它不是什么
----------
* 不 import `icpdf.parser.*`，不调用 `parse_pdf()`。只用 fitz + re + csv。
* 不写 Gold 结论：输出 status 一律 DRAFT_AWAITING_HUMAN_CONFIRM。
"""
from __future__ import print_function

import csv
import json
import re
from pathlib import Path

PREP = Path(__file__).resolve().parent
WORKING = PREP / "Gold_Set_v1.1_WORKING.csv"
OUT_JSON = PREP / "draft_extract.json"

NUM_RE = re.compile(r"^[±+\-\u2212\u2013\u2014]?\d+(?:\.\d+)?$")
UNIT_HINTS = ("MIN", "TYP", "MAX", "NOM", "VALUE", "LIMIT", "UNIT",
              "MIN.", "TYP.", "MAX.")
ROW_TOL = 4.0          # 同一行数值的 y 容差
COL_TOL = 3.0          # 数值右边界与列右边界的容差
LABEL_MAX_X = 175.0    # 参数名列的右边界上限（超过即认为是数值区）


def dedup(words):
    """去掉重复绘制的词：同 bbox 同文本只留一个。

    这批 PDF 有不少把文字画了两遍（伪粗体），get_text('words') 会返回
    两份完全相同的词，如 VIO@49-63 出现两次。不去重会撞坏行分组。
    """
    seen = set()
    out = []
    for x0, y0, x1, y1, t, b, l, n in words:
        k = (round(x0, 1), round(x1, 1), round(y0, 1), t)
        if k in seen:
            continue
        seen.add(k)
        out.append((x0, y0, x1, y1, t))
    return out


def group_lines(words, tol=2.5):
    """按 y0 把词聚成视觉行。"""
    rows = []
    for w in sorted(words, key=lambda z: (z[1], z[0])):
        placed = False
        for r in rows:
            if abs(r["y"] - w[1]) <= tol:
                r["w"].append(w)
                placed = True
                break
        if not placed:
            rows.append({"y": w[1], "w": [w]})
    for r in rows:
        r["w"].sort(key=lambda z: z[0])
    rows.sort(key=lambda r: r["y"])
    return rows


def find_header(rows):
    """找表头行：出现 >=2 个 MIN/TYP/MAX/NOM，或含 VALUE/LIMIT 单列。"""
    for i, r in enumerate(rows):
        toks = [w[4].upper().rstrip(".") for w in r["w"]]
        n = sum(1 for t in toks if t in ("MIN", "TYP", "MAX", "NOM"))
        if n >= 2:
            return i, r
        if n >= 1 and any(t in ("VALUE", "LIMIT") for t in toks):
            return i, r
    for i, r in enumerate(rows):
        toks = [w[4].upper().rstrip(".") for w in r["w"]]
        if any(t in ("VALUE", "LIMIT") for t in toks) and len(toks) <= 6:
            return i, r
    return None, None


def build_columns(header_row):
    """从表头行建列模型，用「相邻表头中心的中点」当列边界。

    为什么不用右边界对齐：实测右边界法在某些行会偏 6.6pt（范围值、负号宽度
    不同导致），而中点边界是按表头词的中心切分，对左右对齐都不敏感。
    列边界取相邻表头词中心的中点；首尾列向表头词外扩 40pt，但不得越过
    UNIT 列，避免把页脚数字吸进来。
    """
    anchors = []
    grp = 0
    last = None
    unit_x0 = None
    for w in header_row["w"]:
        lab = w[4].upper().rstrip(".")
        if lab in ("MIN", "TYP", "MAX", "NOM"):
            if lab == "MIN" or last is None:
                grp += 1
            anchors.append({"label": lab, "group": grp,
                            "x0": w[0], "x1": w[2],
                            "c": (w[0] + w[2]) / 2.0})
            last = lab
        elif lab in ("VALUE", "LIMIT"):
            anchors.append({"label": "VALUE", "group": 1,
                            "x0": w[0], "x1": w[2],
                            "c": (w[0] + w[2]) / 2.0})
            last = "VALUE"
        elif lab == "UNIT" and unit_x0 is None:
            unit_x0 = w[0]

    if not anchors:
        return []
    anchors.sort(key=lambda a: a["c"])
    for i, a in enumerate(anchors):
        if i == 0:
            a["left"] = a["x0"] - 40.0
        else:
            a["left"] = (anchors[i - 1]["c"] + a["c"]) / 2.0
        if i == len(anchors) - 1:
            a["right"] = a["x1"] + 40.0
            if unit_x0 is not None:
                a["right"] = min(a["right"], unit_x0 - 5.0)
        else:
            a["right"] = (a["c"] + anchors[i + 1]["c"]) / 2.0
    return anchors


def assign_col(cols, cx):
    """数值中心落在哪一列；落在边界外返回 None。"""
    for c in cols:
        if c["left"] <= cx <= c["right"]:
            return c
    return None


def nearest_label(rows, y, cat_i, label_right=LABEL_MAX_X):
    """找与该数值行同一视觉行的参数名行。

    允许同行（参数名与 MIN/MAX 本来就印在同一行），但排除以 `•` 开头的
    特性条目，且必须落在同一张表内（由调用方用 bbox 限定词集）。
    为什么要 bbox：V199 p1 右上角 Product Summary 表的数值与左侧特性条目
    同高，不限表就会把 `• Ultra-low Qg` 当成参数名、把 40 当成参数值。

    label_right 由调用方按「第一列值列的左边界」给出，不能用固定阈值：
    V199 的参数名在 x=317-415，固定 175 会全部漏掉。
    """
    best, bestd = None, 1e9
    for r in rows[cat_i + 1:]:
        if not any(w[2] <= label_right and re.search(r"[A-Za-z]{3,}", w[4])
                   for w in r["w"]):
            continue
        txt = " ".join(w[4] for w in r["w"] if w[2] <= label_right)
        if re.match(r"^\s*[•·▪]", txt):
            continue
        d = abs(r["y"] - y)
        if d < bestd:
            best, bestd = r, d
    if best is None or bestd > 12.0:
        return None
    return best


HEADING = {
    "AMR": r"absolute\s+maximum\s+ratings",
    "ELC": r"electrical\s+characteristics",
}


def find_headings(rows, kind):
    """标题所在行的 y 列表（同一页可能重复出现）。"""
    rx = re.compile(HEADING[kind], re.I)
    return [r["y"] for r in rows
            if rx.search(" ".join(w[4] for w in r["w"]))]


def table_bboxes(page):
    """fitz 自带的表格边框。没有边框的页返回空列表。"""
    try:
        return [tuple(t.bbox) for t in page.find_tables().tables]
    except Exception:
        return []


def choose_bbox(bboxes, heading_y):
    """标题下方最近的表格。"""
    cands = [b for b in bboxes if b[1] >= heading_y - 4.0]
    return min(cands, key=lambda b: b[1]) if cands else None


def parse_page(page, kind, bbox=None):
    """解析一页，返回 (records, rejects)。bbox 给定时只在该表格区域内取词。"""
    raw = page.get_text("words")
    words = dedup(raw)
    if bbox is not None:
        words = [w for w in words
                 if w[0] >= bbox[0] - 3 and w[2] <= bbox[2] + 3
                 and w[1] >= bbox[1] - 3 and w[3] <= bbox[3] + 3]
    rows = group_lines(words)
    hi, hrow = find_header(rows)
    if hrow is None:
        return [], [{"reason": "找不到 MIN/TYP/MAX 表头行"}]

    cols = build_columns(hrow)
    if not cols:
        return [], [{"reason": "表头行里没解析出 MIN/TYP/MAX 列"}]

    # 数值词：表头以下、且不是表头词
    vals = []
    for r in rows[hi + 1:]:
        for w in r["w"]:
            t = w[4]
            if t.upper() in UNIT_HINTS:
                continue
            if NUM_RE.match(t):
                vals.append((r["y"], w[0], w[1], w[2], t))
    if not vals:
        return [], [{"reason": "表头以下没有数值"}]

    # 按 y 聚成数值行
    vals.sort(key=lambda z: (z[0], z[1]))
    bands = []
    for v in vals:
        if bands and abs(v[0] - bands[-1]["y"]) <= ROW_TOL:
            bands[-1]["v"].append(v)
        else:
            bands.append({"y": v[0], "v": [v]})

    lo = min(c["left"] for c in cols)
    hi_edge = max(c["right"] for c in cols)

    # 单位列：表头里找 UNIT / UNITS，取其 x 区间
    unit_rng = None
    for r in rows[max(0, hi - 2):hi + 3]:
        for w in r["w"]:
            if w[4].upper().rstrip(".") in ("UNIT", "UNITS"):
                unit_rng = (w[0] - 8.0, w[2] + 8.0)
                break
        if unit_rng:
            break

    records, rejects = [], []
    all_words = [w for r in rows[hi + 1:] for w in r["w"]]
    for b in bands:
        xs = [v[3] for v in b["v"]]
        assigned = []
        unmatched = []
        unit = ""
        for y, x0, y0, x1, t in b["v"]:
            cx = (x0 + x1) / 2.0
            c = assign_col(cols, cx)
            if c is None:
                # 落在值列区之外（页脚、Sub-groups 尾列、页码）→ 直接丢弃，
                # 不因此否掉整行；夹在值列中间却对不上，才是真问题
                if lo - 2 <= cx <= hi_edge + 2:
                    unmatched.append(t)
            else:
                assigned.append((c, t, round(cx, 1)))
        if unit_rng:
            for w in all_words:
                if abs(w[1] - b["y"]) > ROW_TOL:
                    continue
                if unit_rng[0] <= (w[0] + w[2]) / 2.0 <= unit_rng[1]:
                    if not NUM_RE.match(w[4]):
                        unit = w[4]
                        break
        if unmatched:
            rejects.append({"y": round(b["y"], 1),
                            "nums": [v[4] for v in b["v"]],
                            "reason": "数值落在列边界外: %s" % ",".join(unmatched)})
            continue

        # 同一列被赋两个值 → 列归属不可信
        seen = {}
        dup = False
        for c, t, cx in assigned:
            key = (c["group"], c["label"])
            if key in seen:
                dup = True
            seen[key] = t
        if dup:
            rejects.append({"y": round(b["y"], 1),
                            "nums": [v[4] for v in b["v"]],
                            "reason": "同一列被赋了两个值"})
            continue

        # 范围值（-65 to 150）：只有两值且中间夹 to 时才认
        has_to = any(w[4].lower() == "to" and abs(w[1] - b["y"]) <= ROW_TOL
                     and min(xs) <= w[0] <= max(xs) for w in all_words)
        is_range = has_to and len(assigned) == 2

        lab = nearest_label(rows, b["y"], hi, label_right=lo - 1.0)
        records.append({
            "row_y": round(b["y"], 1),
            "label": " ".join(w[4] for w in lab["w"] if w[2] <= lo - 1.0) if lab else "",
            "is_range": is_range,
            "unit": unit,
            "columns": [{"label": c["label"], "group": c["group"],
                         "value": t, "cx": cx, "col_span": [round(c["left"], 1),
                                                            round(c["right"], 1)]}
                        for c, t, cx in assigned],
            "raw": [v[4] for v in b["v"]],
        })
    return records, rejects


def main():
    samples = {}
    with open(WORKING, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            samples[r["sample_no"]] = r

    plan = [
        ("V319", [(5, "AMR"), (6, "ELC")]),
        ("V304", [(4, "AMR"), (5, "ELC")]),
        ("V199", [(1, "AMR"), (3, "ELC")]),
        ("V336", [(4, "AMR"), (5, "ELC")]),
        ("V173", [(4, "AMR"), (5, "ELC")]),
    ]

    import fitz
    out = {}
    for sno, pages in plan:
        meta = samples[sno]
        d = fitz.open(meta["file_path"])
        out[sno] = {"file_name": Path(meta["file_path"]).name,
                    "page_count": int(meta["page_count"]), "pages": []}
        for pno, kind in pages:
            page = d.load_page(pno - 1)
            rows_all = group_lines(dedup(page.get_text("words")))
            hs = find_headings(rows_all, kind)
            bbs = table_bboxes(page)
            entry = {"page": pno, "kind": kind,
                     "heading_y": [round(h, 1) for h in hs],
                     "tables": len(bbs), "rows": [], "rejects": []}
            cands = []
            for h in hs:
                bb = choose_bbox(bbs, h)
                if bb is None:
                    continue
                recs, rej = parse_page(page, kind, bbox=bb)
                scored = sum(1 for r in recs if r["label"])
                cands.append((scored, bb, recs, rej))
            if cands:
                cands.sort(key=lambda x: -x[0])
                scored, bb, recs, rej = cands[0]
                entry["mode"] = "bbox"
                entry["bbox"] = [round(v, 1) for v in bb]
                entry["rows"], entry["rejects"] = recs, rej
            else:
                # 没有可识别的表格边框（如 V199 p2）→ 回退全页，
                # 该模式噪声更大，输出时单独标注
                recs, rej = parse_page(page, kind, bbox=None)
                entry["mode"] = "fallback_no_bbox"
                entry["rows"], entry["rejects"] = recs, rej
            out[sno]["pages"].append(entry)
        d.close()

    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8", newline="\n")

    for sno in out:
        print("=" * 78)
        print("%s  %s" % (sno, out[sno]["file_name"]))
        for pg in out[sno]["pages"]:
            print("  -- p%d [%s] %s 标题y=%s 表格数=%s → 可归位 %d 行，拒判 %d"
                  % (pg["page"], pg["kind"], pg.get("mode"),
                     pg.get("heading_y"), pg.get("tables"),
                     len(pg["rows"]), len(pg["rejects"])))
            for r in pg["rows"][:6]:
                v = "  ".join("%s%d=%s@%.0f"
                              % (c["label"], c["group"], c["value"], c["cx"])
                              for c in r["columns"])
                print("     y=%-6.1f %-34s %-24s u=%s"
                      % (r["row_y"], r["label"][:34], v, r.get("unit") or "?"))
            for r in pg["rejects"][:3]:
                print("     [拒判] y=%-6s nums=%s  %s"
                      % (r.get("y"), r.get("nums"), r["reason"]))
    print()
    print("明细已写: %s" % OUT_JSON.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
