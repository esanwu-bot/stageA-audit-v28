# -*- coding: utf-8 -*-
"""B4 定稿生成器第二轮修订（P0-1 / P0-2）。

四处改动：

1. **签字源入口闸门**（P0-2）：`main()` 在读 `Batch3_B4_ANNOTATED.xlsx` 之前
   先过 `B3.guard_sealed(SIGNED, SEALED_SHA_B4)`。哈希与登记不符、登记缺哈希、
   文件缺失、文件读不出 —— 一律 `SystemExit`，绝不继续。
2. **condition 按符号块回填**（P0-1）：签字件里 V130 五行 condition 为空，
   按原图 TEST CONDITIONS 逐字回填；回填只发生在「该符号块整块为空」时，
   部分有值部分为空一律 `SystemExit`，不按顺序盲填。
3. **回填留痕**：回填行 `entered_by=WB_Agent`，notes 前置
   `【condition 由 WB 按原图补录，待 PM 复核】` —— 不冒充 PM 已核。
4. **撤销 FINAL 三件的封卷登记**：条件尚未经 PM 复核，不能按已签内容登记哈希。
   签字源仍登记（它一变就必须停）。等 PM 补签后再重新登记。
"""
import pathlib

P = pathlib.Path(__file__).with_name("_make_b4_final.py")
s = P.read_text(encoding="utf-8")

# ---------------------------------------------------------------- 1. 引入回填表
OLD_IMP = "import _make_b3_final as B3"
NEW_IMP = """import _make_b3_final as B3
from _build_batch3_interactive import CONDITION_BACKFILL, MUST_HAVE_COND"""
assert s.count(OLD_IMP) == 1
s = s.replace(OLD_IMP, NEW_IMP, 1)

# ---------------------------------------------------------------- 2. 撤销封卷登记
OLD_SEAL = '''# 本轮封卷登记。首次生成时为空 -> guard 返回 write；生成后把哈希填进来再跑一次，
# 必须全部 skip。之后任何字节变化都会被拦下。
SEALED_SHA_B4 = {
    "Batch3_B4_FINAL.csv":
        "2db19c9753f053dda83f4a110fc7099e55797fb22738c3f91b66e03c5c0f551d",
    "Batch3_B4_FINAL.xlsx":
        "972b23f79408da8a568409204db7f25f2ee595e08ef3fc8b602a6cfb6aea86c1",
    "page_text_batch3_b4.json":
        "43e42b3c831b2fcf1df5bb94eb0ca4332937e5af84d6976d671f981315f59aef",
    "Batch3_B4_ANNOTATED.xlsx":
        "cc1b2ae030ee93cecce22e42a9edbbd8888aa514b67c7573d7ca111427cbc7b2",
}'''
NEW_SEAL = '''# 第二轮修订：V130 的 5 条 condition 由 WB 按原图补录，尚未经 PM 复核，
# 因此 FINAL 三件**暂不登记**封卷哈希（上一轮的登记已撤销），等补签后再登记。
# 签字源仍然登记 —— 它一变就必须停下来，不许拿被改过的签字件往下跑。
SEALED_SHA_B4 = {
    "Batch3_B4_ANNOTATED.xlsx":
        "cc1b2ae030ee93cecce22e42a9edbbd8888aa514b67c7573d7ca111427cbc7b2",
}
# 上一轮登记过、本轮主动撤销的三件：留档备查，不再作为放行依据。
NO_LONGER_SEALED = {
    "Batch3_B4_FINAL.csv":
        "2db19c9753f053dda83f4a110fc7099e55797fb22738c3f91b66e03c5c0f551d",
    "Batch3_B4_FINAL.xlsx":
        "972b23f79408da8a568409204db7f25f2ee595e08ef3fc8b602a6cfb6aea86c1",
    "page_text_batch3_b4.json":
        "43e42b3c831b2fcf1df5bb94eb0ca4332937e5af84d6976d671f981315f59aef",
}'''
assert s.count(OLD_SEAL) == 1
s = s.replace(OLD_SEAL, NEW_SEAL, 1)

# ---------------------------------------------------------------- 3. 常量与回填
OLD_NOTE = 'FINAL_NOTE = "人工已核对 PDF 原图并确认"'
NEW_NOTE = ('FINAL_NOTE = "人工已核对 PDF 原图并确认"\n'
            'WB_FILL_PREFIX = "【condition 由 WB 按原图补录，待 PM 复核】"')
