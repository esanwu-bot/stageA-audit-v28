#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_reviewer.py —— Stage A SRS 交付包 · 独立验证脚本 v2.8

运行环境
    Python 3.8+，零外部依赖（仅标准库）。
    不做任何网络请求，不写任何文件，只读不写。

用法
    python verify_reviewer.py                # 校验脚本所在目录
    python verify_reviewer.py --dir <目录>    # 校验指定目录
    python verify_reviewer.py --version      # 只打印版本

------------------------------------------------------------------------------
v2.8 修订（只改验证器，未触碰任何数据文件；只修 Reviewer 点名的两处判定边界）
------------------------------------------------------------------------------
1) P3：解除 Python 版本状态对 V8 与 OVERALL_PASS 的影响
   v2.7 及以前 check_v8 用 ver_ok = ctx.py_match 参与判定，造成判定边界不对称：
   无记录 / config 不可读 / 记录格式无效三种情况一律 ver_ok=True 不影响，
   唯独"有效记录但版本不匹配"使 V8 FAIL，并连带 OVERALL_PASS=false；
   而 main() 又把 PYTHON_REPRODUCIBILITY 声明为 V1–V10 之外的独立状态行。
   v2.8 起 V8 只回答"seed=42 的抽样序列能否复现"（ok = seq_same），
   版本状态仅以 [NOTE] 提示，跨环境结论完全由汇总行 PYTHON_REPRODUCIBILITY 承载。
   因版本不匹配而把 SRS 复现判为失败，在语义上本就不成立：两者是不同命题。

2) P2：_is_absolute_like 拒绝 Windows 盘符相对路径
   v2.7 的盘符判定是 ^[A-Za-z]:[\\/]，只拦 C:\\foo / C:/foo，放过 "D:secret.csv"。
   但后者在 Windows 上不是普通相对路径，而是相对 D 盘"当前目录"的路径：
   ntpath.join(r"C:\\deliver", "D:secret.csv") 直接返回 "D:secret.csv"，
   于是 Ctx.p() 可能在组件事务之前就指向交付根之外。v2.8 改为 ^[A-Za-z]:，
   一条判定同时覆盖绝对盘符路径与盘符相对路径，不再依赖后续 realpath/commonpath 兜底。

P1 正则、P2 的 fail-closed 实现、P3 的异常安全实现均未改动。

------------------------------------------------------------------------------
v2.7 修订（上一版：P1 白名单收紧 + 单反斜杠根路径）
------------------------------------------------------------------------------
按 Reviewer 给定的白名单收紧 P1，并补单反斜杠根路径判定。

1) P1 正则收紧（替换 v2.6 的宽口径）
   括号注释：v2.6 是 \\([^)]*\\)，任意内容都收；v2.7 只收 (32-bit)/(64-bit)，
             且括号前要求 \\s+（至少一个空白），"3.12(64-bit)" 不再接受。
   后缀字符集：v2.6 是 [A-Za-z0-9._-]+，含 "-"，导致 "3.12-x-y" 被整体吞成
             一个后缀；v2.7 是 [A-Za-z0-9._]+，不含 "-"，"3.12-x-y" 返回 None。
   "3.12.1-post1" 仍接受为普通后缀 (3, 12, 1)，不解释为 PEP 440 post-release。
   major >= 100 仍在 fullmatch 成功后独立执行，两条互不替代。

2) _is_absolute_like 增加单反斜杠/斜杠根路径
   "\\Windows\\System32\\drivers\\etc\\hosts" 在 Windows 上是根相对路径，
   在 POSIX 测试环境里 os.path.isabs 返回 False，必须显式拒。
   "/foo" 在 POSIX 上 isabs 已为 True，此处并列判定重复但无害；
   普通相对路径 "foo\\bar.csv" 不以 \\ 或 / 开头，不受影响。

3) 新增 T10i（单反斜杠根路径），T10a–T10h 全部保留

P2 的 fail-closed 实现、P3 的异常安全实现均未改动。

------------------------------------------------------------------------------
v2.6 修订（上一版：Ctx.p 拒绝绝对路径 + 优先级固定）
------------------------------------------------------------------------------
Ctx.p() 拒绝绝对路径入参（Reviewer 裁定：只接受相对路径），新增 T10。

拒绝优先级（接口语义，与本文件实现、回信口径三者一致）：
    1. 绝对路径        -> RuntimeError("拒绝绝对路径：<rel>")
    2. ".." 路径段      -> RuntimeError("拒绝 '..' 路径段：<rel>")
    3. 逐级 symlink/junction
    4. 越界（realpath 不在交付根内）
    5. 非普通文件
因此"绝对路径指向交付根内""绝对路径指向 symlink""绝对路径经 .. 规范化后
越界"三种情况，都先被第 1 条拦下，不会走到 2–5。这是接口语义，不是遗漏。

判据 _is_absolute_like() 必须跨平台：os.path.isabs 只认本平台形态
（POSIX 上对 "C:\\..." 返回 False），故另补两条——
    Windows 盘符：^[A-Za-z]:[\\\\/]
    UNC：          \\\\ 或 // 开头
于是 POSIX 上照样能拒绝 "C:\\Windows\\...\\hosts" 与 "\\\\server\\share\\x.csv"。

影响面：脚本内所有 ctx.p(...) 调用传的都是常量文件名或相对路径，不受影响；
Ctx.__init__ 里的 link_component(d) 用的是构造参数 d，不是 ctx.p 的入参，未改。
其余 P1 / P2 / P3 实现一律未动。

------------------------------------------------------------------------------
v2.5 修订（上一版：P1 锚定 fullmatch / P2 fail-closed / P3 异常安全）
------------------------------------------------------------------------------
1) P1 版本解析改为锚定 fullmatch
   VERSION_RE 改为带首尾锚点的整串正则，parse_version_tuple 用 fullmatch：
       ^\\s*(?:Python\\s+)?(\\d+)\\.(\\d+)(?:\\.(\\d+))?
        (?:\\s*(?:\\([^)]*\\)|[-+][A-Za-z0-9._-]+))?\\s*$
   v2.4 的 search() 会接受 "notpython3.12"、"build-3.12" 这类只含版本子串的
   脏值；现在整串不干净就返回 None。允许的后缀只有两种形态：括号注释
   " (64-bit)" 与 连字符/加号后缀 "-extra"。因此裸 "3.12.1rc1"（无连字符）
   不再被接受，"v3.9.1-rc1" 也因 "v" 前缀不合法而返回 None。
   依据：sampling_config.json 现有 26 个键中没有任何 Python 版本字段
   （generation_python / python_version / generator_python / python /
   python_runtime 五个候选名全部不匹配），没有真实后缀需要兼容，故不为
   任意文本放宽。major >= 100 保留，但它只是附加约束，不能替代格式校验。
2) P2 链接判定改为 fail-closed
   新增 import stat 与 _lstat_strict()：os.lstat 抛 FileNotFoundError 视为
   「不存在 -> 不是链接」；其他 OSError（PermissionError 等）一律
   raise RuntimeError("无法检查路径组件...")，不再用
   except OSError: return False 静默放行。
   is_symlink_strict / is_junction_strict 均走该严格入口；
   link_component() 与 Ctx.p() 中所有链接判定替换为这对函数。
3) P3 异常安全
   check_python_env 改为外层 try/except 包住 _check_python_env：任何异常
   （包括 ctx.has() 因严格路径检查抛出的 RuntimeError）都落成
   ctx.gen_py_unavailable=True，main() 不会在打印汇总行之前崩溃。
   V8 只读 ctx.gen_py_*，不写；四态优先级不变。

