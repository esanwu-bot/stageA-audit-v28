# -*- coding: utf-8 -*-
"""一次性补丁：给 _make_b3_final.write_xlsx 加内容幂等保护。

背景：openpyxl 每次 save 都会刷新 docProps/core.xml 的 dcterms:modified，
导致封卷件 Batch3_B3_FINAL.xlsx 仅因写入时刻不同就整包 SHA-256 漂移
（xl/worksheets/sheet1.xml 其实逐字节一致）。封卷件不应有此现象。

做法：先写临时文件，再用工作簿内容签名与磁盘现件比对；一致则丢弃临时文件、
保留原字节；不一致才原子替换。
"""
import pathlib
import sys

P = pathlib.Path(__file__).with_name("_make_b3_final.py")
src = P.read_text(encoding="utf-8")
orig = src

HELPER = '''def _wb_signature(path):
    """工作簿内容签名：表名/冻结/筛选/列宽 + 每格的值与填充色、加粗。

    只比对「内容」，不含 docProps 时间戳，用于判断是否需要真的重写。
    """
    wb = openpyxl.load_workbook(str(path), data_only=False)
    ws = wb.active
    sig = [ws.title, ws.freeze_panes or "", ws.auto_filter.ref or ""]
    sig.append(tuple(sorted((k, round(float(v.width or 0), 4))
                            for k, v in ws.column_dimensions.items())))
    for row in ws.iter_rows():
        for c in row:
            fill = c.fill
            fg = ""
            if fill is not None and fill.fill_type == "solid":
                rgb = getattr(fill.fgColor, "rgb", None)
                fg = rgb if isinstance(rgb, str) else str(fill.fgColor.index or "")
            font = c.font
            frgb = ""
            try:
                frgb = font.color.rgb if font and font.color else ""
            except (TypeError, AttributeError):
                frgb = ""
            sig.append((c.coordinate, c.value,
                        bool(font.b) if font else False,
                        frgb if isinstance(frgb, str) else ""))
    return tuple(sig)


def write_xlsx(path, rows, sheet, highlights=None, head_color="2F5597"):'''

OLD_HEAD = 'def write_xlsx(path, rows, sheet, highlights=None, head_color="2F5597"):'

OLD_TAIL = '''    tmp = path.with_name(path.name + ".wb_tmp")
    wb.save(str(tmp))
    atomic_replace(tmp, path)'''

NEW_TAIL = '''    tmp = path.with_name(path.name + ".wb_tmp")
    wb.save(str(tmp))
    # 幂等保护：要写的内容与磁盘现件逐格一致时，保留原字节、不重写。
    # openpyxl 每次 save 都会刷新 docProps/core.xml 的 dcterms:modified，
    # 会让封卷件的整包 SHA-256 无意义漂移（数据其实一字未改）。
    if path.exists():
        try:
            if _wb_signature(tmp) == _wb_signature(path):
                tmp.unlink()
                return "未改写（内容与磁盘一致，保留原字节）"
        except (OSError, ValueError, KeyError):
            pass
    atomic_replace(tmp, path)
    return "已改写"'''

OLD_CALL = '''    write_xlsx(OUT_XLSX, rows, "B3_FINAL",
               highlights={(i, "condition"): "E2EFDA" for i in cond_row_ids}
               | {(i, "entered_by"): "E2EFDA" for i in cond_row_ids})'''

NEW_CALL = '''    xlsx_state = write_xlsx(
        OUT_XLSX, rows, "B3_FINAL",
        highlights={(i, "condition"): "E2EFDA" for i in cond_row_ids}
        | {(i, "entered_by"): "E2EFDA" for i in cond_row_ids})'''

OLD_PRINT = '''    print("  补签落点清单：%s" % TARGETS.name)'''

NEW_PRINT = '''    print("  补签落点清单：%s" % TARGETS.name)
    print("  xlsx 写入：%s" % xlsx_state)'''

for old, new, tag in [(OLD_HEAD, HELPER, "helper"),
                      (OLD_TAIL, NEW_TAIL, "tail"),
                      (OLD_CALL, NEW_CALL, "call"),
                      (OLD_PRINT, NEW_PRINT, "print")]:
    n = src.count(old)
    if n != 1:
        raise SystemExit("FAIL 锚点 %s 命中 %d 次（应为 1）" % (tag, n))
    src = src.replace(old, new, 1)

assert src != orig
P.write_bytes(src.encode("utf-8"))
print("patched:", P)
print("lines:", src.count("\n"))
print("CRLF:", src.encode("utf-8").count(b"\r\n"))
