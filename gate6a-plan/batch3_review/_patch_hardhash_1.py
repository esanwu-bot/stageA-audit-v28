# -*- coding: utf-8 -*-
"""把封卷保护从「内容签名软比较」换成「硬哈希拦截」。

Reviewer 抓到的 Fail-Open：上一版 _wb_signature 只比对值/填充/列宽，于是
  · 只改数字格式（值不变、字节变）→ 判定"内容一致"→ 静默跳过；
  · 增删工作表（非活动表不在签名里）→ 同样被放过。
结果就是封卷件字节已经变了，生成器还报告"未改写"。

新规则（全部 Fail-Closed）：
  1. 文件不存在且已登记封卷 → SystemExit（不许凭生成器重造）
  2. 已登记但登记里没有哈希 → SystemExit
  3. 读不出哈希（损坏）→ SystemExit
  4. 哈希 ≠ 登记值 → SystemExit，绝不自动替换
  5. 哈希 = 登记值 → skip，保留原字节
  6. 未登记（本就不是封卷件）→ write，照常生成
"""
import pathlib

P = pathlib.Path(__file__).with_name("_make_b3_final.py")
s = P.read_text(encoding="utf-8")

# ------------------------------------------------------------ 1. 登记表 + 闸门
ANCHOR = 'APPROVAL_SRC = PREP / "Batch3_B3_FINAL_TO_SIGN.xlsx"'
NEW = '''APPROVAL_SRC = PREP / "Batch3_B3_FINAL_TO_SIGN.xlsx"

# 已封卷文件 → 冻结 SHA-256。这张表是封卷的唯一真源：
# 生成器只能"确认没变"，不能"改成别的"。要变更必须先人工改这张表。
SEALED_SHA = {
    "Batch3_B3_FINAL.csv":
        "b940e2e4802d505f69728cbf313f844392c073bd7e2b2c5a7a47d6e36e019b12",
    "Batch3_B3_FINAL.xlsx":
        "b437658dc8d2f8f39b4fdc44ea0b5fb233c1adf3dab72ec2df846c80f7f43035",
    "Batch3_B3_FINAL_TO_SIGN.xlsx":
        "306266374fa4535e20a650d458802d73af614d17663250798a40e6c11a1dc3c7",
    "page_text_batch3_b3.json":
        "fca6fe2f6a896bdb1f32db15be0f86f5a7c52e745193a6613c2d1254e2ff21c4",
}


def guard_sealed(path, registry=None):
    """封卷件写入闸门：'skip' = 保留原字节，'write' = 允许生成。

    任何「已登记封卷却对不上」的情况一律 SystemExit。这里刻意不再做
    内容层面的"看起来一样"比较 —— 那正是上一版被 Reviewer 判为 Fail-Open 的地方。
    """
    reg = SEALED_SHA if registry is None else registry
    name = path.name
    if name not in reg:
        return "write"          # 本就不是封卷件，正常生成
    want = reg[name]
    if not want:
        raise SystemExit("封卷登记缺哈希，拒绝默认放行：%s" % name)
    if not path.exists():
        raise SystemExit("封卷件缺失，不允许凭生成器重造：%s" % path)
    try:
        got = sha(path)
    except OSError as exc:
        raise SystemExit("封卷件无法读取，拒绝继续：%s（%s）" % (path, exc))
    if got != want:
        raise SystemExit(
            "封卷件字节与登记不一致，拒绝自动替换：%s\\n  登记 %s\\n  实际 %s"
            % (path, want, got))
    return "skip"'''
assert s.count(ANCHOR) == 1
s = s.replace(ANCHOR, NEW, 1)

# ------------------------------------------------------------ 2. 删掉软比较函数
start = s.index("def _wb_signature(path):")
end = s.index('def write_xlsx(path, rows, sheet')
removed = s[start:end]
assert "_wb_signature" in removed and len(removed) < 2000, len(removed)
s = s[:start] + s[end:]

# ------------------------------------------------------------ 3. write_xlsx 改闸门
OLD_X = '''    tmp = path.with_name(path.name + ".wb_tmp.xlsx")
    wb.save(str(tmp))
    # 幂等保护：要写的内容与磁盘现件逐格一致时，保留原字节、不重写。
    # openpyxl 每次 save 都会刷新 docProps/core.xml 的 dcterms:modified，
    # 会让封卷件的整包 SHA-256 无意义漂移（数据其实一字未改）。
    if path.exists():
        try:
            if _wb_signature(tmp) == _wb_signature(path):
                tmp.unlink()
                return "未改写（内容与磁盘一致，保留原字节）"
        except (OSError, ValueError, KeyError):
            pass
    atomic_replace(tmp, path)
    return "已改写"'''
NEW_X = '''    tmp = path.with_name(path.name + ".wb_tmp.xlsx")
    wb.save(str(tmp))
    atomic_replace(tmp, path)
    return "已改写"'''
assert s.count(OLD_X) == 1
s = s.replace(OLD_X, NEW_X, 1)

# write_xlsx 开头先过闸门
OLD_X2 = '''def write_xlsx(path, rows, sheet, highlights=None, head_color="2F5597"):
    """写 19 列定稿表；highlights={(行号, 列名): 颜色}，行号从 1 起（数据行）。"""
    wb = openpyxl.Workbook()'''
NEW_X2 = '''def write_xlsx(path, rows, sheet, highlights=None, head_color="2F5597"):
    """写 19 列定稿表；highlights={(行号, 列名): 颜色}，行号从 1 起（数据行）。

    已封卷的目标先过硬哈希闸门：要么原字节不动，要么直接退出，没有第三种可能。
    """
    state = guard_sealed(path)
    if state == "skip":
        return "未改写（封卷件哈希与登记一致，保留原字节）"
    wb = openpyxl.Workbook()'''
assert s.count(OLD_X2) == 1
s = s.replace(OLD_X2, NEW_X2, 1)

P.write_bytes(s.encode("utf-8"))
print("step3 ok, lines=%d" % s.count("\n"))
