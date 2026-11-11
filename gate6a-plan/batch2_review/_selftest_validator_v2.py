# -*- coding: utf-8 -*-
"""validate_annotation.py 自测：喂 14 行故意做坏的标注，看脚本判得对不对。

为什么要自测
------------
机检脚本最怕"全都 OK"——那可能是检查根本没生效。这里每一行都埋一个已知的错，
只改必要字段，其余沿用真 Gold 行，保证不是构造出来的假场景。

期望值与实测值不一致就退出码 1，适合放进 CI 或提交前手动跑一遍。
"""
import csv
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOLD = HERE / "Batch2_GOLD_v1.csv"
SCRIPT = HERE / "validate_annotation.py"

# (说明, 样本, 页码, 覆盖字段, 期望判定)
CASES = [
    ("原样 Gold 行（V101 VIH 1.5V @2V）", "V101", 3, {}, "OK"),
    ("参数名被截断成残词 volta", "V101", 3,
     {"parameter_name": "High Level Input volta"}, "SUSPECT"),
    ("把条件当参数名 VNEG_IN_x", "V145", 12,
     {"parameter_name": "VNEG_IN_x", "symbol": "VNEG_IN_x"}, "SUSPECT"),
    ("数值写公式 VCC-0.2", "V101", 3, {"min_value": "VCC-0.2"}, "ERROR"),
    ("数值写 MIN(2.1, AVDD+0.3)", "V101", 3, {"min_value": "MIN(2.1, AVDD+0.3)"}, "ERROR"),
    ("数值写 Continuous", "V101", 3, {"min_value": "Continuous"}, "ERROR"),
    ("数值混单位 0.5V", "V101", 3, {"min_value": "0.5V"}, "ERROR"),
    ("正负值 ±2.5（应识别为 PM 并命中）", "V097", 3,
     {"min_value": "", "typ_value": "±2.5", "max_value": ""}, "OK"),
    ("范围 -0.5 to 7（应识别两端点）", "V101", 3,
     {"min_value": "-0.5 to 7", "max_value": ""}, "OK"),
    ("值 5.9 填错页（p1 是封面）", "V101", 1,
     {"min_value": "5.9", "max_value": ""}, "ERROR"),
    ("整行与第 2 行完全重复", "V101", 3, {}, "SUSPECT"),
    ("CONFIRMED 却没签名", "V101", 3, {"reviewer": ""}, "ERROR"),
    ("单位写成页面上没有的 dBm", "V101", 3, {"unit": "dBm"}, "ERROR"),
    ("型号写成不存在的 ADC9999", "V349", 5,
     {"device_model": "ADC9999"}, "SUSPECT"),
]


def load_base():
    with open(GOLD, encoding="utf-8-sig", newline="") as fh:
        rd = csv.DictReader(fh)
        cols = rd.fieldnames
        rows = list(rd)
    first = {}
    for r in rows:
        first.setdefault(r["sample_no"], r)
    return cols, first


def main():
    cols, base = load_base()
    test_rows = []
    for i, (name, sno, page, patch, _) in enumerate(CASES, start=1):
        r = dict(base[sno])
        r["evidence_page"] = str(page)
        r.update(patch)
        # 除"重复行"用例外，给 condition 加唯一后缀，免得每行都被判成上一行的重复
        if "重复" in name:
            r = dict(test_rows[0])          # 与第 1 个用例完全一致，才叫重复
        else:
            r["condition"] = (r.get("condition") or "") + " #case%d" % i
        test_rows.append(r)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "selftest.csv"
        with open(tmp, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
            w.writeheader()
            w.writerows(test_rows)

        proc = subprocess.run([sys.executable, str(SCRIPT), "--csv", str(tmp)],
                              capture_output=True, text=True, encoding="utf-8")
    out = (proc.stdout or "") + (proc.stderr or "")
    got = {}
    for line in out.splitlines():
        m = re.match(r"\[(\w+)\s*\] 行(\d+)", line)
        if m:
            got[int(m.group(2))] = m.group(1)

    print("=" * 88)
    print("%-44s %-8s %-8s %s" % ("用例", "期望", "实测", "结果"))
    print("=" * 88)
    bad = 0
    for i, (name, _sno, _p, _patch, want) in enumerate(CASES, start=2):
        have = got.get(i, "缺失")
        ok = have == want
        bad += 0 if ok else 1
        print("%-44s %-8s %-8s %s" % (name[:44], want, have, "PASS" if ok else "FAIL"))
    print("=" * 88)
    print("用例 %d，通过 %d，失败 %d" % (len(CASES), len(CASES) - bad, bad))
    if bad:
        print()
        print("---- 机检原始输出 ----")
        print(out)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
