# -*- coding: utf-8 -*-
"""第 2 批交互式导航图 —— 左图右文，点文本行自动填字段。

为什么改策略
------------
PM 不是硬件专家，不能靠人眼盲敲复杂表格；而机器解析表格结构在部分 PDF 上
必然塌掉（点线式列表、无 MIN/TYP/MAX 表头、标题是图形）。

所以改成「文本原样直出 + 人工圈选」：
  * 左侧 = 该页/该表区域的 300 DPI 截图（导航，看版式）
  * 右侧 = 同一区域**按行抓出的纯文本**，一行一条，可点击
  * 点一行 → JS 解析出 数字 / 单位 / 参数名 → 自动填进下方表格
  * 表格里每格可改，状态可选，最后「导出 CSV」粘回 Excel

人不需要判断"这个数属于哪一列"——只要认得哪个数字和单位对，
点那一行就行。机器只负责把文本摆出来，不做结构判断。

纯扫描件（S01-S03）文字层为空：页面直接标红提示，不让点，
提示整件在 Excel 里记 EXCLUDED: 无 OCR 能力，无法建立 Gold。
"""
from __future__ import print_function

import csv
import re
from pathlib import Path

import fitz

import _build_batch2_viewer as B
import _draft_extract as X

PREP = Path(__file__).resolve().parent
WORKING = PREP / "Gold_Set_v1.1_WORKING.csv"
REPORTS = PREP / "annotation_reports"
OUT_CSV = PREP / "Batch2_DRAFT_FIXED.csv"
OUT_HTML = PREP / "Batch2_Viewer_V3.html"

DONE = {"V319", "V304", "V199", "V336", "V173"}
SCAN = {"S01", "S02", "S03"}
DIAG = {"V022"}
BATCH_SIZE = 6

from _vl_extract import extract_rows as vl_extract

COLS = B.COLS + ["confidence_score"]
KIND_CN = B.KIND_CN

WARN = "LOW_CONFIDENCE_WARNING"
# 绿底阈值。定 0.85 而非 0.90 的原因：VLM 自报分数被压缩在 0.9 以上，
# 合成后大量正确行正好压 0.90 边界（如 V101 det=0.857 → 0.90），
# 0.90 会把它们和真错行混在一起。左侧有图，人扫一眼很快，放宽更划算。
THRESH = 0.85

# 减号家族。U+2212 是数学减号，PDF 里普遍用它表示负号；
# Excel 按 GBK 解码时它和 °、µ 一起变 ?，所以统一转 ASCII 再谈别的。
MINUS = "\u2212\u2010\u2011\u2012\u2013\u2014\u2015\uff0d"


def unify(s):
    """统一减号与不换行空格。只动标点，不动字母和单位。"""
    s = s or ""
    for ch in MINUS:
        s = s.replace(ch, "-")
    return s.replace("\u00a0", " ").strip()


def _tok(t, txt):
    """t 是否作为独立记号出现在 txt 里（避免 VID 命中 DIVIDE 这类子串）。"""
    if not t:
        return False
    return re.search(r"(?<![A-Za-z0-9])" + re.escape(t) + r"(?![A-Za-z0-9])",
                     txt) is not None


def clean_symbol(sym, txt):
    """把模型写的 symbol 收敛成"照抄 PDF"的形式。

    规则按证据强度从高到低：
      1) 含空格或超过 12 字符 → 根本不是符号（是短语/引脚组/范围表达式），留空；
         用户明确要求"太长就留空，不要硬塞"，`V_S− to V_S+`、
         `PVSS_x/REFGND/DCDC_AGND_x/DAC_AGND_x to PBKG` 都属于这类。
      2) 原样能在本页找到 → 保留（少数手册真的写下划线）。
      3) 去掉下划线后能在本页找到 → 下划线是模型加的，用页面形态。
         V097 页面上是 `VID`，模型写 `V_ID`，走这条纠正。
      4) 页面用下标排版、抽取时被空格断开（`V OS`）→ 压掉空白再比一次。
      5) 都没命中 → 保持原样，不猜。
    """
    s = re.sub(r"\s+", " ", unify(sym))
    if not s:
        return ""
    if " " in s or len(s) > 12:
        return ""
    if _tok(s, txt):
        return s
    bare = s.replace("_", "")
    if _tok(bare, txt):
        return bare
    flat = re.sub(r"\s+", "", txt).lower()
    if bare and bare.lower() in flat:
        return bare
    return s


