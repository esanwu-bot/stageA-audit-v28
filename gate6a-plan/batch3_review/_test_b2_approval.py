# -*- coding: utf-8 -*-
"""B2 签名继承（Fail-Closed + 稳定 ID）回归测试。

上版漏洞：_make_b2_final.py 从「现有定稿」按**行号**读回 approved_by，
源不明确、表头/行数异常不报错、行一重排就串签。本测试用临时目录里
自造的 30 行 xlsx 覆盖以下场景，全部不依赖外部 PDF 或真实定稿，SKIP=0：

  1. 签名源不存在               → 退出
  2. 表头不符（19 列结构被改） → 退出
  3. 数据行数不是 30            → 退出
  4. 稳定 ID 重复               → 退出
  5. 出现非 PM 本人签名         → 退出
  6. 签名落在非 WB 代录入行     → 退出
  7. 定稿行在签名源中找不到 ID → 退出
  8. 正常 + 定稿行顺序打乱      → 7 处签名仍按稳定 ID 精确落位
  9. 稳定 ID 的九字段任一改变   → 不再匹配
"""
from __future__ import print_function

import random
import shutil
import sys
import tempfile
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _make_b2_final as M

SIGN_LINES = (8, 9, 16, 17, 18, 19, 20)   # 与真实封卷一致的 7 行
CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


