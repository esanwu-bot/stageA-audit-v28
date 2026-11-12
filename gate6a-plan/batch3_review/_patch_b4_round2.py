# -*- coding: utf-8 -*-
"""B4 第二轮修补：条件绑定、非白名单标注、排除话术按事实分类、V077 高亮。

全部改动都用精确锚点 + 计数断言，锚点命中数不为 1 直接退出，不盲改。
"""
import pathlib

P = pathlib.Path(__file__).with_name("_build_batch3_interactive.py")
s = P.read_text(encoding="utf-8")

# ---------------------------------------------------------------- 1. 官方话术
ANCHOR_EXT_NOTE = 'EXT_NOTE = "非白名单核心参数（一等电气特性），WB 建议，请 PM 定夺"'
NEW_EXT_NOTE = '''EXT_NOTE = "非白名单核心参数（一等电气特性），WB 建议，请 PM 定夺"
EXT_PREFIX = "【非白名单参数·需 PM 决定是否纳入】"

# Reviewer 2026-11-12 定稿的三类排除话术。必须按事实分类，不能一刀切：
#   全书确实没有文本层       → OFF_EXCL_NOLAYER
#   只有电气特性页是扫描图   → OFF_EXCL_SCANPAGE
#   有文本层但版式还原不了行序 → OFF_EXCL_SMD
OFF_EXCL_NOLAYER = ("EXCLUDED: 全书无文本层；当前 Gate6A 流程无可用 OCR 取证路径，"
                    "无法建立可验证 Gold")
OFF_EXCL_SCANPAGE = ("EXCLUDED: 电气特性页为扫描图；当前 Gate6A 流程无可用 OCR "
                     "取证路径，无法建立可验证 Gold")
OFF_EXCL_SMD = ("EXCLUDED: 版式不支持稳定还原行序，当前流程无法建立可验证 Gold；"
                "需 SMD 专用规则后重评")'''

# ---------------------------------------------------------------- 2. condition
ANCHOR_CB = '''CONDITION_BACKFILL = {
    ("V256", "13", "V(MAIN-AUX)"): ['''
NEW_CB = '''CONDITION_BACKFILL = {
    # B4 V077：原文同一张 Recommended Operating Conditions 表里，CVDD 与 RVDD
    # 各按「375 MHz version / 456 MHz version」给了两组值，VLM 只抄数值不抄条件。
    # 顺序按原表自上而下：375 在前（1.14/1.2/1.32），456 在后（1.25/1.3/1.35）。
    ("V077", "38", "CVDD"): ["375 MHz version", "456 MHz version"],
    ("V077", "38", "RVDD"): ["375 MHz version", "456 MHz version"],
    # B4 V290：VIL 两行按温度档区分，0.8 V 对应 0°C to +70°C，
    # 0.5 V 对应 −55°C to +125°C（注意原文用的是 U+2212 减号）。
    ("V290", "3", "VIL"): ["0°C to +70°C", "−55°C to +125°C"],
    ("V256", "13", "V(MAIN-AUX)"): ['''
for old, new, tag in [(ANCHOR_EXT_NOTE, NEW_EXT_NOTE, "ext_note"),
                      (ANCHOR_CB, NEW_CB, "condition_backfill")]:
    assert s.count(old) == 1, "锚点 %s 命中 %d 次" % (tag, s.count(old))
    s = s.replace(old, new, 1)

# ---------------------------------------------------------------- 3. 非白名单标注
OLD_MARK = '''            for r in keep:
                r["notes"] = (r.get("notes", "") + "；" + EXT_NOTE).strip("；")'''
NEW_MARK = '''            for r in keep:
                # 逐行打头标「非白名单」，供 PM 逐条决定是否纳入 Gold；
                # 不能只在样本级说明里提一句，Excel 里筛不出来。
                r["notes"] = (EXT_PREFIX
                              + (r.get("notes", "") + "；" + EXT_NOTE).strip("；"))'''
assert s.count(OLD_MARK) == 1
s = s.replace(OLD_MARK, NEW_MARK, 1)

# ---------------------------------------------------------------- 4. 排除话术落地
OLD_N1 = '''            if blank == npages:
                note = ("全书 %d/%d 页无文本层，前 12 页有连续 %d 页空白；"
                        "EXCLUDED: 无 OCR 能力，无法建立 Gold（不进点选）"
                        % (blank, npages, best))'''
NEW_N1 = '''            if blank == npages:
                note = ("全书 %d/%d 页无文本层，前 12 页有连续 %d 页空白；"
                        "%s（不进点选）" % (blank, npages, best, OFF_EXCL_NOLAYER))'''
OLD_N2 = '''                note = ("全书 %d/%d 页无文本层（前 12 页有连续 %d 页空白），"
                        "其余 %d 页虽有文本层，但未定位到电气参数表；"
                        "EXCLUDED: 电气特性页为扫描图，无 OCR 能力，"
                        "无法建立 Gold（不进点选）"
                        % (blank, npages, best, npages - blank))'''
NEW_N2 = '''                note = ("全书 %d/%d 页无文本层（前 12 页有连续 %d 页空白），"
                        "其余 %d 页虽有文本层，但未定位到电气参数表；"
                        "%s（不进点选）"
                        % (blank, npages, best, npages - blank, OFF_EXCL_SCANPAGE))'''
for old, new, tag in [(OLD_N1, NEW_N1, "note_nolayer"), (OLD_N2, NEW_N2, "note_scanpage")]:
    assert s.count(old) == 1, "锚点 %s 命中 %d 次" % (tag, s.count(old))
    s = s.replace(old, new, 1)

