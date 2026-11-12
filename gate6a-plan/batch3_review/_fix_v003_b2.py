# -*- coding: utf-8 -*-
"""V003 抓错页：定向重截 + 重出草稿 + 重建 B2 圈选台。

背景（Reviewer 反馈）
--------------------
「V003 抓错页了，这页是纯文字术语解释，没有参数。」
B2 草稿里 V003 的 5 行全部来自 p14，内容是 "PULL UP/DOWN TYPE"、
"PU: Internal pull-up" 等 Pin Attributes 术语解释，不是参数表。

根因（三处叠加，已在 _build_batch3_interactive.py 修掉）
--------------------------------------------------------
1. scan3 只扫前 40 页；AM2431BSDFHIALXR__am2431.pdf 共 282 页，
   真正的参数表在第 6 章 Specifications（p101~p116）。
2. 宽松标题正则把 p14 正文里的章节交叉引用
   "For more information, see the hysteresis values in Electrical Characteristics."
   当成表标题。该页连一个 MIN/TYP/MAX 列词都没有。
3. pick_core 没有「零核心命中」闸门，把 5 行无数值的术语条目凑数落盘，
   还伪装成 low_confidence 草稿交给人。

本脚本只修 V003 一件：不重跑 VLM、不动 B2 其余 5 件、不碰已定稿 B1。
5 行草稿全部由 PDF 文本层定向抽取（非 VLM），逐项做「证据页原文断言」：
任一数值 / 参数名 / 单位 / 条件在对应页找不到，直接拒绝生成，
绝不把猜测写进草稿。
"""
from __future__ import print_function

import csv
import json
import re
from pathlib import Path

import fitz

import _build_batch2_viewer as B
import _build_batch2_interactive as I2
import _build_batch3_interactive as I3
import _draft_extract as X

PREP = Path(__file__).resolve().parent
DRAFT = PREP / "Batch3_B2_DRAFT.csv"
HTML = PREP / "Batch3_B2_Viewer.html"
DIAG = PREP / "Batch3_V003_diagnosis.txt"
REPORTS = PREP / "annotation_reports" / "V003"
PDF = Path(r"E:\workspace\IcPdfParser\data\pdfs\AM2431BSDFHIALXR__am2431.pdf")
SNO = "V003"
FNAME = PDF.name
EXPORT_NAME = "Batch3_B2_ANNOTATED"

# 减号家族：PDF 里 TJ 用的是 U+2013 EN DASH（–40），与验证器 MINUS 常量同源。
MINUS = "-\u2212\u2013\u2014"


def norm(s):
    """把各种横杠统一成 ASCII 减号并折叠空白，专用于「原文能否找到」断言。"""
    s = "".join("-" if c in MINUS else c for c in (s or ""))
    return " ".join(s.split())


# 三张正确表格图。hy 是该页标题/表框上沿的实测 y（pt），bbox 由 find_tables() 取。
PANES = [
    dict(kind="AMR", pno=101, hy=98.0, css="t-amr",
         title="Absolute Maximum Ratings", cap="6.1 Absolute Maximum Ratings"),
    dict(kind="ROC", pno=105, hy=75.0, css="t-elc",
         title="Recommended Operating Conditions", cap="6.4 Recommended Operating Conditions"),
    dict(kind="ROC", pno=106, hy=83.0, css="t-elc",
         title="Recommended Operating Conditions（续表）",
         cap="6.4 Recommended Operating Conditions（续表，含 TJ）"),
]

