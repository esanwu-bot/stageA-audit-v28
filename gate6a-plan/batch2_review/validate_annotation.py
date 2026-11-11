# -*- coding: utf-8 -*-
"""标注机检 v1.5 —— 核对"这一行填的东西，是不是真印在你说的那一页上"。

v1 的三个漏洞，v2 逐个补上
--------------------------
1. **没验参数名**：v1 只验 symbol。模型把条件写成参数名（`VPOS_IN_x`）、把名字截断成
   残词（`Input volta`）都能过。v2 要求 parameter_name 在该页原文里能对上，对不上要指出
   缺哪个词。
2. **数值只认第一个数**：v1 的 `num_pattern` 从 `±2.5` 里抠出 `2.5`，只要页面上有 `2.5`
   就放行；`VCC-0.2` 会抠出 `-0.2`；`-0.5 to 7` 只验左端点。v2 先分类再验：
   NUMBER / ±PM / RANGE / FORMULA / WITH_UNIT / TEXT，公式和非数值直接判 ERROR。
3. **路径写死**：v1 把 `Gold_Set_v1.1_WORKING.csv` 和其中的绝对路径当命根子，换个目录就崩。
   v2 只认 --csv 里的 file_name，PDF 目录按 `--pdf-dir` → 环境变量 → 同目录 `pdfs/` 依次找；
   全都没有就退到同目录的 `page_text.json`（证据页原文，随包分发），此时脚本**不依赖 PyMuPDF**。

v1.4 新增
---------
* 版本号统一为 1.4（脚本、报告、README、提交信息同号）；
* **溯源一致性检查**：CSV、page_text.json、Batch2_PDF_PROVENANCE.csv 三处的
  file_name / device_model / sha256 / page_count 必须完全一致，不一致直接 ERROR；
* **PDF 模式重算哈希**：给了 --pdf-dir 就现场算每个 PDF 的 SHA-256 与 sidecar 比对，
  文件被换过就报 ERROR（反例见 _selftest_validator_v2.py 的篡改用例）；
* 不再有任何绝对路径：PDF 目录走 --pdf-dir / ICPDF_PDF_DIR / ./pdfs，
  溯源表走 --provenance / ./Batch2_PDF_PROVENANCE.csv。

v1.5 修正：4 处 Fail-Open
-------------------------
Fail-Open 指"本该报错的地方没报错，于是整批看起来是绿的"。v1.4 有 4 处：

F1. **溯源表读不到只提示**：`check_provenance()` 拿不到 provenance 表时 `notes.append`
    一句就继续，等于第三方参照丢了还照常出 OK=24。现在改成抛 `FatalInput`、打印 `[ERROR]`、
    退出码 2——没有第三方参照，整批不可信。

F2. **空字段跳过互校**：原来是 `if a and b and a != b`，只要任一侧为空就整条跳过。
    空字段被当成"无所谓"，实际是"这条链断了"。现在统一改成
    `if not a or not b or a != b: ERROR`。同时把字段对应关系说清：
      * CSV ↔ sidecar：只比 `file_name`、`device_model`（CSV 没有 sha256 / page_count 列）；
      * sidecar ↔ provenance：比全部四项 `file_name` / `device_model` / `sha256` / `page_count`。

F3. **PDF 缺失静默降级**：`--pdf-dir` 指向不存在的目录时，老逻辑会掉头去读 sidecar，
    报告上只多一行"提示"，结论照样绿。现在：显式给了 `--pdf-dir`（或 `ICPDF_PDF_DIR`）
    却不可用 → `FatalInput`；目录在但某个 PDF 不在、PDF 打不开、哈希算不了 → 该样本 ERROR。
    任何情况下都不再自动退回离线模式。

F4. **哈希不符仍继续读文本**：老逻辑把"哈希不符"混进 `prov_issues` 后，行循环照样调
    `page_text()` 核页内文字——文件都不是那一份了，核出来的字毫无意义。现在发现不符就把
    该样本丢进 `hash_bad`，它的所有行直接 ERROR 并 `continue`，**在调用 `page_text()` 之前**。
    自测最后一项专门断言这一点（`page_text` 调用次数为 0）。

它不是什么
----------
* 不是 Parser，不 import icpdf.*。
* 不改 CSV，只出报告。
* 不判断参数选得对不对，只判断"抄的字在不在那一页"。

用法
----
  python validate_annotation.py                          # 默认 Batch2_GOLD_v1.csv
  python validate_annotation.py --csv X.csv --pdf-dir /path/to/pdfs
  ICPDF_PDF_DIR=/path/to/pdfs python validate_annotation.py
  python validate_annotation.py --no-suggest              # 不做全文找页，快
退出码：0 无 ERROR，1 有 ERROR，2 输入有问题。
"""
from __future__ import print_function

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path

VERSION = "1.5"

HERE = Path(__file__).resolve().parent
DEFAULT_CSV = HERE / "Batch2_GOLD_v1.csv"
SIDECAR = HERE / "page_text.json"
PROVENANCE = HERE / "Batch2_PDF_PROVENANCE.csv"

