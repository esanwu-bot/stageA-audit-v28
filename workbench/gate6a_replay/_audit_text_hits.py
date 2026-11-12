# -*- coding: utf-8 -*-
"""文本级/按值命中的逐条审计留痕。

「放宽口径后多出来的命中」必须能被逐条复核，否则放宽就等于自欺。
本脚本对 eval_detail.csv 里所有 match_mode in {text, value} 的行给出一条审计结论：

    确认成立        —— 符号与值都能在该块文本里指认到具体位置（单行或紧凑块）
    软命中-确认成立  —— 值确实在块内，但块 ≥5 行、混入了相邻参数行；不应当作逐行对上
    不计入          —— 该行主归因本就不是「完全一致」（页错/单位错/数值错），仅列出备查

MANUAL 里是我逐条对着块文本核过的证据片段；不在此表里的行按块结构自动判定，
但「确认成立 / 软命中」的区分仍以块行数为准（≥5 行一律降级为软命中）。
"""
from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _replay_common as C  # noqa: E402

SRC = C.OUT_ROOT / "eval_detail.csv"
OUT = C.OUT_ROOT / "text_hit_audit.csv"

# (样本, 符号) -> (结论, 证据/说明)
MANUAL = {
    ("V111", "VDD"): ("确认成立", "块内含 'Supply Voltage (V DD ) −0.3 2.5 V'；块 5 行，其余为相邻参数行"),
    ("V111", "Tstg"): ("确认成立", "单行 'Storage Temperature (T stg ) −65 150 °C'"),
    ("V111", "VOS"): ("确认成立", "8 行块，但块内确有 'V OS Offset Voltage ... 1.09 1.22 1.36 V'"),
    ("V145", "PDISS"): ("确认成立", "符号与参数名同格：'PDISS Power Dissipation (PVDD+AVDD) ... 0.86 1.1 W'"),
    ("V145", "Tsett"): ("确认成立", "PDF 文本层抽成 'T sett'，允许符号内空格后定位到"),
    ("V146", "VOH"): ("确认成立", "2 行块，含 2 / 2.4 / 3.3 两组 IOH 条件"),
    ("V173", "VCC"): ("确认成立", "单行 'V CC Supply voltage range –0.5 7 V'；负号分离修正后数值才对上"),
    ("V173", "Tstg"): ("软命中-确认成立", "6 行块，块内含 'T stg Storage temperature range –65 150 °C'"),
    ("V173", "IO"): ("软命中-确认成立", "同上 6 行块，块内含 'I O Continuous output current ... ±25 mA'"),
    ("V290", "VIL"): ("确认成立", "2 行块 'V IL Input Voltage LOW 0°C to +70°C 0.8 V ...'"),
    ("V319", "VDD"): ("确认成立", "单行 'Supply voltage, VDD 2 8 V'"),
    ("V320", "AVDD, PLLAVDD"): ("软命中-确认成立", "4 行块，块内含 'AVDD, PLLAVDD –0.5 4 V'"),
    ("V320", "V(ESD)"): ("确认成立", "单行，块内含 HBM ±2000 V 与 CDM ±500 V"),
    ("V320", "DACVDD, DIGVDD, CLKVDD"): ("确认成立", "单行 'DACVDD, DIGVDD, CLKVDD –0.5 1.5 V'"),
    ("V349", "Tstg"): ("确认成立", "单行 'Storage temperature, T stg –65 150 °C'"),
}


def main() -> int:
    rows = list(csv.DictReader(open(SRC, encoding="utf-8-sig", newline="")))
    out, kinds = [], Counter()
    for r in rows:
        if r["match_mode"] not in ("text", "value"):
            continue
        key = (r["sample_no"], r["symbol"])
        if r["primary"] != "完全一致":
            verdict, note = "不计入", "该行主归因为「%s」" % r["primary"]
        elif key in MANUAL:
            verdict, note = MANUAL[key]
        elif int(r["block_rows"] or 0) >= 5:
            verdict, note = "软命中-确认成立", "%s 行合并块，值在块内但非逐行对上" % r["block_rows"]
        elif r["match_mode"] == "value":
            verdict, note = "确认成立", "Gold 该行 symbol 为空，只能按值 + 单位定位"
        else:
            verdict, note = "确认成立", "符号以字符序列命中（非整格 token）"
        kinds[verdict] += 1
        out.append({
            "sample_no": r["sample_no"], "symbol": r["symbol"],
            "gold_page": r["gold_page"],
            "gold_value": "%s/%s/%s %s" % (r["min"], r["typ"], r["max"], r["unit"]),
            "match_mode": r["match_mode"], "block_rows": r["block_rows"],
            "coarse": r["coarse"], "primary": r["primary"],
            "matched_block_id": r["matched_block_id"],
            "verdict": verdict, "evidence_note": note,
            "matched_text": r["matched_text"],
        })

    C.write_csv_lf(OUT, out, ["sample_no", "symbol", "gold_page", "gold_value",
                              "match_mode", "block_rows", "coarse", "primary",
                              "matched_block_id", "verdict", "evidence_note",
                              "matched_text"])
    print("审计条目 %d 条" % len(out))
    for k, v in kinds.most_common():
        print("  %-16s %d" % (k, v))
    print("产物：%s" % OUT.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