# 常见符号 → 参数名。VLM 有时把符号原样当名字返回（V162 的 8 行全是 `V_OH`
# 这种），照着抄等于没有名字。这里只收手册里最标准的叫法，命不中就用符号本身填，
# 绝不留空白（PM 要求：参数名不能是空的，宁可重复也要能看出是哪一行）。
NAME_MAP = {
    "VIH": "High-level input voltage",
    "VIL": "Low-level input voltage",
    "VOH": "High-level output voltage",
    "VOL": "Low-level output voltage",
    "VIK": "Input clamp diode voltage",
    "VOD": "Differential output voltage",
    "VOS": "Input offset voltage",
    "IOS": "Output short-circuit current",
    "IIN": "Input current",
    "II": "Input current",
    "IO": "Output current",
    "VI": "Input voltage",
    "VO": "Output voltage",
    "VCC": "Supply voltage",
    "VDD": "Supply voltage",
    "VSS": "Ground",
    "GND": "Ground",
    "TA": "Operating free-air temperature",
    "TJ": "Junction temperature",
    "TSTG": "Storage temperature",
    "PDISS": "Power dissipation",
    "SNR": "Signal-to-noise ratio",
    "SINAD": "Signal-to-noise and distortion ratio",
    "NSD": "Noise spectral density",
    "TSETT": "Settling time",
}


def repair_name(r):
    """参数名不能是空白，也不能只是符号的复读机。

    判定：把名字里的下划线/空格去掉后与符号相同，就认为模型没给出名字。
    先用 NAME_MAP 补标准叫法，补不上就拿符号本身当名字，并记一笔待人工确认。
    """
    name = (r.get("parameter_name") or "").strip()
    sym = (r.get("symbol") or "").strip()
    key = re.sub(r"[_\s]", "", name).upper()
    if name and (not sym or key != re.sub(r"[_\s]", "", sym).upper()):
        return r
    mapped = NAME_MAP.get(re.sub(r"[_\s]", "", sym).upper())
    r["parameter_name"] = mapped or sym or "UNNAMED"
    r["_name_filled"] = True
    r["notes"] = (r.get("notes", "") + "；参数名由符号补，需人工确认").strip("；")
    return r


def clean_unit(u):
    """去掉单位尾巴上的括号备注（`mV (mV_p-p)` → `mV`），不猜温度换算。

    下划线不动：`V_DC` 这种形态虽然别扭，但它不影响数值核对，
    改了反而会牵动置信度里的"单位是否出现在本页"这一项。
    """
    s = re.sub(r"\s+", " ", unify(u))
    if not s:
        return ""
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s)
    if " " in s:
        s = s.split()[0]
    return s


def sanitize_row(r, txt):
    """就地清理一行草稿的 symbol / unit，并记下"是我们清空的"这个事实。

    被清空的原文不直接丢掉：像 `VPOS_IN_x to PBKG`、`AVDD, IOVDD` 这类
    其实是这一行的引脚条件，挪进 condition 列才不丢身份；那一列本来
    就为空，且不影响置信度公式。
    """
    raw_sym = r.get("symbol") or ""
    r["symbol"] = clean_symbol(raw_sym, txt)
    cleared = bool(raw_sym.strip()) and not r["symbol"]
    r["_sym_cleared"] = cleared
    if cleared:
        phrase = re.sub(r"\s+", " ", unify(raw_sym)).strip()
        if phrase and not (r.get("condition") or "").strip() and len(phrase) <= 60:
            r["condition"] = phrase
            r["notes"] = (r.get("notes", "")
                          + "；symbol 过长已留空，原文移入 condition").strip("；")
        else:
            r["notes"] = (r.get("notes", "") + "；symbol 已按规则留空").strip("；")
    r["unit"] = clean_unit(r.get("unit") or "")
    return r


