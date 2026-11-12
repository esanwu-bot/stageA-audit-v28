# -*- coding: utf-8 -*-
"""B1 定稿备注清理（Reviewer 2026-11-12 第三轮）。

PM 裁定：「那 20 行 notes 里写的『须对左图核』『请确认』等草稿词汇，
一律替换为『人工已核对 PDF 原图并确认』。确保不再出现 low_confidence
和 CONFIRMED 状态并存的矛盾。」

严格边界
--------
* 只改 notes 一列，且只改含过期草稿措辞的 20 行。
* 另外 3 行是 PM 授权代录入的修正记录，notes 已是
  「人工已核对 PDF p4 原图并确认此修正。」，保持不动。
* min/max/typ、unit、condition、symbol、evidence_page、table_title、
  row_status、reviewer、approved_by、entered_by、confidence_score、
  device_model、human_adjudication 一律逐格断言不变。
* 清理前的 xlsx 另存留痕，清理前后 CSV 与 XLSX 都逐格同源。

产物（覆盖最终真源，文件名不变，避免 INDEX 里再出现第二个「唯一真源」）：
  Batch3_B1_RESIGNED.csv / .xlsx
  Batch3_B1_RESIGNED_pre_notes_cleanup.xlsx   （清理前留痕）
"""
from __future__ import print_function

import csv
import os
import shutil
from collections import Counter
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

PREP = Path(__file__).resolve().parent
OUT_CSV = PREP / "Batch3_B1_RESIGNED.csv"
OUT_XLSX = PREP / "Batch3_B1_RESIGNED.xlsx"
BAK_XLSX = PREP / "Batch3_B1_RESIGNED_pre_notes_cleanup.xlsx"

FINAL_NOTE = "人工已核对 PDF 原图并确认"
KEEP_NOTE = "人工已核对 PDF p4 原图并确认此修正。"
STALE = ("须对左图核", "请确认", "low_confidence", "VLM 草稿")
# 三行代录入记录按内容识别，不硬编码行号 —— 行号基准（Excel 行 / 数据下标）
# 差 1，写死过一次就踩过一次，交给断言兜住。


