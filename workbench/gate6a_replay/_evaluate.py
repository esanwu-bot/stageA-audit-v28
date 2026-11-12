# -*- coding: utf-8 -*-
"""回测评估：参数块组装 -> 与 105 行 Gold 对齐 -> 指标与错误归因。

=== 为什么按「块」而不是按「行」===
TI/DSCC 这批手册大量使用**合并单元格**：一个参数名 + 一个符号横跨 3 行，
每行对应一个 V_CC 或温度档。Parser 输出来是 3 个物理行，
第 2、3 行没有自己的符号。若按单行比对，Gold 的 3 条同符号不同条件行
会被判成「后两条数值错」——这是版式表达差异，不是解析错误。

所以组装成**参数块**：以「有符号的行」起头，吞并其后连续的无符号行，
块的数值集合是并集。

=== 口径（必须连同报告一起读）===
本轮评的是**行级检索 + token 保真**，不是逐字段严格解析正确率。
  行命中   该页存在符号归一后相同的参数块
  数值保真 Gold 的每个非空 min/typ/max 都能在该块数值集合里找到（1e-6 相对容差）
  单位      Gold 的 unit 出现在该块单位集合或表头里
  页码      块所在页 == Gold 的 evidence_page
  condition **单列为「可定位 / 不可定位」，不作为主归因**

condition 之所以不并入主归因：这批 Gold 的 condition 常来自**列头**
（`HC, VCC=2V` 对应某条 V_CC 子列 + 一张分组行 `HC TYPES`），
Parser 这一层的块文本里根本不携带那段列头语义。按「字符串能否定位」判，
会把版式差异记成解析错误。报告里仍给出数量，但必须连带限制一起读。
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

if C.LEGACY:
    # 修正前的符号正则：不允许下划线，导致 VDD_CORE / VDDA_0P85_USB0 这类
    # 电源轨名整类不可识别（V003 三条「symbol 错配」由此而来）。
    SYMBOL_RX = re.compile(r"^[A-Za-z][A-Za-z0-9()\[\]/,.\-]*$")
else:
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


def close(a: float, b: float) -> bool:
    return abs(a - b) <= max(1e-9, 1e-6 * max(abs(a), abs(b)))


UNIT_TOKENS = set(C.UNIT_ALIAS.values()) | {"v", "a", "c", "w", "s", "hz", "db"}

# 续行上限：合并单元格最多跨 3~6 行（V_CC / 温度档）。不设上限时出现过 15 行的
# 超长块 —— 那是把后面无关的行也吞进来，会让「数值保真」虚高。上限取 8，
# 宁可少吞（偏保守：少吞会让数值判为缺失）也不多吞。
MAX_BLOCK_ROWS = 8


def looks_like_symbol(text: str) -> bool:
    """整格是否就是一个符号。放宽到容忍下标里的空格（`V IH` → `VIH`），
    且必须容忍下划线 —— 电源轨/引脚名（`VDD_CORE`、`VDDA_0P85_USB0`）全带
    下划线，早期版本漏了它，导致这些行被判「不像符号」而被吞进上一块，
    进而触发按值反查、错记成 `symbol 错配`。但不能把 `High Level Input`
    这种多词参数名、也不能把单位字母 `V` 当符号。"""
    t = (text or "").strip()
    if not t or len(t) > 32:
        return False
    core = t.replace(" ", "").replace("\u00a0", "")
    if not SYMBOL_RX.match(core):
        return False
    if core.lower() in HEADER_WORDS or core.lower() in UNIT_TOKENS:
        return False
    if len(core) < 2:                       # 单个字母几乎总是单位列，不是符号
        return False
    if any(ch.isdigit() for ch in core) or "(" in core or "[" in core:
        return True
    if "_" in core:                         # 带下划线的多段式轨名
        return True
    return len(core) <= 5 and t.count(" ") <= 2


def has_unit_token(text: str, unit: str) -> bool:
    """单位必须作为**独立 token** 出现。

    早期用 `unit in text` 子串判：单位 `V` 会在 `VA19` 里命中，把单位判定
    整体虚高。改成前后都不得紧邻字母/数字（`mV` 里的 `v` 不算 `V`）。
    """
    if not unit:
        return False
    t = C.norm_text(text)
    return re.search(r"(?<![a-z0-9])" + re.escape(unit) + r"(?![a-z0-9])", t) is not None


def is_headerish(cells: list[str]) -> bool:
    hits = sum(1 for x in cells if C.norm_text(x) in HEADER_WORDS)
    return hits >= 2


def load_run(sno: str):
    run_dir = C.OUT_ROOT / "per_sample" / sno
    tables = json.loads((run_dir / "tables.json").read_text(encoding="utf-8"))
    cands = json.loads((run_dir / "candidates.json").read_text(encoding="utf-8"))
    return tables, (cands.get("candidates") or [])


def build_blocks(sno: str, tables, cands) -> list[dict]:
    sym_by_row: dict[str, set[str]] = defaultdict(set)
    for c in cands:
        # Parser 自标的 symbol 角色并不总是对的（会把参数名 `High Level Input`
        # 标成符号），所以这里再用同一个形态判据过一遍，只信「确实长得像符号」的。
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
        # 表级单位上下文：合并单元格的 UNIT 列只在合并起点那一行带值，其余行
        # 拿到的是空格。行级判单位会把这类行全记成「单位错」，而那是版式合并
        # 的必然结果，不是解析错误。所以另记一份表级单位集合做回退依据。
        table_units: set[str] = set()
        for r in t.get("rows") or []:
            for c in (r.get("cells") or []):
                u = C.norm_unit(c.get("text") or "")
                if u in set(C.UNIT_ALIAS.values()):
                    table_units.add(u)
        n_before = len(blocks)
        cur = None
        for r in t.get("rows") or []:
            cells = [(c.get("text") or "") for c in (r.get("cells") or [])]
            joined = " ".join(x for x in cells if x).strip()
            if not joined:
                continue
            if is_headerish(cells):
                cur = None                       # 表头/分组行打断块
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

            # 行自身的页码优先：跨页表的行会用 table.page_number（起始页）导致错一页，
            # V038 的 p8/p9 分歧就是这么来的。单元格自带 page_number 时以它为准。
            row_page = next((int(c["page_number"]) for c in (r.get("cells") or [])
                             if c.get("page_number")), int(t["page_number"]))
            if C.LEGACY:                     # ← 修正项：改用单元格真实页码
                row_page = int(t["page_number"])

            if syms:
                cur = {"block_id": r["row_id"], "sample_no": sno,
                       "table_id": t["table_id"],
                       "page_number": row_page,
                       "table_type": t.get("table_type", ""),
                       "symbols": set(syms), "numbers": list(nums),
                       "units": set(units), "texts": [joined],
                       "header_text": hdr_text, "n_rows": 1,
                       "table_units": set(table_units), "orphan": False}
                blocks.append(cur)
            elif cur is not None and not cur["orphan"] \
                    and cur["n_rows"] < MAX_BLOCK_ROWS:
                cur["numbers"].extend(nums)
                cur["units"] |= units
                cur["texts"].append(joined)
                cur["n_rows"] += 1
            elif nums and not C.LEGACY:      # ← 修正项：无符号孤儿块
                # 没有可识别符号的行也要留成候选块：这批手册里 Gold 的 symbol
                # 常常就是关系式短语（`APWR to AGND`）或与参数名同格
                # （`PDISS Power Dissipation`），形态判据认不出，但内容确实在
                # 解析结果里。若直接丢掉，这些行会被错记成「漏提」。
                # 孤儿块不再吞续行，避免把多个独立参数并成一块。
                cur = {"block_id": r["row_id"], "sample_no": sno,
                       "table_id": t["table_id"],
                       "page_number": row_page,
                       "table_type": t.get("table_type", ""),
                       "symbols": set(), "numbers": list(nums),
                       "units": set(units), "texts": [joined],
                       "header_text": hdr_text, "n_rows": 1,
                       "table_units": set(table_units), "orphan": True}
                blocks.append(cur)
            # 既无符号也无数值：标题、注释、表头残行，丢弃

    for b in blocks:
        b["text"] = " ".join(b.pop("texts"))
        b["cond_source"] = b["text"] + " " + b["header_text"]
    return blocks


def symbol_regex(sym: str) -> re.Pattern | None:
    """把归一化符号编译成「允许字符间夹空格」的边界正则。

    为什么需要：这批手册里 Gold 的 symbol 有很多**不是单 token**——
    `APWR to AGND`、`AGND, AGNDy to DGND` 是关系式短语；`Tsett` 在 PDF 文本层
    常被抽成 `T sett`；`PDISS` 又常和参数名挤在同一格（`PDISS Power Dissipation`）。
    三者都无法靠「整格等于符号」命中，但都能在行文本里以字符序列定位。
    """
    if not sym:
        return None
    body = r"\s*".join(re.escape(ch) for ch in sym)
    return re.compile(r"(?<![a-z0-9])" + body + r"(?![a-z0-9])")


def block_haystack(b: dict) -> str:
    """符号文本匹配的干草堆：去下划线（符号归一里下划线已删）。"""
    return C.norm_text(b["text"]).replace("_", "")


def find_blocks_by_symbol(sym: str, blocks: list[dict]) -> tuple[list[dict], set]:
    """符号候选池：精确集合命中 **与** 文本级命中一起返回。

    不能「精确命中就短路」——实测 V304 的 `VCC` 在正确页上被解析成
    `V CC Supply voltage (2)`（符号与参数名同格），而另一页的引脚说明
    `V CC 8 — Supply voltage pin` 才是精确 token。短路会让错页的精确命中
    赢过正确页的文本命中，凭空造出「evidence page 错」。
    """
    if not sym:
        return [], set()
    exact = [b for b in blocks if sym in b["symbols"]]
    if C.LEGACY:                         # 修正前：只认精确 token，且命中即短路
        return exact, {b["block_id"] for b in exact}
    rx = symbol_regex(sym)
    pool = {b["block_id"]: b for b in exact}
    for b in blocks:
        if b["block_id"] not in pool and rx.search(block_haystack(b)):
            pool[b["block_id"]] = b
    return list(pool.values()), {b["block_id"] for b in exact}


def cond_probe(g_cond: str, block: dict) -> tuple[bool, str]:
    """condition 是否能在块文本 + 表头里定位到关键字。仅作参考指标。"""
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


def eval_gold_row(g: dict, blocks: list[dict]) -> dict:
    page = str(g.get("evidence_page") or "").strip()
    sym = C.norm_symbol(g.get("symbol"))
    need = [C.as_number(g.get(k)) for k in ("min_value", "typ_value", "max_value")]
    need = [x for x in need if x is not None]
    unit = C.norm_unit(g.get("unit"))

    rec = {"sample_no": g["sample_no"], "batch": g["_batch"],
           "gold_key": g.get("_uid", ""), "gold_page": page,
           "symbol": g.get("symbol") or "", "min": g.get("min_value", ""),
           "typ": g.get("typ_value", ""), "max": g.get("max_value", ""),
           "unit": g.get("unit", ""), "condition": g.get("condition", ""),
           "matched_block_id": "", "matched_page": "", "matched_text": "",
           "hit": False, "num_ok": False, "unit_ok": False, "unit_strict": False,
           "page_ok": False, "cond_ok": False, "cond_missing": "", "primary": "",
           "missing_values": "", "block_rows": 0, "match_mode": "", "coarse": False,
           "value_on_gold_page": False}

    def cover(b):
        return sum(1 for v in need if any(close(v, x) for x in b["numbers"]))

    def rank(b):
        # 数值覆盖优先；同覆盖时有真实符号的块优先于孤儿块；再同则取更紧的块
        # （把「落在 8 行合并块里勉强算命中」排到「独占一行」之后）
        return (cover(b), 0 if b.get("orphan") else 1, -b["n_rows"])

    chosen = None
    if sym:
        same_sym, exact_ids = find_blocks_by_symbol(sym, blocks)
        on_page = [b for b in same_sym if str(b["page_number"]) == page]
        if on_page:
            chosen = max(on_page, key=rank)
        elif same_sym:
            chosen = max(same_sym, key=rank)      # 命中但页错
        if chosen is not None:
            rec["hit"] = True
            rec["match_mode"] = "token" if chosen["block_id"] in exact_ids else "text"

    # 找不到符号（含 Gold 本来就没填符号的行）时退回**同页按值定位**。
    # Gold 里有若干行 symbol 为空（例如只写参数名 + 40 nA），这类行只能按值认。
    if chosen is None and need:
        by_value = [b for b in blocks
                    if str(b["page_number"]) == page
                    and all(any(close(v, x) for x in b["numbers"]) for v in need)]
        if by_value:
            if sym:
                # 值在正确页上，但符号列没对上 → 真正的符号错配
                chosen = max(by_value, key=rank)
                rec["by_value"] = True
                rec["hit"] = True
            else:
                # Gold 无符号：只能按值认，命中方式单列，不计入符号召回
                chosen = max(by_value, key=rank)
                rec["match_mode"] = "value"
                rec["hit"] = True

    # 页错 / 漏提时的补充诊断：值本身是否仍在 Gold 页上出现过（不看符号）。
    # 用于区分「行彻底没解析出来」与「行解析出来了但符号没挂到这一行」。
    rec["value_on_gold_page"] = bool(need) and any(
        all(any(close(v, x) for x in b["numbers"]) for v in need)
        for b in blocks if str(b["page_number"]) == page)

    if chosen is None:
        rec["primary"] = "漏提"
        rec["flags"] = "miss"
        return rec

    rec["matched_block_id"] = chosen["block_id"]
    rec["matched_page"] = str(chosen["page_number"])
    rec["matched_text"] = chosen["text"][:120]
    rec["block_rows"] = chosen["n_rows"]
    # 块边界过宽：命中落在一个 ≥5 行的合并块里。值确实在解析结果中，但块内
    # 混入了别的参数行，不能当成「逐行对上」。单列为需人工复核的软命中。
    rec["coarse"] = chosen["n_rows"] >= 5 and rec["match_mode"] != "token"
    rec["page_ok"] = str(chosen["page_number"]) == page
    missing = [v for v in need if not any(close(v, x) for x in chosen["numbers"])]
    rec["num_ok"] = not missing
    rec["missing_values"] = ",".join("%g" % v for v in missing)
    # 单位两级判据：
    #   unit_strict = 本行自己带单位（最严口径，会因合并单元格而误伤）
    #   unit_ok     = 本行带 或 同表内有该单位（表头/合并单元格上下文）
    rec["unit_strict"] = (not unit) or (unit in chosen["units"]) or \
        has_unit_token(chosen["text"], unit)
    if C.LEGACY:
        # 修正前：`unit in text` 子串判，单位 `V` 会在 `VA19` 里命中（虚高）
        rec["unit_ok"] = (not unit) or (unit in chosen["units"]) or \
            (C.norm_text(g.get("unit", "")) in C.norm_text(chosen["text"]))
    else:
        rec["unit_ok"] = rec["unit_strict"] or (unit in chosen.get("table_units", set()))
    ok_cond, miss_cond = cond_probe(g.get("condition", ""), chosen)
    rec["cond_ok"] = ok_cond
    rec["cond_missing"] = miss_cond

    if not rec["page_ok"]:
        rec["primary"] = "evidence page 错"
    elif rec.get("by_value"):
        rec["primary"] = "symbol 错配"
    elif not rec["num_ok"]:
        rec["primary"] = "数值错"
    elif not rec["unit_ok"]:
        rec["primary"] = "单位错"
    else:
        rec["primary"] = "完全一致"
    rec["flags"] = ",".join(k for k, v in (
        ("page", rec["page_ok"]), ("num", rec["num_ok"]),
        ("unit", rec["unit_ok"])) if not v) or "ok"
    return rec


def main() -> int:
    # 口径互不覆盖：legacy 走 *_legacy._ 一套文件，正式指标走无后缀的一套，
    # 这样对照表可以随时重建，不会被后一次运行覆盖。
    TAG = "legacy_" if C.LEGACY else ""
    PSJ = C.OUT_ROOT / ("per_sample_json_legacy" if C.LEGACY else "per_sample_json")
    gold = C.load_gold()
    by_sample: dict[str, list[dict]] = defaultdict(list)
    for g in gold:
        by_sample[g["sample_no"]].append(g)

    all_blocks, details, per_sample = [], [], {}
    missing: list[str] = []
    for sno in sorted(by_sample):
        if not (C.OUT_ROOT / "per_sample" / sno / "tables.json").is_file():
            # 该样本 Parser 未能产出（本次为 V256 在 page 57 建表校验崩溃）。
            # 不能把它的 Gold 行从分母里剔掉 —— 那会把失败伪装成不存在。
            missing.append(sno)
            for g in by_sample[sno]:
                rec = {k: "" for k in (
                    "sample_no", "batch", "gold_key", "symbol", "gold_page", "min", "typ",
                    "max", "unit", "condition", "matched_block_id",
                    "matched_page", "matched_text", "missing_values",
                    "match_mode", "cond_missing", "flags")}
                rec.update({
                    "sample_no": sno, "batch": g["_batch"],
                    "gold_key": g.get("_uid", ""),
                    "symbol": g.get("symbol", ""),
                    "gold_page": str(g.get("evidence_page") or ""),
                    "min": g.get("min_value", ""), "typ": g.get("typ_value", ""),
                    "max": g.get("max_value", ""), "unit": g.get("unit", ""),
                    "condition": g.get("condition", ""),
                    "hit": False, "num_ok": False, "unit_ok": False,
                    "unit_strict": False, "page_ok": False, "cond_ok": False,
                    "coarse": False, "value_on_gold_page": False, "block_rows": 0,
                    "primary": "解析失败", "flags": "crash"})
                details.append(rec)
            per_sample[sno] = {"error": "parser_crash", "gold_rows": len(by_sample[sno]),
                               "hit": 0, "exact": 0, "blocks": 0, "tables": 0,
                               "pages": 0, "gold_pages": 0, "page_blocks": 0,
                               "extra_candidates": 0, "dup_conflict": 0,
                               "extra_examples": []}
            continue
        tables, cands = load_run(sno)
        blocks = build_blocks(sno, tables, cands)
        all_blocks.extend(blocks)

        samples = [eval_gold_row(g, blocks) for g in by_sample[sno]]
        details.extend(samples)
        matched = {d["matched_block_id"] for d in samples if d["matched_block_id"]}

        # 「多余候选」只能在 Gold 页上判：Gold 是 105 行**抽样**，不是全表枚举，
        # 所以整份文档里没被 Gold 引用的块绝大多数是样本外的真实参数行，
        # 把它们算成误提毫无意义。这里只统计 Gold 页上的候选块，供人工抽检。
        gold_pages = {str(g.get("evidence_page") or "").strip() for g in by_sample[sno]}
        page_blocks = [b for b in blocks if str(b["page_number"]) in gold_pages
                       and b["numbers"]]
        extra = [b for b in page_blocks if b["block_id"] not in matched]

        # 真·错提：与某条已命中 Gold 行同页同符号、但数值对不上的块（重复/矛盾候选）
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

        hit = sum(1 for d in samples if d["hit"])
        per_sample[sno] = {
            "pages": len({b["page_number"] for b in blocks}),
            "tables": len(tables), "blocks": len(blocks),
            "gold_pages": len(gold_pages), "page_blocks": len(page_blocks),
            "extra_candidates": len(extra), "dup_conflict": dup,
            "gold_rows": len(samples),
            "hit": hit,
            "exact": sum(1 for d in samples if d["primary"] == "完全一致"),
            "extra_examples": [{"block_id": b["block_id"], "page": b["page_number"],
                                "text": b["text"][:70]} for b in extra[:5]],
        }
        PSJ.mkdir(parents=True, exist_ok=True)
        slim = [{k: (sorted(v) if isinstance(v, set) else v)
                 for k, v in b.items() if k != "header_text"} for b in blocks]
        C.write_json(PSJ / ("%s.json" % sno), {
            "sample_no": sno, "tables": len(tables),
            "blocks": len(blocks), "gold_rows": len(samples),
            "param_blocks": slim, "gold_eval": samples})

    n = len(details)
    if missing:
        print("!! 尚未完成回测的样本 %d 件：%s（本次指标不含它们）"
              % (len(missing), ",".join(missing)))
    hit = sum(1 for d in details if d["hit"])
    exact = sum(1 for d in details if d["primary"] == "完全一致")
    primary = Counter(d["primary"] for d in details)
    modes = Counter(d["match_mode"] or "none" for d in details)
    cond_ok = sum(1 for d in details if d["hit"] and d["cond_ok"])
    page_blocks = sum(v["page_blocks"] for v in per_sample.values())
    extra = sum(v["extra_candidates"] for v in per_sample.values())
    dup = sum(v["dup_conflict"] for v in per_sample.values())
    coarse = sum(1 for d in details if d["hit"] and d["coarse"])

    metrics = {
        "gold_rows": n, "samples": len(per_sample),
        "hit_rows": hit, "exact_rows": exact,
        "recall": round(hit / n, 4), "miss_rate": round(1 - hit / n, 4),
        "exact_rate": round(exact / n, 4),
        "match_mode": dict(modes),
        "coarse_hits": coarse,
        "attribution": dict(primary),
        "candidates": {
            "blocks_total": len(all_blocks),
            "blocks_on_gold_pages": page_blocks,
            "extra_on_gold_pages": extra,
            "dup_conflict": dup,
            "candidate_per_gold_row": round(page_blocks / n, 2) if n else 0.0,
        },
        "field_level": {
            "num_ok": sum(1 for d in details if d["hit"] and d["num_ok"]),
            "unit_ok": sum(1 for d in details if d["hit"] and d["unit_ok"]),
            "unit_ok_strict": sum(1 for d in details if d["hit"] and d["unit_strict"]),
            "page_ok": sum(1 for d in details if d["hit"] and d["page_ok"]),
            "cond_ok": cond_ok,
        },
        "per_sample": per_sample,
    }
    C.write_json(C.OUT_ROOT / (TAG + "metrics.json"), metrics)

    C.write_csv_lf(C.OUT_ROOT / (TAG + "rows_parser.csv"), all_blocks,
                   ["sample_no", "block_id", "table_id", "page_number",
                    "table_type", "n_rows", "symbols", "units", "numbers", "text"])
    C.write_csv_lf(C.OUT_ROOT / (TAG + "eval_detail.csv"), details,
                   ["sample_no", "batch", "gold_key", "symbol", "gold_page", "min", "typ", "max",
                    "unit", "condition", "hit", "page_ok", "num_ok", "unit_ok",
                    "unit_strict", "match_mode", "coarse", "value_on_gold_page",
                    "cond_ok", "cond_missing", "primary", "flags",
                    "missing_values", "matched_block_id", "matched_page",
                    "block_rows", "matched_text"])

    print("Gold 行 %d / 样本 %d" % (n, len(per_sample)))
    print("行命中 %d（召回 %.1f%%）   完全一致 %d（%.1f%%）"
          % (hit, 100 * hit / n, exact, 100 * exact / n))
    print("命中方式：" + "，".join("%s %d" % (k, v) for k, v in modes.most_common()))
    print("Gold 页候选块 %d（%.2f 块/行），样本外 %d，同符号矛盾块 %d"
          % (page_blocks, metrics["candidates"]["candidate_per_gold_row"],
             extra, dup))
    print("归因：" + "，".join("%s %d" % (k, v) for k, v in primary.most_common()))
    print("condition 可定位 %d/%d（参考值，见报告第 7 节限制）" % (cond_ok, hit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