# 5 行核心草稿。每个字段都必须能在 evidence_page 的原文里逐字（规范化后）找到。
# 来源：p101 AMR 表、p105/p106 ROC 表，均为 get_text("text") 的原生列。
SPEC = [
    dict(page=105, title="Recommended Operating Conditions",
         symbol="VDD_CORE", name="Core supply",
         mn="0.81", typ="0.85", mx="0.895", unit="V",
         cond="Recommended Operating Conditions",
         extra="MIN(1)/NOM/MAX(1) 三列；NOM 是否等同 typ 请人工确认"),
    dict(page=105, title="Recommended Operating Conditions",
         symbol="VDDR_CORE", name="RAM supply",
         mn="0.81", typ="0.85", mx="0.895", unit="V",
         cond="Recommended Operating Conditions",
         extra="MIN(1)/NOM/MAX(1) 三列；NOM 是否等同 typ 请人工确认"),
    dict(page=106, title="Recommended Operating Conditions",
         symbol="VDDSHV5", name="Dual-voltage IO supply",
         mn="1.71", typ="1.8", mx="1.89", unit="V",
         cond="1.8V Operation",
         extra="同一符号另有 3.3V Operation（3.135/3.3/3.465 V），本行只取 1.8V 模式"),
    dict(page=106, title="Recommended Operating Conditions",
         symbol="TJ", name="Operating junction temperature range",
         mn="-40", typ="", mx="125", unit="\u00b0C",
         cond="125\u00b0C Industrial",
         extra="原文为 –40 / 125（EN DASH），已按验证器 MINUS 规则写作 -40"),
    dict(page=101, title="Absolute Maximum Ratings",
         symbol="VDD_CORE", name="Core supply",
         mn="-0.3", typ="", mx="1.05", unit="V",
         cond="6.1 Absolute Maximum Ratings",
         extra="绝对最大额定值，与 p105 的推荐工作条件 0.81/0.85/0.895 V 不是同一概念，勿混"),
]

NOTE_BASE = ("文本层定向抽取（非 VLM）：原 p14 是 Pin Attributes 术语解释页（无参数），"
             "已按第 6 章 Specifications 重定位；须对左图复核 | low_confidence")
CONF = "0.60"      # < THRESH 0.85，前端整件标红，强制人工过一遍

# 事故现场固定留证。诊断报告不依赖 CSV 当前内容，重跑也不会把「旧草稿」
# 写成修复后的行（否则实证就失真了）。
OLD_V003_EVIDENCE = [
    "p14  13     PULL UP/DOWN TYPE: Indicates the presence of an internal    conf=0.40  low_confidence",
    "p14         • PU: Internal pull-up                                       conf=0.40  low_confidence",
    "p14         • PD: Internal pull-down                                      conf=0.40  low_confidence",
    "p14         • PU/PD: Internal pull-up and pull-down                       conf=0.40  low_confidence",
    "p14         • An empty box means No internal pull.                        conf=0.40  low_confidence",
]


def assert_evidence(doc, spec):
    """一行草稿的每个证据字段都必须在它自己的 evidence_page 原文里找得到。

    这是本脚本最重要的一道闸：宁可拒绝生成，也不把猜出来的数写进草稿。
    """
    pno = spec["page"]
    ptext = norm(doc.load_page(pno - 1).get_text("text"))
    checks = [("参数名", spec["name"]), ("单位", spec["unit"]),
              ("条件", spec["cond"])]
    for label, v in checks:
        if not v.strip():
            continue
        if norm(v) not in ptext:
            raise AssertionError("p%d 原文找不到%s %r，拒绝生成" % (pno, label, v))
    for label, k in (("min", "mn"), ("typ", "typ"), ("max", "mx")):
        v = spec[k].strip()
        if v and norm(v) not in ptext:
            raise AssertionError("p%d 原文找不到 %s=%r，拒绝生成" % (pno, label, v))
    sym = spec["symbol"].strip()
    if sym and sym not in doc.load_page(pno - 1).get_text("text"):
        raise AssertionError("p%d 原文找不到符号 %r，拒绝生成" % (pno, sym))
    return True


def make_row(spec):
    return {
        "sample_no": SNO, "file_name": FNAME,
        "evidence_page": str(spec["page"]), "table_title": spec["title"],
        "symbol": spec["symbol"], "parameter_name": spec["name"],
        "min_value": spec["mn"], "typ_value": spec["typ"],
        "max_value": spec["mx"], "unit": spec["unit"],
        "condition": spec["cond"],
        "row_status": "DRAFT_AWAITING_HUMAN_CONFIRM",
        "notes": NOTE_BASE + "；" + spec["extra"],
        "reviewer": "", "confidence_score": CONF,
    }


