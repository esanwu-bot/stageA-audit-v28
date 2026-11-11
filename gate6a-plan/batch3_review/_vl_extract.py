# -*- coding: utf-8 -*-
"""Qwen-VL 视觉预标注：把表格截图交给 qwen3-vl-plus，拿回带 confidence 的结构化行。

已知局限（实测，写在这里防止后人误用）
--------------------------------------
* 同一张图，模型对每一行都报 confidence=1.0；把图缩到 22% 再问，
  才降到 0.95/0.90。说明这个分数**没有校准**，只能当弱先验，
  不能当绝对阈值（不能"≥0.9 就免检"）。
* 因此最终 confidence 由 `combine()` 合成：确定性证据占 0.7，模型自报占 0.3。

密钥：从 `E:\\workspace\\IcPdfParser\\.env.local` 读入内存，不落盘、不打印。
"""
from __future__ import print_function

import json
from pathlib import Path

from _vl_probe import ask

MODEL = "qwen3-vl-plus"

PROMPT = """你是芯片数据手册的参数抄录员。图片是一张参数表的截图。

只输出 JSON，不要解释，格式：
{"rows":[{"symbol":"...","parameter":"...","min":"...","typ":"...","max":"...","unit":"...","confidence":0.0}]}

规则：
1. 只抄图片里直接可见的字符。不换算单位、不补零、不推测、不合并单元格。
2. 单元格空着就输出 ""，不要填 "-" 或 "N/A"。
3. 参数名照抄英文原文；symbol 照抄（如 VCC、VIH、Tstg）。
4. 若一张表有多个温度/电压分组（如 VCC=2V 一组、4.5V 一组），
   只输出**第一组**，并在 parameter 末尾加 " [group1]"。
5. confidence 逐行给：字迹清晰且列对齐明确给 0.8-0.95；
   表格拥挤、分不清列、数字与单位距离远，给 0.5 以下。
   不要给所有行同一个分数。
6. 最多 8 行，从表格最上面开始。
"""


def extract_rows(png_path, model=MODEL, use_cache=True):
    """返回 (rows, meta)。rows 里每项含 symbol/parameter/min/typ/max/unit/confidence。

    结果按 (图片字节 sha256, 模型, Prompt) 缓存到 `_vl_cache/`。
    为什么要缓存：改阈值、改 HTML 样式都要重跑生成器，
    每次都重新调 API 等于重复计费；图片没变时结果必然可复用。
    """
    import hashlib

    png_path = Path(png_path)
    raw = png_path.read_bytes()
    key = hashlib.sha256(
        raw + model.encode() + PROMPT.encode()).hexdigest()[:24]
    cdir = png_path.parent / "_vl_cache"
    cfile = cdir / ("%s.json" % key)

    if use_cache and cfile.exists():
        obj = json.loads(cfile.read_text(encoding="utf-8"))
        return obj["rows"], obj["meta"]

    data = ask(str(png_path), model)
    txt = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    s = txt.strip()
    if s.startswith("```"):
        s = s.split("```")[1]
        if s.lower().startswith("json"):
            s = s[4:]
    try:
        obj = json.loads(s)
    except Exception:
        a, b = s.find("{"), s.rfind("}")
        obj = json.loads(s[a:b + 1]) if a >= 0 and b > a else {"rows": []}
    rows = []
    for r in obj.get("rows", [])[:8]:
        try:
            conf = float(r.get("confidence", 0.5))
        except (TypeError, ValueError):
            conf = 0.5
        rows.append({
            "symbol": str(r.get("symbol", "") or "").strip(),
            "parameter_name": str(r.get("parameter", "") or "").strip(),
            "min_value": str(r.get("min", "") or "").strip(),
            "typ_value": str(r.get("typ", "") or "").strip(),
            "max_value": str(r.get("max", "") or "").strip(),
            "unit": str(r.get("unit", "") or "").strip(),
            "vlm_confidence": round(max(0.0, min(conf, 1.0)), 2),
        })
    meta = {"model": model, "usage": usage, "raw_len": len(txt)}

    try:
        cdir.mkdir(parents=True, exist_ok=True)
        cfile.write_text(json.dumps({"rows": rows, "meta": meta},
                                    ensure_ascii=False, indent=1),
                         encoding="utf-8", newline="\n")
    except Exception:
        pass
    return rows, meta


def combine(det_score, vlm_conf):
    """合成最终置信度：确定性证据 0.7 + 模型自报 0.3。

    为什么不直接用模型分：实测它对模糊图仍报 0.95，绝对值不可信。
    确定性证据（数值是否真在该页、单位是否在该页）可被人复算。
    """
    return round(min(0.99, 0.7 * det_score + 0.3 * float(vlm_conf)), 2)
