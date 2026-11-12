# -*- coding: utf-8 -*-
"""`_final_from_signed_xlsx.py` 的定向回归（Reviewer 第十三轮追加要求）。

被测契约只有一条：**签字 xlsx 是唯一事实源，只读不写；字节不对就立刻停。**

六个场景：
  1  正常读取        哈希匹配 -> 允许派生 CSV / sidecar / provenance
  2  字节篡改        改任一字节 -> SystemExit，且发生在 load_workbook() 之前
  3  源文件缺失      文件不存在   -> SystemExit，同样在解析之前
  4  哈希不符/为空   常量置空或改错 -> SystemExit
  5  失败不产物      场景 2-4 的输出目录必须一个文件都没有
  6  源文件零改动    正常运行前后，签字 xlsx 的 SHA-256 必须完全一致

「在 load_workbook 之前」不是靠错误信息猜的：本测试把 `openpyxl.load_workbook`
换成计数器，失败场景里必须 **调用次数 == 0**。为此场景 2 特意准备了两个变体：
  2a 追加一个字节（文件已不是合法 zip，解析必然失败，证明力弱）
  2b 用 openpyxl 改一个单元格后另存（**仍是完全合法的 xlsx**，解析一定能过）
     —— 2b 通过才真正证明拦住它的是哈希闸门，不是解析失败。
"""
from __future__ import print_function

import contextlib
import hashlib
import io
import shutil
import sys
import tempfile
from pathlib import Path

import openpyxl

import _final_from_signed_xlsx as F

PASS, FAIL = [], []
OUT_NAMES = ("Batch3_B4_FINAL.csv", "Batch3_B4_PDF_PROVENANCE.csv",
             "page_text_batch3_b4.json")


def sha(p):
    h = hashlib.sha256()
    h.update(Path(p).read_bytes())
    return h.hexdigest()


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print("  [%s] %-44s %s" % ("PASS" if ok else "FAIL", name, detail))


@contextlib.contextmanager
def sandbox(outdir, signed=None, signed_sha=None):
    """把被测模块的输入/输出路径全部改指向临时目录，并给 load_workbook 装计数器。"""
    saved = {k: getattr(F, k) for k in
             ("SIGNED_XLSX", "SIGNED_SHA", "OUT_CSV", "OUT_PROV", "OUT_SIDE")}
    calls = {"n": 0}
    real_lw = openpyxl.load_workbook

    def counting_lw(*a, **kw):
        calls["n"] += 1
        return real_lw(*a, **kw)

    if signed is not None:
        F.SIGNED_XLSX = Path(signed)
    if signed_sha is not None:
        F.SIGNED_SHA = signed_sha
    F.OUT_CSV = outdir / OUT_NAMES[0]
    F.OUT_PROV = outdir / OUT_NAMES[1]
    F.OUT_SIDE = outdir / OUT_NAMES[2]
    openpyxl.load_workbook = counting_lw
    try:
        yield calls
    finally:
        openpyxl.load_workbook = real_lw
        for k, v in saved.items():
            setattr(F, k, v)


def run(outdir, signed=None, signed_sha=None):
    """跑一遍 main()，返回 (成功?, 错误信息, load_workbook 调用次数)。"""
    buf = io.StringIO()
    with sandbox(outdir, signed, signed_sha) as calls:
        try:
            with contextlib.redirect_stdout(buf):
                rc = F.main()
            return rc == 0, "", calls["n"]
        except SystemExit as exc:
            return False, str(exc), calls["n"]


def produced(outdir):
    return sorted(p.name for p in outdir.iterdir())