def render_panes(doc):
    """重截三张真表图，并返回 (pane 信息, 每张图的文本行)。"""
    REPORTS.mkdir(parents=True, exist_ok=True)
    old = REPORTS / "b3_ELC_p0014.png"
    if old.exists():
        old.unlink()          # 旧错页裁图：不留，免得审计包里又被人当成证据
    info = []
    for pn in PANES:
        page = doc.load_page(pn["pno"] - 1)
        bbs = X.table_bboxes(page)
        bb = min(bbs, key=lambda b: b[1]) if bbs else None
        png = REPORTS / ("b3_%s_p%04d.png" % (pn["kind"], pn["pno"]))
        rect, used = B.render_clip(page, pn["hy"], bb, png)
        lines = I2.lines_in_rect(page, rect)
        pn = dict(pn)
        pn.update(rel=png.relative_to(PREP).as_posix(),
                  bbox=used, lines=lines, size=png.stat().st_size)
        info.append(pn)
        print("  裁图 p%-4d %-38s %3d 行文本 %7d 字节 表格框=%s"
              % (pn["pno"], png.name, len(lines), pn["size"], "有" if used else "无"))
    return info


def build_card(panes, note):
    """按主生成器的同一套 DOM 结构，单独重画 V003 卡片。"""
    h = []
    h.append('<div class="card"><div class="head">')
    h.append('<span class="sn">%s</span><span class="fn">%s</span>'
             % (B.esc(SNO), B.esc(FNAME)))
    h.append('　<a href="file:///%s" target="_blank">在 PDF 中打开</a>'
             % B.esc(str(PDF).replace("\\", "/")))
    tags = ['<span class="tag t-warn">草稿：需重点看</span>',
            '<span class="tag t-amr">AMR = p101</span>',
            '<span class="tag t-elc">ROC = p105/p106</span>']
    h.append('<div class="meta">共 282 页 　%s</div>' % "".join(tags))
    h.append('<div class="meta">%s</div>' % B.esc(note))
    h.append('</div><div class="body">')
    for pn in panes:
        h.append('<div class="pane" data-sno="%s" data-fn="%s" data-page="%d" '
                 'data-title="%s">'
                 % (B.esc(SNO), B.esc(FNAME), pn["pno"], B.esc(pn["title"])))
        h.append('<div class="cols"><div class="left">'
                 '<a href="%s" target="_blank"><img src="%s" alt="%s p%d"></a>'
                 '<div class="cap">%s · 第 %d 页%s</div></div>'
                 % (B.esc(pn["rel"]), B.esc(pn["rel"]), B.esc(SNO),
                    pn["pno"], B.esc(pn["cap"]), pn["pno"],
                    "（按表格边框裁剪）" if pn["bbox"] else "（按标题位置裁剪）"))
        h.append('<div class="right"><div class="rh">点下面任意一行 → 自动填字段'
                 '<span class="cnt">%d 行</span></div><ol class="lines">'
                 % len(pn["lines"]))
        for ln in pn["lines"]:
            h.append('<li class="line" data-t="%s">%s</li>'
                     % (B.esc(ln), B.esc(ln)))
        h.append("</ol></div></div></div>")
    h.append('<div class="dh">本件核心草稿 5 行（另有 0 行非核心未载入）；'
             '<span class="pill ok">绿 ≥%.2f</span> '
             '<span class="pill low">红 &lt;%.2f = low_confidence</span></div>'
             % (I2.THRESH, I2.THRESH))
    h.append("</div></div>")
    return "".join(h)


def replace_card(text, new_card):
    """只换 V003 的 <div class="card"> 块，其余 5 件一字不动。"""
    i = text.find('class="sn">V003')
    if i < 0:
        raise AssertionError("HTML 里找不到 V003 卡片")
    s = text.rfind('<div class="card">', 0, i)
    e = text.find('<div class="card">', i)
    if e < 0:
        e = text.find('<div class="work">', i)
    if s < 0 or e < 0:
        raise AssertionError("V003 卡片边界定位失败")
    return text[:s] + new_card + text[e:]