------------------------------------------------------------------------------
历史修订
------------------------------------------------------------------------------
v2.4：P1 版本解析由 findall 改为严格正则（当时用 search，已被 v2.5 收紧为
      fullmatch）；P2 交付根目录及祖先不得是 symlink/junction（首版用
      realpath 比较，在 Windows 8.3 短名下误判、且漏 junction，已改逐级
      reparse 扫描）；Ctx.p() 拒 ".."；P3 新增 check_python_env 与 V8 解耦，
      汇总行四态。
v2.3：版本比较改元组逐段（修 "" 的 startswith 假匹配与 "3.1"/"3.10" 前缀
      误伤）；符号链接逐级检查（父目录是链接也能拦）；V5 样本缺失不再 PASS；
      MAN_LABEL_DELIM 注释写准（两个 ASCII 空格 + 左括号）。

------------------------------------------------------------------------------
断言 V1–V10，状态只有 PASS / FAIL / SKIP；SKIP 必须带原因，且一律不计入 PASS。
退出码 0 = OVERALL_PASS=true；1 = 其余情况（含任意 SKIP）。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import random
import re
import stat
import sys

VERSION = "2.8"
REQUIRES_PYTHON = (3, 8)

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"

# ---------------------------------------------------------------- 冻结常量
EXPECTED_N_POP = 6327
EXPECTED_N_SAMPLE = 350
EXPECTED_SEED = 42
EXPECTED_POOL_SHA = "42b7482fb9d653c098ed12e1e434aef76f49bcae0180ffd1ba4e69b9f8f1dd40"
EXPECTED_SAMPLE_SHA = "39c55826d6cdf98f7da18d61500005b9de8bf297af5775f92ed254ad94f680cc"
PROB_TOL = 1e-9

SAMPLE_FILE = "sample_350.csv"
TPL_FILE = "human_label_template.csv"
POP_FILE = "population_manifest.csv"
CFG_FILE = "sampling_config.json"
MAN_FILE = "manifest.sha256"

# P0-1：6 个输出文件的冻结基线（写死，不依赖 manifest，防止二者被同时篡改）
EXPECTED_OUTPUT_SHA = {
    "sample_350.csv": "39c55826d6cdf98f7da18d61500005b9de8bf297af5775f92ed254ad94f680cc",
    "human_label_template.csv": "afef29e353790be0de1a5bf88f616f51136da91d893b2d2d764878fa14c06450",
    "population_manifest.csv": "8f8ed27d952a516eb84ec3ac39a929ca6b4972404edfbe918a82ceae5d3777ae",
    "sampling_config.json": "126153f3794b11fbd3a7fbc9aff222cb581bcea5abfe4ea3d468c998379b52b9",
    "sampling_report.md": "c49156be76038724c9a5c05a1029669bb3a192ad6f9b3bc92946f759c400d950",
    "ANNOTATION_GUIDE.md": "bd78b959f863efe8f01bea810622c55412db09fcfaa01036bc8024582dbebec8",
}

EXPECTED_OUTPUT_FILES = set(EXPECTED_OUTPUT_SHA.keys())
EXPECTED_INPUT_FILES = {          # 体积大（1.53 MB / 1.26 MB），允许不随包提供
    "stratified_frame.csv",
    "content_manifest.csv",
}
EXPECTED_ALL_FILES = EXPECTED_OUTPUT_FILES | EXPECTED_INPUT_FILES

# P1-2：manifest 中 8 条记录应出现的完整相对路径（逐字写死，比对时不归一化）
EXPECTED_RELPATHS = {
    "stratified_frame.csv": "runs/stage_A_v3/stratified_frame.csv",
    "content_manifest.csv": "runs/stage_A_v3/content_manifest.csv",
    "population_manifest.csv": "runs/stage_A_sampling/population_manifest.csv",
    "sample_350.csv": "runs/stage_A_sampling/sample_350.csv",
    "human_label_template.csv": "runs/stage_A_sampling/human_label_template.csv",
    "sampling_config.json": "runs/stage_A_sampling/sampling_config.json",
    "sampling_report.md": "runs/stage_A_sampling/sampling_report.md",
    "ANNOTATION_GUIDE.md": "runs/stage_A_sampling/ANNOTATION_GUIDE.md",
}

EXPECTED_SAMPLE_HEADER = [
    "sample_no", "sample_id", "source_sha256", "rep_path", "rel_path", "rep_env",
    "file_size", "path_count", "local_paths", "server_paths", "all_rel_paths",
    "posthoc_filename_heuristic", "selection_prob", "sampling_design",
]

# 模板 9 个必备列（Reviewer 指定，顺序不可动）
EXPECTED_TPL_HEADER = [
    "source_pdf_sha256", "human_semantic_type", "document_subject_mpn",
    "evidence_pages", "human_evidence_text", "reviewer", "review_status",
    "uncertainty_reason", "adjudication_status",
]
# 标注规范 v0.2 追加的 4 列复核留痕（顺序不可动）
TPL_EXTRA_HEADER = [
    "first_pass_label", "second_review_label", "second_reviewer", "adjudicator",
]
TPL_ALLOWED_COL_COUNTS = (len(EXPECTED_TPL_HEADER),
                          len(EXPECTED_TPL_HEADER) + len(TPL_EXTRA_HEADER))

# config 中可能承载"生成时 Python 版本"的键名（大小写不敏感）
PYTHON_KEYS = ("python_version", "generation_python", "generator_python",
               "python", "python_runtime")

SHA_RE = re.compile(r"^[0-9a-f]{64}$")

# 严格版本号（v2.7：按 Reviewer 白名单收紧；整串锚定，配合 fullmatch 使用）
#
# 语法：  行首空白 -> 可选 "Python " 前缀 -> major.minor[.patch]
#          -> 可选后缀（两种形态之一）-> 行尾空白
# 允许的后缀（仅这两种）：
#         " (32-bit)" / " (64-bit)"           括号注释，白名单，前必须有 \s+
#         "-extra" / "+build.7" / "-post1"    连字符或加号后缀，字符集 [A-Za-z0-9._]
# 不接受（T1 逐条有断言）：
#         "3.12(64-bit)"          括号前无空白（v2.6 用 \s* 时会误接受）
#         "3.12 (main)"           括号内容不在 32/64-bit 白名单
#         "3.12 (64-bit)-extra"   括号注释后不得再接后缀
#         "3.12-x-y"              后缀内部含连字符（v2.6 的字符集含 "-" 时会误接受）
#         "3.12+"                 后缀必须非空
#         "3.12++extra"           第二个 "+" 不在字符集内
#         "notpython3.12" / "build-3.12"   整串不是版本号 / 前缀不是 Python
#         "3.12.1rc1" / "v3.9.1-rc1"       裸预发布后缀 / "v" 前缀
#         "2026.11.10"            能匹配，但 major >= 100 由 parse_version_tuple 拒绝
VERSION_RE = re.compile(
    r"^\s*"
    r"(?:Python\s+)?"
    r"(?P<major>\d+)\."
    r"(?P<minor>\d+)"
    r"(?:\.(?P<patch>\d+))?"
    r"(?:\s+\((?:32|64)-bit\)|[-+][A-Za-z0-9._]+)?"
    r"\s*$",
    re.IGNORECASE,
)

V6_DESC = ("9 个必备列正确；允许 9 列基础模板或增加指定的 4 个复核留痕列形成 13 列模板")

# 注意：下面这个常量是 **两个 ASCII 空格 + 一个左括号**（"  ("），
# 不是 " ("（一个空格）。manifest 每行形如：
#   <64位哈希><两个空格><relpath><两个空格>(<label>)
# 用它反查可以把两个空格归属到分隔符，从而让 relpath 保持原样、不被 rstrip。
MAN_LABEL_DELIM = "  ("


