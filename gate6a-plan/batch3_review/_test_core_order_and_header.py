# -*- coding: utf-8 -*-
"""CORE_ORDER 供电符号正则 + prescan3 表头结构判据的回归测试。

Reviewer 2026-11-12 指出的两个通用漏洞：
  1. `^v(cc|dd|s)\\b|\\bv(cc|dd)\\b` 里的 `\\b` 挡住了带后缀的供电符号
     （VDD_CORE / VDDR_CORE / VDDSHV5），它们会被判成 pri=99 的非核心参数，
     在 pick_core() 里被整行丢掉。
  2. prescan3() 只数「页面出现 >=2 个 MIN/TYP/MAX/NOM」，正文里反复提
     minimum / maximum 也会被当成参数表，属于 Fail-Open。

本测试**全部用内存对象与合成 PDF 页**，不依赖任何外部 PDF 或环境变量，
因此不存在 SKIP：跑不全就是 FAIL，退出码非零。
"""
from __future__ import print_function

import sys
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _build_batch3_interactive as I3

CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


def row(symbol, name="", minv="0.8"):
    """构造一行：parameter_name 故意留空，只让符号去命中供电正则。"""
    return {"parameter_name": name, "symbol": symbol,
            "min_value": minv, "typ_value": "", "max_value": "",
            "unit": "V", "condition": "", "confidence_score": "0.90"}


def pdf_page(lines):
    """合成一页只有文本层、没有表格边框的 PDF。"""
    doc = fitz.open()
    pg = doc.new_page()
    y = 72.0
    for ln in lines:
        pg.insert_text((72.0, y), ln, fontsize=9)
        y += 14.0
    return doc


REAL_HEADER_AMR = [
    "6.1 Absolute Maximum Ratings",
    "over operating free-air temperature range",
    "PARAMETER", "MIN", "MAX", "UNIT",
    "VDD_CORE", "Core supply", "-0.3", "1.05", "V",
]

REAL_HEADER_ROC = [
    "6.4 Recommended Operating Conditions",
    "SUPPLY NAME", "DESCRIPTION", "MIN(1)", "NOM", "MAX(1)", "UNIT",
    "VDD_CORE", "Core supply", "0.81", "0.85", "0.895", "V",
]

# 正文里 MIN/MAX/TYP/NOM 出现很多次，也带表标题词，但没有任何表头结构。
PROSE_ONLY = [
    "6.1 Absolute Maximum Ratings",
    "The MIN value and the MAX value must both be observed in this section.",
    "MIN is the lower bound; MAX is the upper bound of the operating range.",
    "TYP and NOM are typical ratings, not MIN or MAX limits.",
    "Stresses beyond those listed under Absolute Maximum Ratings may cause damage.",
    "Refer to the Recommended Operating Conditions for MIN and MAX limits.",
]


# —— 正向：5 个被点名的符号，只靠 symbol 也要判成核心供电 ——
def _positive(sym):
    def _t():
        r = row(sym)
        pri = I3.core_rank(r)[0]
        assert pri == 1, "%s 的优先级应为 1（供电），实际 %d" % (sym, pri)
        keep, drop, _ = I3.pick_core([r])
        assert keep and keep[0] is r, "%s 被 pick_core 丢掉了" % sym
        assert not drop, "%s 不该产生 dropped 行" % sym
    return _t


for _sym in ("VDD_CORE", "VDDR_CORE", "VDDSHV5", "VCC", "VDD"):
    case("正向 供电符号 %-10s → pri=1 且被 pick_core 保留" % _sym)(_positive(_sym))


@case("正向 带前缀的供电符号 AVDD3V / DVDD / IOVDD 同样命中")
def _prefixed():
    for s in ("AVDD3V", "DVDD", "IOVDD"):
        assert I3.core_rank(row(s))[0] == 1, "%s 未命中" % s


@case("正向 参数名里的 Supply voltage range 仍能命中（不依赖符号）")
def _by_name():
    assert I3.core_rank(row("VA19", "Supply voltage range"))[0] == 1
    assert I3.core_rank(row("VFUSE", "Power-supply voltage"))[0] == 1


