# -*- coding: utf-8 -*-
"""v2.8_r3 三态与 P1 超长数字定向验证（外层断言测试，零第三方依赖）。

本脚本不改动 test_verify_reviewer.py 的 81 项口径。做法是用 importlib 加载它，
再以 monkeypatch 构造「环境具备 / 环境受限 / 混合三态」三类场景，直接检查
RESULTS、SKIPPED 与 main() 退出码。

用法：
    python -W error test_three_state_v28r3.py --selfcheck
    python -W error test_three_state_v28r3.py --full real
    python -W error test_three_state_v28r3.py --full limited
    python -W error test_three_state_v28r3.py --full mixed

场景说明：
    real     不打桩，本机真实 symlink / 8.3 短名 / junction
    limited  symlink、junction 创建均抛 OSError，8.3 短名不可用
    mixed    在 limited 基础上，再篡改 parse_version_tuple 制造真实 FAIL
"""
from __future__ import print_function

import argparse
import contextlib
import importlib.util
import io
import os
import shutil
import subprocess
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TV = os.path.join(HERE, "test_verify_reviewer.py")
DEFAULT_VR = os.path.join(HERE, "verify_reviewer.py")
DEFAULT_DATA = os.path.abspath(os.path.join(HERE, "..", "..", "runs", "_data_check"))

CHECKS = []
_SEQ = [0]

# r4 防漂移基线：真实环境（无打桩）全量 81 条断言的 46 个 cid 分布。
# 任一测试组增删或 cid 改名都会让 S4 的固定断言失败，避免统计口径静默漂移。
EXPECTED_CID_COUNTS = {"T1": 28, "T3": 5, "T5g": 5}
EXPECTED_CID_COUNTS.update(
    (cid, 1) for cid in (
        "T2a T2b T2c T2d T2e "
        "T4a T4b "
        "T5a T5b T5c T5d T5e T5f "
        "T6a T6b T6c "
        "T7a T7b "
        "T8a T8b T8c T8d T8e T8f "
        "T9a T9b T9c "
        "T10a T10b T10c T10d T10e T10f T10g T10h T10i T10j T10k "
        "T11a T11b T11c T11d T11e"
    ).split()
)


def check(name, cond, detail=""):
    CHECKS.append((name, bool(cond), detail))
    print("  [%s] %-46s %s" % ("PASS" if cond else "FAIL", name, detail))


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_tv():
    """每次返回全新的测试脚本模块实例，避免场景之间状态污染。"""
    _SEQ[0] += 1
    tv = load_module(DEFAULT_TV, "tv_r3_%d" % _SEQ[0])
    tv.TARGET = os.path.abspath(DEFAULT_VR)
    tv.DATA = os.path.abspath(DEFAULT_DATA)
    sys.argv = ["test_verify_reviewer.py", "--data", tv.DATA,
                "--verifier", tv.TARGET]
    return tv


def reset(tv):
    tv.RESULTS[:] = []
    tv.SKIPPED[:] = []


def cleanup(tv):
    shutil.rmtree(tv.SANDBOX, ignore_errors=True)


