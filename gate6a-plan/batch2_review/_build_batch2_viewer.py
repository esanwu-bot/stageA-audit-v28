# -*- coding: utf-8 -*-
"""第 2 批导航图生成器 —— 每次 6 件，导航图优先，草稿允许烂。

核心原则（用户定的）
--------------------
**草稿可以烂，但导航图必须准。**
机器把数值抄错没关系——人工会看图自己填；但如果导航图指错页、截错表，
人工就会白跑一趟。所以本脚本把力气全花在"哪一页、哪块区域"上：

  * 只在前 40 页找标题（AMR 几乎都在前 20 页，个别在 25-30 页），
    避免 280 页的大文件卡死；find_tables 只在命中标题的页调用，故放宽代价很小
  * find_tables() 只在命中标题的页调用；拿不到边框就按标题位置往下截 320pt
  * 裁剪的是**表格区域**，不是整页 —— 人一眼就能看到要抄的那几行

草稿策略
--------
* 抽得出 → DRAFT_AWAITING_HUMAN_CONFIRM
* 抽不出 → DRAFT_EMPTY（按用户要求，不再写长篇 UNRESOLVED）
* S01-S03 / V022 → 只留样本基本信息，参数列全空，notes 写明原因
"""
from __future__ import print_function

import csv
import re
from pathlib import Path

import fitz

import _draft_extract as X

PREP = Path(__file__).resolve().parent
WORKING = PREP / "Gold_Set_v1.1_WORKING.csv"
REPORTS = PREP / "annotation_reports"
OUT_CSV = PREP / "Batch2_DRAFT.csv"
OUT_HTML = PREP / "Batch2_Viewer.html"

DONE = {"V319", "V304", "V199", "V336", "V173"}
SCAN = {"S01", "S02", "S03"}
DIAG = {"V022"}
BATCH_SIZE = 6
MAX_SCAN_PAGES = 40
RENDER_DPI = 300

COLS = ["sample_no", "file_name", "evidence_page", "table_title", "symbol",
        "parameter_name", "min_value", "typ_value", "max_value", "unit",
        "condition", "row_status", "notes", "reviewer"]

KIND_CN = {"AMR": "Absolute Maximum Ratings", "ELC": "Electrical Characteristics"}
# 标题变体：不覆盖不行。V101 的第二张表叫 `DC Electrical Specifications`，
# 有些器件叫 `Static Characteristics`，只认 `Electrical Characteristics`
# 会漏掉整张表，导航图就把人带偏了。
X.HEADING["AMR"] = (r"(absolute\s+)?maximum\s+ratings")
X.HEADING["ELC"] = (r"(electrical|dc\s+electrical)\s+(characteristics|specifications)"
                    r"|static\s+characteristics|dc\s+characteristics")
X.HEADING["ROC"] = r"recommended\s+operating\s+conditions"
PREFER = [
    r"supply\s+voltage", r"operating\s+(free-air\s+)?temperature",
    r"storage\s+temperature", r"junction\s+temperature",
    r"input\s+voltage", r"output\s+voltage", r"supply\s+current",
    r"quiescent\s+current", r"threshold", r"leakage", r"clamp\s+current",
    r"continuous\s+(drain\s+)?current", r"power\s+dissipation",
]


def split_label(label):
    toks = (label or "").split()
    if not toks:
        return "", ""
    sym = ""
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9()/\-±.]{1,11}", toks[0]):
        sym = toks[0]
        toks = toks[1:]
    return sym, " ".join(toks)


def rank(rec):
    lab = (rec.get("label") or "").lower()
    score = 0
    for i, pat in enumerate(PREFER):
        if re.search(pat, lab):
            score += 100 - i
            break
    if rec.get("unit"):
        score += 30
    if 8 <= len(lab) <= 70:
        score += 10
    return score


