#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""verify_reviewer.py v2.8 定向回归用例

覆盖 Reviewer 在 v2.4 复核中点名的三类边界：

  T1  P1 版本解析锚定 fullmatch
      "notpython3.12" / "build-3.12" -> None（v2.4 的 search 会误接受子串）
      "3.12.1-extra" -> (3,12,1)（连字符后缀允许）
      "3.12 (64-bit)" -> (3,12)（括号注释允许）
      ""/"abc"/"build 2026" -> None；"2026.11.10" -> None（major>=100）
      裸 "3.12.1rc1" 与 "v3.9.1-rc1" -> None（与实现一致，docstring 已同步）
      v2.7 补测三项空白/类型边界：
        "Python 3.12 (64-bit)" -> (3,12)（前缀 + 白名单括号可组合）
        "Python3.12" -> None（前缀后必须有空白，\\s+ 不可省）
        "3.12 (64-bit) " -> (3,12)（尾部空白被 strip 与 \\s*$ 吸收）
        非字符串输入（None / 3.12）-> None，不抛 AttributeError

  T2  符号链接根目录 -> RuntimeError；main exit=1；无 V1–V10 明细
  T3  路径含 ".." -> RuntimeError: 拒绝 '..' 路径段
  T4  symlink 父目录（linkdir/file.csv）-> RuntimeError
  T6  8.3 短名根（realpath != abspath 但无链接）不被拒绝
  T7  junction 根 islink=False 仍被拒（靠 reparse tag）
  T8  monkeypatch os.lstat 抛 PermissionError -> RuntimeError（fail-closed）
  T9  ctx.p("nonexistent_dir/file.csv") 不因 FileNotFoundError 误判为链接

  T10 v2.6/v2.7：ctx.p 只接受相对路径
      T10a 根外绝对路径；T10b 根内绝对路径；T10c Windows 盘符；T10d UNC
      T10e 绝对路径 + ".."（先于越界检查）；T10f 绝对路径指向 symlink
      T10g 对照 ctx.p(SAMPLE_FILE) 仍可用；T10h 优先级自证（绝对路径先于 ".."）
      T10i 单反斜杠根路径 \\Windows\\System32（v2.7 新增，POSIX 上 isabs 为 False）
      T10j/T10k 盘符相对路径 D:secret.csv / C:x（v2.8 新增，经 Ctx.p 断言被拒）

  T11 v2.8：解耦验证 —— 注入合法但不匹配的 generation_python，V8 仍 PASS、
      汇总行仍报 MISMATCH、OVERALL_PASS 与退出码不受影响

  T5  P3 异常安全
      T5a 缺 population -> 汇总 VERIFIED；'build 2026' -> invalid；config 删除 -> unavailable
      T5b load_cfg 抛异常 -> unavailable，main 不崩
      T5c has 抛 RuntimeError -> unavailable，main 不崩
      T5d check_v8 源码中无对 ctx.gen_py_*/py_match 的赋值

用法：
  python tools/stage_a/test_verify_reviewer.py
  python test_verify_reviewer.py                    # 解压后与数据同目录：自动定位
  python test_verify_reviewer.py --data <目录> --verifier <脚本路径>
