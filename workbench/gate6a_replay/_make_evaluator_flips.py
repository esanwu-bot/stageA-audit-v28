# -*- coding: utf-8 -*-
"""冻结两版评估器，并产出 39 行「翻正」证据表。

做法是**把口径差异固化成两份可执行快照**，而不是口头说明：
    audit/evaluator_v1_legacy/   LEGACY = True   （修正前口径）
    audit/evaluator_v2_final/    LEGACY = False  （正式口径）
两份都带 SHA-256，任何人可以重跑并复现 `legacy_*` 与正式指标。

翻正表按 Gold 稳定键 join 两套 eval_detail，只取「旧口径判错 → 新口径完全一致」
的行，并给出成因与 PDF 原页。成因是规则判定的，规则写在 `_reason()` 里，可复核。
"""
from __future__ import annotations

import csv
import hashlib
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _replay_common as C  # noqa: E402

AUDIT = HERE / "audit"
FLIPS = AUDIT / "evaluator_flips_39.csv"
SUMS = AUDIT / "SHA256SUMS.txt"
SNAP = {"v1_legacy": ("evaluator_v1_legacy", "True"),
        "v2_final": ("evaluator_v2_final", "False")}
LEGACY_LINE = 'LEGACY = os.environ.get("ICPDF_EVAL_LEGACY") == "1"'


def freeze() -> list[tuple[str, str]]:
    """生成两份固定口径的快照，返回 (相对路径, sha256)。"""
    out = []
    for tag, (folder, value) in SNAP.items():
        target = AUDIT / folder
        target.mkdir(parents=True, exist_ok=True)
        for name in ("_evaluate.py", "_replay_common.py"):
            src = (HERE / name).read_text(encoding="utf-8")
            if LEGACY_LINE in src:      # 开关只在 _replay_common 里定义
                body = src.replace(
                    LEGACY_LINE,
                    "# 冻结口径：%s（本文件是审计快照，勿直接改）\nLEGACY = %s"
                    % ("修正前" if value == "True" else "修正后", value))
            else:
                assert name != "_replay_common.py", "口径开关行已变，冻结脚本需同步"
                body = src
            p = target / name
            p.write_bytes(body.encode("utf-8"))
            out.append((str(p.relative_to(AUDIT)).replace("\\", "/"),
                        hashlib.sha256(p.read_bytes()).hexdigest()))
    return out


def _reason(o: dict, n: dict) -> str:
    sym = n["symbol"] or ""
    old, new = o["primary"], n["primary"]
    if old == "evidence page 错" and new == "完全一致":
        return ("符号结尾脚注标记未剥离：`%s (2)` ≠ `%s`，目标页的块认不出，"
                "旧口径退而命中了别的页上的同名块" % (sym, sym))
    if old == "数值错" and new == "完全一致":
        return ("负号与数字在文本层被空格分开（`– 0.5` 读成 `+0.5`），"
                "旧口径把符号位丢了")
    if "_" in sym and old in ("漏提", "symbol 错配"):
        return ("符号正则不允许下划线：`%s` 整类电源轨名被判「不像符号」，"
                "该行被吞进上一块" % sym)
    if " to " in sym or "," in sym:
        return ("Gold 的符号是关系式短语（`%s`），只认整格 token 时无法命中，"
                "需按字符序列定位" % sym)
    if n["match_mode"] == "value":
        return "Gold 该行 symbol 为空，旧口径没有「按值 + 单位」回退"
    if old == "evidence page 错" and n["match_mode"] == "text":
        return ("同页候选池优先：正确页的块只能文本级命中，而旧口径被别页的精确 "
                "token 抢先，凭空造出「页错」")
    if n["match_mode"] == "text":
        return ("符号与参数名同格或下标断字（如 `T sett`），整格 token 匹配落空，"
                "文本级定位命中")
    return "同页候选池合并后，正确页的块优先于错误页的同名精确命中"


def main() -> int:
    old = {r["gold_key"]: r for r in csv.DictReader(
        open(C.OUT_ROOT / "legacy_eval_detail.csv", encoding="utf-8-sig", newline=""))}
    new = {r["gold_key"]: r for r in csv.DictReader(
        open(C.OUT_ROOT / "eval_detail.csv", encoding="utf-8-sig", newline=""))}
    assert set(old) == set(new)

    rows = []
    for key, n in new.items():
        o = old[key]
        if not (o["primary"] != "完全一致" and n["primary"] == "完全一致"):
            continue
        idx = int(key.split("|")[0]) + 1
        rows.append({
            "sample_id": n["sample_no"],
            "gold_row_id": "G%03d" % idx,
            "symbol": n["symbol"],
            "old_verdict": o["primary"],
            "new_verdict": n["primary"],
            "reason": _reason(o, n),
            "original_pdf_page": n["gold_page"],
            "old_block": o["matched_block_id"] or "—",
            "new_block": n["matched_block_id"] or "—",
            "new_match_mode": n["match_mode"],
            "gold_key": key,
        })
    rows.sort(key=lambda r: (r["sample_id"], r["gold_row_id"]))

    AUDIT.mkdir(parents=True, exist_ok=True)
    C.write_csv_lf(FLIPS, rows, ["sample_id", "gold_row_id", "symbol", "old_verdict",
                                 "new_verdict", "reason", "original_pdf_page",
                                 "old_block", "new_block", "new_match_mode",
                                 "gold_key"])

    frozen = freeze()
    lines = ["# 冻结评估器快照的 SHA-256", ""]
    for rel, digest in frozen:
        lines.append("%s  %s" % (digest, rel))
    lines += ["", "# 回测产物（只读，作为对照输入的原始 JSON）", ""]
    for name in ("legacy_eval_detail.csv", "eval_detail.csv", "metrics.json",
                 "legacy_metrics.json"):
        p = C.OUT_ROOT / name
        lines.append("%s  runs/gate6a_replay_v1/%s"
                     % (hashlib.sha256(p.read_bytes()).hexdigest(), name))
    SUMS.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))

    print("翻正行 %d -> %s" % (len(rows), FLIPS))
    print("  旧->新:", dict(Counter("%s->%s" % (r["old_verdict"], r["new_verdict"])
                                   for r in rows)))
    print("冻结快照 %d 个文件；SHA256SUMS 已写" % len(frozen))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