def scan(doc, npages):
    """逐页扫一遍。

    返回 (hits, nav)：
      hits[kind] = [(rank, page, rec, heading_y, bbox)]  能解析出数值的行
      nav[kind]  = [(page, heading_y, bbox, n_rows)]     只要命中标题就记导航

    为什么导航与解析分开：老手册的 AMR 常是「点线式列表」
    （`DC Supply Voltage, VCC ......... -0.5V to 7V`），根本没有 MIN/TYP/MAX
    表头，解析必然失败。但**标题在那页就是证据**，导航图必须给出那一页，
    否则人工会被"未定位"误导，白翻 43 页去找一张明明存在的表。

    目录页必须排除：V349/V097 的 p2 是 Table of Contents，
    `Absolute Maximum Ratings...12` 作为条目出现，截在那里就是把人带错页。
    判据用「同一页命中 3 种以上表标题」——正文页几乎不可能同时出现
    AMR + ELC + Recommended Operating Conditions 三张表的标题。
    不用「点点点数量」判，因为点线式表格正文本身满页是点。
    """
    hits = {"AMR": [], "ELC": []}
    nav = {"AMR": [], "ELC": []}
    for pno in range(1, min(npages, MAX_SCAN_PAGES) + 1):
        page = doc.load_page(pno - 1)
        rows = X.group_lines(X.dedup(page.get_text("words")))
        found = {k: X.find_headings(rows, k) for k in ("AMR", "ELC", "ROC")}
        kinds_hit = sum(1 for k, v in found.items() if v)
        if kinds_hit >= 3:
            continue                      # 目录页，跳过
        for kind in ("AMR", "ELC"):
            hs = found.get(kind) or []
            if not hs:
                continue
            bbs = X.table_bboxes(page)
            for h in hs:
                bb = X.choose_bbox(bbs, h)
                recs, _ = X.parse_page(page, kind, bbox=bb)
                good = [r for r in recs if r.get("label")]
                if not any(n[0] == pno for n in nav[kind]):
                    nav[kind].append((pno, h, bb, len(good)))
                for r in good:
                    hits[kind].append((rank(r), pno, r, h, bb))
    return hits, nav


def render_clip(page, heading_y, bbox, out_path):
    """只截表格区域，不是整页。返回 (rect, 是否用了表格边框)。"""
    pr = page.rect
    x0, x1 = pr.x0 + 14, pr.x1 - 14
    top = max(pr.y0 + 4, heading_y - 3)
    if bbox:
        bottom = min(pr.y1 - 6, max(bbox[3] + 6, top + 40))
        used = True
    else:
        bottom = min(pr.y1 - 6, top + 320)
        used = False
    rect = fitz.Rect(x0, top, x1, bottom)
    pix = page.get_pixmap(dpi=RENDER_DPI, clip=rect)
    pix.save(str(out_path))
    return rect, used


def to_rows(sno, fname, kind, cand, limit=2):
    cand = sorted(cand, key=lambda z: -z[0])
    picked, seen = [], set()
    for sc, pno, rec, h, bb in cand:
        key = (rec["label"][:24], pno)
        if key in seen:
            continue
        seen.add(key)
        picked.append((pno, rec))
        if len(picked) >= limit:
            break
    out = []
    for pno, rec in picked:
        sym, name = split_label(rec["label"])
        g1 = [c for c in rec["columns"] if c.get("group") == 1]
        mn = typ = mx = ""
        for c in g1:
            if c["label"] == "MIN":
                mn = c["value"]
            elif c["label"] == "TYP":
                typ = c["value"]
            elif c["label"] in ("MAX", "VALUE"):
                mx = c["value"]
        if rec.get("is_range") and len(g1) == 2:
            mn, mx = g1[0]["value"], g1[1]["value"]
        note = "机器草稿，需人工比对 PDF 页码 %d 确认" % pno
        if any(c["label"] == "VALUE" for c in g1):
            note += "；AMR 单值列"
        out.append({
            "sample_no": sno, "file_name": fname, "evidence_page": str(pno),
            "table_title": KIND_CN[kind], "symbol": sym, "parameter_name": name,
            "min_value": mn, "typ_value": typ, "max_value": mx,
            "unit": rec.get("unit", ""), "condition": "",
            "row_status": "DRAFT_AWAITING_HUMAN_CONFIRM", "notes": note,
            "reviewer": ""})
    return out


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