OLD_E1 = '''        "EXCLUDED: 表格版式不支持稳定还原行序，需 SMD 专用规则后再做"'''
NEW_E1 = '''        + OFF_EXCL_SMD'''
OLD_E2 = '''        "不是电气参数。EXCLUDED: 电气特性页无文本层，无 OCR 能力，无法建立 Gold"'''
NEW_E2 = '''        "不是电气参数。" + OFF_EXCL_SCANPAGE'''
for old, new, tag in [(OLD_E1, NEW_E1, "excl_347"), (OLD_E2, NEW_E2, "excl_041")]:
    assert s.count(old) == 1, "锚点 %s 命中 %d 次" % (tag, s.count(old))
    s = s.replace(old, new, 1)

# ---------------------------------------------------------------- 5. V077 高亮
ANCHOR_HINTS_END = '''REVIEW_HINTS = {'''
NEW_HINTS = '''# 数值长得像但适用条件不同，最容易看错。这类必须红底提醒，不能只放灰字提示。
WARN_BANNER = {
    "V077": ("本件原文同一张 Recommended Operating Conditions 里同时给出 "
             "<b>375 MHz version</b> 与 <b>456 MHz version</b> 两套条件："
             "CVDD 与 RVDD 各两组值已分别绑定 —— 375 MHz → 1.14 / 1.2 / 1.32 V，"
             "456 MHz → 1.25 / 1.3 / 1.35 V。"
             "签字前请重点核对这两组 <code>condition</code> 是否落在正确的行上，"
             "不要只看数值。"),
    "V290": ("VIL 两行按温度档区分，数值不同、适用温度不同："
             "0.8 V 对应 0°C to +70°C，0.5 V 对应 −55°C to +125°C。"
             "本件 II（输入电流）原文条件是 VCC = Max、VI = 5.5V，"
             "文本层抽成 “V CC = Max, VI Max = 5.5V”，是否补录请 PM 定夺。"),
}

REVIEW_HINTS = {'''
assert s.count(ANCHOR_HINTS_END) == 1
s = s.replace(ANCHOR_HINTS_END, NEW_HINTS, 1)

ANCHOR_CARD = '''            "hint": REVIEW_HINTS.get(sno, ""),'''
NEW_CARD = '''            "hint": REVIEW_HINTS.get(sno, ""),
            "warn": WARN_BANNER.get(sno, ""),'''
assert s.count(ANCHOR_CARD) == 1
s = s.replace(ANCHOR_CARD, NEW_CARD, 1)

ANCHOR_CSS = '''                ".hint-review{background:#fff4ce;border-left:4px solid #d68b00;"
                "padding:8px 10px;margin:8px 0;border-radius:4px;font-size:13px}"))'''
NEW_CSS = '''                ".hint-review{background:#fff4ce;border-left:4px solid #d68b00;"
                "padding:8px 10px;margin:8px 0;border-radius:4px;font-size:13px}"
                ".hint-warn{background:#fdecea;border-left:4px solid #c0392b;"
                "padding:9px 11px;margin:8px 0;border-radius:4px;font-size:13px;"
                "color:#7b1a12}"))'''
assert s.count(ANCHOR_CSS) == 1
s = s.replace(ANCHOR_CSS, NEW_CSS, 1)

ANCHOR_RENDER = '''        if c.get("hint"):
            p.append('<div class="hint hint-review"><b>核查提示</b>　%s</div>'
                     % B.esc(c["hint"]))'''
NEW_RENDER = '''        if c.get("warn"):
            # 高亮块：这段是 HTML，带 <b>/<code>，不再转义
            p.append('<div class="hint hint-warn"><b>必须核对</b>　%s</div>'
                     % c["warn"])
        if c.get("hint"):
            p.append('<div class="hint hint-review"><b>核查提示</b>　%s</div>'
                     % B.esc(c["hint"]))'''
assert s.count(ANCHOR_RENDER) == 1
s = s.replace(ANCHOR_RENDER, NEW_RENDER, 1)

# 卡片标签补「二轮兜底：非白名单」
ANCHOR_TAG = '''        tags = ['<span class="tag %s">草稿：%s</span>' % (cls, B.esc(c["quality"]))]
        for pn in c["panes"]:'''
NEW_TAG = '''        tags = ['<span class="tag %s">草稿：%s</span>' % (cls, B.esc(c["quality"]))]
        if c.get("ext"):
            tags.append('<span class="tag t-warn">二轮兜底：非白名单</span>')
        for pn in c["panes"]:'''
assert s.count(ANCHOR_TAG) == 1
s = s.replace(ANCHOR_TAG, NEW_TAG, 1)

# 无文本层卡片的提示语按事实分叉，不再套同一句
ANCHOR_ERR = '''            p.append('<div class="err">本页抓不到任何文字（纯图形/扫描件）。'
                     "请整件标 <code>EXCLUDED: 无 OCR 能力，无法建立 Gold</code>。</div>")'''
NEW_ERR = '''            p.append('<div class="err">本页抓不到任何文字（纯图形/扫描件）。'
                     "排除话术请按事实选：全书确实无文本层用 "
                     "<code>%s</code>；只有电气特性页是扫描图则用 "
                     "<code>%s</code>，不要一刀切。</div>"
                     % (B.esc(OFF_EXCL_NOLAYER), B.esc(OFF_EXCL_SCANPAGE)))'''
assert s.count(ANCHOR_ERR) == 1
s = s.replace(ANCHOR_ERR, NEW_ERR, 1)

P.write_bytes(s.encode("utf-8"))
print("patched lines=%d CRLF=%d" % (s.count("\n"), s.encode("utf-8").count(b"\r\n")))