def main():
    doc = fitz.open(str(PDF))
    npages = doc.page_count
    print("PDF: %s  共 %d 页" % (FNAME, npages))

    # 防呆：真表页必须落在修复后生成器的全书候选页里。
    cand = I3.prescan3(doc, npages)
    print("修复后全书候选页(%d): %s" % (len(cand), cand))
    assert 14 not in cand, "p14 术语解释页不应再入候选"
    for s in SPEC:
        assert s["page"] in cand, "p%d 不在候选页里，拒绝出草稿" % s["page"]
        assert_evidence(doc, s)
    print("5 行草稿逐字段原文断言：全部通过")

    panes = render_panes(doc)
    new_rows = [make_row(s) for s in SPEC]

    # —— 1. CSV：只在原位置替换 V003 的 5 行，其余 25 行保持字节不变 ——
    with open(DRAFT, encoding="utf-8-sig", newline="") as fh:
        rd = csv.DictReader(fh)
        cols = list(rd.fieldnames)
        rows = list(rd)
    idx = [i for i, r in enumerate(rows) if r["sample_no"] == SNO]
    assert len(idx) == 5 and idx == list(range(idx[0], idx[0] + 5)), \
        "V003 草稿不是连续 5 行，拒绝盲改"
    old_v = rows[idx[0]:idx[0] + 5]
    pages = {r["evidence_page"] for r in old_v}
    if pages == {"14"}:
        state = "替换旧错页 5 行"
    elif pages == {"101", "105", "106"}:
        state = "已是修复版，按同一份 SPEC 幂等重写"
    else:
        raise AssertionError("V003 草稿页码状态异常：%s，拒绝盲改" % sorted(pages))
    out_rows = rows[:idx[0]] + new_rows + rows[idx[0] + 5:]
    assert len(out_rows) == len(rows), "总行数变了"
    with open(DRAFT, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in out_rows:
            w.writerow({k: r.get(k, "") for k in cols})
    print("CSV: %s  总 %d 行，%s（其余 %d 行未动）"
          % (DRAFT.name, len(out_rows), state, len(out_rows) - 5))

    # —— 2. HTML：换卡片 + 用同一份 CSV 重建 <script> ——
    text = HTML.read_text(encoding="utf-8")
    n_card_before = text.count('<div class="card">')
    n_img_before = text.count('<img src="')
    note = ("已重定位：原 p14 为 Pin Attributes 术语解释页（无参数）；"
            "现按第 6 章 Specifications 给出 5 行文本层定向草稿，"
            "5 行均 low_confidence，请先核 NOM→TYP 映射与 1.8V/3.3V 条件归属")
    new = replace_card(text, build_card(panes, note))

    js = I3.build_js(out_rows, EXPORT_NAME)
    new, n = re.subn(r"(<script>)(.*?)(</script>)",
                     lambda m: m.group(1) + js + m.group(3),
                     new, flags=re.S)
    assert n == 1, "<script> 段数不是 1"
    assert new.count('<div class="card">') == n_card_before == 6, "卡片数变了"
    assert new.count('<img src="') == n_img_before + 2, "图片引用数不对（1→3）"
    # 注意：V320 也有 b3_ELC_p0014.png（另一个目录），断言必须限定 V003 路径，
    # 同时反向断言 V320 的图没被误伤。
    assert "annotation_reports/V003/b3_ELC_p0014.png" not in new, "V003 旧错页图还在引用"
    assert "annotation_reports/V320/b3_ELC_p0014.png" in new, "误伤了 V320 的裁图"
    assert 'a.download = "Batch2_ANNOTATED.csv"' not in new, "导出名硬编码又回来了"
    assert "window.B3_EXPORT_NAME=%s;" % json.dumps(EXPORT_NAME) in new
    m = re.search(r"const DRAFT = (\[.*?\]);", new, re.S)
    assert m and len(json.loads(m.group(1))) == len(out_rows), "注入行数与 CSV 不一致"
    v003 = new[new.find('class="sn">V003'):]
    v003 = v003[:v003.find('<div class="card">') if '<div class="card">' in v003
                else v003.find('<div class="work">')]
    assert 'data-page="14"' not in v003, "V003 卡片里还留着 p14"
    assert 'data-page="101"' in v003 and 'data-page="105"' in v003 and 'data-page="106"' in v003
    HTML.write_text(new, encoding="utf-8", newline="\n")
    print("HTML: %s  %d 字节，卡片 %d 件，图片 %d 张，回归断言全过"
          % (HTML.name, len(new.encode("utf-8")), n_card_before,
             new.count('<img src="')))

    # —— 3. 诊断实证记录 ——
    DIAG.write_text(build_diag(npages, cand, panes, new_rows),
                    encoding="utf-8", newline="\n")
    doc.close()
    print("诊断实证: %s" % DIAG.name)
    return 0


def build_diag(npages, cand, panes, new_rows):
    L = []
    L.append("Batch 3 / B2 · V003 抓错页诊断与修复实证")
    L.append("=" * 62)
    L.append("")
    L.append("PDF   : %s" % FNAME)
    L.append("页数  : %d（PDF 页码与文件物理页码一致）" % npages)
    L.append("反馈  : 「V003 抓错页了，这页是纯文字术语解释，没有参数。」")
    L.append("")
    L.append("A. 旧草稿现场（Batch3_B2_DRAFT.csv 原 5 行）")
    L.append("-" * 62)
    for line in OLD_V003_EVIDENCE:
        L.append("  " + line)
    L.append("  5 行全部来自 p14，全部无数值，全部 low_confidence；")
    L.append("  旧的 5 行来自 Batch3_B2_DRAFT.csv 修复前，此处为固定留证，不随重跑变化。")
    L.append("")
    L.append("B. p14 原文（该页无任何参数）")
    L.append("-" * 62)
    L.append("  10. For more information, see valid operating voltage range(s) defined")
    L.append("      for each power supply in Recommended Operating Conditions.")
    L.append("  22. For more information, see the hysteresis values in Electrical Characteristics.")
    L.append("  24. 13. PULL UP/DOWN TYPE: Indicates the presence of an internal pull-up")
    L.append("      or pull-down resistor.")
    L.append("  27. • PU: Internal pull-up      29. • PD: Internal pull-down")
    L.append("  35. 14. BUFFER TYPE: ... which Electrical Characteristics table is applicable.")
    L.append("  该页是 Table 5-1 Pin Attributes 的**列说明**，不是参数表。")
    L.append("")
    L.append("C. 全文标题/表头扫描（282 页逐页 get_text，原样结果）")
    L.append("-" * 62)
    L.append("  p6    Table of Contents（AMR / ELC / ROC 三种标题同页 → 目录页）")
    L.append("  p14   正文交叉引用句命中 ELC 字样，但全页 0 个 MIN/TYP/MAX 列词")
    L.append("  p15~p56  Table 5-1 Pin Attributes（引脚表，非参数表）")
    L.append("  p101  6.1 Absolute Maximum Ratings        ← 真 AMR 表")
    L.append("  p102  6.1 续表（AMR/ELC/ROC 字样同页，旧目录判据会误杀）")
    L.append("  p105  6.4 Recommended Operating Conditions ← 真 ROC 表（供电）")
    L.append("  p106  6.4 续表（VDDSHV5、TJ 工作结温）")
    L.append("  p108~p115  6.7.x 各接口 Electrical Characteristics")
    L.append("  修复后 prescan3() 全书候选页共 %d 个：%s" % (len(cand), cand))
    L.append("  prescan3(..., max_pages=40)  → []  ← 旧版上限把真表整段漏掉")
    L.append("  14 in 全书候选 → False；101/105/106 in 全书候选 → True")
    L.append("")
    L.append("D. 根因（三处叠加）")
    L.append("-" * 62)
    L.append("  1. _build_batch3_interactive.scan3() 用 min(npages, B.MAX_SCAN_PAGES=40)")
    L.append("     截断了扫描范围，真表在 p101 之后，前 40 页一页参数表都没有。")
    L.append("  2. X.HEADING['ELC'] 是宽松正则，X.find_headings() 逐行匹配，")
    L.append("     把 p14 正文里的章节交叉引用句当成表标题；该页没有表头校验，")
    L.append("     parse_page 又把术语条目当 label 抽出来。")
    L.append("  3. pick_core() 排序后直接取前 5 行，没有「零核心命中」闸门，")
    L.append("     5 行无数值的术语条目凑数落盘，只被标成 low_confidence。")
    L.append("")
    L.append("E. 生成器修复（_build_batch3_interactive.py，后续批次生效）")
    L.append("-" * 62)
    L.append("  1. prescan3() 全书文本快筛：候选页必须同时有表标题词和")
    L.append("     ≥2 个 MIN/TYP/MAX/NOM 列词；scan3() 只解析候选页，不再限前 40 页。")
    L.append("  2. find_headings3() 要求标题是独立短行（≤90 字符）且不含")
    L.append("     see/refer/for more information/defined in/appropriate/table is 等引用词；")
    L.append("     目录页判定只在前 10 页生效，避免误杀 p102 这类续表。")
    L.append("  3. pick_core() 新增闸门：连一行「命中 CORE_ORDER 且带数值」都没有时")
    L.append("     整件不落草稿，quality=无法定位参数表，HTML 直接给 EXCLUDED 建议。")
    L.append("  实证：旧版 V003 5 行垃圾 → 新闸门 keep=0 / drop=5。")
    L.append("  已定稿 B1 不重跑、不改动；B2 其余 5 件不重跑、不改动。")
    L.append("")
    L.append("F. 重截的正确表格图（300 DPI，按表格边框裁剪）")
    L.append("-" * 62)
    for pn in panes:
        L.append("  p%-4d %-38s %3d 行文本 %8d 字节"
                 % (pn["pno"], Path(pn["rel"]).name, len(pn["lines"]), pn["size"]))
    L.append("  旧错页裁图 b3_ELC_p0014.png 已删除，HTML 不再引用。")
    L.append("")
    L.append("G. 新的 5 行核心草稿（文本层定向抽取，非 VLM）")
    L.append("-" * 62)
    for r in new_rows:
        L.append("  p%-4s %-10s %-38s min=%-6s typ=%-6s max=%-7s %-3s conf=%s"
                 % (r["evidence_page"], r["symbol"], r["parameter_name"][:38],
                    r["min_value"] or "-", r["typ_value"] or "-",
                    r["max_value"] or "-", r["unit"], r["confidence_score"]))
    L.append("  每一行都做了证据页原文断言：参数名、单位、条件、各数值、符号")
    L.append("  必须能在自己的 evidence_page 原文中逐字（横杠规范化后）找到，")
    L.append("  任一缺失即拒绝生成。")
    L.append("  row_status 一律 DRAFT_AWAITING_HUMAN_CONFIRM，reviewer 为空；")
    L.append("  conf=0.60 < 阈值 0.85，5 行全部标 low_confidence，必须人工点选。")
    L.append("")
    L.append("H. 仍需人工确认的点")
    L.append("-" * 62)
    L.append("  1. ROC 表头是 MIN(1) / NOM / MAX(1)；把 NOM 放进 typ_value 是否合适，")
    L.append("     必须由 Reviewer 定，机器不替人决定。")
    L.append("  2. VDDSHV5 同页还有 3.3V Operation（3.135/3.3/3.465 V），本行只取 1.8V。")
    L.append("  3. p101 的 VDD_CORE -0.3/1.05 V 是绝对最大额定值，")
    L.append("     与 p105 的推荐工作条件 0.81/0.85/0.895 V 不是同一概念。")
    L.append("  4. TJ 原文为 –40（U+2013），草稿按验证器 MINUS 规则写 -40。")
    L.append("")
    L.append("I. 产物变更")
    L.append("-" * 62)
    L.append("  Batch3_B2_DRAFT.csv      V003 的 5 行替换（总行数不变，其余 25 行未动）")
    L.append("  Batch3_B2_Viewer.html    V003 卡片重画 + <script> 按同一份 CSV 重建")
    L.append("  annotation_reports/V003/ 新增 3 张真表图，删除 1 张错页图")
    L.append("  _build_batch3_interactive.py  三道定位闸门")
    L.append("  _fix_v003_b2.py          本定向修复脚本")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