@case("反向 非供电的术语条目不得被放宽的正则误判为核心")
def _not_core():
    for s in ("PULL UP/DOWN TYPE", "BUFFER TYPE", "MUX MODE AFTER RESET"):
        assert I3.core_rank(row(s))[0] == 99, "%s 被误判为核心" % s


# —— 表头结构：正向真表头 ——
@case("正向表头 AMR 型（PARAMETER / MIN / MAX / UNIT）识别为表头")
def _hdr_amr():
    assert I3.has_table_header("\n".join(REAL_HEADER_AMR)) is True


@case("正向表头 ROC 型（MIN(1) / NOM / MAX(1) / UNIT）识别为表头")
def _hdr_roc():
    assert I3.has_table_header("\n".join(REAL_HEADER_ROC)) is True


@case("反向表头 只有 1 个独立列词行时不放行")
def _hdr_single():
    assert I3.has_table_header("MIN\nUNIT\nsome other text") is False


@case("反向表头 含多个 MIN/MAX 词汇的纯正文不识别为表头")
def _hdr_prose():
    assert I3.has_table_header("\n".join(PROSE_ONLY)) is False


# —— prescan3：合成整页，验证不会误放行 ——
@case("反向整页 纯正文（含多组 MIN/MAX + 表标题词）不进候选页")
def _prescan_prose():
    doc = pdf_page(PROSE_ONLY)
    got = I3.prescan3(doc, doc.page_count)
    assert got == [], "正文被误放行：%s" % got


@case("正向整页 真 AMR 表头页进候选页")
def _prescan_amr():
    doc = pdf_page(REAL_HEADER_AMR)
    assert I3.prescan3(doc, doc.page_count) == [1]


@case("正向整页 真 ROC 表头页进候选页")
def _prescan_roc():
    doc = pdf_page(REAL_HEADER_ROC)
    assert I3.prescan3(doc, doc.page_count) == [1]


@case("反向整页 p14 式术语解释页（无 MIN/MAX 表头）不进候选页")
def _prescan_terms():
    lines = [
        "5 Pin Configuration and Functions",
        "13. PULL UP/DOWN TYPE: Indicates the presence of an internal pull-up.",
        "For more information, see the hysteresis values in Electrical Characteristics.",
        "PU: Internal pull-up", "PD: Internal pull-down",
        "For electrical characteristics, refer to the appropriate buffer type table.",
    ]
    doc = pdf_page(lines)
    assert I3.prescan3(doc, doc.page_count) == []


@case("回归 温度/电流符号不再被 ^ 锚漏判（TA/Tstg/TJ/IO/II）")
def _symbol_anchors():
    for s, want in (("TA", 2), ("Tstg", 3), ("TJ", 4), ("IO", 5), ("II", 6)):
        pri = I3.core_rank(row(s))[0]
        assert pri == want, "%s 优先级应为 %d，实际 %d" % (s, want, pri)


@case("回归 V003 的 VDD_CORE/VDDR_CORE/VDDSHV5/TJ 全部仍为核心参数")
def _v003_symbols():
    for s in ("VDD_CORE", "VDDR_CORE", "VDDSHV5"):
        assert I3.core_rank(row(s))[0] == 1, "%s 应是核心供电" % s
    assert I3.core_rank(row("TJ"))[0] == 4, "TJ 应是结温（优先级 4）"


def main():
    print("=" * 72)
    print("CORE_ORDER 正则 + prescan3 表头结构判据 · 回归测试")
    print("=" * 72)
    n_pass = n_fail = n_skip = 0
    for name, fn in CASES:
        try:
            fn()
        except AssertionError as e:
            print("FAIL  %s\n        %s" % (name, e))
            n_fail += 1
        except Exception as e:
            print("FAIL  %s\n        %s: %s" % (name, type(e).__name__, e))
            n_fail += 1
        else:
            print("PASS  %s" % name)
            n_pass += 1
    print("-" * 72)
    print("PASS=%d, FAIL=%d, SKIP=%d" % (n_pass, n_fail, n_skip))
    print("测试全部使用内存对象 / 合成 PDF 页，不依赖外部 PDF，故 SKIP 必须为 0。")
    if n_fail or n_skip:
        print("结论：未通过")
        return 1
    print("结论：全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