def det_score(doc, r, cache):
    """确定性证据分（0-1）。每一项都能被人复算，不依赖模型自报。"""
    import validate_annotation as V

    try:
        pno = int(r["evidence_page"])
    except (TypeError, ValueError):
        return 0.30
    if pno not in cache:
        cache[pno] = V.collapse(doc.load_page(pno - 1).get_text("text"))
    txt = cache[pno]

    vals = [r.get("min_value"), r.get("typ_value"), r.get("max_value")]
    vals = [v for v in vals if v]
    hit = 0
    for v in vals:
        rx = V.num_pattern(v)
        if rx and rx.search(txt):
            hit += 1

    s = 0.50
    if vals and hit == len(vals):
        s += 0.25
    elif hit:
        s += 0.10
    else:
        s -= 0.10
    unit = (r.get("unit") or "").strip()
    if unit and V.normalize(unit) in V.normalize(txt):
        s += 0.10
    sym = (r.get("symbol") or "").strip()
    # 允许下划线：`V_IH` 是手册里的真实写法，不该因为带下划线就不算符号。
    if sym and re.fullmatch(r"[A-Za-zΔ][A-Za-z0-9()/_\-±.Δ]{1,11}", sym):
        s += 0.05
    name = (r.get("parameter_name") or "").strip()
    if 6 <= len(name) <= 60:
        s += 0.05
    # 把条件当参数名是典型的坏行（如 "VCC = 2.7 V, II = -18 mA"）
    if "=" in name:
        s -= 0.15
    if not name:
        s -= 0.20
    # 我们自己按规则清空的 symbol 不再倒扣，否则等于因为规范化而二次惩罚
    if not sym and not r.get("_sym_cleared"):
        s -= 0.05
    return max(0.0, min(1.0, s))


def score_rows(doc, rows):
    """给行补置信度。最终分 = 确定性证据分（可复算）。

    视觉模型自报的 confidence 不进公式：实测它恒为 1.00（原图每行都是），
    掺进去只会给所有行统一加 0.3，反而抹平区分度。它仍然写进 notes 备查。
    """
    cache = {}
    for r in rows:
        det = det_score(doc, r, cache)
        r["confidence_score"] = "%.2f" % round(min(0.95, det), 2)
        if det < THRESH and WARN not in r.get("notes", ""):
            r["notes"] = (r.get("notes", "") + " | " + WARN).strip(" |")
    return rows


def page_text(page):
    """整页文本（压成单空格形式），供 symbol / unit 逐项核对。"""
    import validate_annotation as V
    return V.collapse(page.get_text("text"))


def lines_in_rect(page, rect):
    """把区域内文字按视觉行抓出来，供右侧点击。

    去重：伪粗体 PDF 会把同一串画两遍，dict 里会出现完全相同的相邻 span，
    连续相同即跳过（否则右侧会显示 `VVIIOO`）。
    """
    out = []
    for blk in page.get_text("dict")["blocks"]:
        if blk.get("type") != 0:
            continue
        for ln in blk["lines"]:
            x0, y0, x1, y1 = ln["bbox"]
            if y1 < rect.y0 - 1 or y0 > rect.y1 + 1:
                continue
            if x1 < rect.x0 - 2 or x0 > rect.x1 + 2:
                continue
            buf, prev = [], None
            for sp in ln["spans"]:
                t = sp["text"]
                if t == prev:
                    continue
                buf.append(t)
                prev = t
            txt = " ".join("".join(buf).split())
            if len(txt) < 2:
                continue
            out.append((round(y0, 1), round(x0, 1), txt))
    out.sort()
    ded = []
    for item in out:
        if ded and ded[-1][2] == item[2] and abs(ded[-1][1] - item[1]) < 2:
            continue
        ded.append(item)
    return [t for _, _, t in ded]


def render_band(page, heading_y, bbox, png):
    """裁剪表格区域并返回 rect。"""
    rect, used = B.render_clip(page, heading_y, bbox, png)
    return rect, used


JS = (PREP / "_b2_app.js").read_text(encoding="utf-8")