def main():
    real = (F.HERE / "Batch3_B4_FINAL.xlsx").resolve()
    real_sha = sha(real)
    print("  被测签字件：%s" % real.name)
    print("    SHA-256 = %s" % real_sha)
    print("    出厂常量 = %s" % F.SIGNED_SHA)
    check("0 出厂 SIGNED_SHA 与真实签字件一致", F.SIGNED_SHA == real_sha,
          "" if F.SIGNED_SHA == real_sha else "不一致")

    # 运行前给工作目录里的三件产物拍快照，用来证明测试本身没碰它们
    prep = Path(F.HERE)
    snapshot = {n: sha(prep / n) for n in OUT_NAMES if (prep / n).is_file()}

    tmp = Path(tempfile.mkdtemp(prefix="finaltest_"))
    try:
        # ---------------- 1. 正常读取 ----------------
        d1 = tmp / "ok"
        d1.mkdir()
        ok, err, n_lw = run(d1)
        check("1 哈希匹配 -> 允许读取并派生", ok, err[:60])
        check("1a 产出 CSV / provenance / sidecar 三件",
              produced(d1) == sorted(OUT_NAMES), str(produced(d1)))
        check("1b 确实调用过 load_workbook（前置未被误拦）", n_lw >= 1,
              "调用 %d 次" % n_lw)
        csv_rows = []
        if (d1 / OUT_NAMES[0]).is_file():
            import csv as _csv
            csv_rows = list(_csv.DictReader(
                open(d1 / OUT_NAMES[0], encoding="utf-8-sig")))
        check("1c 派生 CSV 为 8 行 19 列",
              len(csv_rows) == 8 and (not csv_rows or len(csv_rows[0]) == 19),
              "%d 行" % len(csv_rows))
        check("1d 派生 CSV 的 approved_by 全为 wuxiaoxian",
              bool(csv_rows) and all(r["approved_by"] == "wuxiaoxian"
                                     for r in csv_rows))
        import json as _json
        side = {}
        if (d1 / OUT_NAMES[2]).is_file():
            side = _json.load(open(d1 / OUT_NAMES[2], encoding="utf-8"))
        check("1e sidecar 只含仍在 Gold 的两个样本",
              sorted(side.get("samples", {})) == ["V077", "V290"],
              str(sorted(side.get("samples", {}))))

        # ---------------- 2a. 追加一个字节 ----------------
        d2a = tmp / "tamper_byte"
        d2a.mkdir()
        f2a = d2a / "signed_copy.xlsx"
        data = real.read_bytes()
        f2a.write_bytes(data + b"\x00")
        ok, err, n_lw = run(d2a, signed=f2a, signed_sha=real_sha)
        check("2a 追加字节 -> 拦下", not ok, err[:60])
        check("2a-1 哈希闸门先于 load_workbook", n_lw == 0,
              "load_workbook 调用 %d 次" % n_lw)

        # ---------------- 2b. 合法 xlsx 改一个单元格 ----------------
        d2b = tmp / "tamper_cell"
        d2b.mkdir()
        f2b = d2b / "signed_edited.xlsx"
        shutil.copy2(real, f2b)
        wb = openpyxl.load_workbook(str(f2b))       # 计数器在外层，不受影响
        ws = wb.active
        hdr = [c.value for c in ws[1]]
        ws.cell(row=2, column=hdr.index("confidence_score") + 1).value = 0.01
        wb.save(str(f2b))
        wb.close()
        check("2b 篡改后仍是合法 xlsx（能被解析）",
              openpyxl.load_workbook(str(f2b)).sheetnames == ["B4_FINAL"])
        check("2b-1 篡改后哈希确实变了", sha(f2b) != real_sha,
              sha(f2b)[:16] + "…")
        ok, err, n_lw = run(d2b, signed=f2b, signed_sha=real_sha)
        check("2b-2 合法结构的篡改件 -> 仍被拦下", not ok, err[:60])
        check("2b-3 拦住它的是哈希闸门而非解析失败", n_lw == 0,
              "load_workbook 调用 %d 次" % n_lw)

        # ---------------- 3. 源文件缺失 ----------------
        d3 = tmp / "missing"
        d3.mkdir()
        ok, err, n_lw = run(d3, signed=d3 / "nope.xlsx", signed_sha=real_sha)
        check("3 源文件不存在 -> 拦下", not ok, err[:60])
        check("3a 同样在解析之前退出", n_lw == 0, "load_workbook 调用 %d 次" % n_lw)

        # ---------------- 4. 哈希不符 / 为空 ----------------
        d4a = tmp / "sha_empty"
        d4a.mkdir()
        ok, err, n_lw = run(d4a, signed=real, signed_sha="")
        check("4a SIGNED_SHA 置空 -> 拦下", not ok, err[:60])
        check("4a-1 未进入解析", n_lw == 0, "调用 %d 次" % n_lw)

        d4b = tmp / "sha_wrong"
        d4b.mkdir()
        ok, err, n_lw = run(d4b, signed=real, signed_sha="0" * 64)
        check("4b SIGNED_SHA 改成错值 -> 拦下", not ok, err[:60])
        check("4b-1 未进入解析", n_lw == 0, "调用 %d 次" % n_lw)

        # ---------------- 5. 失败不产生产物 ----------------
        for label, d in (("2a", d2a), ("2b", d2b), ("3", d3),
                         ("4a", d4a), ("4b", d4b)):
            got = [n for n in produced(d) if n in OUT_NAMES]
            check("5 场景 %s 未产出任何派生文件" % label, not got, str(got))

        # ---------------- 6. 源文件零改动 ----------------
        d6 = tmp / "readonly"
        d6.mkdir()
        before = sha(real)
        before_mtime = real.stat().st_mtime
        ok, err, _ = run(d6)
        after = sha(real)
        check("6 正常运行成功", ok, err[:60])
        check("6a 运行前后签字 xlsx 哈希完全一致", before == after,
              "%s… -> %s…" % (before[:16], after[:16]))
        check("6b 文件修改时间未被触碰",
              real.stat().st_mtime == before_mtime)
        check("6c 再跑一次仍一致（可重复派生）",
              run(d6)[0] and sha(real) == before)
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)

    # ---------------- 7. 测试本身没有污染工作目录 ----------------
    drift = [n for n, h in snapshot.items() if sha(prep / n) != h]
    check("7 测试未改动工作目录里的三件产物", not drift, str(drift))

    print()
    print("PASS=%d  FAIL=%d" % (len(PASS), len(FAIL)))
    if FAIL:
        print("失败用例：%s" % FAIL)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
