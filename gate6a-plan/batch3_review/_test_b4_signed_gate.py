# -*- coding: utf-8 -*-
"""B4 签字源入口闸门的正/负向回归（Reviewer P0-2）。

要证明的不是「guard_sealed 能用」，而是 **`_make_b4_final.main()` 在读签字件
内容之前就先验了字节哈希**。所以负向用例刻意只改一个数值单元格 ——
这种改动 `load_signed()` 是能通过的，如果报错来自内容校验而不是闸门，
就说明闸门放得太晚。断言错误信息必须以「签字源校验失败」开头。

用例：
  1  登记哈希一致            -> 放行，main() 跑通，5 行 V130 都带 condition
  2  只改一个数值单元格      -> 拦（且必须是闸门拦，不是内容校验拦）
  3  签字源文件缺失          -> 拦
  4  登记里哈希为空          -> 拦（拒绝默认放行）
  5  未登记的文件名          -> 放行（write），说明闸门只锁登记过的件
  6  真实签字源 vs 出厂登记   -> 一致
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

import _make_b4_final as M

HERE = Path(__file__).resolve().parent
REAL = HERE / "Batch3_B4_ANNOTATED.xlsx"
GATE_MSG = "签字源校验失败"

PASS, FAIL = [], []


def sha(p):
    h = hashlib.sha256()
    h.update(Path(p).read_bytes())
    return h.hexdigest()


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print("  [%s] %-46s %s" % ("PASS" if ok else "FAIL", name, detail))


def run_main(signed, registry, outdir, honour_superseded=False):
    """把生成器的路径全指向临时目录后跑一遍 main()，返回 (ok, 错误信息)。

    第十三轮起 `_make_b4_final.py` 顶部有 SUPERSEDED 停用闸（定稿事实源已改为
    PM 签字的 FINAL.xlsx）。这里默认临时解除它，好让闸门逻辑本身被测到；
    `honour_superseded=True` 时保留，用来验证停用闸确实生效。
    """
    saved = {k: getattr(M, k) for k in
             ("SIGNED", "SEALED_SHA_B4", "OUT_CSV", "OUT_XLSX", "OUT_PROV",
              "OUT_SIDE", "TO_SIGN", "SUPERSEDED_BY")}
    M.SIGNED = Path(signed)
    M.SEALED_SHA_B4 = registry
    if not honour_superseded:
        M.SUPERSEDED_BY = None
    M.OUT_CSV = outdir / "Batch3_B4_FINAL.csv"
    M.OUT_XLSX = outdir / "Batch3_B4_FINAL.xlsx"
    M.OUT_PROV = outdir / "Batch3_B4_PDF_PROVENANCE.csv"
    M.OUT_SIDE = outdir / "page_text_batch3_b4.json"
    M.TO_SIGN = outdir / "Batch3_B4_DRAFT_TO_SIGN.xlsx"
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = M.main()
        return rc == 0, ""
    except SystemExit as exc:
        return False, str(exc)
    finally:
        for k, v in saved.items():
            setattr(M, k, v)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="b4gate_"))
    try:
        # ---------- 6. 出厂登记与真实签字源一致 ----------
        print("  真实签字源：%s" % REAL.name)
        print("    sha256 = %s" % sha(REAL))
        check("6 真实签字源与出厂登记一致",
              M.SEALED_SHA_B4.get(REAL.name) == sha(REAL),
              M.SEALED_SHA_B4.get(REAL.name, "")[:16] + "…")

        # ---------- 1. 正向：登记一致 -> 放行 ----------
        d1 = tmp / "ok"
        d1.mkdir()
        src = d1 / REAL.name
        shutil.copy2(REAL, src)
        reg_ok = {REAL.name: sha(src)}
        ok, err = run_main(src, reg_ok, d1)
        check("1 登记一致 -> 放行并跑通 main()", ok, err[:70])
        if ok:
            import csv
            rows = list(csv.DictReader(open(d1 / "Batch3_B4_FINAL.csv",
                                            encoding="utf-8-sig")))
            v130 = [r for r in rows if r["sample_no"] == "V130"]
            cond_ok = all(r["condition"].strip() for r in v130)
            mark_ok = all(r["entered_by"] == "WB_Agent" for r in v130)
            pref_ok = all(r["notes"].startswith(M.WB_FILL_PREFIX) for r in v130)
            check("1a V130 五行 condition 非空", cond_ok,
                  str([r["condition"] for r in v130])[:80])
            check("1b V130 五行 entered_by=WB_Agent", mark_ok)
            check("1c V130 五行 notes 带补录前缀", pref_ok)
            v290 = [r for r in rows if r["sample_no"] == "V290"
                    and r["symbol"] == "II"]
            check("1d V290 II 条件已补",
                  bool(v290) and v290[0]["condition"] == "VCC = Max, VI Max = 5.5V",
                  v290[0]["condition"] if v290 else "-")

        # ---------- 2. 负向：只改一个数值单元格 ----------
        d2 = tmp / "tamper"
        d2.mkdir()
        src2 = d2 / REAL.name
        shutil.copy2(REAL, src2)
        reg2 = {REAL.name: sha(src2)}          # 先按原样登记
        wb = openpyxl.load_workbook(str(src2))
        ws = wb.active
        hdr = [c.value for c in ws[1]]
        col = hdr.index("confidence_score") + 1
        ws.cell(row=2, column=col).value = 0.01   # 结构仍合法，load_signed 能过
        wb.save(str(src2))
        wb.close()
        check("2  篡改后哈希确实变了", sha(src2) != reg2[REAL.name],
              sha(src2)[:16] + "…")
        ok2, err2 = run_main(src2, reg2, d2)
        check("2a 篡改签字源 -> 拦下", not ok2, err2[:70])
        check("2b 是闸门拦的（先于内容校验）", err2.startswith(GATE_MSG), err2[:40])
        check("2c 拦下后没有产出 FINAL",
              not (d2 / "Batch3_B4_FINAL.csv").exists())

        # ---------- 3. 签字源缺失 ----------
        d3 = tmp / "missing"
        d3.mkdir()
        ok3, err3 = run_main(d3 / REAL.name, {REAL.name: "deadbeef"}, d3)
        check("3  签字源缺失 -> 拦下",
              not ok3 and err3.startswith(GATE_MSG), err3[:70])

        # ---------- 4. 登记缺哈希 ----------
        d4 = tmp / "nohash"
        d4.mkdir()
        src4 = d4 / REAL.name
        shutil.copy2(REAL, src4)
        ok4, err4 = run_main(src4, {REAL.name: ""}, d4)
        check("4  登记哈希为空 -> 拦下（不默认放行）",
              not ok4 and err4.startswith(GATE_MSG), err4[:70])

        # ---------- 5. 未登记的文件名 -> write ----------
        d5 = tmp / "unreg"
        d5.mkdir()
        src5 = d5 / "Batch3_B4_ANNOTATED_copy.xlsx"
        shutil.copy2(REAL, src5)
        ok5, err5 = run_main(src5, M.SEALED_SHA_B4, d5)
        check("5  未登记件 -> 放行（write）", ok5, err5[:70])

        # ---------- 7. 停用闸：默认状态下必须拒绝运行 ----------
        d7 = tmp / "superseded"
        d7.mkdir()
        ok7, err7 = run_main(REAL, M.SEALED_SHA_B4, d7, honour_superseded=True)
        check("7  停用闸生效（不再按 ANNOTATED 重造）",
              not ok7 and "已停用" in err7, err7[:60])
        check("7a 停用后没有任何产出",
              not (d7 / "Batch3_B4_FINAL.csv").exists())
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)

    print()
    print("PASS=%d  FAIL=%d" % (len(PASS), len(FAIL)))
    if FAIL:
        print("失败用例：%s" % FAIL)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