def build_js(rows):
    """把草稿行注入前端，并把阈值一起带过去（避免两边各写一个 0.85）。"""
    import json

    slim = []
    for r in rows:
        slim.append({k: r.get(k, "") for k in COLS})
    payload = json.dumps(slim, ensure_ascii=False).replace("</", "<\\/")
    return (JS.replace("__DRAFT__", payload)
              .replace("__THRESH__", "%.2f" % THRESH))






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
        path = Path(meta["file_path"])
        pdf_url = "file:///" + str(path).replace("\\", "/")

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
                          "pdf": pdf_url, "panes": [], "rows": [],
                          "quality": "特殊样本", "note": why})
            continue

        doc = fitz.open(str(path))
        hits, nav = B.scan(doc, npages)
        out_dir = REPORTS / sno
        out_dir.mkdir(parents=True, exist_ok=True)

        panes = []
        for kind in ("AMR", "ELC"):
            if not nav.get(kind):
                continue
            withrows = [c for c in nav[kind] if c[3] > 0]
            if withrows:
                pno, hy, bb, _n = max(withrows, key=lambda c: (c[3], -c[0]))
            else:
                pno, hy, bb, _n = min(nav[kind], key=lambda c: c[0])
            png = out_dir / ("b2_%s_p%04d.png" % (kind, pno))
            page = doc.load_page(pno - 1)
            rect, used = render_band(page, hy, bb, png)
            lines = lines_in_rect(page, rect)
            vrows, vmeta = [], {}
            try:
                vrows, vmeta = vl_extract(png)
            except Exception as e:
                vmeta = {"error": "%s: %s" % (type(e).__name__, e)}

            pane_rows = []
            ptxt = page_text(page)
            for vr in vrows:
                row = {
                    "sample_no": sno, "file_name": fname,
                    "evidence_page": str(pno), "table_title": KIND_CN[kind],
                    "symbol": vr["symbol"],
                    "parameter_name": vr["parameter_name"],
                    "min_value": vr["min_value"], "typ_value": vr["typ_value"],
                    "max_value": vr["max_value"], "unit": vr["unit"],
                    "condition": "",
                    "row_status": "DRAFT_AWAITING_HUMAN_CONFIRM",
                    "notes": "Qwen-VL 预标注，需与左图核对",
                    "reviewer": ""}
                row["notes"] += "；vlm自报=%.2f" % vr["vlm_confidence"]
                pane_rows.append(row)

            if not pane_rows:
                pane_rows = B.to_rows(sno, fname, kind, hits.get(kind, []))
                for r in pane_rows:
                    r["notes"] = (r.get("notes", "")
                                  + "；视觉模型无结果，退回文本表格解析").strip("；")

            # 先把 symbol / unit 收敛成"照抄 PDF"的形态，再算分；
            # 否则会拿模型编出来的 `V_ID` 去和页面比，白扣分。
            for r in pane_rows:
                sanitize_row(r, ptxt)
                repair_name(r)
            rows_out.extend(pane_rows)

            panes.append({"kind": kind, "pno": pno,
                          "rel": png.relative_to(PREP).as_posix(),
                          "bbox": used, "lines": lines,
                          "vmeta": vmeta, "use_vl": bool(vrows),
                          "span": sorted({n[0] for n in nav[kind]})})
        mine = [r for r in rows_out if r["sample_no"] == sno]
        score_rows(doc, mine)          # 必须在 doc.close() 之前算
        doc.close()

        my_rows = [r for r in rows_out if r["sample_no"] == sno]
        good = sum(1 for r in my_rows if r["symbol"] and r["unit"])
        nlines = sum(len(p["lines"]) for p in panes)
        if not panes:
            quality = "未定位"
            note = "前 %d 页未找到 AMR/ELC 标题，需人工翻查" % B.MAX_SCAN_PAGES
        elif nlines == 0:
            quality = "无文本层"
            note = ("页面里抓不到任何文字（纯图形/扫描），无法直出文本；"
                    "建议整件在 Excel 里标 EXCLUDED: 无 OCR 能力，无法建立 Gold")
        elif good >= len(my_rows) - 1:
            quality, note = "好", "表格已定位，可左侧看版式、右侧点行录入"
        else:
            quality = "一般"
            note = "表格已定位，右侧点行录入即可，机器草稿仅作参考"
        cards.append({"sno": sno, "fname": fname, "npages": npages,
                      "pdf": pdf_url, "panes": panes, "rows": my_rows,
                      "quality": quality, "note": note})

    # utf-8-sig：带 BOM 的 UTF-8。Excel 靠 BOM 判断编码，
    # 少了它会把 ° µ − 当无法映射字符显示成 ?（中文 Windows 默认按 GBK 解码）。
    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        for r in rows_out:
            w.writerow({k: r.get(k, "") for k in COLS})

    # ---------------- HTML ----------------
    p = []
    p.append('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">')
    p.append("<title>Batch 2 圈选台（左图右文）</title>")
    p.append("<style>%s%s</style></head><body>"
             % (B.CSS, EXTRA_CSS))
    p.append("<header><h1>Batch 2 圈选台 · %d 件</h1>" % len(cards))
    p.append("<p>左边是原图，右边是同区域抓出的纯文本。点一行文本，"
             "自动解析数字与单位并填进下方表格；表里每格都能改。</p></header>")
    p.append('<div class="wrap">')

    p.append('<div class="note"><h2>怎么用</h2><ul>'
             "<li>页面最下面的表格<b>已经载入机器草稿</b>，不用从零录入。</li>"
             "<li>对着左边的图，把每行核一遍：数值对不对、单位对不对、参数名是否说得清。</li>"
             "<li>核过的行把状态改成 <code>CONFIRMED</code>；说不清的行改成 "
             "<code>UNRESOLVED</code>；确认这行不是参数（表头、注释）就直接删掉。</li>"
             "<li><b>缺值不用去右边点</b>：草稿行里直接输入就行。"
             "右边有些行只有数字（表格里数字和标签不在同一条基线上），点它不会建行。</li>"
             "<li>草稿没覆盖的参数，用「新增空行」自己写一行。</li>"
             "<li>每件留 <b>3~5 个</b>最显眼的参数就够，不需要整表全录。</li>"
             "<li>最后按「下载 CSV」。<b>不要用 Excel 另存</b>，会把编码变成 GBK。</li>"
             "<li>换新版本页面时，用「导入上次的 CSV」把进度接回来，不用重做。</li>"
             "</ul>"
             '<div class="hint">黄底行是 min/typ/max 全空的；'
             "确认了却没有数值的行、以及既无参数名又无符号的行，导出时会拦下来。</div></div>")

    for c in cards:
        p.append('<div class="card"><div class="head">')
        p.append('<span class="sn">%s</span><span class="fn">%s</span>'
                 % (B.esc(c["sno"]), B.esc(c["fname"])))
        p.append('　<a href="%s" target="_blank">在 PDF 中打开</a>' % B.esc(c["pdf"]))
        cls = "t-ok" if c["quality"] == "好" else "t-warn"
        tags = ['<span class="tag %s">草稿：%s</span>' % (cls, B.esc(c["quality"]))]
        for pn in c["panes"]:
            tags.append('<span class="tag %s">%s = p%s</span>'
                        % ("t-amr" if pn["kind"] == "AMR" else "t-elc",
                           pn["kind"], "/".join(str(x) for x in pn["span"])))
        p.append('<div class="meta">共 %d 页 　%s</div>' % (c["npages"], "".join(tags)))
        p.append('<div class="meta">%s</div>' % B.esc(c["note"]))
        p.append('</div><div class="body">')

        if c["quality"] == "无文本层":
            p.append('<div class="err">本页抓不到任何文字（纯图形/扫描件）。'
                     "无法直出文本，请整件标 "
                     "<code>EXCLUDED: 无 OCR 能力，无法建立 Gold</code>。</div>")
        for pn in c["panes"]:
            p.append('<div class="pane" data-sno="%s" data-fn="%s" data-page="%d" '
                     'data-title="%s">'
                     % (B.esc(c["sno"]), B.esc(c["fname"]), pn["pno"],
                        B.esc(KIND_CN[pn["kind"]])))
            p.append('<div class="cols"><div class="left">'
                     '<a href="%s" target="_blank"><img src="%s" alt="%s p%d"></a>'
                     '<div class="cap">%s · 第 %d 页%s</div></div>'
                     % (B.esc(pn["rel"]), B.esc(pn["rel"]), B.esc(c["sno"]),
                        pn["pno"], B.esc(KIND_CN[pn["kind"]]), pn["pno"],
                        "（按表格边框裁剪）" if pn["bbox"] else "（按标题位置裁剪）"))
            p.append('<div class="right"><div class="rh">点下面任意一行 → 自动填字段'
                     '<span class="cnt">%d 行</span></div><ol class="lines">'
                     % len(pn["lines"]))
            for ln in pn["lines"]:
                p.append('<li class="line" data-t="%s">%s</li>'
                         % (B.esc(ln), B.esc(ln)))
            p.append("</ol></div></div></div>")

        if c["rows"]:
            p.append('<div class="dh">本件草稿 %d 行，已载入下方编辑区（'
                     '<span class="pill ok">绿 ≥%.2f</span> '
                     '<span class="pill low">红 &lt;%.2f 需对图看</span>）</div>'
                     % (len(c["rows"]), THRESH, THRESH))

        p.append("</div></div>")

    p.append('<div class="work"><h2>标注编辑区　<span id="cnt">0</span></h2>')
    p.append('<div class="filter">'
             '<label>样本 <select id="fsample"></select></label>'
             '<label><input type="checkbox" id="fnum"> 只看有数值的行</label>'
             '<label><input type="checkbox" id="ftodo"> 只看未确认的行</label>'
             '<button class="ghost" onclick="addBlank()">新增空行</button>'
             '<button class="ghost" onclick="dropNoName()">删掉无参数名的行</button>'
             '<button class="ghost" onclick="cleanEmpty()">删掉本样本无值行</button>'
             '<button class="ghost" onclick="resetDraft()">恢复机器草稿</button>'
             '<label class="imp">导入上次的 CSV <input type="file" id="fimp" accept=".csv"></label>'
             "</div>")
    p.append('<div id="stat" class="stat"></div>')
    p.append('<table class="rows" id="tbl"><thead><tr>'
             "<th>样本</th><th>页</th><th>符号</th><th>参数名</th><th>min</th>"
             "<th>typ</th><th>max</th><th>单位</th><th>状态</th><th>草稿分</th>"
             "<th></th></tr></thead>"
             '<tbody id="tbody"></tbody></table>')
    p.append('<div class="bar"><button onclick="downloadCSV()">下载 CSV（UTF-8 带 BOM）</button>'
             '<button onclick="copyOut()" class="dl">复制 CSV</button> '
             '<label style="font-size:12.5px;margin-left:8px">'
             '<input type="checkbox" id="dropEmpty" checked> 导出时丢掉无值行/无参数名行</label>'
             '<span id="msg" class="msg"></span></div>')
    p.append('<textarea id="out" readonly></textarea>')
    p.append("</div>")

    p.append("</div><script>%s</script></body></html>" % build_js(rows_out))
    OUT_HTML.write_text("".join(p), encoding="utf-8", newline="\n")

    print("圈选台: %s (%.1f KB, %d 件)" % (OUT_HTML.name,
                                            OUT_HTML.stat().st_size / 1024, len(cards)))
    print("草稿  : %s (%d 行)" % (OUT_CSV.name, len(rows_out)))
    for c in cards:
        nl = sum(len(pn["lines"]) for pn in c["panes"])
        print("  %-5s %-8s panes=%d 文本行=%-4d %s"
              % (c["sno"], c["quality"], len(c["panes"]), nl, c["note"][:38]))
    return 0


