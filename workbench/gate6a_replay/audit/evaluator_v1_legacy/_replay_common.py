# -*- coding: utf-8 -*-
"""Gate 6A 首次受控 Parser 回测：公共定义。

Reviewer 的硬边界落在这里：
  · 输入白名单：24 件 Gold 样本，哈希必须与台账一致；
  · 输出隔离：一律写 runs/gate6a_replay_v1/，绝不碰既有 Gold 与 runs 数据；
  · LLM 硬禁用：出站网络事件直接抛错（见 _no_llm_guard.py）。
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import unicodedata
from pathlib import Path

# 口径回放开关：置 1 时恢复「修正前」的评估口径，用于产出对照表，
# 证明哪些行是评估器判错、哪些是 Parser 真错。正式指标一律不设此变量。
# 冻结口径：修正前（本文件是审计快照，勿直接改）
LEGACY = True

REPO = Path(__file__).resolve().parents[2]          # E:/workspace/icpdf-extractor
PREP = REPO / "workbench" / "_gate6a_prep"
LEDGER = PREP / "Gold_Set_v1.1_WORKING.csv"
# 默认写首次回测目录。修 Parser 之后要复跑做「除 V256 外逐位不变」的对照，
# 用 ICPDF_REPLAY_OUT 指到另一个根，绝不覆盖首次回测的原始产物。
OUT_ROOT = Path(os.environ.get("ICPDF_REPLAY_OUT")
                or (REPO / "runs" / "gate6a_replay_v1")).resolve()
# 首次回测（审计基线）目录；对照用的清单/快照始终从这里取。
BASELINE_ROOT = REPO / "runs" / "gate6a_replay_v1"

# 105 行 Gold 的五个来源（Batch2 24 + B1 23 + B2 30 + B3 20 + B4 8）
GOLD_SOURCES = [
    ("Batch2", PREP / "Batch2_GOLD_v1.csv"),
    ("B1", PREP / "Batch3_B1_RESIGNED.csv"),
    ("B2", PREP / "Batch3_B2_FINAL.csv"),
    ("B3", PREP / "Batch3_B3_FINAL.csv"),
    ("B4", PREP / "Batch3_B4_FINAL.csv"),
]
EXPECT_SAMPLES = 24
EXPECT_ROWS = 105


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def norm_text(s: str | None) -> str:
    """比对用的归一化：全角→半角、去多余空白、统一小写。

    只做排版层归一，不做同义改写 —— 单位符号的别名在 norm_unit 里单独处理。
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\u2212", "-").replace("\u2013", "-").replace("\u2014", "-")
    s = s.replace("\u00b0", "o").replace("\u03bc", "u").replace("\u00b5", "u")
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


# 脚注引用标记：`VA19 (2)` 的 `(2)` 指正文脚注，不是符号的一部分。
# 只剥**结尾处纯数字**的括号；`V_GS(th)`、`D[7:0]` 这类语义括号必须原样保留。
FOOTNOTE_TAIL = re.compile(r"\(\s*\d{1,2}\s*\)\s*$")


def norm_symbol(s: str | None) -> str:
    """符号归一：去下标空格与标点，保留字母数字与括号。

    PDF 文本层常把 V_IH 抽成 `V IH`、V_GS(th) 抽成 `V GS(th)`，
    甚至把下标挤成 `VGS(th)`；这三种都要落到同一个键上。

    另需剥掉结尾的脚注引用标记（见 FOOTNOTE_TAIL）：TI/DSCC 手册用上标数字
    标脚注，文本层会把它直接拼在符号后面（`VA19 (2)`），不剥就永远对不上号。
    """
    s = norm_text(s)
    s = re.sub(r"[\s\u00a0]+", "", s)
    s = s.replace("_", "")
    if not LEGACY:                       # ← 修正项：剥结尾脚注标记
        s = FOOTNOTE_TAIL.sub("", s)
    return s


