# -*- coding: utf-8 -*-
"""把 CSV 与 sidecar 的软比较也换成硬哈希闸门。"""
import pathlib

P = pathlib.Path(__file__).with_name("_make_b3_final.py")
s = P.read_text(encoding="utf-8")

# ---------------------------------------------------------------- CSV
OLD_CSV = '''    tmp_csv = OUT_CSV.with_name(OUT_CSV.name + ".wb_tmp")
    with open(tmp_csv, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FINAL_COLS)
        w.writeheader()
        w.writerows(rows)
    atomic_replace(tmp_csv, OUT_CSV)'''
NEW_CSV = '''    csv_state = guard_sealed(OUT_CSV)
    if csv_state == "skip":
        csv_state = "未改写（封卷件哈希与登记一致，保留原字节）"
    else:
        tmp_csv = OUT_CSV.with_name(OUT_CSV.name + ".wb_tmp")
        with open(tmp_csv, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FINAL_COLS)
            w.writeheader()
            w.writerows(rows)
        atomic_replace(tmp_csv, OUT_CSV)
        csv_state = "已改写"'''
assert s.count(OLD_CSV) == 1
s = s.replace(OLD_CSV, NEW_CSV, 1)

# ---------------------------------------------------------------- sidecar
start = s.index('    # 幂等保护：例外字段只有 generated_at。')
end = s.index('    xlsx_state = write_xlsx(')
OLD_SIDE = s[start:end]
assert "side_same" in OLD_SIDE and len(OLD_SIDE) < 1200
NEW_SIDE = '''    # sidecar 同样是封卷件：软比较（只忽略 generated_at）等于又留一个 Fail-Open，
    # 改成硬哈希闸门 —— 要么字节与登记一致原地不动，要么直接退出。
    side_state = guard_sealed(OUT_SIDE)
    if side_state == "skip":
        side_state = "未改写（封卷件哈希与登记一致，保留原字节）"
    else:
        tmp_side = OUT_SIDE.with_name(OUT_SIDE.name + ".wb_tmp")
        tmp_side.write_text(side_text, encoding="utf-8", newline="\\n")
        atomic_replace(tmp_side, OUT_SIDE)
        side_state = "已改写"

'''
s = s[:start] + NEW_SIDE + s[end:]

# ---------------------------------------------------------------- 打印
OLD_P = '''    print("  xlsx 写入：%s" % xlsx_state)'''
NEW_P = '''    print("  CSV 写入：%s" % csv_state)
    print("  xlsx 写入：%s" % xlsx_state)
    print("  sidecar 写入：%s" % side_state)'''
assert s.count(OLD_P) == 1
s = s.replace(OLD_P, NEW_P, 1)

P.write_bytes(s.encode("utf-8"))
print("ok lines=%d crlf=%d" % (s.count("\n"), s.encode("utf-8").count(b"\r\n")))