def cell(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def read_xlsx(path):
    ws = openpyxl.load_workbook(str(path), data_only=True).active
    vals = list(ws.values)
    cols = [str(x or "").strip() for x in vals[0]]
    rows = []
    for v in vals[1:]:
        if not any(x is not None and str(x).strip() for x in v):
            continue
        rows.append({k: cell(v[cols.index(k)]) for k in cols})
    return cols, rows


def atomic_replace(tmp, dst):
    """Windows 上目标被 Excel/预览独占时 os.replace 也会失败，明确报错不静默。"""
    try:
        os.replace(str(tmp), str(dst))
    except PermissionError:
        raise SystemExit("目标被占用且内容需要改写，请关闭 Excel/预览后重跑：%s" % dst)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def main():
    cols, rows = read_xlsx(OUT_XLSX)
    assert len(cols) == 19, "B1 定稿应为 19 列，实际 %d" % len(cols)
    assert len(rows) == 23, "B1 定稿应为 23 行，实际 %d" % len(rows)
    assert "notes" in cols

    # 清理前：CSV 与 XLSX 必须逐格同源，否则「唯一真源」不成立
    with open(OUT_CSV, encoding="utf-8-sig", newline="") as fh:
        csv_rows = list(csv.DictReader(fh))
    assert len(csv_rows) == 23
    for i, (a, b) in enumerate(zip(rows, csv_rows), 1):
        for k in cols:
            assert a[k] == (b.get(k) or ""), \
                "清理前 xlsx/CSV 不同源：行%d 列%s %r != %r" % (i, k, a[k], b.get(k))

    before = [dict(r) for r in rows]
    before_notes = Counter(r["notes"] for r in rows)

    # 留痕：清理前的 xlsx 原样保存
    if not BAK_XLSX.exists():
        shutil.copy2(str(OUT_XLSX), str(BAK_XLSX))
        print("留痕：%s" % BAK_XLSX.name)
    else:
        print("留痕已存在，跳过：%s" % BAK_XLSX.name)

    keep_rows = {i for i, r in enumerate(rows) if r["notes"] == KEEP_NOTE}
    assert len(keep_rows) == 3, \
        "PM 代录入定稿语应有 3 行，实际 %d 行" % len(keep_rows)

    changed = []
    for i, r in enumerate(rows):
        old = r["notes"]
        if any(w in old for w in STALE):
            r["notes"] = FINAL_NOTE
            changed.append(i)
        else:
            assert old == KEEP_NOTE, \
                "行%d 的 notes 既不是过期措辞也不是代录入定稿语：%r" % (i + 1, old)

    assert len(changed) == 20, "应清理 20 行，实际 %d 行" % len(changed)
    assert len(set(changed) & keep_rows) == 0, "误改了 PM 代录入的三行"

    # 只改了 notes：其余 18 列逐格不变
    for i, (a, b) in enumerate(zip(before, rows), 1):
        for k in cols:
            if k == "notes":
                continue
            assert a[k] == b[k], "行%d 列%s 被改动：%r → %r" % (i, k, a[k], b[k])
    assert all(r["notes"] == FINAL_NOTE
               or r["notes"] == KEEP_NOTE for r in rows)
    assert not any("low_confidence" in r["notes"].lower() for r in rows), \
        "仍有 low_confidence 与 CONFIRMED 并存的矛盾"
    assert all(r["row_status"] == "CONFIRMED" for r in rows)
    assert all(r["reviewer"] == "wuxiaoxian" for r in rows)

    # 写 CSV（UTF-8 BOM）
    tmp_csv = OUT_CSV.with_name(OUT_CSV.name + ".wb_tmp")
    with open(tmp_csv, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    atomic_replace(tmp_csv, OUT_CSV)

    # 写 XLSX：全部按文本，别让 Excel 把 ±25 / -50 / °C 做类型转换
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "B1_RESIGNED"
    ws.append(cols)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="2F5597")
        c.alignment = Alignment(horizontal="center")
    for r in rows:
        ws.append([r.get(k, "") for k in cols])
    for ci, k in enumerate(cols, 1):
        width = {"parameter_name": 42, "notes": 60, "file_name": 40,
                 "human_adjudication": 34, "row_status": 16,
                 "table_title": 32, "approved_by": 16,
                 "entered_by": 15}.get(k, 15)
        ws.column_dimensions[get_column_letter(ci)].width = width
    green = PatternFill("solid", fgColor="E2EFDA")
    for i in keep_rows:
        for k in ("row_status", "reviewer", "approved_by", "entered_by"):
            ws.cell(row=i + 2, column=cols.index(k) + 1).fill = green
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    tmp_xlsx = OUT_XLSX.with_name(OUT_XLSX.name + ".wb_tmp")
    wb.save(str(tmp_xlsx))
    atomic_replace(tmp_xlsx, OUT_XLSX)

    # 清理后：再次逐格断言 CSV == XLSX == 内存
    cols2, rows2 = read_xlsx(OUT_XLSX)
    assert cols2 == cols
    with open(OUT_CSV, encoding="utf-8-sig", newline="") as fh:
        csv2 = list(csv.DictReader(fh))
    assert len(rows2) == len(csv2) == 23
    for i, (a, b, c) in enumerate(zip(rows, rows2, csv2), 1):
        for k in cols:
            assert a[k] == b[k] == (c.get(k) or ""), \
                "清理后不同源：行%d 列%s" % (i, k)

    print("\n清理前 notes 分布：")
    for k, v in before_notes.items():
        print("  %2d 行 | %s" % (v, k[:96]))
    print("\n清理后 notes 分布：")
    for k, v in Counter(r["notes"] for r in rows).items():
        print("  %2d 行 | %s" % (v, k))
    print("\nB1 备注清理：%d 行改写，%d 行保持代录入定稿语，其余 18 列逐格未变。"
          % (len(changed), len(rows) - len(changed)))
    print("low_confidence 残留 0；confidence_score 分布：%s"
          % dict(Counter(r["confidence_score"] for r in rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