MINUS = "-\u2212\u2013\u2014"          # 连字符/数学减号/短横/长横
SPACE_RE = re.compile(r"\s+")
# 边界断言：左右不能是"字母或数字"。用 Unicode 字符类而不是 [a-z0-9]，
# 否则 `µA` 里的 A 会被当成独立的单位 A（µ 不在 a-z 里，边界就漏了）。
BOUND_L = r"(?<![^\W_])"
BOUND_R = r"(?![^\W_])"
NUM_BODY = r"\d+(?:\.\d+)?"

KIND_LABEL = {
    "NUMBER": "数值", "PM": "正负值", "RANGE": "范围", "FORMULA": "公式",
    "WITH_UNIT": "数值带单位", "TEXT": "文字", "EMPTY": "空",
}


# ---------------------------------------------------------------- 文本归一


def unify(s):
    """统一微符号 / 减号 / 不换行空格 / 摄氏度写法。空白另行处理。"""
    if s is None:
        return ""
    t = str(s)
    t = t.replace("\u00b5", "u").replace("\u03bc", "u").replace("\u212b", "A")
    t = t.replace("\u2103", "\u00b0C")                 # ℃ -> °C
    for ch in MINUS:
        t = t.replace(ch, "-")
    return t.replace("\u00a0", " ")


def collapse(s):
    """压成单空格。数值核对必须保留边界，不能把空白删光（`0 to 1.75` 会粘连）。"""
    return SPACE_RE.sub(" ", unify(s)).strip()


def nos(s):
    """压成无空白小写，用于名字/符号这类"排版换了但字没变"的比对。"""
    return SPACE_RE.sub("", unify(s)).lower()


def num_body(num):
    """把一个数字串变成"容忍 PDF 把 1.75 抽成 1 . 75"的正则体，并剥掉尾零。"""
    core = num
    if "." in core:
        core = core.rstrip("0").rstrip(".")
    return r"\s*".join(re.escape(ch) for ch in core)


def num_pattern(val):
    """数字的宽松正则：容忍 `1 . 75` 这种被拆开的抽取，剥尾零，两侧不许贴数字。"""
    v = collapse(val)
    m = re.search(r"-?" + NUM_BODY, v)
    if not m:
        return None
    body = num_body(m.group(0))
    return re.compile(r"(?<![\d.])" + body + r"0*(?![\d.])")


# ---------------------------------------------------------------- 数值分类


def classify(val):
    """把数值列拆成 6 类。返回 (kind, numbers, 原文)。"""
    v = collapse(val)
    if not v:
        return "EMPTY", [], v

    m = re.fullmatch(r"[±]\s*(" + NUM_BODY + r")", v)
    if m:
        return "PM", [m.group(1)], v

    m = re.fullmatch(r"\+\s*(" + NUM_BODY + r")\s*/\s*-\s*(" + NUM_BODY + r")", v)
    if m:
        return "PM", [m.group(1)], v

    m = re.fullmatch(r"(-?" + NUM_BODY + r")\s*(?:to|~|\.\.\.|—|–|-)\s*(-?" + NUM_BODY + r")", v)
    if m:
        return "RANGE", [m.group(1), m.group(2)], v

    if re.fullmatch(r"-?" + NUM_BODY, v):
        return "NUMBER", [v], v

    m = re.fullmatch(r"(-?" + NUM_BODY + r")\s*[A-Za-z%/\u00b0\u03a9][A-Za-z0-9%/\u00b0\u03a9\u00b7]*", v)
    if m:
        return "WITH_UNIT", [m.group(1)], v

    if re.search(r"MIN\s*\(|MAX\s*\(", v, re.I):
        return "FORMULA", [], v
    if re.search(r"[A-Za-z_]{2,}\s*[-+*/]|[-+*/]\s*[A-Za-z_]{2,}", v):
        return "FORMULA", [], v

    return "TEXT", [], v


def pm_pattern(num):
    """`±2.5` 的宽松正则：允许 ± 与数字之间有空格。"""
    core = num.rstrip("0").rstrip(".") if "." in num else num
    body = r"\s*".join(re.escape(ch) for ch in core)
    return re.compile(r"[±]\s*" + body + r"0*(?![\d.])")