UNIT_ALIAS = {
    "ua": "ua", "u a": "ua", "µa": "ua", "μa": "ua",
    "na": "na", "ma": "ma", "a": "a", "v": "v", "mv": "mv", "kv": "kv",
    "mo": "mohm", "mohm": "mohm", "mω": "mohm", "ohm": "ohm", "ω": "ohm",
    "ns": "ns", "us": "us", "ms": "ms", "s": "s",
    "mhz": "mhz", "khz": "khz", "hz": "hz",
    "pf": "pf", "nf": "nf", "uf": "uf",
    "c": "c", "w": "w", "mw": "mw", "%": "%", "db": "db",
}


def norm_unit(s: str | None) -> str:
    return UNIT_ALIAS.get(norm_text(s).replace(" ", ""), norm_text(s).replace(" ", ""))


NUM_RX = re.compile(r"^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$")


def as_number(s: str | None) -> float | None:
    """只有「纯数值」才算数；1.5V、<1、TBD 之类一律不当数值。

    对称容差 `±20` 按量值 20 参与比对：这类值在手册里极常见（ESD、钳位电流、
    输出电流），若直接判成「非数值」就等于整条不校验，会凭空放大一致率。
    """
    if s is None:
        return None
    t = norm_text(s).replace(",", "").strip()
    t = re.sub(r"^[±]\s*", "", t)
    if not t or not NUM_RX.match(t):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def numbers_in(s: str | None) -> list[float]:
    """从任意文本里抽出所有数值 token（用于行级数值保真比对）。

    PDF 文本层经常把负号和数字拆开：`– 0.5`、`- 1.5`。若直接按空白切，
    会被读成 +0.5，把「值没对上」错记成数值错。这里先把符号与数字贴合。
    """
    if not s:
        return []
    t = norm_text(s).replace(",", "")
    if not LEGACY:                       # ← 修正项：负号与数字分隔
        t = re.sub(r"(?<![\d.])(?<!\d\s)-(\s+)(?=\d)", "-", t)
        t = re.sub(r"(?<![\d.+])(?<!\d\s)\+(\s+)(?=\d)", "+", t)
    out = []
    for m in re.finditer(r"[+-]?(?:\d+\.\d+|\d+|\.\d+)(?:e[+-]?\d+)?", t):
        try:
            out.append(float(m.group(0)))
        except ValueError:
            pass
    return out


def load_ledger() -> dict[str, dict]:
    with open(LEDGER, encoding="utf-8-sig", newline="") as fh:
        return {r["sample_no"]: r for r in csv.DictReader(fh)}


def load_gold() -> list[dict]:
    """105 行 Gold，逐行带上来源批次与稳定 ID。"""
    rows: list[dict] = []
    for batch, path in GOLD_SOURCES:
        assert path.is_file(), "缺 Gold 文件：%s" % path
        with open(path, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                r["_batch"] = batch
                # 稳定 ID：样本 + 页 + 符号 + 值 + 条件（B3 定稿口径）
                r["_key"] = "|".join([
                    r["sample_no"], r.get("evidence_page", ""),
                    norm_symbol(r.get("symbol")),
                    norm_text(r.get("min_value")), norm_text(r.get("typ_value")),
                    norm_text(r.get("max_value")), norm_text(r.get("unit")),
                    norm_text(r.get("condition")),
                ])
                rows.append(r)
    assert len(rows) == EXPECT_ROWS, "Gold 行数 %d，预期 %d" % (len(rows), EXPECT_ROWS)
    samples = sorted({r["sample_no"] for r in rows})
    assert len(samples) == EXPECT_SAMPLES, \
        "Gold 样本数 %d，预期 %d" % (len(samples), EXPECT_SAMPLES)
    # `_key` 会把「同页同符号同值同条件」的两行折叠成同一个键（合并单元格里
    # 常有这种重复行），对口径逐行对照不够用，另给一个含序号的稳定唯一键。
    for i, r in enumerate(rows):
        r["_uid"] = "%03d|%s" % (i, r["_key"])
    assert len({r["_uid"] for r in rows}) == len(rows), "Gold 唯一键重复"
    return rows


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(obj, ensure_ascii=False, indent=2)
                     .encode("utf-8") + b"\n")


def write_csv_lf(path: Path, rows: list[dict], cols: list[str]) -> None:
    import io
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    data = buf.getvalue().encode("utf-8-sig")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