CSS = """
*{box-sizing:border-box}
body{margin:0;padding:0 0 60px;background:#f4f5f7;color:#1c1f23;
 font-family:"Microsoft YaHei","Segoe UI",Arial,sans-serif;font-size:14px;line-height:1.65}
header{position:sticky;top:0;z-index:10;background:#fff;border-bottom:1px solid #d8dbe0;padding:10px 22px}
header h1{margin:0;font-size:16px}
header p{margin:3px 0 0;font-size:12px;color:#666}
.wrap{max-width:1100px;margin:0 auto;padding:20px 22px}
.card{background:#fff;border:1px solid #dcdfe4;border-radius:6px;margin:0 0 22px;overflow:hidden}
.head{padding:11px 16px;border-bottom:1px solid #e6e9ed;background:#fafbfc}
.sn{font-weight:700;font-size:15px;color:#0b5cad;margin-right:10px}
.fn{font-family:Consolas,monospace;font-size:12px;color:#444}
.meta{margin-top:4px;font-size:12px;color:#555}
.tag{display:inline-block;padding:1px 7px;margin-right:6px;border-radius:3px;
 font-size:11px;font-weight:600;border:1px solid}
.t-amr{background:#e8f0fb;color:#14509e;border-color:#c3d8f4}
.t-elc{background:#e9f6ec;color:#1c6b33;border-color:#c3e3cc}
.t-warn{background:#fdeceb;color:#a12a20;border-color:#f3c9c5}
.t-ok{background:#eef7ee;color:#2c6b34;border-color:#c8e2c9}
.body{padding:12px 16px 16px}
figure{margin:0 0 18px}
figure img{width:100%;height:auto;display:block;border:1px solid #cfd3d9}
figcaption{font-size:12px;color:#555;padding:5px 2px 0}
figcaption b{color:#1c1f23}
table.rows{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:8px}
table.rows th,table.rows td{border:1px solid #dcdfe4;padding:5px 7px;text-align:left}
table.rows th{background:#f2f4f7;font-weight:600}
table.rows td.num{font-family:Consolas,monospace;text-align:right}
.note{background:#fffbe8;border:1px solid #efe0a8;border-radius:6px;padding:12px 16px;margin:0 0 22px;font-size:13px}
.note h2{margin:0 0 8px;font-size:14px}
.note ul{margin:6px 0 0;padding-left:20px}
.hint{font-size:12px;color:#777;margin-top:6px}
a{color:#0b5cad}
"""