EXTRA_CSS = """
.dh{font-size:12px;color:#444;margin:6px 0 6px}
.pill{display:inline-block;padding:1px 7px;border-radius:3px;font-size:11px;
 font-weight:600;margin-right:4px}
.pill.ok{background:#e9f6ec;color:#1c6b33;border:1px solid #c3e3cc}
.pill.low{background:#fdeceb;color:#a12a20;border:1px solid #f3c9c5}
tr.conf-ok td{background:#f3faf4}
tr.conf-low td{background:#fdf3f2}
tr.empty-row td{background:#fff8e6;color:#8a6d3b}
tr.empty-row input{background:#fffdf5}
tr.clicked td.sn::after{content:" ·点";color:#0b5cad;font-size:10px}
.warn{color:#a12a20;font-size:10.5px;font-weight:600}
.filter{display:flex;gap:14px;align-items:center;flex-wrap:wrap;
 font-size:12.5px;background:#f4f6f9;border:1px solid #dfe3e8;
 border-radius:4px;padding:8px 10px;margin-bottom:10px}
.filter select{font-size:12.5px;padding:3px 6px;border:1px solid #cfd5dd;border-radius:3px}
.filter label{display:inline-flex;align-items:center;gap:4px;cursor:pointer}
.stat{font-size:12px;color:#444;margin:6px 0 10px}
.stat.bad{color:#a12a20;font-weight:600}
.filter .imp{font-size:12px;color:#0b5cad;border:1px dashed #b9cde4;
 border-radius:4px;padding:5px 9px;cursor:pointer}
.filter .imp input{display:none}
button.mini{background:#fff;border:1px solid #d8b4b0;color:#a12a20;
 border-radius:3px;font-size:11px;padding:2px 7px;cursor:pointer}
button.ghost{background:#fff;color:#44536a;border:1px solid #cfd5dd;border-radius:4px;
 padding:7px 12px;font-size:12.5px;cursor:pointer;margin-left:6px}
td.cf{font-size:11px;color:#666}
.cols{display:flex;gap:14px;align-items:flex-start;margin-bottom:14px}
.cols .left{flex:0 0 56%;min-width:0}
.cols .right{flex:1 1 auto;min-width:0}
.cols img{width:100%;height:auto;border:1px solid #cfd3d9;display:block}
.cap{font-size:12px;color:#666;padding-top:4px}
.rh{font-size:12px;color:#444;background:#f4f6f9;border:1px solid #dfe3e8;
 border-bottom:0;padding:5px 8px;border-radius:4px 4px 0 0}
.cnt{float:right;color:#888}
ol.lines{margin:0;padding:4px 0;list-style:none;border:1px solid #dfe3e8;
 max-height:520px;overflow:auto;background:#fff;border-radius:0 0 4px 4px}
ol.lines li{padding:3px 8px;font-size:12.5px;font-family:Consolas,monospace;
 cursor:pointer;border-bottom:1px dotted #eef0f3;white-space:pre-wrap}
ol.lines li:hover{background:#e8f0fb}
ol.lines li.picked{background:#e6f4ea}
.pane{margin:0 0 18px}
.err{background:#fdeceb;border:1px solid #f3c9c5;color:#a12a20;
 padding:10px 14px;border-radius:5px;font-size:13px;margin-bottom:12px}
.work{background:#fff;border:1px solid #dcdfe4;border-radius:6px;padding:14px 16px;margin-top:8px}
.work h2{margin:0 0 10px;font-size:15px}
table.rows input{width:100%;border:1px solid #e2e5ea;padding:3px 5px;font-size:12px}
table.rows select{width:100%;border:1px solid #e2e5ea;font-size:11.5px;padding:3px}
table.rows td.num input{text-align:right;font-family:Consolas,monospace}
.bar{margin:10px 0 6px}
.bar button{background:#0b5cad;color:#fff;border:0;border-radius:4px;
 padding:7px 16px;font-size:13px;cursor:pointer}
.bar button.dl{background:#fff;color:#0b5cad;border:1px solid #b9cde4;margin-left:6px}
.msg{margin-left:10px;font-size:12px;color:#2c6b34}
#out{width:100%;height:110px;font-family:Consolas,monospace;font-size:11.5px;
 border:1px solid #dfe3e8;border-radius:4px;padding:8px;background:#fbfcfd}
"""


if __name__ == "__main__":
    raise SystemExit(main())