def run_main(tv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = tv.main()
    return rc, buf.getvalue()


def stat_lines(out):
    return [l for l in out.splitlines()
            if l.startswith("统计：") or l.startswith("  SKIP 明细")
            or l.startswith("  FAIL [") or l.startswith("结论：")]


def _raise_oserror(*_a, **_k):
    raise OSError("mock: 当前环境无法创建符号链接 / junction")


def _no_short_path(_p):
    return None


def install_limited(tv):
    tv.make_symlink_dir = _raise_oserror
    tv.make_junction = _raise_oserror
    tv.short_path = _no_short_path


def install_fail(tv):
    """篡改主程序模块，让 T1 的多条版本解析断言真实失败。"""
    real_load = tv.load_target

    def tampered_load():
        mod = real_load()
        mod.parse_version_tuple = lambda s: (3, 12)
        return mod

    tv.load_target = tampered_load


# ------------------------------------------------------------------- P1
def p1_long_digits():
    print("\nP1 超长数字（主程序 parse_version_tuple 修复后的回归断言）")
    vr = load_module(DEFAULT_VR, "vr_p1")
    f = vr.parse_version_tuple
    cases = [
        ("1" * 5000 + ".0", None, "major 5000 位"),
        ("1" * 4301 + ".0", None, "刚好超过 4300 位上限"),
        ("3." + "1" * 5000, None, "minor 5000 位"),
        ("3.12." + "1" * 5000, None, "patch 5000 位"),
        ("3.13.15", (3, 13, 15), "正常三段不受影响"),
        ("3.10", (3, 10), "正常两段不受影响"),
        ("Python 3.12 (64-bit)", (3, 12), "白名单括号注释不受影响"),
        ("3.12 (main)", None, "括号白名单仍生效"),
        ("2026.11.10", None, "major>=100 仍拒绝"),
        (3.12, None, "非字符串仍返回 None"),
        (None, None, "None 仍返回 None"),
    ]
    bad = []
    for s, want, desc in cases:
        try:
            got = f(s)
            if got != want:
                bad.append("%s: got=%r want=%r" % (desc, got, want))
        except Exception as e:
            bad.append("%s: RAISED %s: %s" % (desc, type(e).__name__, e))
    check("P1 超长数字与白名单共 %d 例全部符合" % len(cases),
          not bad, "; ".join(bad) if bad else "无异常、无错值")


# ------------------------------------------------------------------- S1
def s1_real():
    print("\nS1 环境具备（真机，不打桩）")
    tv = load_tv()
    vr = tv.load_target()
    reset(tv)
    try:
        tv.t2(vr)
        tv.t4(vr)
        tv.t6(vr)
        ids = [r[0] for r in tv.RESULTS]
        fails = [r for r in tv.RESULTS if not r[2]]
        check("S1 T2/T4/T6 全部非 FAIL", not fails,
              "共 %d 条记录" % len(tv.RESULTS))
        check("S1 T2a/T4a 已登记（建链成功）",
              "T2a" in ids and "T4a" in ids, ",".join(ids))
        if "T6a" in tv.SKIPPED:
            check("S1 T6a 本机 8.3 不可用，记 SKIP", True,
                  "PASS 分支本机未覆盖，由 S2 覆盖 SKIP 分支")
        else:
            ok = ("T6a" in ids
                  and all(r[2] for r in tv.RESULTS if r[0] == "T6a"))
            check("S1 T6a 可用且正确记 PASS", ok,
                  "SKIPPED=%r" % (tv.SKIPPED,))
        check("S1 无 SKIP 登记（除可能的 T6a）",
              all(c == "T6a" for c in tv.SKIPPED),
              "SKIPPED=%r" % (tv.SKIPPED,))
    finally:
        cleanup(tv)


# ------------------------------------------------------------------- S2
def s2_limited():
    print("\nS2 环境受限（模拟 OSError 与 8.3 不可用）")
    tv = load_tv()
    vr = tv.load_target()
    reset(tv)
    install_limited(tv)
    try:
        tv.t2(vr)
        tv.t4(vr)
        tv.t6(vr)
        ids = [r[0] for r in tv.RESULTS]
        check("S2 SKIPPED 恰为 T2/T4/T6a",
              tv.SKIPPED == ["T2", "T4", "T6a"], repr(tv.SKIPPED))
        check("S2 三组各只登记 1 条", len(tv.RESULTS) == 3, repr(ids))
        check("S2 SKIP 项均非 FAIL", all(r[2] for r in tv.RESULTS))
        check("S2 SKIP 后不再产生后续断言",
              not any(i.startswith(("T2a", "T2b", "T4a", "T4b", "T6b", "T6c"))
                      for i in ids), repr(ids))
        check("S2 SKIP 不计入 PASS（统计扣除）",
              len(tv.RESULTS) - len(tv.SKIPPED) == 0,
              "n=%d skip=%d" % (len(tv.RESULTS), len(tv.SKIPPED)))
    finally:
        cleanup(tv)


# ------------------------------------------------------------------- S3
def s3_mixed():
    print("\nS3 混合三态（真实 FAIL + SKIP + PASS）")
    tv = load_tv()
    reset(tv)
    install_limited(tv)
    install_fail(tv)
    try:
        rc, out = run_main(tv)
    finally:
        cleanup(tv)
    n = len(tv.RESULTS)
    bad = [r for r in tv.RESULTS if not r[2]]
    n_skip = len(tv.SKIPPED)
    n_pass = n - n_skip - len(bad)
    fail_ids = set(r[0] for r in bad)
    for line in stat_lines(out)[:6]:
        print("      %s" % line)
    check("S3 真实 FAIL 导致退出码为 1", rc == 1, "rc=%d" % rc)
    check("S3 存在真实 FAIL", len(bad) > 0, "FAIL=%d" % len(bad))
    check("S3 存在 SKIP", n_skip > 0, "SKIP=%d" % n_skip)
    check("S3 存在 PASS", n_pass > 0, "PASS=%d" % n_pass)
    check("S3 三态守恒 PASS+SKIP+FAIL==n",
          n_pass + n_skip + len(bad) == n, "n=%d" % n)
    check("S3 FAIL 未被降级为 SKIP",
          not (fail_ids & set(tv.SKIPPED)),
          "FAIL ids=%r / SKIPPED=%r" % (sorted(fail_ids), tv.SKIPPED))
    check("S3 统计行确实打印 FAIL>0",
          any(l.startswith("统计：") and " FAIL=0" not in l for l in out.splitlines()),
          next((l for l in out.splitlines() if l.startswith("统计：")), ""))


# ------------------------------------------------------------------- S4
def s4_uniqueness():
    print("\nS4 唯一性与三态统计口径（本机全量、无打桩）")
    tv = load_tv()
    reset(tv)
    try:
        rc, out = run_main(tv)
    finally:
        cleanup(tv)
    n = len(tv.RESULTS)
    counter = Counter(r[0] for r in tv.RESULTS)
    reused = {k: v for k, v in sorted(counter.items()) if v > 1}
    bad = [r for r in tv.RESULTS if not r[2]]
    n_skip = len(tv.SKIPPED)
    n_pass = n - n_skip - len(bad)
    check("S4 全量项数为 81", n == 81, "n=%d rc=%d" % (n, rc))
    check("S4 SKIPPED 无重复",
          len(tv.SKIPPED) == len(set(tv.SKIPPED)), repr(tv.SKIPPED))
    check("S4 每个 SKIP cid 在 RESULTS 中恰好一次",
          all(sum(1 for r in tv.RESULTS if r[0] == c) == 1
              for c in tv.SKIPPED), repr(tv.SKIPPED))
    check("S4 三态守恒", n_pass + n_skip + len(bad) == n,
          "PASS=%d SKIP=%d FAIL=%d" % (n_pass, n_skip, len(bad)))
    check("S4 退出码为 0（SKIP 不导致非零）", rc == 0, "rc=%d" % rc)
    expected = Counter(EXPECTED_CID_COUNTS)
    missing = sorted(set(expected) - set(counter))
    extra = sorted(set(counter) - set(expected))
    drift = {k: (counter.get(k), expected.get(k))
             for k in set(expected) | set(counter)
             if counter.get(k) != expected.get(k)}
    check("S4 唯一 cid 数固定为 46", len(counter) == 46,
          "unique=%d baseline=%d" % (len(counter), len(expected)))
    check("S4 46 个 cid 分布与固定基线逐项一致",
          counter == expected,
          "缺失=%r 多出=%r 计数差异=%r" % (missing, extra, drift))
    print("  [INFO] 81 是断言条数口径，唯一 cid 数 = %d" % len(counter))
    print("  [INFO] 复用 ID（分组一対多）：%r" % (reused,))
    print("  [INFO] 统计行：%s"
          % next((l for l in out.splitlines() if l.startswith("统计：")), ""))


# ------------------------------------------------------------------- S5
def s5_typeerror():
    print("\nS5 TypeError 不得被降级为 SKIP（r4 T7 异常捕获收窄）")
    tv = load_tv()
    vr = tv.load_target()
    reset(tv)

    def raise_typeerror(*_a, **_k):
        raise TypeError("mock: 非预期的接口错误")

    tv.make_junction = raise_typeerror
    raised = None
    try:
        tv.t7(vr)
    except TypeError as e:
        raised = e
    finally:
        cleanup(tv)
    check("S5 TypeError 向上抛出，未被 except 捕获",
          raised is not None,
          str(raised) if raised is not None else "未抛出")
    check("S5 SKIPPED 中无 T7a / T7b",
          not any(c in ("T7a", "T7b") for c in tv.SKIPPED),
          repr(tv.SKIPPED))
    check("S5 RESULTS 未登记任何 T7 的 SKIP 记录",
          len(tv.RESULTS) == 0, "RESULTS=%r" % (tv.RESULTS,))

    # 进程级：完整 main() 同样向上抛出，脚本以非零退出码终止。
    driver = """
import importlib.util, sys, os
spec = importlib.util.spec_from_file_location("tv_ty", r"%s")
tv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tv)
tv.TARGET = r"%s"
tv.DATA = r"%s"
sys.argv = ["test_verify_reviewer.py", "--data", tv.DATA, "--verifier", tv.TARGET]
def boom(*_a, **_k):
    raise TypeError("mock: 非预期的接口错误")
tv.make_junction = boom
sys.exit(tv.main())
""" % (os.path.abspath(DEFAULT_TV), os.path.abspath(DEFAULT_VR),
       os.path.abspath(DEFAULT_DATA))
    proc = subprocess.run(
        [sys.executable, "-W", "error", "-c", driver],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        encoding="utf-8", errors="replace")
    out = proc.stdout or ""
    check("S5 进程级退出码非 0", proc.returncode != 0,
          "rc=%d" % proc.returncode)
    check("S5 输出含未捕获的 TypeError", "TypeError" in out,
          next((l for l in out.splitlines() if "TypeError" in l), "")[:120])
    check("S5 未打印 [SKIP] T7a", "[SKIP] T7a" not in out)
    check("S5 未走到汇总统计行（main 提前终止）",
          "统计：共" not in out, "main() 在汇总前终止")
    print("  [INFO] 实际表现为未捕获异常终止（退出码非 0），未在 RESULTS 中登记 FAIL 记录")


def selfcheck():
    print("=" * 78)
    print("v2.8_r4 三态 / P1 / 异常收窄定向验证（外层断言测试）")
    print("=" * 78)
    print("test  = %s" % DEFAULT_TV)
    print("vr    = %s" % DEFAULT_VR)
    print("data  = %s" % DEFAULT_DATA)
    p1_long_digits()
    s1_real()
    s2_limited()
    s3_mixed()
    s4_uniqueness()
    s5_typeerror()
    bad = [c for c in CHECKS if not c[1]]
    print("\n" + "=" * 78)
    print("定向断言：共 %d 项，PASS=%d FAIL=%d"
          % (len(CHECKS), len(CHECKS) - len(bad), len(bad)))
    for name, _, detail in bad:
        print("  FAIL [%s] %s" % (name, detail))
    print("=" * 78)
    return 0 if not bad else 1


def full(mode):
    tv = load_tv()
    if mode in ("limited", "mixed"):
        install_limited(tv)
    if mode == "mixed":
        install_fail(tv)
    print("=" * 78)
    print("mode = %s   test = %s" % (mode, os.path.basename(DEFAULT_TV)))
    print("=" * 78)
    try:
        rc, out = run_main(tv)
    finally:
        cleanup(tv)
    for line in stat_lines(out):
        print(line)
    n = len(tv.RESULTS)
    bad = [r for r in tv.RESULTS if not r[2]]
    n_skip = len(tv.SKIPPED)
    n_pass = n - n_skip - len(bad)
    print("RESULTS=%d  PASS=%d SKIP=%d FAIL=%d  SKIPPED=%r"
          % (n, n_pass, n_skip, len(bad), tv.SKIPPED))
    print("EXIT=%d" % rc)
    return rc


def main():
    ap = argparse.ArgumentParser(description="v2.8_r3 三态与 P1 定向验证")
    ap.add_argument("--selfcheck", action="store_true", help="跑 P1 + S1..S4 定向断言")
    ap.add_argument("--full", choices=("real", "limited", "mixed"),
                    help="按指定场景跑一次完整 main()")
    ap.add_argument("--data", default=None, help="覆盖数据目录")
    ap.add_argument("--test", default=None, help="覆盖测试脚本路径")
    ap.add_argument("--verifier", default=None, help="覆盖主程序路径")
    args = ap.parse_args()
    if args.data:
        globals()["DEFAULT_DATA"] = os.path.abspath(args.data)
    if args.test:
        globals()["DEFAULT_TV"] = os.path.abspath(args.test)
    if args.verifier:
        globals()["DEFAULT_VR"] = os.path.abspath(args.verifier)
    if args.selfcheck:
        return selfcheck()
    if args.full:
        return full(args.full)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