退出码 0 = 全部通过；1 = 存在失败。
"""

from __future__ import print_function

import argparse
import importlib.util
import inspect
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))


def _pick_data():
    """数据目录自动定位：本仓库布局 -> 脚本同级目录（Reviewer 解压后的布局）。"""
    for cand in (os.path.join(PROJ, "runs", "stage_A_sampling"), HERE):
        if os.path.isfile(os.path.join(cand, "sample_350.csv")):
            return cand
    return os.path.join(PROJ, "runs", "stage_A_sampling")


def _pick_sandbox():
    """临时产物目录：优先本仓库 runs/，否则退到系统临时目录。"""
    root = os.path.join(PROJ, "runs")
    if not os.path.isdir(root):
        root = tempfile.gettempdir()
    return os.path.join(root, "_v28_test")


DATA = _pick_data()
TARGET = os.path.join(HERE, "verify_reviewer.py")
SANDBOX = _pick_sandbox()

PY_RUNTIME = "%d.%d.%d" % sys.version_info[:3]
RESULTS = []
SKIPPED = []          # 环境不具备条件而无法覆盖的项：既不算 PASS 也不算 FAIL


def _utf8_stdout():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def check(cid, desc, cond, detail=""):
    RESULTS.append((cid, desc, bool(cond), detail))
    print("  [%s] %-4s %s" % ("PASS" if cond else "FAIL", cid, desc))
    if detail:
        for line in str(detail).splitlines():
            print("            %s" % line)


def skip(cid, desc, reason=""):
    """记录"环境不具备测试条件"。与 FAIL 区分：不计入 PASS，也不影响退出码。"""
    SKIPPED.append(cid)
    RESULTS.append((cid, desc, True, reason))
    print("  [SKIP] %-4s %s" % (cid, desc))
    if reason:
        for line in str(reason).splitlines():
            print("            %s" % line)


def load_target():
    spec = importlib.util.spec_from_file_location("vr_under_test", TARGET)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_script(args):
    cmd = [sys.executable, TARGET] + list(args)
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=HERE)
    return p.returncode, p.stdout.decode("utf-8", "replace")


def fresh(path):
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)
    os.makedirs(path)
    return path


def rm_link(path):
    if not os.path.exists(path) and not os.path.islink(path):
        return
    try:
        if os.path.islink(path):
            os.unlink(path)
            return
    except OSError:
        pass
    try:
        os.rmdir(path)
    except OSError:
        try:
            os.unlink(path)
        except OSError:
            pass


def make_symlink_dir(src, dst):
    os.symlink(src, dst, target_is_directory=True)


def make_junction(src, dst):
    subprocess.check_call(["cmd", "/c", "mklink", "/J", dst, src],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def short_path(p):
    if os.name != "nt":
        return None
    import ctypes
    buf = ctypes.create_unicode_buffer(1024)
    n = ctypes.windll.kernel32.GetShortPathNameW(p, buf, 1024)
    return buf.value if n else None


# ------------------------------------------------------------------ T1
def t1(vr):
    print("\nT1  P1 版本解析：fullmatch 整串锚定")
    cases = [
        ("notpython3.12",  None,       "整串不是版本号（v2.4 search 会误接受 3.12）"),
        ("build-3.12",     None,       "前缀不是 Python"),
        ("3.12.1-extra",   (3, 12, 1), "连字符后缀允许"),
        ("3.12 (32-bit)",  (3, 12),    "白名单括号注释 32-bit"),
        ("3.12 (64-bit)",  (3, 12),    "白名单括号注释，64 不当 patch"),
        ("3.12(64-bit)",   None,       "括号前缺空白（v2.6 的 \\s* 会误接受）"),
        ("3.12 (main)",    None,       "括号内容不在 32/64-bit 白名单"),
        ("3.12 (64-bit)-extra", None,  "括号注释后不得再接后缀"),
        ("3.12-x-y",       None,       "后缀内部含连字符（v2.6 会吞成单后缀）"),
        ("3.12.1-post1",   (3, 12, 1), "普通连字符后缀，不解释为 PEP 440"),
        ("3.12+",          None,       "空后缀（+ 后无内容）"),
        ("3.12++extra",    None,       "第二个 + 不在字符集内"),
        ("Python 3.12 (64-bit)", (3, 12), "前缀 + 白名单括号注释（v2.7 补测）"),
        ("Python3.12",     None,       "Python 前缀后缺空白，\\s+ 不可省（v2.7 补测）"),
        ("3.12 (64-bit) ", (3, 12),    "尾部空白由 strip + \\s*$ 共同吸收（v2.7 补测）"),
        (3.12,             None,       "非字符串 float 不得抛 AttributeError（v2.7 补测）"),
        ("Python 3.12.1",  (3, 12, 1), "Python 前缀"),
        ("",               None,       "空串"),
        ("abc",            None,       "无数字"),
        ("build 2026",     None,       "只有构建号"),
        ("2026.11.10",     None,       "major>=100 拒绝"),
        ("3.13.15",        (3, 13, 15), "三段完整"),
        ("3.10",           (3, 10),    "只到 minor"),
        ("python 3.13",    (3, 13),    "小写前缀"),
        ("3.13.15+build.7", (3, 13, 15), "加号后缀允许"),
        ("3.12.1rc1",      None,       "裸预发布后缀不接受（与实现一致）"),
        ("v3.9.1-rc1",     None,       "\"v\" 前缀不合法"),
        (None,             None,       "非字符串"),
    ]
    for raw, want, why in cases:
        got = vr.parse_version_tuple(raw)
        check("T1", "parse_version_tuple(%r) == %r  # %s" % (raw, want, why),
              got == want, "实际 %r" % (got,))


# ------------------------------------------------------------------ T2
def t2(vr):
    print("\nT2  符号链接根目录必须报错")
    base = fresh(os.path.join(SANDBOX, "linkroot"))
    link = os.path.join(base, "delivery_link")
    try:
        make_symlink_dir(DATA, link)
    except OSError as e:
        skip("T2", "当前环境无法创建目录符号链接，测试未覆盖",
             "%s: %s" % (type(e).__name__, e))
        return
    print("       realpath = %s" % os.path.realpath(link))
    print("       abspath  = %s" % os.path.abspath(link))
    try:
        vr.Ctx(link)
        ok, detail = False, "未报错（根目录可被符号链接伪装）"
    except RuntimeError as e:
        ok, detail = ("拒绝符号链接" in str(e)), "RuntimeError: %s" % e
    check("T2a", "Ctx(<symlink root>) 抛 RuntimeError", ok, detail)

    rc, out = run_script(["--dir", link])
    check("T2b", "main(--dir <symlink root>) 退出码 == 1", rc == 1, "returncode=%d" % rc)
    check("T2c", "输出含『拒绝符号链接：交付根目录』",
          "拒绝符号链接：交付根目录" in out,
          "命中行：%r" % [l for l in out.splitlines() if "拒绝符号链接" in l])
    check("T2d", "未执行任何断言（无『V1–V10 断言明细』）",
          "V1–V10 断言明细" not in out, "")
    check("T2e", "输出 OVERALL_PASS = false", "OVERALL_PASS               = false" in out, "")


# ------------------------------------------------------------------ T3
def t3(vr):
    print("\nT3  路径含 '..' 必须报错")
    ctx = vr.Ctx(DATA)
    for bad in ("../sample_350.csv", "sub/../../etc/passwd", "..", "./../x"):
        try:
            ctx.p(bad)
            ok, detail = False, "未报错（可越界，危险）"
        except RuntimeError as e:
            ok = (".." in str(e))
            detail = "RuntimeError: %s" % e
        check("T3", "ctx.p(%r) 被拒绝" % bad, ok, detail)
    try:
        p = ctx.p("sample_350.csv")
        ok, detail = os.path.isfile(p), p
    except Exception as e:
        ok, detail = False, "%s: %s" % (type(e).__name__, e)
    check("T3", "对照：ctx.p('sample_350.csv') 正常解析", ok, detail)


# ------------------------------------------------------------------ T4
def t4(vr):
    print("\nT4  symlink 父目录（linkdir/file.csv）必须报错")
    base = fresh(os.path.join(SANDBOX, "parentlink"))
    link = os.path.join(base, "linkdir")
    try:
        make_symlink_dir(DATA, link)
    except OSError as e:
        skip("T4", "当前环境无法创建目录符号链接，测试未覆盖",
             "%s: %s" % (type(e).__name__, e))
        return
    ctx = vr.Ctx(SANDBOX)
    rel = "parentlink/linkdir/sample_350.csv"
    try:
        ctx.p(rel)
        ok, detail = False, "未报错（父目录链接漏判）"
    except RuntimeError as e:
        ok = ("拒绝符号链接" in str(e) and "linkdir" in str(e))
        detail = "RuntimeError: %s" % e
    check("T4a", "ctx.p(<经 symlink 父目录的相对路径>) 抛 RuntimeError", ok, detail)

    # 对照：同一相对路径去掉链接层后必须可解析
    shutil.copy2(os.path.join(DATA, "sample_350.csv"),
                 os.path.join(base, "sample_350.csv"))
    try:
        p = ctx.p("parentlink/sample_350.csv")
        ok, detail = os.path.isfile(p), p
    except Exception as e:
        ok, detail = False, "%s: %s" % (type(e).__name__, e)
    check("T4b", "对照：同级真实文件正常解析", ok, detail)


# ------------------------------------------------------------------ T5
def t5(vr):
    print("\nT5  P3 异常安全：三态实测（子进程）")
    root = fresh(os.path.join(SANDBOX, "nopop"))
    for fn in ("sample_350.csv", "human_label_template.csv", "manifest.sha256",
               "sampling_config.json", "sampling_report.md", "ANNOTATION_GUIDE.md"):
        shutil.copy2(os.path.join(DATA, fn), os.path.join(root, fn))
    shutil.copy2(TARGET, os.path.join(root, "verify_reviewer.py"))
    assert not os.path.exists(os.path.join(root, "population_manifest.csv"))

    cfgp = os.path.join(root, "sampling_config.json")
    with io.open(cfgp, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)

    def write_cfg(obj):
        with io.open(cfgp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(obj, ensure_ascii=False, indent=2))

    def status_line(out):
        m = re.search(r"^PYTHON_REPRODUCIBILITY\s+= (.+)$", out, re.M)
        return m.group(1).strip() if m else None

    cfg["generation_python"] = PY_RUNTIME
    write_cfg(cfg)
    rc, out = run_script(["--dir", root])
    line = status_line(out)
    print("       汇总行 = %s" % line)
    check("T5a", "缺总体 -> V8 SKIP", "[SKIP] V8" in out,
          "命中行：%r" % [l for l in out.splitlines() if "SKIP" in l and "V8" in l])
    check("T5b", "未误报『config 无 generation_python 记录』",
          "config 无 generation_python 记录" not in out)
    want = "VERIFIED (generation_python=%s, runtime=%s)" % (PY_RUNTIME, PY_RUNTIME)
    check("T5c", "有合法记录 -> %r" % want, line == want, "实际 %r" % (line,))

    cfg["generation_python"] = "build 2026"
    write_cfg(cfg)
    rc, out = run_script(["--dir", root])
    line = status_line(out)
    want = "UNVERIFIED (config 记录值 'build 2026' 无效，视为未记录)"
    check("T5d", "无效记录 -> invalid 而非『无记录』", line == want, "实际 %r" % (line,))

    os.remove(cfgp)
    rc, out = run_script(["--dir", root])
    line = status_line(out)
    want = "UNVERIFIED (config unavailable/read error)"
    check("T5e", "config 删除 -> unavailable", line == want, "实际 %r" % (line,))
    check("T5f", "全程无 Traceback", "Traceback (most recent call last)" not in out,
          "returncode=%d" % rc)


def t5_inject(vr):
    print("\nT5g  P3 注入异常：check_python_env 不得让 main() 崩")

    # T5g-1：load_cfg 抛异常
    ctx = vr.Ctx(DATA)
    ctx.load_cfg = lambda: (_ for _ in ()).throw(ValueError("injected load_cfg"))
    vr.check_python_env(ctx)
    check("T5g", "load_cfg 抛 ValueError -> unavailable",
          ctx.gen_py_unavailable and "ValueError" in (ctx.gen_py_error or ""),
          "unavailable=%s error=%r" % (ctx.gen_py_unavailable, ctx.gen_py_error))
    check("T5g", "读取失败时 py_match 保持 None、gen_py_invalid 保持 None（不误报 MISMATCH）",
          ctx.py_match is None and ctx.gen_py_invalid is None,
          "py_match=%r gen_py_invalid=%r gen_py_val=%r"
          % (ctx.py_match, ctx.gen_py_invalid, ctx.gen_py_val))

    # T5g-2：has 抛 RuntimeError（模拟 P2 严格路径检查在 config 上抛错）
    ctx2 = vr.Ctx(DATA)
    ctx2.has = lambda rel: (_ for _ in ()).throw(RuntimeError("injected has"))
    vr.check_python_env(ctx2)
    check("T5g", "has 抛 RuntimeError -> unavailable",
          ctx2.gen_py_unavailable and "RuntimeError" in (ctx2.gen_py_error or ""),
          "unavailable=%s error=%r" % (ctx2.gen_py_unavailable, ctx2.gen_py_error))
    check("T5g", "unavailable 与 invalid 互斥：unavailable=True 时 invalid 必为 None",
          ctx2.gen_py_invalid is None and ctx2.py_match is None,
          "gen_py_invalid=%r py_match=%r" % (ctx2.gen_py_invalid, ctx2.py_match))

    # T5g-3：check_v8 不得写 gen_py_*
    src = inspect.getsource(vr.check_v8)
    bad = re.findall(r"ctx\.(?:gen_py_\w+|py_match|gen_py_key)\s*=", src)
    check("T5g", "check_v8 源码中对 ctx.gen_py_*/py_match 无赋值", not bad,
          "命中 %r（check_v8 共 %d 行）" % (bad, len(src.splitlines())))


# ------------------------------------------------------------------ T6
def t6(vr):
    print("\nT6  8.3 短名根不得被误判为符号链接")
    root = fresh(os.path.join(SANDBOX, "shortname"))
    longdir = os.path.join(root, "delivery_package_directory")
    os.makedirs(longdir)
    shutil.copy2(os.path.join(DATA, "sample_350.csv"),
                 os.path.join(longdir, "sample_350.csv"))
    sp = short_path(longdir)
    print("       长名 = %s" % longdir)
    print("       短名 = %s" % sp)
    if not sp or os.path.abspath(sp) == longdir:
        skip("T6a", "卷未启用 8.3 短名，当前环境无法覆盖该场景",
             "GetShortPathNameW -> %r" % (sp,))
        return
    print("       realpath != abspath ? %s" % (os.path.realpath(sp) != os.path.abspath(sp)))
    try:
        ctx = vr.Ctx(sp)
        detail = "未被拒绝（正确）"
        try:
            ok2 = os.path.isfile(ctx.p("sample_350.csv"))
        except Exception as e:
            ok2 = False
            detail += "；ctx.p 异常 %s: %s" % (type(e).__name__, e)
        ok = ok2
        detail += "；ctx.p 可用 = %s" % ok2
    except RuntimeError as e:
        ok, detail = False, "RuntimeError: %s" % e
    check("T6a", "Ctx(<8.3 短名根>) 不得被拒绝", ok, detail)

    rc, out = run_script(["--dir", sp])
    check("T6b", "main(--dir <8.3 短名>) 无『拒绝符号链接』",
          "拒绝符号链接" not in out, "returncode=%d" % rc)
    check("T6c", "main 正常跑完 10 项（数据不全故 FAIL，但不是崩溃）",
          "统计：PASS=" in out and "Traceback" not in out, "returncode=%d" % rc)


# ------------------------------------------------------------------ T7
def t7(vr):
    print("\nT7  junction 根必须被拒绝")
    base = fresh(os.path.join(SANDBOX, "juncroot"))
    j = os.path.join(base, "delivery_junc")
    try:
        make_junction(DATA, j)
    except Exception as e:
        reason = ("当前环境无法创建 junction（需 NTFS 且沙箱与数据同卷；"
                  "跨卷、FAT/exFAT、非管理员受限场景均会失败）")
        skip("T7a", "junction 根拒绝：本环境不具备测试条件", reason)
        skip("T7b", "main(--dir <junction>) 拒绝：同上未执行",
             "%s: %s" % (type(e).__name__, e))
        return
    print("       os.path.islink=%s  stat 层 S_ISLNK=%s  reparse_tag=0x%X"
          % (os.path.islink(j), vr.is_symlink_strict(j),
             getattr(os.lstat(j), "st_reparse_tag", 0)))
    try:
        vr.Ctx(j)
        ok, detail = False, "未报错（junction 可绕过 P2）"
    except RuntimeError as e:
        ok, detail = ("拒绝符号链接" in str(e)), "RuntimeError: %s" % e
    check("T7a", "Ctx(<junction root>) 被拒绝（islink=False，靠 reparse tag）", ok, detail)

    rc, out = run_script(["--dir", j])
    check("T7b", "main(--dir <junction>) 退出码 == 1 且给出原因",
          rc == 1 and "拒绝符号链接" in out,
          "returncode=%d；命中=%r"
          % (rc, [l for l in out.splitlines() if "拒绝符号链接" in l]))
    rm_link(j)


# ------------------------------------------------------------------ T8
def t8(vr):
    print("\nT8  lstat 抛 PermissionError 必须 fail-closed")
    ctx = vr.Ctx(DATA)
    victim = os.path.join(os.path.abspath(DATA), "sample_350.csv")
    real_lstat = os.lstat
    hits = []

    def boom(path, *a, **k):
        if "sample_350.csv" in str(path):
            hits.append(str(path))
            raise PermissionError(13, "Access is denied (injected)")
        return real_lstat(path, *a, **k)

    os.lstat = boom
    try:
        try:
            r = vr.is_symlink_strict(victim)
            ok1, d1 = False, "返回 %r（静默放行，fail-open）" % (r,)
        except RuntimeError as e:
            ok1, d1 = ("无法检查路径组件" in str(e)), "RuntimeError: %s" % e
        check("T8a", "is_symlink_strict 抛 RuntimeError 而非 return False", ok1, d1)

        try:
            r = vr.is_junction_strict(victim)
            ok2, d2 = False, "返回 %r（静默放行，fail-open）" % (r,)
        except RuntimeError as e:
            ok2, d2 = ("无法检查路径组件" in str(e)), "RuntimeError: %s" % e
        check("T8b", "is_junction_strict 抛 RuntimeError 而非 return False", ok2, d2)

        try:
            ctx.p("sample_350.csv")
            ok3, d3 = False, "未报错（fail-open）"
        except RuntimeError as e:
            ok3, d3 = ("无法检查路径组件" in str(e)), "RuntimeError: %s" % e
        check("T8c", "Ctx.p 抛 RuntimeError（不返回路径）", ok3, d3)

        try:
            vr.link_component(victim)
            ok4, d4 = False, "未报错（fail-open）"
        except RuntimeError as e:
            ok4, d4 = ("无法检查路径组件" in str(e)), "RuntimeError: %s" % e
        check("T8d", "link_component 抛 RuntimeError", ok4, d4)

        check("T8e", "monkeypatch 确实生效", len(hits) >= 1, "命中 %d 次" % len(hits))
    finally:
        os.lstat = real_lstat

    # 复原后必须恢复正常，证明补丁未污染后续状态
    try:
        ok5 = os.path.isfile(ctx.p("sample_350.csv"))
    except Exception as e:
        ok5 = False
        check("T8f", "复原 os.lstat 后恢复", False, "%s: %s" % (type(e).__name__, e))
    check("T8f", "复原 os.lstat 后 ctx.p 正常", ok5, "")


# ------------------------------------------------------------------ T9
def t9(vr):
    print("\nT9  不存在的路径不得被误判为链接")
    ctx = vr.Ctx(DATA)
    try:
        p = ctx.p("nonexistent_dir/file.csv")
        exists = os.path.exists(p)
        check("T9a", "ctx.p 返回路径而不抛错", True, p)
        check("T9b", "exists == False", exists is False, "exists=%s" % exists)
        check("T9c", "返回值是绝对路径且落在交付根内",
              os.path.isabs(p) and os.path.normcase(p).startswith(
                  os.path.normcase(os.path.abspath(DATA))), p)
    except Exception as e:
        check("T9a", "ctx.p 返回路径而不抛错", False, "%s: %s" % (type(e).__name__, e))


def t10(vr):
    print("\nT10  v2.6：Ctx.p 只接受相对路径，绝对路径一律先拒")
    ctx = vr.Ctx(DATA)
    inside = os.path.join(os.path.abspath(DATA), "sample_350.csv")
    outside = os.path.join(os.path.dirname(os.path.abspath(DATA)), "elsewhere.csv")
    win_abs = r"C:\Windows\System32\drivers\etc\hosts"
    unc = r"\\server\share\x.csv"

    cases = [
        ("T10a", outside, "根目录外绝对路径"),
        ("T10b", inside, "根目录内绝对路径（存在且合法也要拒）"),
        ("T10c", win_abs, "Windows 盘符绝对路径（跨平台可测）"),
        ("T10d", unc, "UNC 路径"),
        ("T10e", os.path.join(os.path.abspath(DATA), "..", "escaped.csv"),
         "绝对路径 + ..（先于越界检查）"),
    ]
    for cid, arg, why in cases:
        try:
            r = ctx.p(arg)
            ok, detail = False, "返回 %r（应拒未拒）" % (r,)
        except RuntimeError as e:
            ok = str(e).startswith("拒绝绝对路径：")
            detail = "RuntimeError: %s" % e
        check(cid, "ctx.p(<%s>) 被拒" % why, ok, detail)

    # T10f：绝对路径指向 symlink —— 测的是"绝对路径先拒"，不依赖链接是否真实存在
    base = fresh(os.path.join(SANDBOX, "abslink"))
    link = os.path.join(base, "linkdir")
    try:
        make_symlink_dir(DATA, link)
    except OSError:
        link = None
    abs_link = os.path.join(link, "sample_350.csv") if link else \
        os.path.join(base, "linkdir", "sample_350.csv")
    try:
        r = ctx.p(abs_link)
        ok, detail = False, "返回 %r（应拒未拒）" % (r,)
    except RuntimeError as e:
        ok = str(e).startswith("拒绝绝对路径：")
        detail = "RuntimeError: %s（未走到链接检查，符号链接存在=%s）" % (e, bool(link))
    check("T10f", "ctx.p(<绝对路径指向 symlink>) 被拒且先于链接检查", ok, detail)

    # T10g：对照 —— 常量文件名仍可用
    try:
        p = ctx.p(vr.SAMPLE_FILE)
        ok = os.path.isabs(p) and os.path.isfile(p)
        detail = p
    except Exception as e:
        ok, detail = False, "%s: %s" % (type(e).__name__, e)
    check("T10g", "对照：ctx.p(SAMPLE_FILE) 正常返回绝对目标路径", ok, detail)

    # 顺序自证：绝对路径 + ".." 报的是绝对路径，不是 ".."
    try:
        ctx.p(os.path.join(os.path.abspath(DATA), "..", "..", "x.csv"))
        ok, detail = False, "未报错"
    except RuntimeError as e:
        ok = str(e).startswith("拒绝绝对路径：")
        detail = "RuntimeError: %s" % e
    check("T10h", "优先级：绝对路径先于 '..' 判定", ok, detail)

    # T10i（v2.7）：单反斜杠根路径 —— Windows 上是根相对路径，POSIX 上 isabs 为 False
    root_rel = r"\Windows\System32\drivers\etc\hosts"
    try:
        r = ctx.p(root_rel)
        ok, detail = False, "返回 %r（应拒未拒）" % (r,)
    except RuntimeError as e:
        ok = str(e).startswith("拒绝绝对路径：")
        detail = "RuntimeError: %s" % e
    check("T10i", r"ctx.p('\Windows\System32\drivers\etc\hosts') 被拒", ok, detail)

    # T10j/T10k（v2.8）：盘符相对路径 —— Windows 上相对"该盘当前目录"，不是相对交付根
    # ntpath.join(r"C:\deliver", "D:secret.csv") == "D:secret.csv"，必须在入口拒绝
    for cid, bad_path in (("T10j", "D:secret.csv"), ("T10k", "C:x")):
        try:
            r = ctx.p(bad_path)
            ok, detail = False, "返回 %r（应拒未拒）" % (r,)
        except RuntimeError as e:
            ok = str(e).startswith("拒绝绝对路径：")
            detail = "RuntimeError: %s" % e
        check(cid, "ctx.p(%r) 被拒（盘符相对路径）" % bad_path, ok, detail)


def t11(vr):
    print("\nT11  P3 解耦：版本状态不得决定 V8 的 PASS/FAIL（v2.8）")

    # T11a：直接构造"序列一致 + 版本不匹配"，V8 必须 PASS
    ctx = vr.Ctx(DATA)
    vr.check_python_env(ctx)
    ctx.gen_py_val = "3.10.0"
    ctx.py_match = False
    status, msg = vr.check_v8(ctx)
    print("       版本不匹配 + 序列一致 -> %s / %s" % (status, msg))
    check("T11a", "py_match=False 且序列一致 -> V8 PASS", status == vr.PASS,
          "实际 %s：%s" % (status, msg))

    # T11c：控制组 —— 把序列打乱，V8 仍必须 FAIL（证明不是恒 PASS）
    ctx2 = vr.Ctx(DATA)
    vr.check_python_env(ctx2)
    ctx2.gen_py_val = "3.10.0"
    ctx2.py_match = False
    ctx2.load_pop()
    ctx2.load_sample()
    real = list(ctx2.sample_shas)
    ctx2.sample_shas = list(reversed(real))
    ctx2.load_sample = lambda: None          # 阻止 check_v8 重新装载覆盖
    status2, msg2 = vr.check_v8(ctx2)
    print("       序列打乱 + 版本不匹配 -> %s / %s" % (status2, msg2))
    check("T11c", "序列不一致仍 FAIL（判定未被架空）", status2 == vr.FAIL,
          "实际 %s：%s" % (status2, msg2))

    # T11d：源码级 —— V8 判定表达式不得引用版本状态
    src = inspect.getsource(vr.check_v8)
    # 只看代码行：注释里解释"v2.7 曾用 ver_ok = ..."是允许的，不算判定依据
    code = "\n".join(l for l in src.splitlines() if not l.strip().startswith("#"))
    bad = re.findall(r"ver_ok\s*=|seq_same\s+and\b", code)
    check("T11d", "check_v8 代码行无 ver_ok / 无 seq_same and 复合判定", not bad,
          "命中 %r" % (bad,))

    # T11e：main() 侧 —— OVERALL_PASS 的计算不得引用 py_match
    msrc = inspect.getsource(vr.main)
    m = re.search(r"overall\s*=\s*(.+)", msrc)
    expr = m.group(1) if m else ""
    check("T11e", "main() 的 overall 表达式不引用 py_match",
          "py_match" not in expr, "表达式 %r" % expr)

    # T11b：子进程级 —— 版本不匹配时汇总行仍显式报 MISMATCH（不弱化独立状态行）
    root = fresh(os.path.join(SANDBOX, "v8ver"))
    for fn in ("sample_350.csv", "human_label_template.csv", "manifest.sha256",
               "sampling_config.json", "sampling_report.md", "ANNOTATION_GUIDE.md"):
        shutil.copy2(os.path.join(DATA, fn), os.path.join(root, fn))
    shutil.copy2(TARGET, os.path.join(root, "verify_reviewer.py"))
    cfgp = os.path.join(root, "sampling_config.json")
    with io.open(cfgp, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)
    fake = "3.10.0" if PY_RUNTIME != "3.10.0" else "3.11.0"
    cfg["generation_python"] = fake
    with io.open(cfgp, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(cfg, ensure_ascii=False, indent=2))
    rc, out = run_script(["--dir", root])
    m = re.search(r"^PYTHON_REPRODUCIBILITY\s+= (.+)$", out, re.M)
    got = m.group(1).strip() if m else None
    want = "MISMATCH (generation_python=%s, runtime=%s)" % (fake, PY_RUNTIME)
    print("       汇总行 = %s" % got)
    check("T11b", "版本不匹配时汇总行仍报 MISMATCH", got == want, "实际 %r" % (got,))


def main():
    global DATA, TARGET, SANDBOX
    _utf8_stdout()
    ap = argparse.ArgumentParser(description="verify_reviewer.py v2.8 定向回归用例")
    ap.add_argument("--data", default=None, help="交付数据目录（默认自动定位）")
    ap.add_argument("--verifier", default=None,
                    help="被测脚本路径（默认本脚本同级的 verify_reviewer.py）")
    args = ap.parse_args()
    if args.data:
        DATA = os.path.abspath(args.data)
    if args.verifier:
        # run_script 以 HERE 为 cwd 启动子进程，相对路径会解析错并 exit 2
        TARGET = os.path.abspath(args.verifier)
    SANDBOX = _pick_sandbox()

    print("=" * 78)
    print("verify_reviewer.py v2.8 定向回归用例")
    print("=" * 78)
    print("target      = %s" % TARGET)
    print("data        = %s" % DATA)
    print("python      = %s" % sys.version.split()[0])
    print("sandbox     = %s" % SANDBOX)

    if not os.path.isfile(TARGET):
        print("FAIL: 找不到被测脚本 %s" % TARGET)
        return 1
    if not os.path.isdir(DATA):
        print("FAIL: 找不到交付数据目录 %s" % DATA)
        return 1

    vr = load_target()
    print("target ver  = %s" % getattr(vr, "VERSION", "?"))
    if getattr(vr, "VERSION", "") != "2.8":
        print("WARN: 被测脚本版本不是 2.8")

    fresh(SANDBOX)
    try:
        t1(vr)
        t2(vr)
        t3(vr)
        t4(vr)
        t5(vr)
        t5_inject(vr)
        t6(vr)
        t7(vr)
        t8(vr)
        t9(vr)
        t10(vr)
        t11(vr)
    finally:
        for sub in os.listdir(SANDBOX):
            p = os.path.join(SANDBOX, sub)
            if os.path.islink(p):
                rm_link(p)
            elif os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
        shutil.rmtree(SANDBOX, ignore_errors=True)

    n = len(RESULTS)
    bad = [r for r in RESULTS if not r[2]]
    n_skip = len(SKIPPED)
    n_pass = n - n_skip - len(bad)
    print("\n" + "=" * 78)
    print("统计：共 %d 项，PASS=%d SKIP=%d FAIL=%d"
          % (n, n_pass, n_skip, len(bad)))
    if SKIPPED:
        print("  SKIP 明细（环境不具备条件，不代表被测代码有问题，也不计 PASS）：%s"
              % ", ".join(SKIPPED))
    if bad:
        for cid, desc, _, detail in bad:
            print("  FAIL [%s] %s" % (cid, desc))
    print("结论：%s" % ("ALL PASS（无 FAIL）" if not bad else "存在失败"))
    print("=" * 78)
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