def sha256_file(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


# ---------------------------------------------------------------- 页文本来源


class FatalInput(Exception):
    """输入/环境层面就错了，不允许继续核。

    和"某一行有 ERROR"不同：那种情况其余行还能核，能出完整报告；
    这种是判据本身没了（溯源表读不到、PDF 目录不存在），继续跑只会产出一份
    看起来全绿、实际没有任何证据支撑的报告。所以直接退出，退出码 2。
    """


class Pages(object):
    """按样本提供页文本。PDF 优先，退到 page_text.json。

    v1.5 起 PDF 模式的规矩变硬了：**要么真读到 PDF，要么报错，绝不悄悄换源**。
    老版本在"--pdf-dir 不存在""文件不在""打不开"三种情况下都会掉头去读 sidecar，
    报告上只多一行提示，结论照样绿——那是最难查的一类假绿。
    """

    def __init__(self, rows, pdf_dir=None, sidecar=None, no_suggest=False,
                 pdf_explicit=False):
        self.mode = "none"
        self.pdf_dir = pdf_dir
        self.sidecar = sidecar
        self.no_suggest = no_suggest
        self.docs = {}
        self.cache = {}
        self.pdf_sha = {}
        self.json = None
        self.error = ""
        self.fatal = []          # 致命：显式声明的 PDF 源不可用
        self.sample_errors = {}  # 样本级致命：这个样本的 PDF 缺失/打不开/算不了哈希

        # sidecar 里的 sha256/page_count 是"期望值"，两种模式都要读——所以放在最前面，
        # 不能等 PDF 分支 return 之后才加载（那样 PDF 模式下就没有期望值可对）。
        self.expected = {}
        if sidecar and sidecar.exists():
            try:
                self.expected = (json.loads(sidecar.read_text(encoding="utf-8"))
                                 .get("samples") or {})
            except Exception as e:
                self.error = "page_text.json 解析失败: %s" % e
                if pdf_explicit:
                    self.fatal.append(self.error)

        if pdf_dir is not None:
            if not pdf_dir.exists():
                # 明确给了 --pdf-dir / ICPDF_PDF_DIR 却指不到目录：直接判死。
                # 自动探测出来的 ./pdfs 不存在不算错，那只是"没提供 PDF"。
                if pdf_explicit:
                    self.fatal.append("--pdf-dir 指定的目录不存在: %s" % pdf_dir)
                return
            if not pdf_dir.is_dir():
                if pdf_explicit:
                    self.fatal.append("--pdf-dir 指向的不是目录: %s" % pdf_dir)
                return
            try:
                import fitz  # noqa: F401
            except ImportError:
                msg = "指定了 --pdf-dir 但没装 PyMuPDF，无法读取 PDF 原件"
                if pdf_explicit:
                    self.fatal.append(msg)
                else:
                    self.error = msg
            else:
                self.mode = "pdf"
                return

        if self.fatal:
            return

        if sidecar and sidecar.exists():
            self.json = json.loads(sidecar.read_text(encoding="utf-8"))
            self.mode = "json"
            if self.error:
                self.error += "；"
            self.error += "使用随包的 page_text.json（只含证据页，无法给出建议页）"
            return

        self.error = "既没有 PDF 目录也没有 page_text.json，无法核对页内文字"

    def _sample_error(self, sno, msg):
        bucket = self.sample_errors.setdefault(sno, [])
        if msg not in bucket:
            bucket.append(msg)

    def open_doc(self, sno, file_name):
        """PDF 模式必须打开成功；任何失败都记成样本级错误，不降级。"""
        if self.mode != "pdf":
            return None
        if sno in self.docs:
            return self.docs[sno]
        path = self.pdf_dir / (file_name or "")
        if not file_name:
            self._sample_error(sno, "PDF 缺失：该行没有 file_name，无法定位原件")
            return None
        if not path.exists():
            self._sample_error(
                sno, "PDF 缺失：%s 不在 %s（PDF 模式不做离线降级）"
                     % (file_name, self.pdf_dir))
            return None
        try:
            import fitz
            self.docs[sno] = fitz.open(str(path))
        except Exception as e:
            self._sample_error(sno, "PDF 打不开：%s（%s: %s）"
                                    % (file_name, type(e).__name__, e))
            return None
        return self.docs[sno]

    def page_text(self, sno, file_name, page_no):
        key = (sno, page_no)
        if key in self.cache:
            return self.cache[key]
        text = None
        if self.mode == "pdf":
            doc = self.open_doc(sno, file_name)
            if doc is not None and 1 <= page_no <= doc.page_count:
                text = doc.load_page(page_no - 1).get_text("text") or ""
        elif self.mode == "json":
            node = (self.json.get("samples") or {}).get(sno) or {}
            text = (node.get("pages") or {}).get(str(page_no))
        self.cache[key] = text
        return text

    def page_count(self, sno, file_name=None):
        if self.mode == "pdf":
            doc = self.open_doc(sno, file_name) if file_name else self.docs.get(sno)
            if doc is not None:
                return doc.page_count
        if self.mode == "json":
            node = (self.json.get("samples") or {}).get(sno) or {}
            return node.get("page_count")
        return None

    def pdf_sha256(self, sno, file_name):
        """PDF 模式下现场算哈希；非 PDF 模式返回 None。

        算不了（文件不在/路径是目录/读权限不够）一律记样本级错误并返回 None，
        绝不返回一个"看起来没问题"的值让上层当通过。
        """
        if self.mode != "pdf":
            return None
        if sno in self.pdf_sha:
            return self.pdf_sha[sno]
        path = self.pdf_dir / (file_name or "")
        if not file_name:
            self._sample_error(sno, "PDF 缺失：该行没有 file_name，无法计算哈希")
            self.pdf_sha[sno] = None
            return None
        if not path.exists():
            self._sample_error(
                sno, "PDF 缺失：%s 不在 %s（PDF 模式不做离线降级）"
                     % (file_name, self.pdf_dir))
            self.pdf_sha[sno] = None
            return None
        try:
            val = sha256_file(path)
        except Exception as e:
            self._sample_error(sno, "PDF 无法计算哈希：%s（%s: %s）"
                                    % (file_name, type(e).__name__, e))
            self.pdf_sha[sno] = None
            return None
        self.pdf_sha[sno] = val
        return val

    def suggest(self, sno, file_name, rx):
        """值不在本页时，扫描全文找它出现在哪几页。只有 PDF 模式能做。"""
        if self.mode != "pdf" or self.no_suggest:
            return []
        doc = self.open_doc(sno, file_name)
        if doc is None:
            return []
        hits = []
        for i in range(doc.page_count):
            if rx.search(collapse(doc.load_page(i).get_text("text") or "")):
                hits.append(i + 1)
            if len(hits) >= 6:
                break
        return hits

    def close(self):
        for d in self.docs.values():
            d.close()



# ---------------------------------------------------------------- 各项检查


FAMILY_RE = re.compile(r"\b([A-Z]{2,4}\d{2})/(\d{2})([A-Z0-9\-]*)")


def family_forms(text):
    """TI 封面的族名写法 CD54/74HCT574 还原成 CD74HCT574，供型号核对用。"""
    out = set()
    for m in FAMILY_RE.finditer(text):
        out.add((m.group(1)[:-2] + m.group(2) + m.group(3)).lower())
    return out


def check_name(name, ptext):
    """参数名核验：整串 → 去空白整串 → 逐词。

    三级都用字母/数字边界断言，不能只判子串：`Input volta` 是
    `...input voltage...` 的子串，只用 in 判断会让截断词混过去。
    """
    if not name:
        return "ERROR", "parameter_name 为空"
    coll = collapse(ptext).lower()
    flat = nos(ptext)

    def bounded(hay, needle):
        if not needle:
            return False
        pat = BOUND_L + re.escape(needle) + BOUND_R
        return re.search(pat, hay) is not None

    if bounded(coll, collapse(name).lower()):
        if "_" in name and " " not in name.strip():
            return "SUSPECT", "全大写带下划线，疑似引脚/条件名而不是参数名"
        return "OK", ""
    if bounded(flat, nos(name)):
        return "OK", "跨行断字，去空白后命中"

    tokens = [t for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9.%+/\-]*", name) if len(t) >= 3]
    if not tokens:
        return "SUSPECT", "名字太短，无法分词核对"
    missing = [t for t in tokens
               if not (bounded(coll, t.lower()) or bounded(flat, t.lower()))]
    if not missing:
        return "OK", "逐词命中（原串被排版拆开）"
    hit = len(tokens) - len(missing)
    ratio = hit / float(len(tokens))
    msg = "本页缺词: %s（%d/%d 词命中）" % (",".join(missing[:4]), hit, len(tokens))
    return ("SUSPECT" if ratio >= 0.6 else "ERROR"), msg


ADJ_NO_SYMBOL = "ACCEPTED_SOURCE_HAS_NO_SYMBOL"
ADJ_KNOWN = {ADJ_NO_SYMBOL}


def check_symbol(sym, ptext, adjudication=""):
    """符号核验。手册只印名字不印符号时，允许用人工裁定码放行——
    但要留痕：裁定码写进 CSV 的 human_adjudication 列，报告里单独列一节，
    这样"没查"和"查过、源头确实没有"能区分开。"""
    """符号核验。

    表格里符号和相邻单元格是"粘"在一起的（`VIH` 右边紧跟 `-0.02`），
    去空白后必然贴在字母/数字上，所以不能像参数名那样上边界断言；
    先按原样（带空格）判一次边界，再退回子串包含。
    """
    if not sym:
        adj = (adjudication or "").strip()
        if adj == ADJ_NO_SYMBOL:
            return "OK", ""
        return "SUSPECT", "symbol 为空且没有人工裁定（需填 human_adjudication）"
    s = nos(sym)
    if re.search(BOUND_L + re.escape(s) + BOUND_R, collapse(ptext).lower()):
        return "OK", ""
    if s and s in nos(ptext):
        return "OK", ""
    return "ERROR", "symbol=%s 在本页找不到" % sym


def check_unit(unit, ptext):
    """单位核验。

    先要"独立出现"（`V` 两侧不是字母数字），避免 `A` 混在 `mA`/`\u03bcA` 里也算命中；
    只作为更长串的一部分出现时降为 SUSPECT 而不是判错——表格里单位与相邻单元格粘连是常态。
    """
    if not unit:
        return "SUSPECT", "unit 为空"
    cands = [unify(unit), unify(unit).replace("\u00b0C", "oC"), unify(unit).replace("\u00b0C", "C")]
    coll = collapse(ptext).lower()
    flat = nos(ptext)
    for c in cands:
        n = nos(c)
        if re.search(BOUND_L + re.escape(n) + BOUND_R, coll):
            return "OK", ""
    for c in cands:
        n = nos(c)
        if n and n in flat:
            return "SUSPECT", "unit=%s 只作为更长串的一部分出现，请确认" % unit
    return "ERROR", "unit=%s 在本页找不到" % unit


def check_value(col, val, ptext_coll, pages, sno, file_name):
    """返回 (verdict, 说明, kind)。verdict: OK/SUSPECT/ERROR。"""
    kind, nums, raw = classify(val)
    if kind == "EMPTY":
        return "OK", "", kind

    if kind in ("FORMULA", "TEXT", "WITH_UNIT"):
        why = {"FORMULA": "是公式/表达式，不是数值",
               "TEXT": "是文字，不是数值",
               "WITH_UNIT": "数值里混了单位，应拆到 unit 列"}[kind]
        return "ERROR", "%s=%s %s" % (col, raw, why), kind

    if kind == "NUMBER":
        rx = num_pattern(nums[0])
        if rx and rx.search(ptext_coll):
            return "OK", "", kind
        where = pages.suggest(sno, file_name, rx) if rx else []
        if where:
            return "ERROR", "%s=%s 不在本页，出现在 p%s" % (col, raw, ",".join(map(str, where))), kind
        return "ERROR", "%s=%s 本页找不到（也没有别页命中）" % (col, raw), kind

    if kind == "PM":
        core = nums[0]
        body = num_body(core)
        # 写法一：页面上就是 ±2.5
        if re.search(r"[±]\s*" + body + r"0*(?![\d.])", ptext_coll):
            return "OK", "本页印作 ±%s" % core, kind
        # 写法二：分列成 +2.5 与 -2.5。两侧正负号都必须真的出现——
        # 只找到一个 -2.5 时，num_pattern 会从里面抠出 2.5 从而误判为"正数也在"，
        # 所以这里必须用带符号的正则，不能复用不限符号的 num_pattern。
        plus_rx = re.compile(r"(?<![\d.+])\+\s*" + body + r"0*(?![\d.])")
        minus_rx = re.compile(r"(?<![\d.])-\s*" + body + r"0*(?![\d.])")
        has_plus = plus_rx.search(ptext_coll) is not None
        has_minus = minus_rx.search(ptext_coll) is not None
        if has_plus and has_minus:
            return "OK", "本页以 +%s / -%s 分列印出" % (core, core), kind
        lack = []
        if not has_plus:
            lack.append("正号（+%s 或无符号的 %s）" % (core, core))
        if not has_minus:
            lack.append("负号（-%s）" % core)
        return ("ERROR", "%s=±%s 本页缺 %s，不能证明是正负对称" %
                (col, core, "、".join(lack)), kind)

    if kind == "RANGE":
        lo, hi = nums[0], nums[1]
        # 结构化匹配：必须是 "A to B" / "A ~ B" / "A ... B" / "A - B"（连字符要求两侧有空格，
        # 否则会和负数自身的负号混淆）。只验两个数字各自存在是不够的：
        # 表格里两列分别印 -0.5 和 7，也满足"两端点都在"，但那不是一个区间。
        # 端点和分隔符之间可能夹着单位（真实页面印的是 `-0.5V to 7V`），
        # 所以两端各允许一段短的单位尾巴，否则会把规范写法判成没有结构。
        unit_tail = r"(?:\s*[A-Za-z%\u00b0\u00b5\u03a9/]{1,6})?"
        sep = (r"(?:" + unit_tail + r"\s+(?:to|through)\s*"
               r"|\s*~\s*|\s*\.\.\.\s*"
               r"|" + unit_tail + r"\s+-\s+)")
        rx = re.compile(r"(?<![\d.])" + num_body(lo) + r"0*" + sep
                        + num_body(hi) + r"0*(?![\d.])")
        if rx.search(ptext_coll):
            return "OK", "本页以 A to B 结构印出", kind
        miss = [n for n in nums if not (num_pattern(n) and num_pattern(n).search(ptext_coll))]
        if miss:
            return "ERROR", "%s=%s 的端点本页找不到: %s" % (col, raw, ",".join(miss)), kind
        return ("ERROR", "%s=%s 两个端点都在页面上，但没有 'A to B' 这样的区间结构"
                "（可能分属两列或两行），不能证明是同一个区间" % (col, raw), kind)

    return "ERROR", "%s=%s 无法归类" % (col, raw), kind


def check_model(model, ptext1):
    if not model:
        return "SUSPECT", "device_model 为空"
    flat = nos(ptext1)
    if nos(model) in flat:
        return "OK", ""
    if nos(model) in family_forms(ptext1):
        return "OK", "封面以族名 CDxx/yy 形式印出"
    return "SUSPECT", "型号 %s 未在封面原文找到（可能只印族名或订购码）" % model


def load_provenance(path):
    """读 Batch2_PDF_PROVENANCE.csv，返回 {sample_no: row}。

    读不到就是 FatalInput，不再返回 None 让上层"优雅跳过"。
    缺了这张表，三处互校就只剩两处，而两处都是我们自己生成的——
    自己跟自己对账，对得再齐也证明不了什么。
    """
    if not path:
        raise FatalInput("没有指定 provenance 表路径")
    if not path.exists():
        raise FatalInput("溯源表不存在：%s（它是第三方参照，缺了就只能自己跟自己对账）"
                         % path)
    try:
        with open(path, encoding="utf-8-sig", newline="") as fh:
            table = {r["sample_no"]: r for r in csv.DictReader(fh)}
    except Exception as e:
        raise FatalInput("溯源表读不了：%s（%s: %s）" % (path, type(e).__name__, e))
    if not table:
        raise FatalInput("溯源表是空的：%s" % path)
    return table


def check_provenance(rows, pages, prov):
    """三处溯源必须一致。

    字段对应关系（v1.5 明确写死，别再"看情况跳过"）：

      * CSV ↔ sidecar：比 `file_name`、`device_model` 两项。
        CSV 没有 sha256 / page_count 列，这两项无从比，不是"不要求"，是"这一侧没有"。
      * sidecar ↔ provenance：比全部四项 `file_name`、`device_model`、`sha256`、`page_count`。

    判定口径统一为：**任一侧为空，或两侧都有但不相等，都是 ERROR**。
    空字段意味着这条溯源链断了，和"值不对"一样致命——v1.4 的
    `if a and b and a != b` 把"空"当成了"无所谓"，这是第 2 处 Fail-Open。
    """
    if prov is None:
        raise FatalInput("溯源表没有加载成功，拒绝出报告")

    issues, notes = {}, []
    side = pages.expected or {}
    if not side:
        raise FatalInput("page_text.json 里没有任何样本溯源条目，无法互校")
    csv_meta = {}
    for r in rows:
        csv_meta.setdefault(r["sample_no"], ((r.get("file_name") or "").strip(),
                                             (r.get("device_model") or "").strip()))

    def add(sno, msg):
        bucket = issues.setdefault(sno, [])
        if msg not in bucket:
            bucket.append(msg)

    for sno, (fname, model) in sorted(csv_meta.items()):
        node = side.get(sno)
        if not node:
            add(sno, "溯源缺失：page_text.json 里没有 %s 的条目" % sno)
            continue
        # CSV ↔ sidecar：只比 CSV 有的两列
        for key, csv_val in (("file_name", fname), ("device_model", model)):
            side_val = str(node.get(key) or "").strip()
            if not csv_val or not side_val or csv_val != side_val:
                add(sno, "溯源不一致/缺失：%s，CSV=%r ≠ sidecar=%r"
                    % (key, csv_val, side_val))

    # sidecar ↔ provenance：四项全比
    for sno, node in sorted(side.items()):
        pr = prov.get(sno)
        if not pr:
            add(sno, "溯源不一致：provenance 表缺 %s" % sno)
            continue
        for key in ("file_name", "device_model", "sha256", "page_count"):
            a = str(node.get(key) or "").strip()
            b = str(pr.get(key) or "").strip()
            if not a or not b or a != b:
                add(sno, "溯源不一致/缺失：%s 的 %s，sidecar=%r ≠ provenance=%r"
                    % (sno, key, a, b))
    for sno in prov:
        if sno not in side:
            add(sno, "溯源一致性问题：provenance 表有 %s，sidecar 没有对应条目" % sno)

    return issues, notes



# ---------------------------------------------------------------- 主流程


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(DEFAULT_CSV))
    ap.add_argument("--pdf-dir", default=None, help="PDF 目录；不给则按环境变量/同目录 pdfs 找")
    ap.add_argument("--page-text", default=str(SIDECAR), help="离线页文本 JSON（含溯源期望值）")
    ap.add_argument("--provenance", default=str(PROVENANCE),
                    help="PDF 溯源表（默认同目录 Batch2_PDF_PROVENANCE.csv）")
    ap.add_argument("--no-suggest", action="store_true")
    args = ap.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print("找不到标注文件: %s" % csv_path)
        return 2
    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        print("标注文件是空的（只有表头）。")
        return 0

    # PDF 目录从哪来，分"显式"和"自动探测"两种。
    # 显式给了却不可用 → 致命；自动探测没探到 → 只是没有 PDF，走离线。
    pdf_dir, pdf_explicit = None, False
    if args.pdf_dir:
        pdf_dir, pdf_explicit = Path(args.pdf_dir), True
    else:
        env = os.environ.get("ICPDF_PDF_DIR")
        if env:
            pdf_dir, pdf_explicit = Path(env), True
        elif (csv_path.parent / "pdfs").is_dir():
            pdf_dir = csv_path.parent / "pdfs"

    try:
        return _run(rows, csv_path, pdf_dir, pdf_explicit,
                    Path(args.page_text), Path(args.provenance), args.no_suggest)
    except FatalInput as e:
        print("=" * 78)
        print("[ERROR] 拒绝出报告：%s" % e)
        print("=" * 78)
        print("这是判据/环境层面的错误，不是某一行的数据问题。")
        print("继续跑只会产出一份看起来全绿、实际没有证据支撑的报告，所以直接退出（退出码 2）。")
        return 2


