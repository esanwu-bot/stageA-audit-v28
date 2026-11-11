# -*- coding: utf-8 -*-
"""用百炼（DashScope）视觉模型读页面图，输出带置信度的结构化草稿。

只做一件事：把一张表格截图发给 qwen-vl-max，要求它逐行返回
symbol / parameter / min / typ / max / unit / confidence，并把原始回复
原样打印出来，供人工判断这份"模型自报置信度"到底可不可信。

密钥从 `E:\\workspace\\IcPdfParser\\.env.local` 读入内存，不落盘、不打印。
"""
from __future__ import print_function

import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ENV_PATH = Path(r"E:\workspace\IcPdfParser\.env.local")
API = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"


def load_key():
    env = {}
    for line in ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    key = env.get("DASHSCOPE_API_KEY", "")
    if not key:
        raise SystemExit("未找到 DASHSCOPE_API_KEY")
    return key


PROMPT = """你是芯片数据手册的参数抄录员。图片是一张表格的截图。

请只输出 JSON，不要任何解释文字，格式：
{"rows":[{"symbol":"...","parameter":"...","min":"...","typ":"...","max":"...","unit":"...","confidence":0.0}]}

规则：
1. 只抄图片里能直接看到的字符，绝对不要换算单位、不要补零、不要推测。
2. 单元格是空的就留空字符串 ""，不要填 "-" 或 "N/A"。
3. confidence 是你对**这一行整体**抄录正确的把握（0-1）。字体模糊、
   行列对齐不清、多组列分不清时，必须给低分（0.5 以下），不要一律给高分。
4. 最多输出 8 行，优先表格最上面几行。
"""


def ask(img_path, model="qwen-vl-max", timeout=90):
    b64 = base64.b64encode(Path(img_path).read_bytes()).decode()
    body = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url",
                 "image_url": {"url": "data:image/png;base64," + b64}},
                {"type": "text", "text": PROMPT},
            ],
        }],
        "temperature": 0,
        "max_tokens": 1500,
    }
    req = urllib.request.Request(
        API, data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": "Bearer " + load_key(),
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    img = sys.argv[1] if len(sys.argv) > 1 else \
        r"E:\workspace\icpdf-extractor\workbench\_gate6a_prep\annotation_reports\V101\b2_AMR_p0003.png"
    model = sys.argv[2] if len(sys.argv) > 2 else "qwen-vl-max"
    print("图片: %s" % Path(img).name)
    print("模型: %s" % model)
    try:
        data = ask(img, model)
    except urllib.error.HTTPError as e:
        print("HTTP %s: %s" % (e.code, e.read().decode("utf-8", "replace")[:600]))
        return 1
    except Exception as e:
        print("调用失败: %s: %s" % (type(e).__name__, e))
        return 1

    usage = data.get("usage", {})
    print("usage: %s" % usage)
    txt = data["choices"][0]["message"]["content"]
    print("-" * 70)
    print(txt[:2500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