assert s.count(OLD_NOTE) == 1
s = s.replace(OLD_NOTE, NEW_NOTE, 1)

OLD_CLEAN = '''def clean_notes(notes):'''
NEW_CLEAN = '''def fill_missing_conditions(rows):
    """签字件里 condition 为空的行，按原图 TEST CONDITIONS 回填。

    粒度是「符号块」而非「整件」：同一样本里 V290 的 VIL 有温度档、
    II / VIH 原表本来就没给测试条件，不能因为整件里有一块空就一律判定失败。

    三条 Fail-Closed：
      · 同一符号块里部分有值、部分为空 → 不猜顺序，直接退出；
      · 回填表条数与实际行数不符 → 退出（不按顺序盲配）；
      · 回填后 MUST_HAVE_COND 规定的符号仍缺 condition → 退出。
        P0：没有测试条件的电气参数不能进 Gold。
    """
    filled_cnt = 0
    for sno in SAMPLES:
        here = [r for r in rows if r["sample_no"] == sno]
        if not here:
            continue
        for (bsno, page, sym), conds in CONDITION_BACKFILL.items():
            if bsno != sno:
                continue
            hit = [r for r in here
                   if str(r["evidence_page"]) == page
                   and (r["symbol"] or "").strip() == sym]
            if not hit:
                continue
            has = [r for r in hit if (r["condition"] or "").strip()]
            if len(has) == len(hit):
                continue                      # PM 已填，原样保留，不覆盖
            if has:
                raise SystemExit(
                    "%s p%s %s 的 condition 部分有值（%d/%d），"
                    "拒绝按顺序盲填" % (sno, page, sym, len(has), len(hit)))
            if len(hit) != len(conds):
                raise SystemExit(
                    "%s p%s %s 保留 %d 行，与回填表 %d 条不一致，拒绝盲配"
                    % (sno, page, sym, len(hit), len(conds)))
            for r, c in zip(hit, conds):
                r["condition"] = c
                r["entered_by"] = "WB_Agent"
                r["notes"] = WB_FILL_PREFIX + r["notes"]
                filled_cnt += 1

    for sno, syms in MUST_HAVE_COND.items():
        here = [r for r in rows if r["sample_no"] == sno]
        if not here:
            continue
        lack = [(r["symbol"], r["condition"]) for r in here
                if r["symbol"].strip() in syms
                and not (r["condition"] or "").strip()]
        if lack:
            raise SystemExit(
                "FAIL %s 条件缺失：%s 没有 TEST CONDITIONS，拒绝出定稿"
                % (sno, [x[0] for x in lack]))
        had = {r["symbol"].strip() for r in here}
        miss = sorted(syms - had)
        if miss:
            raise SystemExit("FAIL %s 缺少必需符号：%s" % (sno, miss))
    print("  condition 回填：%d 格（标 entered_by=WB_Agent，待 PM 复核）"
          % filled_cnt)
    return rows


def clean_notes(notes):'''
assert s.count(OLD_CLEAN) == 1
s = s.replace(OLD_CLEAN, NEW_CLEAN, 1)

# ---------------------------------------------------------------- 4. TO_SIGN 导出
OLD_PROV = '''def write_prov(path, side):'''
NEW_PROV = '''TO_SIGN = HERE / "Batch3_B4_DRAFT_TO_SIGN.xlsx"


def write_to_sign(path, rows):
    """导出 15 列签字表，供 PM 在带 condition 的版本上重新签字。

    只在文件不存在时写：PM 一旦签过就保存成这个文件，重跑不许覆盖签名。
    """
    if path.exists():
        print("  TO_SIGN 已存在，保留原字节（避免覆盖 PM 已签内容）：%s" % path.name)
        return "未改写"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "B4_TO_SIGN"
    ws.append(SIGNED_COLS)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="C00000")
        c.alignment = Alignment(horizontal="center")
    for r in rows:
        ws.append([r.get(k, "") for k in SIGNED_COLS])
    for ci, k in enumerate(SIGNED_COLS, 1):
        width = {"parameter_name": 46, "notes": 40, "file_name": 34,
                 "condition": 32, "table_title": 28, "row_status": 14}.get(k, 14)
        ws.column_dimensions[get_column_letter(ci)].width = width
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    tmp = path.with_name(path.name + ".wb_tmp.xlsx")
    wb.save(str(tmp))
    B3.atomic_replace(tmp, path)
    return "已改写"


def write_prov(path, side):'''
assert s.count(OLD_PROV) == 1
s = s.replace(OLD_PROV, NEW_PROV, 1)