def make_rows(n=30):
    rows = []
    for i in range(1, n + 1):
        r = dict((k, "") for k in M.FINAL_COLS)
        r["sample_no"] = "V%03d" % (i // 5 + 1)
        r["file_name"] = "sample_%02d.pdf" % i
        r["evidence_page"] = str(i % 7 + 1)
        r["symbol"] = "SYM%02d" % i
        r["parameter_name"] = "Parameter %02d" % i
        r["min_value"] = "%.2f" % (i * 0.1)   # 消歧字段，保证 30 行 ID 唯一
        r["unit"] = "V"
        r["row_status"] = "CONFIRMED"
        r["reviewer"] = M.REVIEWER
        r["entered_by"] = M.ENTERED_BY if i in SIGN_LINES else ""
        r["approved_by"] = M.REVIEWER if i in SIGN_LINES else ""
        rows.append(r)
    return rows


def write_xlsx(path, rows, hdr=None):
    hdr = list(hdr or M.FINAL_COLS)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(hdr)
    for r in rows:
        ws.append([r.get(k, "") for k in hdr])
    wb.save(str(path))


def expect_fail(fn, keyword):
    try:
        fn()
    except SystemExit as e:
        assert keyword in str(e), \
            "退出原因不含 %r：%r" % (keyword, str(e))
        return str(e)
    except Exception as e:
        raise AssertionError("应当以 SystemExit 退出，实际抛出 %s: %s"
                             % (type(e).__name__, e))
    raise AssertionError("没有 Fail-Closed 退出")


@case("Fail-Closed 1 唯一签名源不存在 → 直接退出")
def _c1_missing(tmp):
    expect_fail(lambda: M.load_approval_map(tmp / "no_such.xlsx"), "找不到")


@case("Fail-Closed 2 签名源表头不符（approved_by 被改名）→ 直接退出")
def _c2_header(tmp):
    hdr = list(M.FINAL_COLS)
    hdr[hdr.index("approved_by")] = "approved"
    p = tmp / "bad_header.xlsx"
    write_xlsx(p, make_rows(), hdr)
    expect_fail(lambda: M.load_approval_map(p), "表头不符")


@case("Fail-Closed 3 签名源数据行数 29（不是 30）→ 直接退出")
def _c3_rowcount(tmp):
    p = tmp / "bad_count.xlsx"
    write_xlsx(p, make_rows(29))
    expect_fail(lambda: M.load_approval_map(p), "行数异常")


@case("Fail-Closed 4 签名源出现重复稳定 ID → 直接退出")
def _c4_dup_id(tmp):
    rows = make_rows()
    # 把第 2 行的九字段全改成与第 1 行一致
    for k in M.STABLE_ID_FIELDS:
        rows[1][k] = rows[0][k]
    p = tmp / "dup.xlsx"
    write_xlsx(p, rows)
    expect_fail(lambda: M.load_approval_map(p), "重复稳定 ID")


@case("Fail-Closed 5 签名源出现非 PM 本人签名 → 直接退出")
def _c5_bad_signer(tmp):
    rows = make_rows()
    rows[7]["approved_by"] = "someone_else"
    p = tmp / "bad_signer.xlsx"
    write_xlsx(p, rows)
    expect_fail(lambda: M.load_approval_map(p), "非 PM")


@case("Fail-Closed 6 签名落在非 WB 代录入行 → 授权链不匹配，退出")
def _c6_wrong_row(tmp):
    rows = make_rows()
    rows[7]["approved_by"] = ""          # 原签名行清空
    rows[0]["approved_by"] = M.REVIEWER  # 挪到未代录入的第 1 行
    p = tmp / "wrong_row.xlsx"
    write_xlsx(p, rows)
    amap = M.load_approval_map(p)
    draft = [dict(r, approved_by="") for r in rows]
    expect_fail(lambda: M.apply_approval(draft, amap), "签名落点")


@case("Fail-Closed 7 定稿行在签名源中找不到对应稳定 ID → 退出")
def _c7_unknown_id(tmp):
    rows = make_rows()
    p = tmp / "ok.xlsx"
    write_xlsx(p, rows)
    amap = M.load_approval_map(p)
    draft = [dict(r, approved_by="") for r in rows]
    draft[3]["min_value"] = "99.99"     # 改掉消歧字段，ID 失真
    expect_fail(lambda: M.apply_approval(draft, amap), "找不到对应稳定 ID")


@case("正向 8 正常 + 定稿行顺序打乱 → 7 处签名仍按稳定 ID 精确落位")
def _c8_shuffled(tmp):
    rows = make_rows()
    p = tmp / "ok.xlsx"
    write_xlsx(p, rows)
    amap = M.load_approval_map(p)
    assert len(amap) == 30
    assert sum(1 for a in amap.values() if a) == 7
    draft = [dict(r, approved_by="") for r in rows]
    random.Random(20261112).shuffle(draft)
    M.apply_approval(draft, amap)
    got = [i for i, r in enumerate(draft, 1) if r["approved_by"]]
    wb = [i for i, r in enumerate(draft, 1)
          if r["entered_by"] == M.ENTERED_BY]
    assert got == wb and len(got) == 7, \
        "签名行与代录入行不一致：%s / %s" % (got, wb)
    want = set(M.stable_id(rows[i - 1]) for i in SIGN_LINES)
    assert set(M.stable_id(r) for r in draft if r["approved_by"]) == want, \
        "打乱后签名串到了别的行"


@case("正向 9 稳定 ID 九字段逐一把关（任一改变即不同）")
def _c9_id_fields(tmp):
    base = make_rows()[0]
    for k in M.STABLE_ID_FIELDS:
        r = dict(base)
        r[k] = str(r[k]) + "_X"
        assert M.stable_id(r) != M.stable_id(base), \
            "字段 %s 改变后稳定 ID 竟然没变" % k


def main():
    print("=" * 72)
    print("B2 签名继承 · Fail-Closed + 稳定 ID 回归测试")
    print("=" * 72)
    tmp = Path(tempfile.mkdtemp(prefix="b2_approval_"))
    n_pass = n_fail = n_skip = 0
    try:
        for name, fn in CASES:
            try:
                fn(tmp)
            except AssertionError as e:
                print("FAIL  %s\n        %s" % (name, e))
                n_fail += 1
            except Exception as e:
                print("FAIL  %s\n        %s: %s" % (name, type(e).__name__, e))
                n_fail += 1
            else:
                print("PASS  %s" % name)
                n_pass += 1
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)
    print("-" * 72)
    print("PASS=%d, FAIL=%d, SKIP=%d" % (n_pass, n_fail, n_skip))
    print("全部使用临时目录里的合成 xlsx，不依赖外部 PDF / 真实定稿，SKIP 必须为 0。")
    if n_fail or n_skip:
        print("结论：未通过")
        return 1
    print("结论：全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