def main():
    samples = []
    with open(WORKING, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            samples.append(r)
    todo = [r for r in samples if r["sample_no"] not in DONE][:BATCH_SIZE]

    rows_out, cards = [], []
    for meta in todo:
        sno = meta["sample_no"]
        fname = Path(meta["file_path"]).name
        npages = int(meta["page_count"])
        pdf_url = "file:///" + str(Path(meta["file_path"])).replace("\\", "/")

        if sno in SCAN or sno in DIAG:
            why = ("扫描件无文本层，请人工看图录入" if sno in SCAN
                   else "diagnostic_only 样本，不参与准确率计算，无需录入")
            rows_out.append({
                "sample_no": sno, "file_name": fname, "evidence_page": "1",
                "table_title": "", "symbol": "", "parameter_name": "",
                "min_value": "", "typ_value": "", "max_value": "", "unit": "",
                "condition": "", "row_status": "DRAFT_EMPTY",
                "notes": why, "reviewer": ""})
            cards.append({"sno": sno, "fname": fname, "npages": npages,
                          "pdf": pdf_url, "figs": [], "rows": [],
                          "quality": "特殊样本", "note": why})
            continue

        doc = fitz.open(meta["file_path"])
        hits, nav = scan(doc, npages)
        out_dir = REPORTS / sno
        out_dir.mkdir(parents=True, exist_ok=True)

        figs = []
        for kind in ("AMR", "ELC"):
            if not nav.get(kind):
                continue
            # 多页候选时优先「解析出数值最多的那页」，其次页码最小
            withrows = [c for c in nav[kind] if c[3] > 0]
            if withrows:
                pno, hy, bb, _n = max(withrows, key=lambda c: (c[3], -c[0]))
            else:
                pno, hy, bb, _n = min(nav[kind], key=lambda c: c[0])
            png = out_dir / ("b2_%s_p%04d.png" % (kind, pno))
            page = doc.load_page(pno - 1)
            rect, used_bbox = render_clip(page, hy, bb, png)
            figs.append({"kind": kind, "pno": pno, "png": png,
                         "rel": png.relative_to(PREP).as_posix(),
                         "bbox": used_bbox, "rect": rect,
                         "span": sorted({n[0] for n in nav[kind]})})
            if hits.get(kind):
                rows_out.extend(to_rows(sno, fname, kind, hits[kind]))

        doc.close()
        my_rows = [r for r in rows_out if r["sample_no"] == sno]
        good = sum(1 for r in my_rows if r["symbol"] and r["unit"])
        if not figs:
            quality = "未定位"
            note = ("前 %d 页未找到 AMR/ELC 标题，需人工翻查"
                    % min(npages, MAX_SCAN_PAGES))
            rows_out.append({
                "sample_no": sno, "file_name": fname, "evidence_page": "",
                "table_title": "", "symbol": "", "parameter_name": "",
                "min_value": "", "typ_value": "", "max_value": "", "unit": "",
                "condition": "", "row_status": "DRAFT_EMPTY",
                "notes": note, "reviewer": ""})
        elif not my_rows:
            quality = "只有导航图"
            note = ("表格已定位并按图裁剪，但该表不是 MIN/TYP/MAX 结构"
                    "（如点线式列表），机器不填值，请直接看图录入")
            rows_out.append({
                "sample_no": sno, "file_name": fname,
                "evidence_page": str(figs[0]["pno"]),
                "table_title": "", "symbol": "", "parameter_name": "",
                "min_value": "", "typ_value": "", "max_value": "", "unit": "",
                "condition": "", "row_status": "DRAFT_EMPTY",
                "notes": note, "reviewer": ""})
        elif good >= len(my_rows) - 1:
            quality, note = "好", "表格已定位，草稿行带符号与单位"
        else:
            quality = "一般"
            note = "表格已定位，草稿行可能缺符号或单位，请以图为准"

        if figs and len(figs) < 2:
            note += ("；只定位到 %d 张表。另一张的标题在 PDF 里是图形"
                     "（文字层抽不到），但常与这张同屏，请以裁剪图为准" % len(figs))
        cards.append({"sno": sno, "fname": fname, "npages": npages,
                      "pdf": pdf_url, "figs": figs, "rows": my_rows,
                      "quality": quality, "note": note})

    with open(OUT_CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        for r in rows_out:
            w.writerow({k: r.get(k, "") for k in COLS})

    # ---------- HTML ----------
    p = []
    p.append('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">')
    p.append("<title>Batch 2 导航图（前 6 件）</title>")
    p.append("<style>%s</style></head><body>" % CSS)
    p.append("<header><h1>Batch 2 导航图 · %d 件</h1>" % len(cards))
    p.append("<p>草稿可以烂，导航图必须准。表格区域已按标题自动裁剪，"
             "点图看原尺寸；右侧页码即 PDF 物理页码。</p></header>")
    p.append('<div class="wrap">')

    p.append('<div class="note"><h2>怎么用这张导航图</h2><ul>'
             "<li>每件下面按 <b>Absolute Maximum Ratings</b> 与 "
             "<b>Electrical Characteristics</b> 分块，图就是那张表本身。</li>"
             "<li>图下的表格是<b>机器草稿</b>，只作参考。数值、单位、列归属一律<b>以图为准</b>。</li>"
             "<li>要跳回 PDF 原文，点标题右侧的「在 PDF 中打开」。</li>"
             "<li>找不到的件会标红「未定位」，那种就整件留空、直接在图里补。</li>"
             "</ul>"
             '<div class="hint">填 10 个空白/UNRESOLVED，比填 10 个瞎编的数字强一万倍。</div></div>')

    for c in cards:
        tags = []
        for f in c["figs"]:
            tags.append('<span class="tag %s">%s = p%s</span>'
                        % ("t-amr" if f["kind"] == "AMR" else "t-elc",
                           "AMR" if f["kind"] == "AMR" else "ELC",
                           "/".join(str(x) for x in f["span"])))
        cls = ("t-ok" if c["quality"] == "好" else
               "t-warn" if c["quality"] in ("未定位", "特殊样本") else "t-warn")
        tags.append('<span class="tag %s">草稿：%s</span>' % (cls, c["quality"]))

        p.append('<div class="card"><div class="head">')
        p.append('<span class="sn">%s</span><span class="fn">%s</span>'
                 % (esc(c["sno"]), esc(c["fname"])))
        p.append('　<a href="%s" target="_blank">在 PDF 中打开</a>' % esc(c["pdf"]))
        p.append('<div class="meta">共 %d 页 　%s</div>'
                 % (c["npages"], "".join(tags)))
        p.append('<div class="meta">%s</div>' % esc(c["note"]))
        p.append('</div><div class="body">')

        for f in c["figs"]:
            p.append('<figure><a href="%s" target="_blank"><img src="%s" alt="%s %s p%d"></a>'
                     '<figcaption><b>%s · 第 %d 页</b>　%s　点图看原尺寸</figcaption></figure>'
                     % (esc(f["rel"]), esc(f["rel"]), esc(c["sno"]),
                        esc(f["kind"]), f["pno"], esc(KIND_CN[f["kind"]]),
                        f["pno"],
                        "已按表格边框裁剪" if f["bbox"] else "无表格边框，按标题位置裁剪"))

        if c["rows"]:
            p.append('<table class="rows"><tr><th>页</th><th>符号</th>'
                     "<th>参数名</th><th>min</th><th>typ</th><th>max</th>"
                     "<th>单位</th><th>状态</th></tr>")
            for r in c["rows"]:
                p.append("<tr><td>%s</td><td>%s</td><td>%s</td>"
                         '<td class="num">%s</td><td class="num">%s</td>'
                         '<td class="num">%s</td><td>%s</td><td>%s</td></tr>'
                         % (esc(r["evidence_page"]), esc(r["symbol"]),
                            esc(r["parameter_name"]), esc(r["min_value"]),
                            esc(r["typ_value"]), esc(r["max_value"]),
                            esc(r["unit"]),
                            esc(r["row_status"]).replace(
                                "DRAFT_AWAITING_HUMAN_CONFIRM", "待人工确认")))
            p.append("</table>")
        else:
            p.append('<div class="hint">本件无机器草稿（%s）。</div>' % esc(c["quality"]))
        p.append("</div></div>")

    p.append("</div></body></html>")
    OUT_HTML.write_text("".join(p), encoding="utf-8", newline="\n")

    print("导航图: %s (%d 件)" % (OUT_HTML.name, len(cards)))
    print("草稿  : %s (%d 行)" % (OUT_CSV.name, len(rows_out)))
    for c in cards:
        print("  %-5s %-8s figs=%d rows=%d  %s"
              % (c["sno"], c["quality"], len(c["figs"]), len(c["rows"]), c["note"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
