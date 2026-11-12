# -*- coding: utf-8 -*-
"""封卷保护 7 场景回归：全部必须 Fail-Closed。

针对 Reviewer 指出的 Fail-Open：上一版 `_wb_signature` 只比值/填充/列宽，
以下两种"内容没变、字节变了"的情况会被判成"一致"从而静默跳过：
  · 只改数字格式（number_format）—— 值一样，字节不一样；
  · 增删工作表 —— 非活动表根本不在签名范围里。

本测试只用临时目录里的合成 xlsx 与被改坏的副本，不碰任何真实交付件。
用法：python _test_seal_guard.py [> Batch3_seal_guard_test.txt]
"""
from __future__ import print_function

import hashlib
import shutil
import tempfile
from pathlib import Path

import openpyxl

import _make_b3_final as M

PASS = FAIL = 0
NOTES = []


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ok(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("PASS  %s%s" % (name, ("  " + detail) if detail else ""))
    else:
        FAIL += 1
        print("FAIL  %s%s" % (name, ("  " + detail) if detail else ""))


def expect_exit(name, fn, must_contain):
    """调用必须抛 SystemExit，且消息里带上指定关键词。"""
    try:
        r = fn()
    except SystemExit as exc:
        msg = str(exc)
        hit = must_contain in msg
        ok(name, hit, "→ SystemExit：%s" % msg.replace("\n", " / ")[:110])
        if not hit:
            NOTES.append("%s 的退出消息里没有 %r" % (name, must_contain))
        return
    except Exception as exc:                       # noqa: BLE001
        ok(name, False, "→ 抛了 %s 而不是 SystemExit" % type(exc).__name__)
        return
    ok(name, False, "→ 没有退出，返回 %r（Fail-Open）" % (r,))


def make_xlsx(path, rows=((1, 2), (3, 4)), sheet="S1"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet
    for r in rows:
        ws.append(list(r))
    wb.save(str(path))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="sealguard_"))
    target = tmp / "SEALED.xlsx"
    make_xlsx(target)
    frozen = sha(target)

    # ---------- 场景 1：哈希与登记一致 → 跳过，原字节保留 ----------
    reg = {target.name: frozen}
    before = sha(target)
    r = M.guard_sealed(target, reg)
    ok("1 哈希一致 → skip 且字节未动", r == "skip" and sha(target) == before,
       "返回 %r" % r)

    # ---------- 场景 2：只改数字格式（值不变、字节变）→ 退出 ----------
    fmt = tmp / "fmt.xlsx"
    make_xlsx(fmt)
    frozen_fmt = sha(fmt)
    wb = openpyxl.load_workbook(str(fmt))
    wb.active["A1"].number_format = "0.0000"        # 只动格式，不动值
    wb.save(str(fmt))
    changed_fmt = sha(fmt) != frozen_fmt
    expect_exit("2 只改数字格式（值不变）→ 退出",
                lambda: M.guard_sealed(fmt, {fmt.name: frozen_fmt}),
                "拒绝自动替换")
    ok("2b 该场景确实只改了字节（证明老逻辑会误判一致）", changed_fmt)

    # ---------- 场景 3：增/删工作表 → 退出 ----------
    sh = tmp / "sheet.xlsx"
    make_xlsx(sh)
    frozen_sh = sha(sh)
    wb = openpyxl.load_workbook(str(sh))
    wb.create_sheet("EXTRA")
    wb.save(str(sh))
    expect_exit("3 新增工作表 → 退出",
                lambda: M.guard_sealed(sh, {sh.name: frozen_sh}),
                "拒绝自动替换")

    sh2 = tmp / "sheet_del.xlsx"
    make_xlsx(sh2)
    wb = openpyxl.load_workbook(str(sh2))
    wb.create_sheet("KEEP")
    wb.save(str(sh2))
    frozen_del = sha(sh2)
    wb = openpyxl.load_workbook(str(sh2))
    del wb["KEEP"]
    wb.save(str(sh2))
    expect_exit("3b 删除工作表 → 退出",
                lambda: M.guard_sealed(sh2, {sh2.name: frozen_del}),
                "拒绝自动替换")

    # ---------- 场景 4：文件损坏，读不出哈希 → 退出 ----------
    bad = tmp / "broken.xlsx"
    bad.write_bytes(b"PK\x03\x04 not really a zip" * 40)
    expect_exit("4 文件损坏（非 zip）→ 退出",
                lambda: M.guard_sealed(bad, {bad.name: "0" * 64}),
                "拒绝自动替换")

    # 场景 4b：路径存在但读不出内容（这里用同名目录触发 OSError 分支）。
    # sha() 抛 OSError 时必须走"无法读取"分支，而不是被当成普通哈希不符。
    unread = tmp / "unreadable.xlsx"
    unread.mkdir()
    expect_exit("4b 路径存在但读不出字节 → 退出（无法读取分支）",
                lambda: M.guard_sealed(unread, {unread.name: "0" * 64}),
                "无法读取")

    # ---------- 场景 5：封卷件被删 → 退出，不许凭生成器重造 ----------
    gone = tmp / "gone.xlsx"
    expect_exit("5 封卷件缺失 → 退出（不许重造）",
                lambda: M.guard_sealed(gone, {gone.name: "0" * 64}),
                "封卷件缺失")

    # ---------- 场景 6：未登记（本就不是封卷件）→ 允许生成 ----------
    free = tmp / "draft.csv"
    free.write_text("a,b\n", encoding="utf-8")
    r = M.guard_sealed(free, {})
    ok("6 未登记文件 → write（不误伤草稿）", r == "write", "返回 %r" % r)

    # ---------- 场景 7：已登记封卷但登记表缺哈希 → 退出 ----------
    expect_exit("7 登记缺哈希 → 退出（不默认放行）",
                lambda: M.guard_sealed(target, {target.name: ""}),
                "封卷登记缺哈希")

    # ---------- 附加：真实封卷件必须仍与登记一致 ----------
    real = Path(M.__file__).with_name("Batch3_B3_FINAL.xlsx")
    if real.exists():
        got = sha(real)
        ok("8 真实封卷件 Batch3_B3_FINAL.xlsx 与登记一致",
           got == M.SEALED_SHA["Batch3_B3_FINAL.xlsx"], "sha=%s…" % got[:16])
        ok("8b 真实封卷件过闸门返回 skip",
           M.guard_sealed(real) == "skip")
    else:
        NOTES.append("真实封卷件不在预期路径，跳过 8/8b")

    shutil.rmtree(str(tmp), ignore_errors=True)

    print("-" * 72)
    print("PASS=%d, FAIL=%d" % (PASS, FAIL))
    for n in NOTES:
        print("  注：%s" % n)
    print("结论：%s" % ("全部通过" if FAIL == 0 else "有失败项，必须修"))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