# ---------------------------------------------------------------- 工具函数
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_rows_strict(path):
    """csv.reader 逐行读，返回 (header, rows)。不吞异常、不做类型推断。"""
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))
    if not rows:
        return [], []
    return rows[0], rows[1:]


def count_bad_rows(rows, want_cols, start_line=2):
    """返回 [(真实行号, 实际列数)]，表头记为第 1 行。"""
    out = []
    for i, r in enumerate(rows, start_line):
        if len(r) != want_cols:
            out.append((i, len(r)))
    return out


def parse_version_tuple(s):
    """把版本串解析成 (major, minor[, patch])；整串不合法返回 None。

    v2.7：整串 fullmatch，且后缀按 Reviewer 白名单收紧。
        "3.13.15"               -> (3, 13, 15)
        "3.10"                  -> (3, 10)
        "Python 3.12.1"         -> (3, 12, 1)
        "python 3.13"           -> (3, 13)
        "3.12 (64-bit)"         -> (3, 12)        # 白名单括号注释
        "3.12 (32-bit)"         -> (3, 12)
        "3.12.1-extra"          -> (3, 12, 1)     # 普通连字符后缀
        "3.12.1-post1"          -> (3, 12, 1)     # 不解释为 PEP 440 post-release
        "3.13.15+build.7"       -> (3, 13, 15)    # 加号后缀
        "3.12(64-bit)"          -> None           # 括号前缺空白
        "3.12 (main)"           -> None           # 括号内容不在白名单
        "3.12 (64-bit)-extra"   -> None           # 括号后不得再接后缀
        "3.12-x-y"              -> None           # 后缀内部含连字符
        "3.12+" / "3.12++extra" -> None           # 空后缀 / 第二个 + 非法
        "notpython3.12"         -> None           # 整串不是版本号
        "build-3.12"            -> None           # 前缀不是 Python
        "3.12.1rc1"             -> None           # 裸预发布后缀，无连字符
        "v3.9.1-rc1"            -> None           # "v" 前缀不合法
        ""/"abc"/"build 2026"   -> None
        "1"*5000 + ".0"         -> None           # 超长数字触发 int 转换上限
    major >= 100（"2026.11.10" 这类日期/构建号）判为 None——只是附加约束，
    格式合法性由 fullmatch 单独把关。
    """
    if not isinstance(s, str):
        return None
    m = VERSION_RE.fullmatch(s.strip())
    if not m:
        return None
    # Python 3.11+ 对 int() 的十进制转换设了默认上限
    # （sys.get_int_max_str_digits() 默认 4300）。VERSION_RE 的 \d+ 不限制长度，
    # 超长数字会在 int() 处抛 ValueError，使本函数对外抛异常而非返回 None。
    # 按"整串不合法返回 None"的契约统一兜住，只捕获 ValueError，不吞其他异常。
    try:
        major = int(m.group("major"))
        if major >= 100:
            return None
        vals = [major, int(m.group("minor"))]
        if m.group("patch") is not None:
            vals.append(int(m.group("patch")))
    except ValueError:
        return None
    return tuple(vals)


def version_compatible(runtime_str, recorded_str):
    """逐段比较版本号，返回 True/False；任一侧无法解析返回 None。

    规则：按较短者的段数逐段比较。
      (3,10) vs (3,10,0)   -> True      允许"只写到 minor"的写法
      (3,10) vs (3,10,15)  -> True
      (3,1)  vs (3,10)     -> False     "3.1" 不得匹配 "3.10"
      (3,13,15) vs (3,13,14) -> False
      "" 或 "abc"          -> None      无效版本
    """
    a = parse_version_tuple(runtime_str)
    b = parse_version_tuple(recorded_str)
    if a is None or b is None:
        return None
    n = min(len(a), len(b))
    if n == 0:
        return None
    return a[:n] == b[:n]


def parse_manifest_strict(path):
    """严格解析 manifest.sha256；relpath 原样保留，不做 rstrip / strip。

    行格式：<64位小写sha256><两个空格><relpath><两个空格>(<label>)
    relpath 与 label 之间用固定分隔符 "  ("（两个空格 + 左括号）切开：
        relpath_raw = rest[:idx]                    —— 原样，含尾部空格/Tab
        label       = rest[idx+len(delim):-1]       —— 仅此子串允许 strip
    若结构不合法（不以 ")" 结尾或找不到分隔符），relpath_raw = rest 原样，label 为空。
    返回 (records, errors)，records = [(sha, relpath_raw, label)]。
    """
    records, errors = [], []
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    n = 0
    for lineno, line in enumerate(lines, 1):
        if not line.strip():
            continue
        n += 1
        digest, sep, rest = line.partition("  ")
        if not sep:
            errors.append("第 %d 行缺少双空格分隔" % lineno)
            continue
        if not SHA_RE.fullmatch(digest):
            errors.append("第 %d 行哈希非法（要求 64 位小写 hex）：%r" % (lineno, digest))
            continue
        # —— 关键：rest 原样保留，不做任何 rstrip/strip ——
        idx = rest.rfind(MAN_LABEL_DELIM)
        if idx != -1 and rest.endswith(")"):
            relpath_raw = rest[:idx]
            label = rest[idx + len(MAN_LABEL_DELIM):-1].strip()
        else:
            relpath_raw = rest
            label = ""
        if relpath_raw == "":
            errors.append("第 %d 行 relpath 为空" % lineno)
            continue
        records.append((digest, relpath_raw, label))
    if n != 8:
        errors.append("记录条数 = %d，期望 8 条" % n)
    return records, errors


def relpath_problems(relpath_raw):
    """P1-2：relpath 结构性缺陷（不含映射比对）。传入原样值，内部不做任何清理。"""
    probs = []
    if relpath_raw == "":
        probs.append("空路径")
        return probs
    if relpath_raw.startswith("/") or re.match(r"^[A-Za-z]:", relpath_raw):
        probs.append("绝对路径")
    if ".." in relpath_raw.split("/"):
        probs.append("含 '..' 段")
    if "\\" in relpath_raw:
        probs.append("含反斜杠")
    if any(s == "" for s in relpath_raw.split("/")):
        probs.append("空路径段")
    if relpath_raw != relpath_raw.rstrip():
        probs.append("尾部空白 %r" % relpath_raw[-1])
    return probs


def find_generation_python(cfg):
    """在 config 顶层查找生成时 Python 版本字段，返回 (键名, 值) 或 (None, None)。"""
    if not isinstance(cfg, dict):
        return None, None
    for key in cfg:
        if key.lower() in PYTHON_KEYS:
            return key, cfg[key]
    return None, None


def _lstat_strict(path):
    """fail-closed 的 lstat：只有"不存在"能当"不是链接"，其他错误一律上抛。

    FileNotFoundError -> None（路径不存在，无从是链接）
    其他 OSError      -> raise RuntimeError（PermissionError / 设备错误 / 路径过长）
                         绝不 return False 静默放行 —— 那是 fail-open。
    """
    try:
        return os.lstat(path)
    except FileNotFoundError:
        return None
    except OSError as e:
        raise RuntimeError("无法检查路径组件（%s）：%s: %s"
                           % (path, type(e).__name__, e))


def is_symlink_strict(path):
    """符号链接判定（走 _lstat_strict，不吞异常）。"""
    st = _lstat_strict(path)
    return st is not None and stat.S_ISLNK(st.st_mode)