# ---------------------------------------------------------------- 5. main 闸门
OLD_MAIN = '''def main():
    if not SIGNED.exists():
        raise SystemExit("找不到签字件：%s" % SIGNED)
    signed_sha = B3.sha(SIGNED)'''
NEW_MAIN = '''def main():
    # 签字源入口闸门：先验哈希，再读内容。被改过就直接停，绝不允许继续。
    try:
        B3.guard_sealed(SIGNED, SEALED_SHA_B4)
    except SystemExit as exc:
        raise SystemExit("签字源校验失败，拒绝继续：%s" % exc)
    if not SIGNED.exists():
        raise SystemExit("找不到签字件：%s" % SIGNED)
    signed_sha = B3.sha(SIGNED)'''
assert s.count(OLD_MAIN) == 1
s = s.replace(OLD_MAIN, NEW_MAIN, 1)

OLD_BUILD = '''    rows, side = build_rows(rows_signed, work)
'''
NEW_BUILD = '''    rows, side = build_rows(rows_signed, work)
    rows = fill_missing_conditions(rows)
'''
assert s.count(OLD_BUILD) == 1
s = s.replace(OLD_BUILD, NEW_BUILD, 1)

# ---------------------------------------------------------------- 6. 落盘后断言
OLD_ASSERT = '''    for r in csv2:
        if not r["notes"].endswith(FINAL_NOTE) or "VLM" in r["notes"]:
            raise SystemExit("notes 未清理干净：%s %r" % (r["sample_no"], r["notes"]))
        if not r["device_model"]:
            raise SystemExit("device_model 为空：%s" % r["sample_no"])'''
NEW_ASSERT = '''    for r in csv2:
        if not r["notes"].endswith(FINAL_NOTE) or "VLM" in r["notes"]:
            raise SystemExit("notes 未清理干净：%s %r" % (r["sample_no"], r["notes"]))
        if not r["device_model"]:
            raise SystemExit("device_model 为空：%s" % r["sample_no"])

    # P0-1 硬断言：MUST_HAVE_COND 的符号落盘后必须有 condition，且与回填表逐字一致。
    for sno, syms in MUST_HAVE_COND.items():
        got = [r for r in csv2 if r["sample_no"] == sno]
        lack = [r["symbol"] for r in got
                if r["symbol"].strip() in syms and not r["condition"].strip()]
        if lack:
            raise SystemExit("落盘后 %s 仍缺 condition：%s" % (sno, lack))
        for (bsno, page, sym), conds in CONDITION_BACKFILL.items():
            if bsno != sno:
                continue
            hit = [r for r in got
                   if r["evidence_page"] == page and r["symbol"].strip() == sym]
            if not hit:
                continue
            if [r["condition"] for r in hit] != conds:
                raise SystemExit(
                    "落盘后 %s %s 的 condition 与回填表不一致：%s"
                    % (sno, sym, [r["condition"] for r in hit]))
            wb_marks = [r["entered_by"] for r in hit]
            if any(w != "WB_Agent" for w in wb_marks):
                raise SystemExit(
                    "落盘后 %s %s 的 entered_by 未标 WB_Agent：%s"
                    % (sno, sym, wb_marks))
            if any(not r["notes"].startswith(WB_FILL_PREFIX) for r in hit):
                raise SystemExit(
                    "落盘后 %s %s 的 notes 缺补录前缀" % (sno, sym))
'''
assert s.count(OLD_ASSERT) == 1
s = s.replace(OLD_ASSERT, NEW_ASSERT, 1)

OLD_TAIL = '''    s_csv = write_csv(OUT_CSV, rows)'''
NEW_TAIL = '''    s_sign = write_to_sign(TO_SIGN, rows)
    s_csv = write_csv(OUT_CSV, rows)'''
assert s.count(OLD_TAIL) == 1
s = s.replace(OLD_TAIL, NEW_TAIL, 1)

OLD_PRINT = '''    print("  CSV 写入：%s" % s_csv)'''
NEW_PRINT = '''    print("  TO_SIGN 写入：%s" % s_sign)
    print("  CSV 写入：%s" % s_csv)'''
assert s.count(OLD_PRINT) == 1
s = s.replace(OLD_PRINT, NEW_PRINT, 1)

P.write_bytes(s.encode("utf-8"))
print("ok lines", s.count("\n"))
