# -*- coding: utf-8 -*-
"""回测评估 v3：一对一消费匹配 + 硬/软命中分离。

=== v3 相对 v2 改了什么（Reviewer 的两条指控）===
1. **假一对一**：v2 的 eval_gold_row 让每条 Gold 独立扫全池，同一候选块可以被
   任意多条 Gold 行反复引用（实测 14 个块被 2~3 行共用，V256 的 G089/G090 甚至
   抢同一个 n_rows=1 的单行块）。v3 引入 consumed_blocks / consumed_rows，
   一块只能用一次；多行合并块（父块）则按「父块-子行」拆到不同物理行，
   在 eval_detail 里记 matched_physical_row_id 而不只是 parser_output_id。

2. **软硬混算**：v2 的 exact_rows 把 coarse=True（命中落在 ≥5 行的大块里、
   且不是 token 匹配）的行也算成「完全一致」。v3 强制把 coarse 行剔出硬命中，
   单列为 soft_hits.csv。

=== 不重跑 Parser ===
输入是 v2 冻结在盘上的 per_sample/<sno>/{tables.json, candidates.json}。
本脚本只重跑评估器侧的块组装与匹配。块组装结果与 v2 冻结的 param_blocks
逐块比对过（见 _verify_v3_faithful.py），零漂移。

=== 口径（连同报告一起读）===
  location_rate   定位率 = located_rows / 105，只问「有没有挂上候选块」
  strict_hit_rate 硬命中率 = located 且 值/单位/页码 全过 且 NOT coarse
  soft_hit_rate   软命中率 = 同上但 coarse=True（大块内命中，需人工复核）
  condition_match 仅参考，不参与任何命中判定
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _replay_common as C  # noqa: E402

PARAM_TABLE_TYPES = {"absolute_maximum", "recommended_operating",
                     "electrical_characteristics", "thermal"}

SYMBOL_RX = re.compile(r"^[A-Za-z][A-Za-z0-9_()\[\]/,.\-]*$")
HEADER_WORDS = {
    "parameter", "parameters", "symbol", "symbols", "min", "max", "typ", "units",
    "unit", "test", "conditions", "condition", "note", "notes", "see", "and",
    "value", "values", "limit", "limits", "min.", "max.", "typ.", "nom",
    "electrical", "characteristics", "recommended", "operating", "absolute",
    "maximum", "ratings", "temperature", "range", "package", "part", "number",
    "types", "type", "level", "input", "output", "high", "low",
}
COND_STOP = {"to", "and", "or", "at", "of", "the", "with", "unless", "otherwise",
             "specified", "min", "max", "typ"}

# 证据分层必须忠实于 v2 的实际选择语义，否则「一对一」的差值就不能归因。
# v2 的 find_blocks_by_symbol 把 exact 与 text 候选**放进同一个池**，再按
# (数值覆盖, 非孤儿, 块更紧) 选——token/text 只用来记 match_mode，**不优先于覆盖**。
# 早期 v3 草稿把 token 做成绝对优先，结果 V173 的 VCC 被一个符号精确但数值
# 不符的块抢走，硬命中凭空少 1。分层因此按「页内符号命中 / 页外符号命中 /
# 按值兜底」三级，与 v2 结构对齐。
TIER_LABEL = {
    1: "symbol_on_page",
    2: "symbol_wrong_page",
    3: "by_value_with_symbol",
    4: "by_value_no_symbol",
    99: "no_candidate",
}


def close(a: float, b: float) -> bool:
    return abs(a - b) <= max(1e-9, 1e-6 * max(abs(a), abs(b)))


UNIT_TOKENS = set(C.UNIT_ALIAS.values()) | {"v", "a", "c", "w", "s", "hz", "db"}

MAX_BLOCK_ROWS = 8

# coarse 判据：命中落在一个跨度 >= 5 行的块里，且不是 token 级匹配。
# 这类命中「值确实在解析结果里」，但块内混入了别的参数行，不能算逐行对上。
COARSE_MIN_ROWS = 5


def looks_like_symbol(text: str) -> bool:
    t = (text or "").strip()
    if not t or len(t) > 32:
        return False
    core = t.replace(" ", "").replace("\u00a0", "")
    if not SYMBOL_RX.match(core):
        return False
    if core.lower() in HEADER_WORDS or core.lower() in UNIT_TOKENS:
        return False
    if len(core) < 2:
        return False
    if any(ch.isdigit() for ch in core) or "(" in core or "[" in core:
        return True
    if "_" in core:
        return True
    return len(core) <= 5 and t.count(" ") <= 2


def has_unit_token(text: str, unit: str) -> bool:
    if not unit:
        return False
    t = C.norm_text(text)
    return re.search(r"(?<![a-z0-9])" + re.escape(unit) + r"(?![a-z0-9])", t) is not None


def is_headerish(cells: list[str]) -> bool:
    hits = sum(1 for x in cells if C.norm_text(x) in HEADER_WORDS)
    return hits >= 2


def load_run(sno: str):
    """只读 Parser 冻结产物，不触发任何解析。"""
    run_dir = C.PARSER_ROOT / "per_sample" / sno
    tables = json.loads((run_dir / "tables.json").read_text(encoding="utf-8"))
    cands = json.loads((run_dir / "candidates.json").read_text(encoding="utf-8"))
    return tables, (cands.get("candidates") or [])


def build_blocks(sno: str, tables, cands) -> list[dict]:
    """组装参数块，并为每个块记录**逐物理行明细**。

    v2 只把吸收进来的行并成 numbers/text 的并集，块内到底是哪几行没有留痕，
    所以一条 Gold 行「命中块」之后就无从判断它到底落在哪一个物理行上 ——
    这正是「假一对一」能藏住的土壤。v3 把 rows_detail 留下来，后续才能做
    父块-子行分配，并证明两条 Gold 行没有共用同一物理行。
    """
    sym_by_row: dict[str, set[str]] = defaultdict(set)
    for c in cands:
        if c.get("column_role") == "symbol" or c.get("candidate_type") == "symbol":
            raw = c.get("raw_text") or ""
            if not looks_like_symbol(raw):
                continue
            s = C.norm_symbol(raw)
            if s:
                sym_by_row[c["row_id"]].add(s)

    blocks: list[dict] = []
    for t in tables:
        hdr_text = " ".join(filter(None, [
            t.get("title") or "",
            " ".join(str(h or "") for h in (t.get("headers") or [])),
        ]))
        table_units: set[str] = set()
        for r in t.get("rows") or []:
            for c in (r.get("cells") or []):
                u = C.norm_unit(c.get("text") or "")
                if u in set(C.UNIT_ALIAS.values()):
                    table_units.add(u)
        cur = None
        for r in t.get("rows") or []:
            cells = [(c.get("text") or "") for c in (r.get("cells") or [])]
            joined = " ".join(x for x in cells if x).strip()
            if not joined:
                continue
            if is_headerish(cells):
                cur = None
                continue
            syms = set(sym_by_row.get(r["row_id"]) or set())
            for x in cells:
                if looks_like_symbol(x):
                    syms.add(C.norm_symbol(x))
            syms = {s for s in syms if s}
            nums: list[float] = []
            for x in cells:
                nums.extend(C.numbers_in(x))
            units = {C.norm_unit(x) for x in cells}
            units = {u for u in units if u in set(C.UNIT_ALIAS.values())}

            row_page = next((int(c["page_number"]) for c in (r.get("cells") or [])
                             if c.get("page_number")), int(t["page_number"]))

            detail = {"row_id": r["row_id"], "text": joined,
                      "numbers": list(nums), "units": sorted(units),
                      "symbols": sorted(syms)}

            if syms:
                cur = {"block_id": r["row_id"], "sample_no": sno,
                       "table_id": t["table_id"],
                       "page_number": row_page,
                       "table_type": t.get("table_type", ""),
                       "symbols": set(syms), "numbers": list(nums),
                       "units": set(units), "texts": [joined],
                       "header_text": hdr_text, "n_rows": 1,
                       "table_units": set(table_units), "orphan": False,
                       "rows_detail": [detail]}
                blocks.append(cur)
            elif cur is not None and not cur["orphan"] \
                    and cur["n_rows"] < MAX_BLOCK_ROWS:
                cur["numbers"].extend(nums)
                cur["units"] |= units
                cur["texts"].append(joined)
                cur["n_rows"] += 1
                cur["rows_detail"].append(detail)
            elif nums:
                cur = {"block_id": r["row_id"], "sample_no": sno,
                       "table_id": t["table_id"],
                       "page_number": row_page,
                       "table_type": t.get("table_type", ""),
                       "symbols": set(), "numbers": list(nums),
                       "units": set(units), "texts": [joined],
                       "header_text": hdr_text, "n_rows": 1,
                       "table_units": set(table_units), "orphan": True,
                       "rows_detail": [detail]}
                blocks.append(cur)

    for i, b in enumerate(blocks):
        b["text"] = " ".join(b.pop("texts"))
        b["cond_source"] = b["text"] + " " + b["header_text"]
        b["order"] = i                       # 稳定序，用于并列时打破僵局
    return blocks


def symbol_regex(sym: str) -> re.Pattern | None:
    if not sym:
        return None
    body = r"\s*".join(re.escape(ch) for ch in sym)
    return re.compile(r"(?<![a-z0-9])" + body + r"(?![a-z0-9])")


def block_haystack(b: dict) -> str:
    return C.norm_text(b["text"]).replace("_", "")


def find_blocks_by_symbol(sym: str, blocks: list[dict]) -> tuple[list[dict], set]:
    if not sym:
        return [], set()
    exact = [b for b in blocks if sym in b["symbols"]]
    rx = symbol_regex(sym)
    pool = {b["block_id"]: b for b in exact}
    for b in blocks:
        if b["block_id"] not in pool and rx.search(block_haystack(b)):
            pool[b["block_id"]] = b
    return list(pool.values()), {b["block_id"] for b in exact}


def cond_probe(g_cond: str, block: dict) -> tuple[bool, str]:
    """condition 是否能在块文本 + 表头里定位到关键字。**仅参考指标**。"""
    cond = C.norm_text(g_cond)
    if not cond:
        return True, ""
    src = C.norm_text(block["cond_source"]).replace(" ", "")
    flat = cond.replace(" ", "")
    if flat and flat in src:
        return True, ""
    toks = [x for x in re.split(r"[^0-9a-z]+", flat) if len(x) >= 2 and x not in COND_STOP]
    if toks and all(x in src for x in toks):
        return True, ""
    missing = [x for x in toks if x not in src]
    return False, ",".join(missing[:4])


def cover_count(b: dict, need: list[float]) -> int:
    return sum(1 for v in need if any(close(v, x) for x in b["numbers"]))


def candidates_for(g: dict, blocks: list[dict]) -> list[dict]:
    """给一条 Gold 行列出候选 {"tier","block","token"}。

    与 v2 的差别仅在「不在这里做最终选择」——选择交给全局分配，
    因为只有全局视图才知道哪块/哪行已经被别人消费掉了。

    分层与 v2 对齐：同页符号命中（token 与 text 同层，靠覆盖度决胜）
    → 页外符号命中 → 按值兜底。按值兜底只在符号路径整体失败时才启用。
    """
    page = str(g.get("evidence_page") or "").strip()
    sym = C.norm_symbol(g.get("symbol"))
    need = [C.as_number(g.get(k)) for k in ("min_value", "typ_value", "max_value")]
    need = [x for x in need if x is not None]

    out: list[dict] = []
    if sym:
        same_sym, exact_ids = find_blocks_by_symbol(sym, blocks)
        on_page = [b for b in same_sym if str(b["page_number"]) == page]
        if on_page:
            for b in on_page:
                out.append({"tier": 1, "block": b, "token": b["block_id"] in exact_ids})
            return out
        if same_sym:
            for b in same_sym:
                out.append({"tier": 2, "block": b, "token": b["block_id"] in exact_ids})
            return out

    if need:
        by_value = [b for b in blocks
                    if str(b["page_number"]) == page
                    and all(any(close(v, x) for x in b["numbers"]) for v in need)]
        for b in by_value:
            out.append({"tier": 3 if sym else 4, "block": b, "token": False})
    return out


def _row_cover(row: dict, need: list[float]) -> tuple[int, int]:
    """物理行对 Gold 数值的覆盖：(是否全覆盖, 覆盖个数)。"""
    if not need:
        return (1, 0)
    hit = sum(1 for v in need if any(close(v, x) for x in row["numbers"]))
    return (1 if hit == len(need) else 0, hit)


def assign_one_to_one(gold_rows: list[dict], blocks: list[dict]) -> tuple[dict, dict]:
    """全局贪心分配：物理行只能被消费一次，多行父块拆到不同物理行。

    候选是 **(块, 物理行) 对**，不是「先选块、再从块里随便挑一行」。这点很关键：
    V077 的 RVDD 块跨 2 行，一行是 456 MHz 那组值、一行是 I/O 电压那组值，
    若先按块分配再挑行，先到的 Gold 行会盲占首行，把真正含其数值的行挤掉。

    排序键（都对结果可复现）：
      1. tier 小的先 —— 符号精确命中绝不被「按值兜底」抢块；
      2. 同 tier 内「有某个物理行能完整覆盖其数值」的先 —— 先把能对好的对上；
      3. 候选少的先（最少剩余值启发式）；
      4. 文档顺序兜底。

    注意：condition **不参与**分配。它是参考字段，用它挑行等于拿答案选答案。
    分配完成后可以回头检验「被指派的行与 Gold condition 是否自洽」，
    那是事后佐证，不是输入。
    """
    planned = []
    for idx, g in enumerate(gold_rows):
        cands = candidates_for(g, blocks)
        need = [C.as_number(g.get(k)) for k in ("min_value", "typ_value", "max_value")]
        need = [x for x in need if x is not None]
        if not cands:
            planned.append((99, 0, 0, idx, g, need, []))
            continue
        best_tier = min(c["tier"] for c in cands)
        tier_c = [c for c in cands if c["tier"] == best_tier]
        # 展开成 (tier, 块, 是否 token, 行序, 行) 对
        pairs = [(c["tier"], c["block"], c["token"], i, r)
                 for c in tier_c for i, r in enumerate(c["block"]["rows_detail"])]
        # 排序键复刻 v2 的 rank=(cover, 非孤儿优先, 更紧的块)：v2 在覆盖度相同时
        # 偏好有真实符号的块而不是孤儿块。少了这一项，V349 会与 v2 分叉到另一个块，
        # 把「排序细节差异」混进「消费效应」里，改动范围就说不清了。
        pairs.sort(key=lambda p: (-_row_cover(p[4], need)[0],
                                  -_row_cover(p[4], need)[1],
                                  0 if not p[1].get("orphan") else 1,
                                  p[1]["n_rows"], p[1]["order"], p[3]))
        best_cov = _row_cover(pairs[0][4], need) if pairs else (0, 0)
        n_best = len(pairs)
        planned.append((best_tier, -best_cov[0], n_best, idx, g, need, pairs))
    planned.sort(key=lambda x: (x[0], x[1], x[2], x[3]))

    consumed_rows: set[tuple[str, str]] = set()
    assignments: dict[str, dict] = {}
    stats = {"seq": 0, "skipped_consumed": 0}

    for tier, _bc, _n, _idx, g, need, pairs in planned:
        taken = None
        for t, b, token, _ri, row in pairs:
            if (b["block_id"], row["row_id"]) in consumed_rows:
                stats["skipped_consumed"] += 1
                continue
            taken = (t, b, token, row)
            break
        if taken is None:
            continue
        t, b, token, row = taken
        stats["seq"] += 1
        consumed_rows.add((b["block_id"], row["row_id"]))
        assignments[g["_uid"]] = {
            "block": b, "row": row, "tier": t, "token": token,
            "seq": stats["seq"],
            "fully_covered": bool(_row_cover(row, need)[0]),
        }
    return assignments, {"consumed_rows": consumed_rows, **stats}


def judge(g: dict, asg: dict) -> dict:
    """字段级判定。数值/单位仍按 v2 的块级口径算（保证可比），
    另加 row_value_ok 说明「这条 Gold 行的值是否真的落在被指派的那一物理行上」。"""
    page = str(g.get("evidence_page") or "").strip()
    sym = C.norm_symbol(g.get("symbol"))
    need = [C.as_number(g.get(k)) for k in ("min_value", "typ_value", "max_value")]
    need = [x for x in need if x is not None]
    unit = C.norm_unit(g.get("unit"))

    b = asg["block"]
    row = asg["row"]
    tier = asg["tier"]
    by_value = tier in (3, 4)
    # v2 里「符号挂不上、退回按值」那一支把 match_mode 留成空串，统计时混进
    # "none" 里没法区分。v3 显式命名：by_value_symbol / value。
    if tier in (3, 4):
        mode = "by_value_symbol" if tier == 3 else "value"
    else:
        mode = "token" if asg["token"] else "text"

    rec = {"sample_no": g["sample_no"], "batch": g["_batch"],
           "gold_key": g.get("_uid", ""), "gold_page": page,
           "symbol": g.get("symbol") or "", "min": g.get("min_value", ""),
           "typ": g.get("typ_value", ""), "max": g.get("max_value", ""),
           "unit": g.get("unit", ""), "condition": g.get("condition", ""),
           "hit": True,
           "matched_block_id": b["block_id"],
           "matched_physical_row_id": row["row_id"],
           "block_covered_rows": "|".join(r["row_id"] for r in b["rows_detail"]),
           "matched_page": str(b["page_number"]),
           "matched_text": b["text"][:120],
           "block_rows": b["n_rows"],
           "match_mode": mode,
           "assign_tier": tier,
           "assign_tier_label": TIER_LABEL.get(tier, "?"),
           "assign_seq": asg["seq"],
           "by_value": by_value,
           "row_value_ok": asg["fully_covered"],
           "coarse": b["n_rows"] >= COARSE_MIN_ROWS and mode != "token",
           }

    rec["page_ok"] = str(b["page_number"]) == page
    missing = [v for v in need if not any(close(v, x) for x in b["numbers"])]
    rec["num_ok"] = not missing
    rec["missing_values"] = ",".join("%g" % v for v in missing)

    rec["unit_strict"] = (not unit) or (unit in b["units"]) or \
        has_unit_token(b["text"], unit)
    rec["unit_ok"] = rec["unit_strict"] or (unit in b.get("table_units", set()))

    ok_cond, miss_cond = cond_probe(g.get("condition", ""), b)
    rec["cond_ok"] = ok_cond
    rec["cond_missing"] = miss_cond

    if not rec["page_ok"]:
        rec["primary"] = "evidence page 错"
    elif rec["by_value"] and sym:
        rec["primary"] = "symbol 错配"
    elif not rec["num_ok"]:
        rec["primary"] = "数值错"
    elif not rec["unit_ok"]:
        rec["primary"] = "单位错"
    else:
        rec["primary"] = "完全一致"

    # 硬/软分离：完全一致再按 coarse 拆开。
    all_fields_ok = (rec["primary"] == "完全一致")
    rec["soft_hit"] = bool(all_fields_ok and rec["coarse"])
    rec["strict_hit"] = bool(all_fields_ok and not rec["coarse"])
    rec["flags"] = ",".join(k for k, v in (
        ("page", rec["page_ok"]), ("num", rec["num_ok"]),
        ("unit", rec["unit_ok"])) if not v) or "ok"
    return rec


def miss_record(g: dict) -> dict:
    rec = {k: "" for k in (
        "sample_no", "batch", "gold_key", "symbol", "gold_page", "min", "typ",
        "max", "unit", "condition", "matched_block_id", "matched_physical_row_id",
        "block_covered_rows", "matched_page", "matched_text", "missing_values",
        "match_mode", "cond_missing", "flags")}
    rec.update({
        "sample_no": g["sample_no"], "batch": g["_batch"],
        "gold_key": g.get("_uid", ""), "symbol": g.get("symbol", ""),
        "gold_page": str(g.get("evidence_page") or ""),
        "min": g.get("min_value", ""), "typ": g.get("typ_value", ""),
        "max": g.get("max_value", ""), "unit": g.get("unit", ""),
        "condition": g.get("condition", ""),
        "hit": False, "num_ok": False, "unit_ok": False, "unit_strict": False,
        "page_ok": False, "cond_ok": False, "coarse": False, "by_value": False,
        "row_value_ok": False, "soft_hit": False, "strict_hit": False,
        "block_rows": 0, "assign_tier": 99, "assign_tier_label": "no_candidate",
        "assign_seq": "", "primary": "漏提", "flags": "miss"})
    return rec


def _setrepr(s) -> str:
    """把集合写成**排序后**的 set 字面量。

    直接把 set 交给 csv 写出是不确定的：字符串哈希受 PYTHONHASHSEED 随机化影响，
    同一份数据两次运行会得到不同的元素顺序（实测 v1 的 rows_parser.csv 有 7485 行
    顺序不同、内容相同）。审计产物必须逐字节可复现，所以这里固定成排序输出。
    外观与 Python 的 set repr 保持一致，只是有序。
    """
    items = sorted(s)
    return "{" + ", ".join(repr(x) for x in items) + "}" if items else "set()"


def main() -> int:
    gold = C.load_gold()
    by_sample: dict[str, list[dict]] = defaultdict(list)
    for g in gold:
        by_sample[g["sample_no"]].append(g)

    all_blocks, details, per_sample = [], [], {}
    missing: list[str] = []
    total_consumed = 0
    shared_parents: list[dict] = []
    reassigned, lost = [], []

    # v2 冻结的逐行结果，用于「v3 相对 v2 到底改了哪几行」
    import csv as _csv
    v2_blocks, v2_primary = {}, {}
    _v2f = C.PARSER_ROOT / "eval_detail.csv"
    if _v2f.is_file():
        with open(_v2f, encoding="utf-8-sig", newline="") as fh:
            for r in _csv.DictReader(fh):
                v2_blocks[r["gold_key"]] = r["matched_block_id"]
                v2_primary[r["gold_key"]] = r["primary"]

    for sno in sorted(by_sample):
        run_dir = C.PARSER_ROOT / "per_sample" / sno / "tables.json"
        if not run_dir.is_file():
            missing.append(sno)
            for g in by_sample[sno]:
                rec = miss_record(g)
                rec["primary"] = "解析失败"
                rec["flags"] = "crash"
                details.append(rec)
            per_sample[sno] = {"error": "parser_crash",
                               "gold_rows": len(by_sample[sno]),
                               "located": 0, "strict": 0, "soft": 0,
                               "blocks": 0, "tables": 0}
            continue

        tables, cands = load_run(sno)
        blocks = build_blocks(sno, tables, cands)
        all_blocks.extend(blocks)

        rows = by_sample[sno]
        asg, st = assign_one_to_one(rows, blocks)
        total_consumed += len(st["consumed_rows"])

        samples = []
        for g in rows:
            a = asg.get(g["_uid"])
            samples.append(judge(g, a) if a else miss_record(g))
        details.extend(samples)

        # 父块被多条 Gold 行共用的情况：必须是不同物理行，否则就是 bug
        by_block = defaultdict(list)
        for r in samples:
            if r["matched_block_id"]:
                by_block[r["matched_block_id"]].append(r)
        for bid, rs in by_block.items():
            if len(rs) > 1:
                rids = [x["matched_physical_row_id"] for x in rs]
                shared_parents.append({
                    "sample_no": sno, "block_id": bid,
                    "n_gold_rows": len(rs), "physical_rows": rids,
                    "distinct": len(set(rids)) == len(rids)})

        # 与 v2 冻结产物逐行比对块归属。口径只有一个：拿 v2 的 eval_detail.csv
        # 按 gold_key 对齐，看 matched_block_id 变没变。任何人都能自己 diff 两份 CSV 复算。
        for d in samples:
            k = d["gold_key"]
            old = v2_blocks.get(k, "")
            cur = d["matched_block_id"]
            if old == cur:
                continue
            rec = {"sample_no": sno, "gold_key": k,
                   "gold_symbol": d["symbol"],
                   "v2_block": old or "(none)",
                   "v3_block": cur or "(none)",
                   "v3_physical_row": d["matched_physical_row_id"] or "(none)",
                   "primary_v2": v2_primary.get(k, ""),
                   "primary_v3": d["primary"],
                   "reason": "消费冲突：v2 所选块/行已被本样本另一条 Gold 行占用，"
                             "按排序顺序顺位到下一个可用物理行"
                             if cur else "消费冲突后无可用候选"}
            (reassigned if cur else lost).append(rec)

        located = sum(1 for d in samples if d["hit"])
        strict = sum(1 for d in samples if d["strict_hit"])
        soft = sum(1 for d in samples if d["soft_hit"])

        # 候选统计沿用 v2 口径，供报告与人工抽检；不能因为改了匹配算法就丢掉
        gold_pages = {str(g.get("evidence_page") or "").strip() for g in rows}
        page_blocks = [b for b in blocks if str(b["page_number"]) in gold_pages
                       and b["numbers"]]
        matched_blocks = {d["matched_block_id"] for d in samples if d["matched_block_id"]}
        extra = [b for b in page_blocks if b["block_id"] not in matched_blocks]

        dup = 0
        for d in samples:
            if not d["hit"] or not d["symbol"]:
                continue
            sym = C.norm_symbol(d["symbol"])
            for b in blocks:
                if b["block_id"] == d["matched_block_id"]:
                    continue
                if str(b["page_number"]) != d["gold_page"] or sym not in b["symbols"]:
                    continue
                if b["numbers"] and not any(
                        close(v, x) for v in b["numbers"]
                        for x in [C.as_number(d[k]) for k in ("min", "typ", "max")]
                        if x is not None):
                    dup += 1

        per_sample[sno] = {
            "pages": len({b["page_number"] for b in blocks}),
            "tables": len(tables), "blocks": len(blocks),
            "gold_pages": len(gold_pages), "page_blocks": len(page_blocks),
            "extra_candidates": len(extra), "dup_conflict": dup,
            "gold_rows": len(samples),
            "located": located, "strict": strict, "soft": soft,
            "consumed_physical_rows": len(st["consumed_rows"]),
            "parent_blocks_shared": sum(1 for x in shared_parents if x["sample_no"] == sno),
            "extra_examples": [{"block_id": b["block_id"], "page": b["page_number"],
                                "text": b["text"][:70]} for b in extra[:5]],
        }

    n = len(details)
    located = sum(1 for d in details if d["hit"])
    strict = sum(1 for d in details if d["strict_hit"])
    soft = sum(1 for d in details if d["soft_hit"])
    row_verified = sum(1 for d in details if d["strict_hit"] and d["row_value_ok"])
    coarse_n = sum(1 for d in details if d["coarse"])
    primary = Counter(d["primary"] for d in details)
    modes = Counter((d["match_mode"] or "none") for d in details)
    cond_ok = sum(1 for d in details if d["hit"] and d["cond_ok"])
    bad_share = [x for x in shared_parents if not x["distinct"]]

    metrics = {
        "schema_version": "3.1",
        "evaluator": "evaluator_v3_1to1",
        "parser_root": str(C.PARSER_ROOT),
        "parser_rerun": False,
        "matching": {
            "strategy": "one_to_one_consumption",
            "granularity": "physical_row",
            "order": "tier asc -> best_row_cover desc -> fewer_candidates first -> document order",
            "blocks_total": len(all_blocks),
            "physical_rows_consumed": total_consumed,
            "parent_blocks_shared": len(shared_parents),
            "parent_blocks_with_duplicate_row": len(bad_share),
            "rows_differing_from_v2": len(reassigned),
            "rows_lost_vs_v2": len(lost),
        },
        "gold_rows": n,
        "samples": len(per_sample),
        "located_rows": located,
        "location_rate": round(located / n, 4),
        "strict_hit_rows": strict,
        "strict_hit_rate": round(strict / n, 4),
        "soft_hit_rows": soft,
        "soft_hit_rate": round(soft / n, 4),
        "exact_rows": strict,
        "exact_rate": round(strict / n, 4),
        "row_verified_hit_rows": row_verified,
        "row_verified_hit_rate": round(row_verified / n, 4),
        "coarse_rows": coarse_n,
        "miss_rate": round(1 - located / n, 4),
        "match_mode": dict(modes),
        "attribution": dict(primary),
        "reference_only": {
            "condition_match": cond_ok,
            "note": "condition 仅作参考，不参与命中判定（Gold 的 condition 常来自列头，"
                    "Parser 块文本不携带该语义）",
        },
        "candidates": {
            "blocks_total": len(all_blocks),
            "blocks_on_gold_pages": sum(v.get("page_blocks", 0) for v in per_sample.values()),
            "extra_on_gold_pages": sum(v.get("extra_candidates", 0) for v in per_sample.values()),
            "dup_conflict": sum(v.get("dup_conflict", 0) for v in per_sample.values()),
            "candidate_per_gold_row": round(
                sum(v.get("page_blocks", 0) for v in per_sample.values()) / n, 2) if n else 0.0,
        },
        "field_level": {
            "num_ok": sum(1 for d in details if d["hit"] and d["num_ok"]),
            "unit_ok": sum(1 for d in details if d["hit"] and d["unit_ok"]),
            "unit_ok_strict": sum(1 for d in details if d["hit"] and d["unit_strict"]),
            "page_ok": sum(1 for d in details if d["hit"] and d["page_ok"]),
        },
        "definitions": {
            "located_rows": "挂上候选块即算，不看值/单位/符号/页码",
            "strict_hit_rows": "located 且 值/单位/页码 全过 且 NOT coarse",
            "soft_hit_rows": "同上但 coarse=True（命中落在 >=5 行的大块里且非 token 匹配）",
            "exact_rows": "同 strict_hit_rows，仅表示严格全字段一致",
            "row_verified_hit_rows": "strict 且 Gold 的数值确实落在被指派的那一物理行上",
            "condition_match": "参考指标，不计入任何命中率",
        },
        "per_sample": per_sample,
    }
    C.write_json(C.OUT_ROOT / "metrics.json", metrics)

    C.write_csv_lf(C.OUT_ROOT / "rows_parser.csv",
                   [{**b, "symbols": _setrepr(b["symbols"]),
                     "units": _setrepr(b["units"])} for b in all_blocks],
                   ["sample_no", "block_id", "table_id", "page_number",
                    "table_type", "n_rows", "symbols", "units", "numbers", "text"])

    COLS = ["sample_no", "batch", "gold_key", "symbol", "gold_page",
            "min", "typ", "max", "unit", "condition",
            "hit", "located", "strict_hit", "soft_hit",
            "page_ok", "num_ok", "unit_ok", "unit_strict",
            "row_value_ok", "coarse", "match_mode", "assign_tier",
            "assign_tier_label", "assign_seq", "by_value",
            "cond_ok", "cond_missing", "primary", "flags", "missing_values",
            "matched_block_id", "matched_physical_row_id", "block_covered_rows",
            "matched_page", "block_rows", "matched_text"]
    detail_rows = []
    for d in details:
        r = dict(d)
        r["located"] = bool(d["hit"])
        detail_rows.append(r)
    C.write_csv_lf(C.OUT_ROOT / "eval_detail.csv", detail_rows, COLS)

    # 软命中单列：coarse=True 且被判为完全一致的那些行
    soft_rows = [r for r in detail_rows if r["soft_hit"]]
    C.write_csv_lf(C.OUT_ROOT / "soft_hits.csv", soft_rows, COLS)

    # 父块共用清单：证明多行 Gold 落在不同物理行
    C.write_csv_lf(C.OUT_ROOT / "parent_block_sharing.csv",
                   [{"sample_no": x["sample_no"], "block_id": x["block_id"],
                     "n_gold_rows": x["n_gold_rows"],
                     "physical_rows": "|".join(x["physical_rows"]),
                     "all_distinct": x["distinct"]} for x in shared_parents],
                   ["sample_no", "block_id", "n_gold_rows", "physical_rows", "all_distinct"])

    C.write_csv_lf(C.OUT_ROOT / "consumption_reassignments.csv",
                   reassigned + lost,
                   ["sample_no", "gold_key", "gold_symbol", "v2_block", "v3_block",
                    "v3_physical_row", "primary_v2", "primary_v3", "reason"])

    print("Gold 行 %d / 样本 %d" % (n, len(per_sample)))
    print("定位 %d（%.2f%%）  硬命中 %d（%.2f%%）  软命中 %d（%.2f%%）"
          % (located, 100 * located / n, strict, 100 * strict / n,
             soft, 100 * soft / n))
    print("其中 row_verified %d（%.2f%%）" % (row_verified, 100 * row_verified / n))
    print("消费物理行 %d；父块共用 %d 个（其中行重复 %d 个）"
          % (total_consumed, len(shared_parents), len(bad_share)))
    print("相对 v2 冻结产物：块归属变动 %d 行，丢失 %d 行" % (len(reassigned), len(lost)))
    print("归因：" + "，".join("%s %d" % (k, v) for k, v in primary.most_common()))
    print("condition 可定位 %d/%d（参考值）" % (cond_ok, located))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