def is_junction_strict(path):
    """目录联接（junction）判定（走 _lstat_strict，不吞异常）。

    os.path.islink / stat.S_ISLNK 对 junction 返回 False（Python 3.13 实测），
    故 junction 只能靠 reparse tag 识别：IO_REPARSE_TAG_MOUNT_POINT = 0xA0000003。
    不用 os.path.isjunction，避免"它在旧版本不存在 / 它内部吞异常"两种差异。
    """
    st = _lstat_strict(path)
    if st is None or stat.S_ISLNK(st.st_mode):
        return False
    return getattr(st, "st_reparse_tag", 0) == 0xA0000003


def link_component(path):
    """从盘符/根逐级下探，返回第一个符号链接或 junction 的完整路径；无则 None。

    只按原样字符串逐级判定，不比较 realpath：
        C:\\Users\\ADMINI~1\\... 的 realpath 是长名，两者不等，但路径里
        并没有任何链接 —— 用 realpath 比较会把它误判成符号链接。
    v2.5：判定改走 is_symlink_strict / is_junction_strict，任一 OSError 都向上
    抛 RuntimeError（fail-closed），由 Ctx.__init__ / main() 接住并 exit 1。
    """
    p = os.path.abspath(path)
    drive, tail = os.path.splitdrive(p)
    parts = [x for x in tail.replace("\\", "/").split("/") if x]
    cur = (drive + os.sep) if drive else os.sep
    for part in parts:
        cur = os.path.join(cur, part)
        if is_symlink_strict(cur) or is_junction_strict(cur):
            return cur
    return None


def _is_absolute_like(rel):
    """判断入参是否"绝对路径形态"（v2.8，跨平台）。

    os.path.isabs 只认当前平台的形态：POSIX 上对 "C:\\Windows\\hosts" 返回
    False，所以只靠它会在 Linux/macOS 上放过 Windows 绝对路径。这里补三条：
        单反斜杠/斜杠根路径： "\\\\Windows\\System32" 或 "/foo"
        Windows 盘符前缀：    ^[A-Za-z]:   同时覆盖 C:\\foo 与 D:secret.csv
        UNC：                \\\\ 开头 或 // 开头
    盘符判定刻意只写到冒号为止：Windows 上 "D:secret.csv" 是相对 D 盘"当前目录"
    的路径，不是相对交付根目录，ntpath.join(r"C:\\deliver", "D:secret.csv") 会
    直接返回 "D:secret.csv"。这类输入不符合"相对根目录"的契约，必须在入口拒绝，
    不能指望后续 realpath/commonpath 兜底。
    反例说明：v2.7 写成 ^[A-Za-z]:[\\\\/]，把 "D:secret.csv" 当成普通相对名放过；
             "\\Windows\\System32" 在 Windows 上是根相对路径，在 POSIX 上 isabs 为
             False，必须显式拒；"/foo" 在 POSIX 上 isabs 已 True，并列判定重复但无害；
             普通相对路径 "foo\\bar.csv" 不以 \\ 或 / 开头，不受影响。
    已知取舍：POSIX 上 "a:b" 是合法文件名，本函数会一并拒绝——本脚本只处理交付包内
             的固定文件名，跨平台语义一致性优先于该极小概率的误拒。
    """
    s = str(rel)
    if os.path.isabs(s):
        return True
    if s.startswith("\\") or s.startswith("/"):
        return True
    if re.match(r"^[A-Za-z]:", s):
        return True
    if s.startswith("\\\\") or s.startswith("//"):
        return True
    return False


class Ctx(object):
    def __init__(self, d):
        # P2(v2.4)：交付根目录本身及其祖先不得是符号链接 / junction
        lk = link_component(d)
        if lk:
            raise RuntimeError("拒绝符号链接：交付根目录（%s）" % lk)
        self.d = d
        self.records = []
        self.man_sha = {}
        self.man_rel = {}
        self.sample_header = None
        self.sample_rows = None
        self.sample_shas = None
        self.pop_header = None
        self.pop_rows = None
        self.pop_shas = None
        self.tpl_header = None
        self.tpl_rows = None
        self.tpl_shas = None
        self.cfg = None
        # P3(v2.4)：Python 环境状态由 check_python_env() 统一解析
        self.py_runtime = "%d.%d.%d" % sys.version_info[:3]
        self.gen_py_key = None
        self.gen_py_val = None        # 有效记录值
        self.gen_py_invalid = None    # 记录值无法解析时保留原文
        self.gen_py_unavailable = False
        self.gen_py_error = None
        self.py_match = None          # None=未判定；True/False=比对结果

    def p(self, rel):
        """P2 + v2.6：绝对路径 / 符号链接 / 目录联接 / 越界 / 非普通文件 五重防护。

        拒绝优先级（自上而下，命中即停）：
            1) 绝对路径        -> "拒绝绝对路径：<rel>"
            2) ".." 路径段      -> "拒绝 '..' 路径段：<rel>"
            3) 逐级 symlink/junction（is_symlink_strict / is_junction_strict，
               v2.5 起以 RuntimeError 上抛 lstat 的非 FileNotFoundError 异常，
               不存在"except OSError: return False"之类降级分支）
            4) 越界（realpath 必须落在交付根内）
            5) 非普通文件
        绝对路径无论指向根内、指向 symlink、还是经 ".." 规范化后越界，
        都在第 1 步被拒，不会进入 2–5 —— 接口只接受相对路径。
        """
        if _is_absolute_like(rel):
            raise RuntimeError("拒绝绝对路径：%s" % rel)
        root_abs = os.path.abspath(self.d)
        rel_norm = str(rel).replace("\\", "/")
        parts = [x for x in rel_norm.split("/") if x not in ("", ".")]
        if ".." in parts:
            raise RuntimeError("拒绝 '..' 路径段：%s" % rel)
        cur = root_abs
        for part in parts:
            cur = os.path.join(cur, part)
            if is_symlink_strict(cur) or is_junction_strict(cur):
                raise RuntimeError("拒绝符号链接：%s" % cur)
        target = os.path.join(root_abs, *parts) if parts else root_abs
        if os.path.exists(target):
            real = os.path.realpath(target)
            root_real = os.path.realpath(root_abs)
            try:
                inside = (os.path.commonpath([real, root_real]) == root_real)
            except ValueError:
                inside = False
            if not inside:
                raise RuntimeError("路径越界：%s -> %s" % (rel, real))
            if not os.path.isfile(real):
                raise RuntimeError("非普通文件：%s" % rel)
        return target

    def has(self, rel):
        return os.path.exists(self.p(rel))

    def load_sample(self):
        if self.sample_rows is None:
            self.sample_header, self.sample_rows = read_rows_strict(self.p(SAMPLE_FILE))
            self.sample_shas = [r[2] if len(r) > 2 else "" for r in self.sample_rows]
        return self.sample_header, self.sample_rows

    def load_pop(self):
        if self.pop_rows is None:
            self.pop_header, self.pop_rows = read_rows_strict(self.p(POP_FILE))
            self.pop_shas = []
            if self.pop_header.count("source_sha256") == 1:
                idx = self.pop_header.index("source_sha256")
                self.pop_shas = [r[idx] if len(r) > idx else "" for r in self.pop_rows]
        return self.pop_rows

    def load_tpl(self):
        if self.tpl_rows is None:
            self.tpl_header, self.tpl_rows = read_rows_strict(self.p(TPL_FILE))
            self.tpl_shas = [r[0] if r else "" for r in self.tpl_rows]
        return self.tpl_rows

    def load_cfg(self):
        if self.cfg is None:
            with io.open(self.p(CFG_FILE), "r", encoding="utf-8") as fh:
                self.cfg = json.load(fh)
        return self.cfg