def _run(rows, csv_path, pdf_dir, pdf_explicit, sidecar_path, prov_path, no_suggest):
    pages = Pages(rows, pdf_dir, sidecar_path, no_suggest, pdf_explicit=pdf_explicit)
    if pages.fatal:
        pages.close()
        raise FatalInput("；".join(pages.fatal))

    # 先把"判据"验完，再打印任何模式提示——否则致命错误前面会先冒一句无关的提示，
    # 让人以为只是换了个数据源接着跑。
    prov = load_provenance(prov_path)
    prov_issues, prov_notes = check_provenance(rows, pages, prov)

    if pages.mode == "none":
        print("!! %s" % pages.error)
        print("   所有行将标 CANNOT_VERIFY。给 --pdf-dir 或把 page_text.json 放在本目录。")
    elif pages.error:
        print("提示: %s" % pages.error)
        print()

    # ---- F4：哈希不符的样本，整批判死，且不再读它的页文本
    hash_bad = set()
    if pages.mode == "pdf":
        for sno in sorted({(r.get("sample_no") or "").strip() for r in rows}):
            if not sno:
                continue
            node = (pages.expected or {}).get(sno) or {}
            want = str(node.get("sha256") or "").strip()
            fname = next((r.get("file_name") for r in rows
                          if (r.get("sample_no") or "").strip() == sno), None)
            if not want:
                prov_issues.setdefault(sno, []).append(
                    "溯源缺失：sidecar 里 %s 没有 sha256，无法验哈希" % sno)
                continue
            got = pages.pdf_sha256(sno, fname)
            if got is None:
                continue        # 具体原因已由 Pages 记进 sample_errors
            if got != want:
                hash_bad.add(sno)
                bucket = prov_issues.setdefault(sno, [])
                msg = ("PDF 哈希不符：磁盘文件 sha256=%s… ≠ 溯源期望=%s…"
                       "（文件被替换或改动过，该样本页内文字一律不采信）"
                       % (got[:16], want[:16]))
                if msg not in bucket:
                    bucket.append(msg)

    print("=" * 78)
    print("溯源一致性检查")
    print("=" * 78)
    print("  provenance 表：%d 个样本" % len(prov))
    print("  sidecar：%d 个样本" % len(pages.expected or {}))
    print("  字段对应：CSV↔sidecar 比 file_name/device_model；"
          "sidecar↔provenance 比 file_name/device_model/sha256/page_count")
    print("  判据：任一侧为空 或 两侧不等 → ERROR（空字段不再当作“跳过”）")
    print("  PDF 实算哈希：%s" % ("已比对" if pages.mode == "pdf" else "跳过（非 PDF 模式）"))
    if prov_issues:
        for sno in sorted(prov_issues):
            for m in prov_issues[sno]:
                print("  [ERROR] %s %s" % (sno, m))
    else:
        print("  结论：三处溯源一致")
    for m in prov_notes:
        print("  [提示] %s" % m)
    print()

    verdicts = []
    kinds = {}
    model_seen = {}
    seen = {}

    for idx, r in enumerate(rows, start=2):
        sno = (r.get("sample_no") or "").strip()
        problems, notes = [], []
        fname = (r.get("file_name") or "").strip()
        if sno in prov_issues:
            problems.extend(prov_issues[sno])

        if not sno or not fname:
            verdicts.append(("ERROR", idx, sno, ["sample_no 或 file_name 为空"]))
            continue

        # F4：哈希不符的样本，页内文字一律不采信。
        # 必须在 page_text() 之前短路——文件都不是溯源记录里的那一份了，
        # 再去核"这一页面上有没有这个数"，核得再对也没有意义。
        if sno in hash_bad:
            verdicts.append(("ERROR", idx, sno,
                             list(prov_issues.get(sno) or ["PDF 哈希不符"])))
            continue

        # F3：PDF 缺失/打不开/算不了哈希的样本，同样是整批 ERROR，不降级。
        if pages.sample_errors.get(sno):
            msgs = list(pages.sample_errors[sno])
            for m in prov_issues.get(sno, []):
                if m not in msgs:
                    msgs.append(m)
            verdicts.append(("ERROR", idx, sno, msgs))
            continue

        try:
            page = int(str(r.get("evidence_page") or "").strip())
        except ValueError:
            verdicts.append(("ERROR", idx, sno, ["evidence_page 不是整数"]))
            continue

        pc = pages.page_count(sno, fname)
        if pc and page > pc:
            verdicts.append(("ERROR", idx, sno,
                             ["evidence_page=%d 超出该 PDF 页数 %d" % (page, pc)]))
            continue

        ptext = pages.page_text(sno, fname, page)
        if ptext is None:
            verdicts.append(("CANNOT_VERIFY", idx, sno,
                             ["没有 p%d 的页文本（JSON 未收录或页号超出）" % page]))
            continue
        if len(collapse(ptext)) < 20:
            verdicts.append(("CANNOT_VERIFY", idx, sno,
                             ["第 %d 页抽不出文字（扫描件），需人工复看" % page]))
            continue

        ptext_coll = collapse(ptext)

        # 1) 参数名
        nv, nmsg = check_name((r.get("parameter_name") or "").strip(), ptext)
        if nmsg and nv != "OK":
            (problems if nv == "ERROR" else notes).append("参数名: " + nmsg)

        # 2) 符号（空符号可用人工裁定码放行）
        adj = (r.get("human_adjudication") or "").strip()
        if adj and adj not in ADJ_KNOWN:
            problems.append("human_adjudication=%s 不是已知裁定码（可选：%s）"
                            % (adj, ", ".join(sorted(ADJ_KNOWN))))
        sv, smsg = check_symbol((r.get("symbol") or "").strip(), ptext, adj)
        if smsg:
            (problems if sv == "ERROR" else notes).append(smsg)

        # 3) 单位
        uv, umsg = check_unit((r.get("unit") or "").strip(), ptext)
        if umsg:
            (problems if uv == "ERROR" else notes).append(umsg)

        # 4) 三个数值
        used = 0
        for col in ("min_value", "typ_value", "max_value"):
            val = (r.get(col) or "").strip()
            v, msg, kind = check_value(col, val, ptext_coll, pages, sno, fname)
            if kind != "EMPTY":
                used += 1
                kinds[kind] = kinds.get(kind, 0) + 1
            if msg and v != "OK":
                (problems if v == "ERROR" else notes).append(msg)
        if used == 0:
            rs = (r.get("row_status") or "").strip()
            if not rs.startswith(("UNRESOLVED", "EXCLUDED", "DRAFT")):
                problems.append("三个数值列全空，但 row_status 不是 UNRESOLVED/EXCLUDED/DRAFT")

        # 5) 型号（只在第 1 页核，逐样本核一次即可，但每行都记首见结论）
        model = (r.get("device_model") or "").strip()
        if "device_model" in r:
            if sno not in model_seen:
                p1 = pages.page_text(sno, fname, 1)
                model_seen[sno] = (model, check_model(model, p1) if p1 else
                                   ("SUSPECT", "没有封面页文本，型号无法核对"))
            mv, mmsg = model_seen[sno][1]
            if mmsg:
                (problems if mv == "ERROR" else notes).append("型号: " + mmsg)

        # 6) 行列错位启发式
        vals = [(r.get(c) or "").strip() for c in ("min_value", "typ_value", "max_value")]
        present = [v for v in vals if v]
        if len(present) == 1 and present[0] == str(page):
            notes.append("evidence_page 与唯一数值相同（%d），确认是否错位" % page)
        if re.fullmatch(r"[\d.]+", (r.get("unit") or "").strip()):
            problems.append("unit 列是纯数字，疑似列错位")
        if re.fullmatch(r"[\d.]+", (r.get("symbol") or "").strip()):
            problems.append("symbol 列是纯数字，疑似列错位")

        # 7) 状态与签名
        rs = (r.get("row_status") or "").strip()
        if not rs:
            problems.append("row_status 为空")
        elif rs.upper().startswith("CONFIRMED") and not (r.get("reviewer") or "").strip():
            problems.append("CONFIRMED 但没有 reviewer 签名")
        elif rs.startswith("UNRESOLVED") and len(rs) <= len("UNRESOLVED:"):
            problems.append("UNRESOLVED 必须写明原因")
        elif rs.startswith("EXCLUDED") and len(rs) <= len("EXCLUDED:"):
            problems.append("EXCLUDED 必须写明原因")

        # 8) 重复行：同样本+符号+条件+单位+页码+三个数值全同，视为重复占位
        dkey = (sno, r.get("symbol"), r.get("condition"), r.get("unit"),
                r.get("evidence_page"), r.get("min_value"),
                r.get("typ_value"), r.get("max_value"))
        if dkey in seen:
            notes.append("与第 %d 行完全重复" % seen[dkey])
        else:
            seen[dkey] = idx

        verdict = "ERROR" if problems else ("SUSPECT" if notes else "OK")
        verdicts.append((verdict, idx, sno, problems + notes))

    pages.close()

    order = {"ERROR": 0, "SUSPECT": 1, "CANNOT_VERIFY": 2, "OK": 3, "SKIP": 4}
    counts = {}
    for v, _, _, _ in verdicts:
        counts[v] = counts.get(v, 0) + 1

    print("=" * 78)
    print("标注机检 v%s  %s   行数 %d   样本 %d" % (VERSION, csv_path.name, len(rows),
                                              len({r.get("sample_no") for r in rows})))
    print("页文本来源: %s" % {"pdf": "PDF 原件", "json": "page_text.json",
                          "none": "无"}[pages.mode])
    print("=" * 78)
    for verdict, idx, sno, msgs in sorted(verdicts, key=lambda x: (order.get(x[0], 9), x[1])):
        if verdict == "OK" and not msgs:
            print("[OK      ] 行%-4d %-6s" % (idx, sno))
            continue
        print("[%-9s] 行%-4d %-6s" % (verdict, idx, sno))
        for m in msgs:
            print("            - %s" % m)

    adjudged = [(i, r) for i, r in enumerate(rows, start=2)
                if (r.get("human_adjudication") or "").strip()]
    if adjudged:
        print()
        print("人工裁定（human_adjudication）：")
        for i, r in adjudged:
            print("  行%-4d %-6s %-40s %s"
                  % (i, r.get("sample_no"), (r.get("parameter_name") or "")[:40],
                     r.get("human_adjudication")))

    print()
    if kinds:
        print("数值分类: " + "  ".join("%s=%d" % (KIND_LABEL.get(k, k), kinds[k])
                                   for k in ("NUMBER", "PM", "RANGE", "FORMULA",
                                             "WITH_UNIT", "TEXT") if k in kinds))
    print("统计: " + "  ".join("%s=%d" % (k, counts[k])
                             for k in ("OK", "SUSPECT", "ERROR", "CANNOT_VERIFY") if k in counts))
    if counts.get("ERROR"):
        print()
        print("有 ERROR，先修这些再谈 CONFIRMED。")
        return 1
    print()
    print("无 ERROR。SUSPECT 需人工再看一眼；CANNOT_VERIFY 缺页文本，只能人眼核。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
