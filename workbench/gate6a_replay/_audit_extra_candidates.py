# -*- coding: utf-8 -*-
"""样本外候选块抽检留痕。

Gold 只有 105 行，是抽样而非全表枚举，所以「Gold 页上未被引用的块」不能
直接当误提率。为了给出可核的说法，这里对固定三个样本（V101 / V319 / V320）
各取前 5 个样本外候选块，逐块判定：

    合法参数行  —— 是 Gold 样本之外的真实参数行（抽样未覆盖）
    版式碎片    —— 表头行 / 合并单元格残行，值零散但无捏造
    疑似错提    —— 值或语义明显不属于任何参数行（本次为 0）

判定写在 MANUAL 里，键为 block_id，可逐块回查 matched text。
"""
from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _replay_common as C  # noqa: E402
import _evaluate as E  # noqa: E402

SAMPLES = ("V101", "V319", "V320")
PER_SAMPLE = 5
OUT = C.OUT_ROOT / "extra_candidate_audit.csv"

MANUAL = {
    "p003-t01-r01": ("版式碎片", "表头行（TEST CONDITIONS / 温度档 / UNITS）漏成候选块，值为温度档"),
    "p003-t01-r16": ("合法参数行", "`Low Level Output V OL`，Gold 抽样未覆盖该参数"),
    "p003-t01-r22": ("合法参数行", "`Input Leakage Current I I`，Gold 抽样未覆盖"),
    "p005-t01-r02": ("版式碎片", "合并热阻表残行（封装代号 + 多档功率），值零散"),
    "p005-t02-r06": ("合法参数行", "`TLV2354M –55 125`，推荐工作温度的另一档"),
    "p012-t01-r08": ("合法参数行", "`Pin voltage` 参数行"),
    "p012-t01-r11": ("合法参数行", "`LPF 0.5 PLLAVDD + 0.5V`"),
    "p012-t01-r12": ("合法参数行", "`Peak input current` / `Peak total input current`"),
    "p012-t02-r02": ("合法参数行", "`Human-body model (HBM) ±2000 V`，ESD 参数行"),
    "p012-t03-r02": ("合法参数行", "`Recommended operating junction temperature 105 °C`"),
}


def main() -> int:
    gold = C.load_gold()
    by: dict[str, list[dict]] = {}
    for g in gold:
        by.setdefault(g["sample_no"], []).append(g)
    used = {(r["sample_no"], r["matched_block_id"])
            for r in csv.DictReader(open(C.OUT_ROOT / "eval_detail.csv",
                                         encoding="utf-8-sig", newline=""))
            if r["matched_block_id"]}

    out, kinds = [], Counter()
    for sno in SAMPLES:
        tables, cands = E.load_run(sno)
        blocks = E.build_blocks(sno, tables, cands)
        pages = {str(g["evidence_page"]) for g in by[sno]}
        extra = [b for b in blocks
                 if str(b["page_number"]) in pages and b["numbers"]
                 and (sno, b["block_id"]) not in used][:PER_SAMPLE]
        for b in extra:
            verdict, note = MANUAL.get(b["block_id"], ("未判定", "需人工补判"))
            kinds[verdict] += 1
            out.append({"sample_no": sno, "block_id": b["block_id"],
                        "page": b["page_number"], "n_rows": b["n_rows"],
                        "symbols": "|".join(sorted(b["symbols"])),
                        "numbers": "|".join("%g" % x for x in b["numbers"]),
                        "verdict": verdict, "note": note,
                        "text": b["text"][:200]})

    C.write_csv_lf(OUT, out, ["sample_no", "block_id", "page", "n_rows", "symbols",
                              "numbers", "verdict", "note", "text"])
    print("抽检 %d 块：%s" % (len(out), dict(kinds)))
    print("产物：%s" % OUT.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