def check_python_env(ctx):
    """P3(v2.5)：异常安全外壳。任何异常都落成 unavailable，绝不让 main() 崩。

    被包住的异常包括：
        ctx.has() 因 P2 严格路径检查抛出的 RuntimeError（lstat 权限不足等）
        ctx.load_cfg() 的 JSON 解析错误 / 编码错误
        find_generation_python / version_compatible 的类型错误
    四态优先级不变：unavailable > invalid > 无记录 > 有记录（match/mismatch）。
    """
    try:
        _check_python_env(ctx)
    except Exception as e:
        ctx.gen_py_unavailable = True
        ctx.gen_py_error = "%s: %s" % (type(e).__name__, e)


def _check_python_env(ctx):
    """主体：独立解析 Python 环境状态，与 V8 解耦。

    与 V8 是否 SKIP 无关：即使 population_manifest.csv 缺失导致 V8 SKIP，
    本函数仍会读 config 并把状态放进 ctx，汇总行不会误报「config 无记录」。
    """
    pyver = ctx.py_runtime
    if not ctx.has(CFG_FILE):
        ctx.gen_py_unavailable = True
        ctx.gen_py_error = "%s 不存在" % CFG_FILE
        return
    try:
        cfg = ctx.load_cfg()
    except Exception as e:
        ctx.gen_py_unavailable = True
        ctx.gen_py_error = "%s: %s" % (type(e).__name__, e)
        return
    key, val = find_generation_python(cfg)
    ctx.gen_py_key = key
    if val is None:
        return                      # 无该字段
    cmp = version_compatible(pyver, val)
    if cmp is None:
        ctx.gen_py_invalid = val    # 字段存在但格式无效
        return
    ctx.gen_py_val = val
    ctx.py_match = cmp


class Reporter(object):
    def __init__(self):
        self.items = []

    def add(self, vid, name, status, detail):
        self.items.append((vid, name, status, detail))

    def status(self, vid):
        for v, _, s, _ in self.items:
            if v == vid:
                return s
        return SKIP

    def group_pass(self, vids):
        return all(self.status(v) == PASS for v in vids)


# ---------------------------------------------------------------- 各检查项
def check_v1(ctx):
    print("-" * 78)
    print("V1  manifest 八条记录完整、relpath 原样逐字匹配、文件名唯一、白名单匹配")
    print("-" * 78)
    if not ctx.has(MAN_FILE):
        print("    FAIL: missing manifest file %s" % MAN_FILE)
        return FAIL, "manifest.sha256 不存在"

    records, errors = parse_manifest_strict(ctx.p(MAN_FILE))
    ctx.records = records
    names, relpaths, probs = [], [], []
    for digest, relpath_raw, label in records:
        base = os.path.basename(relpath_raw)
        print("    %s  %s  (%s)" % (digest, relpath_raw, label))
        names.append(base)
        relpaths.append(relpath_raw)
        ctx.man_sha[base] = digest
        ctx.man_rel[base] = relpath_raw
        for pr in relpath_problems(relpath_raw):
            probs.append("%s: %s" % (base, pr))
        if base not in EXPECTED_ALL_FILES:
            hint = ""
            if base.rstrip() in EXPECTED_ALL_FILES:
                hint = "（rstrip 后为 %r，说明只是尾部空白作祟；本脚本不做此归一化）" % base.rstrip()
            probs.append("%s: 不在白名单%s" % (base, hint))
        else:
            if relpath_raw != EXPECTED_RELPATHS[base]:
                probs.append("%s: relpath 与冻结值不符（实际 %r / 期望 %r）"
                             % (base, relpath_raw, EXPECTED_RELPATHS[base]))
    print()
    dup_name = sorted({x for x in names if names.count(x) > 1})
    dup_rel = sorted({x for x in relpaths if relpaths.count(x) > 1})
    extra = sorted(set(names) - EXPECTED_ALL_FILES)
    lack = sorted(EXPECTED_ALL_FILES - set(names))

    print("    记录数             = %d（期望 8）" % len(records))
    print("    唯一 basename 数   = %d（期望 8）" % len(set(names)))
    print("    唯一 relpath 数    = %d（期望 8）" % len(set(relpaths)))
    print("    重复 basename      = %s" % (dup_name if dup_name else "无"))
    print("    重复 relpath       = %s" % (dup_rel if dup_rel else "无"))
    print("    白名单外文件       = %s" % (extra if extra else "无"))
    print("    白名单缺失         = %s" % (lack if lack else "无"))
    print("    relpath 原样/结构  = %s" % (probs if probs else "全部逐字匹配（未归一化）"))
    for e in errors:
        print("    PARSE_ERROR        = %s" % e)

    ok = (not errors and len(records) == 8 and not dup_name and not dup_rel
          and not extra and not lack and not probs)
    if ok:
        return PASS, "8 条记录 / relpath 原样逐字匹配 / 0 重复 / 白名单恰好匹配"
    return FAIL, "errors=%d probs=%d dup=%s extra=%s lack=%s" % (
        len(errors), len(probs), dup_name or dup_rel, extra, lack)


def check_v2(ctx):
    print("-" * 78)
    print("V2  六个输出文件存在，SHA-256 同时匹配 manifest 与冻结基线")
    print("-" * 78)
    missing, bad_man, bad_frozen, ok_list = [], [], [], []
    for name in sorted(EXPECTED_OUTPUT_FILES):
        target = ctx.p(name)
        if not os.path.exists(target):
            print("    FAIL: missing output file %s" % name)
            missing.append(name)
            continue
        actual = sha256_file(target)
        m_ok = (actual == ctx.man_sha.get(name))
        f_ok = (actual == EXPECTED_OUTPUT_SHA.get(name))
        print("    [%s] %-28s %s" % ("PASS" if (m_ok and f_ok) else "FAIL", name, actual))
        if not m_ok:
            print("           manifest 记录 %s" % ctx.man_sha.get(name))
            bad_man.append(name)
        if not f_ok:
            print("           冻结基线    %s" % EXPECTED_OUTPUT_SHA.get(name))
            bad_frozen.append(name)
        if m_ok and f_ok:
            ok_list.append(name)
    for name in sorted(EXPECTED_INPUT_FILES):
        if not os.path.exists(ctx.p(name)):
            print("    INPUT_FILE_MISSING_OK: %s (N/A, 预期)" % name)
        else:
            actual = sha256_file(ctx.p(name))
            m_ok = (actual == ctx.man_sha.get(name))
            print("    [%s] %-28s %s" % ("PASS" if m_ok else "FAIL", name, actual))
            if not m_ok:
                print("           manifest 记录 %s" % ctx.man_sha.get(name))
                bad_man.append(name)
    print()
    print("    冻结基线核对       = %d/6 一致；manifest 核对 = %d 处不符"
          % (6 - len(bad_frozen), len(bad_man)))
    ok = (not missing and not bad_man and not bad_frozen and len(ok_list) == 6)
    if ok:
        return PASS, "6/6 存在，且 manifest 与冻结基线双条件均一致"
    return FAIL, "缺失=%s manifest不符=%s 基线不符=%s" % (missing, bad_man, bad_frozen)


def check_v3(ctx):
    print("-" * 78)
    print("V3  样本 350 行、14 列、表头正确")
    print("-" * 78)
    if not ctx.has(SAMPLE_FILE):
        print("    FAIL: missing output file %s" % SAMPLE_FILE)
        return FAIL, "sample_350.csv 不存在"
    header, rows = ctx.load_sample()
    hdr_ok = (header == EXPECTED_SAMPLE_HEADER)
    badlen = count_bad_rows(rows, len(EXPECTED_SAMPLE_HEADER))
    print("    表头列数           = %d（期望 14）" % len(header))
    print("    表头逐列匹配       = %s" % ("是" if hdr_ok else "否"))
    if not hdr_ok:
        print("      实际 = %r" % (header,))
        print("      期望 = %r" % (EXPECTED_SAMPLE_HEADER,))
    print("    数据行数           = %d（期望 350）" % len(rows))
    print("    列数不符行         = %s" % (badlen[:10] if badlen else "无"))
    ok = hdr_ok and len(rows) == EXPECTED_N_SAMPLE and not badlen
    if ok:
        return PASS, "350 行 / 14 列 / 表头逐列一致"
    return FAIL, "header_ok=%s rows=%d badlen=%d" % (hdr_ok, len(rows), len(badlen))


