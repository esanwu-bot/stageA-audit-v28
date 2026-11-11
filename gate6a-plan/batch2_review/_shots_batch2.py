# -*- coding: utf-8 -*-
"""Batch 2 证据截图：封面型号 + V101 第 3 页 5.9 圈选。

产物落在 screenshots/，供 Reviewer 直接看图，不用打开 PDF。
两个原则：
  1. 坐标全部取自 PDF 词表/命中框，再乘缩放倍数映射到像素，不手写像素值；
  2. 说明文字一律放在图片下方的白条里，不往页面上叠字——叠字会盖住被证明的东西。
"""
import argparse
import os
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFont

PREP = Path(__file__).resolve().parent
OUT = PREP / "screenshots"
OUT.mkdir(exist_ok=True)
PDF_DIR = None      # 由入口按 --pdf-dir / ICPDF_PDF_DIR 赋值，脚本内不留绝对路径

RED = (198, 28, 28)
BLUE = (20, 80, 190)
BAND = 64


def font(size, bold=False):
    """优先微软雅黑；换机器没有就退回默认位图字体（英文仍可读）。"""
    for p in (r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
              r"C:\Windows\Fonts\simhei.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render(page, zoom, clip=None):
    pm = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip, alpha=False)
    img = Image.frombytes("RGB", (pm.width, pm.height), pm.samples)
    return img, (clip.x0 if clip else 0), (clip.y0 if clip else 0)


def to_px(rect, zoom, ox, oy):
    """PDF 坐标 -> 裁剪图内的像素坐标。"""
    return ((rect.x0 - ox) * zoom, (rect.y0 - oy) * zoom,
            (rect.x1 - ox) * zoom, (rect.y1 - oy) * zoom)


def add_caption(img, text, color=RED):
    """在图片下方接一条白条写说明，绝不覆盖页面内容。"""
    canvas = Image.new("RGB", (img.width, img.height + BAND), (255, 255, 255))
    canvas.paste(img, (0, 0))
    d = ImageDraw.Draw(canvas)
    d.line([(0, img.height), (canvas.width, img.height)], fill=(170, 170, 170), width=2)
    size = 30
    f = font(size, True)
    while d.textlength(text, font=f) > canvas.width - 24 and size > 14:
        size -= 2
        f = font(size, True)
    d.text((12, img.height + (BAND - size) / 2 - 3), text, font=f, fill=color)
    return canvas


def best_hit(page, needle):
    """同一串型号在封面上可能命中多处（页眉、订购表、大标题），取面积最大的那处。"""
    hits = page.search_for(needle)
    if not hits:
        return None
    return max(hits, key=lambda r: r.width * r.height)


def cover_shot(pdf_name, needle, out_name, caption, zoom=2.4):
    doc = fitz.open(str(PDF_DIR / pdf_name))
    page = doc[0]
    hit = best_hit(page, needle)
    if hit is None:
        print("WARN 未命中 %s @ %s" % (needle, pdf_name))
        doc.close()
        return None
    # 通栏裁：横向取满页宽，避免把左右文字切掉；纵向以命中框为中心上下留白
    clip = fitz.Rect(0, max(0, hit.y0 - 60),
                     page.rect.x1, min(page.rect.y1, hit.y1 + 150))
    img, ox, oy = render(page, zoom, clip)
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = to_px(hit, zoom, ox, oy)
    d.rectangle((x0 - 3, y0 - 3, x1 + 3, y1 + 3), outline=RED, width=4)
    img = add_caption(img, caption)
    path = OUT / out_name
    img.save(path)
    print("写出", path.name, img.size, "命中框", ["%.0f" % v for v in hit])
    doc.close()
    return path


def v101_page3():
    """第 3 页整页 + VOH 区块放大，两处都圈 5.9（MIN 列，25°C 组）。"""
    doc = fitz.open(str(PDF_DIR / "CD74HCT574EE4__schs183c.pdf"))
    page = doc[2]
    target = fitz.Rect(305.0, 541.0, 323.0, 558.5)   # 5.9 词框外扩

    zoom = 2.2
    img, ox, oy = render(page, zoom)
    d = ImageDraw.Draw(img)
    d.rectangle(to_px(target, zoom, ox, oy), outline=RED, width=4)
    # 蓝框标出 VCC=6 整行，说明 5.9 属于哪一行（此时 MIN 列有三组温度，值相同）
    d.rectangle(to_px(fitz.Rect(60, 540.5, 545, 558.5), zoom, ox, oy), outline=BLUE, width=2)
    p1 = OUT / "V101_p3_full_5.9.png"
    add_caption(img, "CD74HCT574 第 3 页：VOH MIN = 5.9 V（蓝框为 VCC=6V 行；红框为 5.9）").save(p1)
    print("写出", p1.name)

    clip = fitz.Rect(55, 513.0, 600, 558.0)   # 右留到页边、下切在 5.9 行之后，别带入下一行
    img2, ox2, oy2 = render(page, 6.0, clip)
    d2 = ImageDraw.Draw(img2)
    d2.rectangle(to_px(target, 6.0, ox2, oy2), outline=RED, width=4)
    p2 = OUT / "V101_p3_VOH_zoom.png"
    add_caption(img2, "VOH 三行放大：VCC=2V→1.9 / 4.5V→4.4 / 6V→5.9（VCC 在 TEST CONDITIONS 列，按行读）").save(p2)
    print("写出", p2.name)
    doc.close()
    return p1, p2


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="生成 Batch 2 证据截图")
    ap.add_argument("--pdf-dir", default=os.environ.get("ICPDF_PDF_DIR"))
    a = ap.parse_args()
    if not a.pdf_dir:
        raise SystemExit("必须给 --pdf-dir 或设 ICPDF_PDF_DIR")
    PDF_DIR = Path(a.pdf_dir)

    v101_page3()
    cover_shot("ADC3544IRSBT__adc3544.pdf", "ADC3544", "V349_cover_ADC3544.png",
               "V349 实际型号 ADC3544（README 曾误写 ADC3541）")
    cover_shot("DAC8775IRWFR__dac8775.pdf", "DAC8775", "V145_cover_DAC8775.png",
               "V145 实际型号 DAC8775（README 曾误写 DAC7750）")
    cover_shot("DEM-OPA-MSOP-2A__opa2830.pdf", "OPA2830", "V097_cover_OPA2830.png",
               "V097 手册为 OPA2830；DEM-OPA-MSOP-2A 是评估板订购码")
    cover_shot("74LVTH182504APMG4__sn74lvth18504a.pdf", "SN74LVTH182504A",
               "V162_cover_SN74LVTH182504A.png",
               "V162 订购码为 182504A（手册同页并列 18504A）")
    cover_shot("DS90C189TWRTDTQ1__ds90c189-q1.pdf", "DS90C189-Q1",
               "V111_cover_DS90C189-Q1.png", "V111 实际型号 DS90C189-Q1")
    cover_shot("CD74HCT574EE4__schs183c.pdf", "CD74HCT574",
               "V101_cover_CD74HCT574E.png", "V101 实际型号 CD74HCT574E")