def check_v4(ctx):
    print("-" * 78)
    print("V4  350 个 SHA 全唯一且格式合法（原始字段，不 strip / 不 lower）")
    print("-" * 78)
    if not ctx.has(SAMPLE_FILE):
        print("    FAIL: missing output file %s" % SAMPLE_FILE)
        return FAIL, "sample_350.csv 不存在"
    ctx.load_sample()
    shas = ctx.sample_shas              # 原始值
    empty = [i for i, s in enumerate(shas, 2) if s == ""]
    badfmt = [(i, s) for i, s in enumerate(shas, 2) if not SHA_RE.fullmatch(s)]
    dup = sorted({s for s in shas if shas.count(s) > 1})
    print("    SHA 个数           = %d（期望 350）" % len(shas))
    print("    唯一 SHA 数        = %d（期望 350）" % len(set(shas)))
    print("    空值行             = %s" % (empty[:10] if empty else "无"))
    print("    格式非法行         = %d %s" % (len(badfmt), badfmt[:5] if badfmt else ""))
    if badfmt:
        i, s = badfmt[0]
        print("      首例第 %d 行     = %r（要求 64 位小写 hex，大小写敏感）" % (i, s))
    print("    重复 SHA           = %s" % (dup[:5] if dup else "无"))
    ok = (len(shas) == EXPECTED_N_SAMPLE and not empty and not badfmt and not dup)
    if ok:
        return PASS, "350/350 唯一，原始字段全部匹配 ^[0-9a-f]{64}$"
    return FAIL, "unique=%d empty=%d badfmt=%d dup=%d" % (
        len(set(shas)), len(empty), len(badfmt), len(dup))


def check_v5(ctx):
    print("-" * 78)
    print("V5  总体 6,327 个唯一 SHA，样本全部属于总体（表头无 fallback）")
    print("-" * 78)
    if not ctx.has(POP_FILE):
        print("    SKIP: %s 未提供" % POP_FILE)
        return SKIP, "%s 未提供" % POP_FILE
    header, rows = read_rows_strict(ctx.p(POP_FILE))
    ctx.pop_header, ctx.pop_rows = header, rows
    n_col = header.count("source_sha256")
    print("    表头列数           = %d" % len(header))
    print("    表头含 source_sha256 次数 = %d（必须恰好 1）" % n_col)
    if n_col != 1:
        print("    FAIL: 表头 source_sha256 缺失或重复，拒绝使用列号 fallback")
        return FAIL, "表头 source_sha256 出现 %d 次" % n_col
    idx = header.index("source_sha256")
    badlen = count_bad_rows(rows, len(header))
    print("    列数不符行         = %s" % (badlen[:10] if badlen else "无"))
    pop_shas = [r[idx] if len(r) > idx else "" for r in rows]
    ctx.pop_shas = pop_shas
    badfmt = [(i, s) for i, s in enumerate(pop_shas, 2) if not SHA_RE.fullmatch(s)]
    dup = sorted({s for s in pop_shas if pop_shas.count(s) > 1})
    print("    总体行数           = %d（期望 6,327）" % len(rows))
    print("    唯一 SHA 数        = %d（期望 6,327）" % len(set(pop_shas)))
    print("    格式非法行         = %d %s" % (len(badfmt), badfmt[:5] if badfmt else ""))
    print("    重复 SHA           = %s" % (dup[:5] if dup else "无"))

    # v2.3：样本缺失不得 PASS —— 归属关系无从验证，直接 FAIL
    if not ctx.has(SAMPLE_FILE):
        print("    FAIL: 样本文件缺失，无法验证归属")
        return FAIL, "样本文件缺失，无法验证归属"
    ctx.load_sample()
    outside = sorted(set(ctx.sample_shas) - set(pop_shas))
    print("    样本越界           = %d" % len(outside))
    ok = (len(rows) == EXPECTED_N_POP and len(set(pop_shas)) == EXPECTED_N_POP
          and not badlen and not badfmt and not dup and not outside)
    if ok:
        return PASS, "6,327 唯一 / 无非法格式 / 无重复 / 越界 0"
    return FAIL, "rows=%d unique=%d badlen=%d badfmt=%d dup=%d outside=%d" % (
        len(rows), len(set(pop_shas)), len(badlen), len(badfmt), len(dup), len(outside))


def check_v6(ctx):
    print("-" * 78)
    print("V6  %s" % V6_DESC)
    print("-" * 78)
    if not ctx.has(TPL_FILE):
        print("    FAIL: missing output file %s" % TPL_FILE)
        return FAIL, "%s 不存在" % TPL_FILE
    ctx.load_tpl()
    header, rows = ctx.tpl_header, ctx.tpl_rows
    ncol = len(header)
    head9 = (ncol >= 9 and header[:9] == EXPECTED_TPL_HEADER)
    if ncol == 9:
        extra_ok, extra_note = True, "9 列基础模板"
    elif ncol == 13:
        extra_ok = (header[9:] == TPL_EXTRA_HEADER)
        extra_note = "13 列（9 必备 + 4 复核留痕）"
    else:
        extra_ok, extra_note = False, "%d 列，不在允许集合内" % ncol
    badlen = count_bad_rows(rows, ncol) if ncol else []
    shas = ctx.tpl_shas
    badfmt = [(i, s) for i, s in enumerate(shas, 2) if not SHA_RE.fullmatch(s)]
    seq_ok = False
    if ctx.has(SAMPLE_FILE):
        ctx.load_sample()
        seq_ok = (shas == ctx.sample_shas)
    print("    表头列数           = %d（允许 9 或 13）-> %s" % (ncol, extra_note))
    print("    前 9 列逐列匹配    = %s" % ("是" if head9 else "否"))
    if not head9 and ncol >= 9:
        print("      实际前 9 = %r" % (header[:9],))
        print("      期望前 9 = %r" % (EXPECTED_TPL_HEADER,))
    if ncol == 13:
        print("    第 10–13 列匹配    = %s" % ("是" if extra_ok else "否"))
        if not extra_ok:
            print("      实际 10–13 = %r" % (header[9:],))
            print("      期望 10–13 = %r" % (TPL_EXTRA_HEADER,))
    print("    数据行数           = %d（期望 350）" % len(rows))
    print("    列数不符行         = %s" % (badlen[:10] if badlen else "无"))
    print("    SHA 格式非法行     = %d（原始字段，大小写敏感）" % len(badfmt))
    print("    与样本逐项一致     = %s" % ("是" if seq_ok else "否"))
    ok = head9 and extra_ok and len(rows) == EXPECTED_N_SAMPLE and not badlen \
        and not badfmt and seq_ok
    if ok:
        return PASS, "9 必备列一致；%s；350 行；与样本逐项一致" % extra_note
    return FAIL, "head9=%s extra=%s ncol=%d rows=%d badlen=%d badfmt=%d seq=%s" % (
        head9, extra_ok, ncol, len(rows), len(badlen), len(badfmt), seq_ok)


def check_v7(ctx):
    print("-" * 78)
    print("V7  总体池指纹与冻结值一致")
    print("-" * 78)
    if not ctx.has(POP_FILE):
        print("    SKIP: %s 未提供" % POP_FILE)
        return SKIP, "%s 未提供" % POP_FILE
    ctx.load_pop()
    if ctx.pop_shas is None:
        print("    FAIL: 总体表头无唯一 source_sha256，无法计算池指纹")
        return FAIL, "总体表头异常，无法计算池指纹"
    digest = hashlib.sha256("\n".join(sorted(set(ctx.pop_shas))).encode()).hexdigest()
    print("    复算池指纹         = %s" % digest)
    print("    冻结值             = %s" % EXPECTED_POOL_SHA)
    ok = (digest == EXPECTED_POOL_SHA)
    return (PASS, digest) if ok else (FAIL, "%s != 冻结值" % digest)


def check_v8(ctx):
    print("-" * 78)
    print("V8  重新执行 seed=42 的 SRS，抽样序列完全一致")
    print("-" * 78)
    if not ctx.has(POP_FILE):
        print("    SKIP: population_manifest.csv 未提供，无法复现抽样")
        return SKIP, "population_manifest.csv 未提供"
    if not ctx.has(SAMPLE_FILE):
        print("    SKIP: sample_350.csv 不可用，无法比对序列")
        return SKIP, "sample_350.csv 不可用"
    ctx.load_pop()
    if ctx.pop_shas is None or not ctx.pop_shas:
        print("    SKIP: 总体表头异常，池不可构造")
        return SKIP, "总体表头异常，池不可构造"
    ctx.load_sample()
    pool = sorted(set(ctx.pop_shas))
    expected = random.Random(EXPECTED_SEED).sample(pool, EXPECTED_N_SAMPLE)
    actual = ctx.sample_shas
    first_diff = None
    for i, (a, b) in enumerate(zip(actual, expected), 1):
        if a != b:
            first_diff = (i, a, b)
            break
    seq_actual = hashlib.sha256("\n".join(actual).encode()).hexdigest()
    seq_expect = hashlib.sha256("\n".join(expected).encode()).hexdigest()
    print("    pool 大小          = %d（唯一 SHA，升序）" % len(pool))
    print("    rng                = random.Random(%d).sample(pool, %d)"
          % (EXPECTED_SEED, EXPECTED_N_SAMPLE))
    print("    复现序列首 3       = %s" % expected[:3])
    print("    实际序列首 3       = %s" % actual[:3])
    print("    复现序列末 3       = %s" % expected[-3:])
    print("    实际序列末 3       = %s" % actual[-3:])
    print("    seq_sha256(复现)   = %s" % seq_expect)
    print("    seq_sha256(实际)   = %s" % seq_actual)
    print("    等于扰动测试指纹   = %s"
          % (seq_actual == "a08a909a5930863709e65813e06c2c209b7c8ae2d09234cf9e897775c7f0aba8"))
    if first_diff:
        print("    首个差异位置       = #%d 实际=%s 复现=%s" % first_diff)
    seq_same = (actual == expected)
    if not seq_same:
        print("    assert actual == expected, \"SRS 序列与 seed=42 复现结果不一致\"")

    # ---- P1/P3（v2.8）：版本状态只作提示，不参与 V8 的 PASS/FAIL ----
    # 设计口径：PYTHON_REPRODUCIBILITY 是 main() 的独立状态行，不进 V1–V10。
    # v2.7 及以前用 ver_ok = ctx.py_match 参与判定，造成判定边界不对称：
    # 无记录 / 不可读 / 记录无效三种情况一律不影响，唯独「有效记录但不匹配」导致
    # V8 FAIL 并连带 OVERALL_PASS=false。v2.8 起 V8 只回答"抽样序列能否复现"。
    pyver = ctx.py_runtime
    if ctx.gen_py_unavailable:
        print("    [NOTE] python_runtime = %s；config 不可读（%s）"
              % (pyver, ctx.gen_py_error))
    elif ctx.gen_py_invalid is not None:
        print("    [WARN] 无效的版本格式：%r（无法解析出严格版本号），视为未记录"
              % (ctx.gen_py_invalid,))
    elif ctx.gen_py_val is None:
        print("    [NOTE] python_runtime = %s；generation_python = 未记录（待补证）"
              % pyver)
    else:
        print("    [NOTE] python_runtime = %s / generation_python = %s -> %s"
              % (pyver, ctx.gen_py_val, "VERIFIED" if ctx.py_match else "MISMATCH"))
        if not ctx.py_match:
            print("           仅在本机 %s 下可复现，跨环境可重复性未验证。" % pyver)
    print("           版本状态不参与 V8 判定；跨环境结论见汇总行 PYTHON_REPRODUCIBILITY")

    ok = seq_same
    if ok:
        return PASS, "350 条逐条一致，seq_sha256=%s" % seq_actual
    return FAIL, "SRS 序列一致=%s（Python 版本状态不参与本项判定）" % seq_same


def check_v9(ctx):
    print("-" * 78)
    print("V9  selection_prob 与 350/6327 一致（config 容差 1e-9 / 样本列 8 位展示）")
    print("-" * 78)
    if not ctx.has(CFG_FILE):
        print("    FAIL: missing output file %s" % CFG_FILE)
        return FAIL, "%s 不存在" % CFG_FILE
    cfg = ctx.load_cfg()
    calc = EXPECTED_N_SAMPLE / EXPECTED_N_POP
    raw = cfg.get("selection_probability")
    print("    350/6327           = %.12f" % calc)
    if raw is None:
        print("    FAIL: config 缺少 selection_probability 字段")
        return FAIL, "config 缺少 selection_probability"
    try:
        prob = float(raw)
    except (TypeError, ValueError) as e:
        print("    FAIL: selection_probability 非数值 %r（%s: %s）"
              % (raw, type(e).__name__, e))
        return FAIL, "selection_probability 非数值：%r" % (raw,)
    d_cfg = abs(prob - calc)
    disp = "%.8f" % calc
    col = []
    if ctx.has(SAMPLE_FILE):
        ctx.load_sample()
        col = sorted({r[12] for r in ctx.sample_rows if len(r) > 12})
    col_dev = 0.0
    if col:
        try:
            col_dev = abs(float(col[0]) - calc)
        except (TypeError, ValueError):
            col_dev = 9.9
    print("    config 记录值      = %s（差 %.3e，容差 %.0e）%s"
          % (raw, d_cfg, PROB_TOL, "PASS" if d_cfg <= PROB_TOL else "FAIL"))
    print("    样本列取值         = %s（%d 种）" % (col, len(col)))
    print("    样本列期望值       = %s（\"%%.8f\" 8 位展示）" % disp)
    print("    NOTE: 样本列 8 位舍入偏差 %.3e 属展示精度，非取值不一致" % col_dev)
    ok = (d_cfg <= PROB_TOL and col == [disp])
    if ok:
        return PASS, "config 偏差 %.3e <= 1e-9；样本列 == %s" % (d_cfg, disp)
    return FAIL, "config 偏差 %.3e；样本列 %s（期望 %s）" % (d_cfg, col, disp)


def check_v10(ctx):
    print("-" * 78)
    print("V10 config / population / sample / 冻结基线的哈希关系一致")
    print("-" * 78)
    if not ctx.has(CFG_FILE):
        print("    SKIP: %s 未提供" % CFG_FILE)
        return SKIP, "%s 未提供" % CFG_FILE
    cfg = ctx.load_cfg()
    bad = []

    for key, fname in (("sample_sha256", SAMPLE_FILE),
                       ("population_manifest_sha256", POP_FILE),
                       ("human_template_sha256", TPL_FILE)):
        declared = cfg.get(key)
        if not ctx.has(fname):
            print("    [SKIP] %-30s 文件缺失，无法比对" % key)
            bad.append(key + "(缺失)")
            continue
        actual = sha256_file(ctx.p(fname))
        same = (declared == actual)
        print("    [%s] %-30s config=%s" % ("PASS" if same else "FAIL", key, declared))
        if not same:
            print("           实际 %s" % actual)
            bad.append(key)
        if key == "sample_sha256":
            fb = (declared == EXPECTED_SAMPLE_SHA)
            print("    [%s] %-30s baseline=%s"
                  % ("PASS" if fb else "FAIL", "sample_sha256 vs frozen(decl)",
                     EXPECTED_SAMPLE_SHA))
            if not fb:
                bad.append("sample_sha256!=frozen(decl)")

    for key, fname in (("sample_sha256", SAMPLE_FILE),
                       ("population_manifest_sha256", POP_FILE),
                       ("human_template_sha256", TPL_FILE)):
        same = (cfg.get(key) == ctx.man_sha.get(fname))
        print("    [%s] %-30s manifest=%s"
              % ("PASS" if same else "FAIL", key + " vs manifest", ctx.man_sha.get(fname)))
        if not same:
            bad.append(key + "!=manifest")

    if ctx.has(SAMPLE_FILE):
        actual_sample_sha = sha256_file(ctx.p(SAMPLE_FILE))
        frozen_sample_ok = (actual_sample_sha == EXPECTED_SAMPLE_SHA)
        print("    [%s] sample_sha256 vs frozen baseline  %s"
              % ("PASS" if frozen_sample_ok else "FAIL", actual_sample_sha))
        if not frozen_sample_ok:
            print("           冻结基线 %s" % EXPECTED_SAMPLE_SHA)
            bad.append("sample!=frozen(actual)")
    else:
        print("    [FAIL] sample_sha256 vs frozen baseline  文件缺失")
        bad.append("sample(缺失)")

    print("    generator                          = %s" % cfg.get("generator"))
    ok_p = (cfg.get("sample_size") == EXPECTED_N_SAMPLE
            and cfg.get("population_count") == EXPECTED_N_POP
            and cfg.get("seed") == EXPECTED_SEED
            and cfg.get("stratified") is False)
    print("    [%s] sample_size=%s population_count=%s seed=%s stratified=%s"
          % ("PASS" if ok_p else "FAIL", cfg.get("sample_size"),
             cfg.get("population_count"), cfg.get("seed"), cfg.get("stratified")))
    if not ok_p:
        bad.append("规模参数")
    ok = (not bad)
    if ok:
        return PASS, "3 哈希×实际/基线/manifest 三方一致 + 规模参数一致"
    return FAIL, "不一致项 %s" % (bad,)


CHECKS = [
    ("V1", "manifest 八条记录完整、relpath 原样逐字匹配、文件名唯一、白名单匹配", check_v1),
    ("V2", "六个输出文件存在，SHA-256 同时匹配 manifest 与冻结基线", check_v2),
    ("V3", "样本 350 行、14 列、表头正确", check_v3),
    ("V4", "350 个 SHA 全唯一且格式合法（原始字段）", check_v4),
    ("V5", "总体 6,327 个唯一 SHA，样本全部属于总体", check_v5),
    ("V6", V6_DESC, check_v6),
    ("V7", "总体池指纹与冻结值一致", check_v7),
    ("V8", "重新执行 seed=42 的 SRS，抽样序列完全一致", check_v8),
    ("V9", "selection_prob 与 350/6327 一致（容差 1e-9）", check_v9),
    ("V10", "config / population / sample / 冻结基线的哈希关系一致", check_v10),
]


def main():
    ap = argparse.ArgumentParser(description="Stage A SRS 交付包独立验证 v%s" % VERSION)
    ap.add_argument("--dir", default=os.path.dirname(os.path.abspath(__file__)),
                    help="交付包解压目录，默认本脚本所在目录")
    ap.add_argument("--version", action="version", version="verify_reviewer.py %s" % VERSION)
    args = ap.parse_args()
    d = args.dir

    pyver = "%d.%d.%d" % sys.version_info[:3]
    print("=" * 78)
    print("Stage A · SRS 交付包 · 独立验证  v%s" % VERSION)
    print("=" * 78)
    print("python_version = %s" % pyver)
    print("requires       = Python %d.%d+" % REQUIRES_PYTHON)
    print("verify_dir     = %s" % d)
    print("network        = none    file_write = none    third_party = none")
    print()

    if sys.version_info[:2] < REQUIRES_PYTHON:
        print("FAIL: python_version %s < 要求 %d.%d"
              % (pyver, REQUIRES_PYTHON[0], REQUIRES_PYTHON[1]))
        return 1

    try:
        ctx = Ctx(d)
    except RuntimeError as e:
        print("FAIL: %s" % e)
        print("交付根目录不可信，终止全部检查（V1–V10 均未执行）。")
        print("OVERALL_PASS               = false")
        return 1
    check_python_env(ctx)
    rep = Reporter()

    for vid, name, fn in CHECKS:
        st, detail = None, None
        try:
            st, detail = fn(ctx)
        except Exception as e:
            print("    EXCEPTION %s: %s" % (type(e).__name__, e))
            st, detail = FAIL, "异常 %s: %s" % (type(e).__name__, e)
        rep.add(vid, name, st, detail)
        print()

    print("=" * 78)
    print("V1–V10 断言明细")
    print("=" * 78)
    for vid, name, status, detail in rep.items:
        print("[%-4s] %-4s %s" % (status, vid, name))
        print("           %s" % detail)
    print()

    file_int = rep.group_pass(["V1", "V2", "V3", "V6"])
    pop_int = rep.group_pass(["V5", "V7", "V10"])
    srs_rep = rep.group_pass(["V8", "V9"])
    overall = all(rep.status(v) == PASS for v in
                  ["V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8", "V9", "V10"])

    n_pass = sum(1 for x in rep.items if x[2] == PASS)
    n_fail = sum(1 for x in rep.items if x[2] == FAIL)
    n_skip = sum(1 for x in rep.items if x[2] == SKIP)

    print("=" * 78)
    print("四项分类结论（互不替代）")
    print("=" * 78)
    print("FILE_INTEGRITY_PASS        = %s   # V1+V2+V3+V6"
          % ("true" if file_int else "false"))
    print("POPULATION_INTEGRITY_PASS  = %s   # V5+V7+V10"
          % ("true" if pop_int else "false"))
    print("SRS_REPRODUCIBILITY_PASS   = %s   # V8+V9"
          % ("true" if srs_rep else "false"))
    print("OVERALL_PASS               = %s   # V1–V10 全 PASS，SKIP 视为 false"
          % ("true" if overall else "false"))
    print()
    # P3(v2.4)：独立状态行，不进 V1–V10、不影响 OVERALL_PASS
    if ctx.gen_py_unavailable:
        print("PYTHON_REPRODUCIBILITY     = UNVERIFIED (config unavailable/read error)")
    elif ctx.gen_py_invalid is not None:
        print("PYTHON_REPRODUCIBILITY     = UNVERIFIED (config 记录值 %r 无效，视为未记录)"
              % (ctx.gen_py_invalid,))
    elif ctx.gen_py_val is None:
        print("PYTHON_REPRODUCIBILITY     = UNVERIFIED (config 无 generation_python 记录)")
    else:
        print("PYTHON_REPRODUCIBILITY     = %s (generation_python=%s, runtime=%s)"
              % ("VERIFIED" if ctx.py_match else "MISMATCH",
                 ctx.gen_py_val, ctx.py_runtime))
    print()
    print("统计：PASS=%d FAIL=%d SKIP=%d（共 10 项）" % (n_pass, n_fail, n_skip))
    print("python_version = %s    verify_reviewer_version = %s" % (pyver, VERSION))
    print("=" * 78)
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
