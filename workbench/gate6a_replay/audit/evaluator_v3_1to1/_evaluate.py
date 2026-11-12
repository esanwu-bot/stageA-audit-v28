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

        # 表级「合并证据」：Parser 若记录了纵向合并，这里是唯一的显式来源。
        # 同时把重建状态一并带上 —— reconstruction_status=partial 的表，
        # 「某列没有单元格」既可能是合并，也可能是丢格，不能默认前者。
        tbl_evidence = {
            "merge_evidence_n": len(t.get("merge_evidence") or []),
            "merge_evidence": list(t.get("merge_evidence") or []),
            "recon_status": str(t.get("reconstruction_status") or ""),
            "uncertainty_reason": str(t.get("uncertainty_reason") or ""),
            "header_cells": [{"column_id": int(hc.get("column_id", -1)),
                              "text": (hc.get("text") or "")}
                             for hc in (t.get("header_cells") or [])],
        }
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

            row_bb = r.get("bbox") or [0.0, 0.0, 0.0, 0.0]
            # 行级几何是「符号能否跨行继承」的唯一可证材料：
            #   - 行 bbox 给出这一行的纵向范围
            #   - 单元格 bbox 给出符号文字实际占的纵向范围
            # 只有符号单元格的 bbox 真的把目标行盖住，才谈得上「合并单元格继承」。
            # 否则「符号属于这一行」只是推断 —— Reviewer 这一轮要的正是这条界线。
            detail = {"row_id": r["row_id"], "text": joined,
                      "numbers": list(nums), "units": sorted(units),
                      "symbols": sorted(syms),
                      "y0": float(row_bb[1]), "y1": float(row_bb[3]),
                      "cells": [{"column_id": int(c.get("column_id", -1)),
                                 "text": (c.get("text") or ""),
                                 "y0": float((c.get("bbox") or [0, 0, 0, 0])[1]),
                                 "y1": float((c.get("bbox") or [0, 0, 0, 0])[3])}
                                for c in (r.get("cells") or [])]}

            if syms:
                cur = {"block_id": r["row_id"], "sample_no": sno,
                       "table_id": t["table_id"],
                       "page_number": row_page,
                       "table_type": t.get("table_type", ""),
                       "symbols": set(syms), "numbers": list(nums),
                       "units": set(units), "texts": [joined],
                       "header_text": hdr_text, "n_rows": 1,
                       "table_units": set(table_units), "orphan": False,
                       "rows_detail": [detail], **tbl_evidence}
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
                       "rows_detail": [detail], **tbl_evidence}
                blocks.append(cur)

    for i, b in enumerate(blocks):
        b["text"] = " ".join(b.pop("texts"))
        b["cond_source"] = b["text"] + " " + b["header_text"]
        b["order"] = i                       # 稳定序，用于并列时打破僵局
    return blocks


def symbol_regex(sym: str) -> re.Pattern | None:
    """符号匹配正则：允许符号内部夹排版空格（`V IH`），两侧不许粘字母数字。

    **必须大小写不敏感**：`norm_symbol()` 会把符号归一成小写（`Tstg` -> `tstg`），
    而物理行原文是原始大小写（`Storage Temperature (T stg )`）。早期版本没加 re.I，
    于是「符号明明就在这一行」也被判成不在 —— 那是判定缺陷，不是数据缺陷。
    边界断言仍用小写字符类，配合 re.I 等价于 `(?<![A-Za-z0-9])`。
    """
    if not sym:
        return None
    body = r"\s*".join(re.escape(ch) for ch in sym)
    return re.compile(r"(?<![a-z0-9])" + body + r"(?![a-z0-9])", re.IGNORECASE)


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


# ---------------------------------------------------------------- 符号继承证据
#
# Reviewer 这一轮的问题：一条 Gold 行落在父块的第 2、3 行上，而符号只写在第 1 行。
# v3 之前只保证「这条 Gold 行占了这个物理行」，没保证「符号也属于这个物理行」。
# 于是出现一批「数值确实在这一行、但符号是借来的」的所谓严格命中。
#
# 判定只认三个证据通道，任一成立才算跨行继承站得住：
#   1. 符号文字就在该行              -> 同一行直接命中
#   2. 承载符号的单元格 bbox 纵向盖住该行 -> 跨行合并单元格继承（几何证据）
#   3. 表级 merge_evidence 明确记了两行的合并 -> 跨行合并单元格继承（显式证据）
# 三者皆不成立 -> 无依据跨行继承。此时「符号属于这一行」是推断，不是证据。

INH_DIRECT = "同一行直接命中"
INH_MERGED = "跨行合并单元格继承"
INH_UNPROVEN = "无依据跨行继承"
INH_NA = "不适用（Gold 无符号，按值兜底）"

ROW_EPS = 0.5          # pt，浮点比较容差；与 V256 证据里的 0.2pt 阈值不是一回事


def _cell_holding(cells: list[dict], sym: str) -> dict | None:
    """在若干单元格里找承载该符号的那一个（按归一化文本比，容忍 `V IH` 这类下标空格）。"""
    rx = symbol_regex(sym)
    for c in cells:
        t = c.get("text") or ""
        if sym and (C.norm_symbol(t) == sym or (rx and rx.search(C.norm_text(t)))):
            return c
    return None


def classify_symbol_inheritance(g: dict, asg: dict) -> dict:
    """判定命中物理行上的符号从哪来。"""
    block = asg["block"]
    row = asg["row"]
    rows_d: list[dict] = block["rows_detail"]
    first = rows_d[0]
    sym = C.norm_symbol(g.get("symbol"))

    out = {"symbol_inheritance": "", "symbol_row_verified": False,
           "symbol_carrier_row": "", "row_text": row.get("text", ""),
           "parent_block_id": block["block_id"],
           "matched_row_id": row["row_id"],
           "parent_first_row": first["row_id"],
           "symbol_cell_y": "", "symbol_row_y": "", "merge_evidence_n": "",
           "recon_status": "", "basis": ""}

    if not sym:
        out["symbol_inheritance"] = INH_NA
        out["symbol_row_verified"] = True      # 不涉及符号继承，不因此降级
        out["basis"] = "Gold 行本身没有符号，走按值兜底，不存在符号归属问题"
        return out

    rx = symbol_regex(sym)
    # 在**归一化后**的行文本上找：norm_text 会统一大小写、全角/半角、破折号，
    # 与 norm_symbol 的口径一致。直接拿原文比会把 `Tstg` 和 `tstg` 当成两个东西。
    row_norm = C.norm_text(row.get("text") or "")
    on_row = (sym in (row.get("symbols") or [])) or bool(rx and rx.search(row_norm))
    if on_row:
        out["symbol_inheritance"] = INH_DIRECT
        out["symbol_row_verified"] = True
        out["symbol_carrier_row"] = row["row_id"]
        out["basis"] = "符号文字出现在该物理行自身的文本里"
        return out

    # 符号不在这一行：找承载它的那一行（同样按归一化文本比）
    carrier = next((x for x in rows_d if sym in (x.get("symbols") or [])), None)
    if carrier is None:
        carrier = next((x for x in rows_d
                        if rx and rx.search(C.norm_text(x.get("text") or ""))), first)
    out["symbol_carrier_row"] = carrier["row_id"]

    # 通道 2：几何 —— 符号单元格的纵向范围是否盖住目标行
    cell = _cell_holding(carrier.get("cells") or [], sym)
    if cell:
        cy0, cy1 = cell.get("y0", 0.0), cell.get("y1", 0.0)
        ry0, ry1 = row.get("y0", 0.0), row.get("y1", 0.0)
        out["symbol_cell_y"] = "%.2f-%.2f" % (cy0, cy1)
        out["symbol_row_y"] = "%.2f-%.2f" % (ry0, ry1)
        if cy0 <= ry0 + ROW_EPS and cy1 >= ry1 - ROW_EPS:
            out["symbol_inheritance"] = INH_MERGED
            out["symbol_row_verified"] = True
            out["basis"] = ("符号单元格 bbox 纵向从 %.2f 覆盖到 %.2f，"
                            "完整盖住目标行 %.2f-%.2f（几何证据）"
                            % (cy0, cy1, ry0, ry1))
            return out

    # 通道 3：表级显式合并证据
    out["merge_evidence_n"] = block.get("merge_evidence_n", 0)
    out["recon_status"] = block.get("recon_status", "")
    for ev in block.get("merge_evidence") or []:
        blob = json.dumps(ev, ensure_ascii=False)
        if carrier["row_id"] in blob and row["row_id"] in blob:
            out["symbol_inheritance"] = INH_MERGED
            out["symbol_row_verified"] = True
            out["basis"] = "表级 merge_evidence 显式记录了两行的合并关系（显式证据）"
            return out

    out["symbol_inheritance"] = INH_UNPROVEN
    out["symbol_row_verified"] = False
    span = ""
    if cell:
        span = ("符号单元格只占 %.2f-%.2f，未覆盖目标行 %.2f-%.2f；"
                % (cell.get("y0", 0.0), cell.get("y1", 0.0),
                   row.get("y0", 0.0), row.get("y1", 0.0)))
    out["basis"] = (span +
                    "表级 merge_evidence=%d 条，reconstruction_status=%s。"
                    "「该列在这一行没有单元格」既可能是纵向合并，也可能是丢格，"
                    "Parser 自己把后者写进了 uncertainty_reason，故不能判为合并。"
                    % (block.get("merge_evidence_n", 0),
                       block.get("recon_status") or "(空)"))
    return out


# ------------------------------------------------------------ condition 归属层级
#
# v3.1 之前 condition 只在「块文本 + 表头」里找，找到了就算过。
# 但块文本是整块拼接的，父块任何一行出现过都算 —— 这等于用正确答案去挑行。
# 现在拆成四层，只认这一行的证据优先：
#   row     ：条件就写在这一行上           （最强，无需推断）
#   header  ：条件在表头，且能按列索引对齐到这一行
#   block   ：只在父块的其他行出现过       （需要列出具体位置）
#   unresolved：哪里都找不到

COND_IN_ROW = "条件在命中行"
COND_IN_HEADER = "条件在表头且按列对齐"
COND_IN_BLOCK = "条件仅在父块他行"
COND_UNRESOLVED = "条件未定位"
COND_NONE = "无条件（不适用）"


def _flat(s: str) -> str:
    return C.norm_text(s or "").replace(" ", "")


def cond_attribution(cond: str, block: dict, row: dict) -> dict:
    """把 condition 落到具体层级，四层互斥，优先级 row > header > block > unresolved。"""
    out = {"condition_row_match": False, "condition_header_match": False,
           "condition_block_match": False, "condition_unresolved": False,
           "condition_attribution": COND_NONE, "condition_evidence": ""}

    flat = _flat(cond)
    if not flat:
        return out

    toks = [x for x in re.split(r"[^0-9a-z]+", flat) if len(x) >= 2 and x not in COND_STOP]
    if not toks:
        toks = [flat]

    def _all_in(hay: str) -> bool:
        return flat in hay or all(t in hay for t in toks)

    # 第 1 层：命中行自身
    row_flat = _flat(row.get("text", ""))
    if _all_in(row_flat):
        out["condition_row_match"] = True
        out["condition_attribution"] = COND_IN_ROW
        out["condition_evidence"] = "该物理行文本：%s" % (row.get("text", "")[:100])
        return out

    # 第 2 层：表头 + 列索引对齐
    hdr_flat = _flat(block.get("header_text", ""))
    if _all_in(hdr_flat):
        hcs = block.get("header_cells") or []
        row_cols = {c.get("column_id") for c in (row.get("cells") or [])
                    if (c.get("text") or "").strip()}
        aligned, cols = True, []
        for t in toks:
            hit_cols = {hc["column_id"] for hc in hcs if t in _flat(hc.get("text", ""))}
            if not hit_cols:
                continue
            cols.extend(sorted(hit_cols))
            if not (hit_cols & row_cols):
                aligned = False
        if cols and aligned:
            out["condition_header_match"] = True
            out["condition_attribution"] = COND_IN_HEADER
            out["condition_evidence"] = ("表头命中，且目标行在列 %s 上有取值"
                                         % ",".join(str(c) for c in sorted(set(cols))))
            return out

    # 第 3 层：只在父块其他行
    locs = []
    for r2 in block.get("rows_detail") or []:
        if r2["row_id"] == row["row_id"]:
            continue
        if _all_in(_flat(r2.get("text", ""))):
            locs.append(r2["row_id"])
    if locs:
        out["condition_block_match"] = True
        out["condition_attribution"] = COND_IN_BLOCK
        out["condition_evidence"] = "命中父块其他行：%s" % "|".join(locs)
        return out

    # 第 4 层：找不到（连同父块整体文本一起兜底判断）
    # 注意两种兜底要分开写清楚，否则会把「表级条件」误报成「父块他行条件」：
    #   只在表题/表头文本里出现 -> 表级条件（整张表共用），无法按列对齐到某一行
    #   只在块正文里出现        -> 父块他行条件，位置不可定
    if _all_in(hdr_flat):
        out["condition_block_match"] = True
        out["condition_attribution"] = COND_IN_BLOCK
        out["condition_evidence"] = ("条件只出现在表题/表头文本，属整表共用条件，"
                                     "无法按列索引对齐到该行")
        return out
    if _all_in(hdr_flat + _flat(block.get("text", ""))):
        out["condition_attribution"] = COND_IN_BLOCK
        out["condition_block_match"] = True
        out["condition_evidence"] = "仅在父块整体文本中出现，无法定位到具体行"
        return out

    out["condition_unresolved"] = True
    out["condition_attribution"] = COND_UNRESOLVED
    out["condition_evidence"] = "命中行 / 表头 / 父块他行 均未出现"
    return out


# ------------------------------------------------------------ 未落行的成因分类
#
# 条件没落到命中行时，光说「未定位」等于没说。这里的四个成因对应四种完全不同的
# 责任方，混在一起会让人以为是同一个毛病：
#   table_title        条件是表题/整表共用条件 —— 本来就不该按行去找（Gold 字段问题）
#   grouped_subheader  条件印在分组子列头上，Parser 的 header_cells 只到顶层列（Parser 表头建模）
#   other_row_in_block 条件在同一个父块的其他行上 —— 行指派错了（分配算法）
#   other_block        条件在同一个样本的另一块里 —— 行/块指派错了（分配算法）
#   unresolved         哪里都找不到（真·未定位）
MISS_TABLE_TITLE = "table_title"
MISS_GROUPED_SUBHEADER = "grouped_subheader"
MISS_OTHER_ROW = "other_row_in_block"
MISS_OTHER_BLOCK = "other_block"
MISS_SECTION_HEADING = "section_heading"
MISS_UNRESOLVED = "unresolved"

# 章节标题的形态：`6.1 Absolute Maximum Ratings` / `5 Recommended Operating Conditions`。
# 这类字符串不属任何一张表，是文档结构标题，被 Gold 的 condition 字段误收进来。
SECTION_HEADING_RX = re.compile(r"^\d+(?:\.\d+)*\s+[A-Za-z]")


def condition_miss_kind(cond: str, block: dict, blocks: list[dict]) -> str:
    """条件未落到命中行时，判定它到底在哪一层。纯证据判定，不看样本号。"""
    flat = _flat(cond)
    if not flat:
        return ""
    toks = [x for x in re.split(r"[^0-9a-z]+", flat) if len(x) >= 2 and x not in COND_STOP]
    if not toks:
        toks = [flat]

    def _all_in(hay: str) -> bool:
        return flat in hay or all(t in hay for t in toks)

    # 1) 表题 / 整表共用
    if _all_in(_flat(block.get("header_text", ""))):
        return MISS_TABLE_TITLE

    # 2) 同块其他行（行指派错位）
    for r2 in block.get("rows_detail") or []:
        if _all_in(_flat(r2.get("text", ""))):
            return MISS_OTHER_ROW

    # 3) 表头单元格能部分命中（分组子列头：只有碎片落在 header_cells 里）
    hcs = block.get("header_cells") or []
    for t in toks:
        if any(t in _flat(hc.get("text", "")) for hc in hcs):
            return MISS_GROUPED_SUBHEADER

    # 4) 本样本其他块（块指派错位）
    for b2 in blocks:
        if b2["block_id"] == block["block_id"]:
            continue
        if _all_in(_flat(b2.get("text", ""))) or _all_in(_flat(b2.get("header_text", ""))):
            return MISS_OTHER_BLOCK

    # 5) 章节标题形态，且全样本任何表里都没有 —— 说明它压根不是行级条件
    if SECTION_HEADING_RX.match(C.norm_text(cond)):
        return MISS_SECTION_HEADING

    return MISS_UNRESOLVED


def cover_count(b: dict, need: list[float]) -> int:    return sum(1 for v in need if any(close(v, x) for x in b["numbers"]))


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
           "condition_miss_kind": "",
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

    # 符号归属：不是「挂上块」就算，要能指认符号落在这一行的证据
    inh = classify_symbol_inheritance(g, asg)
    rec["symbol_inheritance"] = inh["symbol_inheritance"]
    rec["symbol_row_verified"] = inh["symbol_row_verified"]
    rec["symbol_carrier_row"] = inh["symbol_carrier_row"]
    for _k in ("row_text", "symbol_cell_y", "symbol_row_y",
               "merge_evidence_n", "recon_status", "basis"):
        rec[_k] = inh.get(_k, "")

    # condition 落到层级上，而不是「父块里出现过就算过」
    ca = cond_attribution(g.get("condition", ""), b, row)
    rec.update(ca)

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

    # 三层收窄，逐层可见：
    #   字段全一致（exact）  值/单位/页码/符号在块级全过
    #   ├─ 严格命中（strict）再要求：非 coarse 且 符号归属在行级可证
    #   └─ 软命中（soft）    exact 但不满足 strict 的那些，必须写明是哪一类
    all_fields_ok = (rec["primary"] == "完全一致")
    rec["exact_hit"] = bool(all_fields_ok)
    rec["soft_reason"] = ""
    if all_fields_ok and rec["coarse"]:
        rec["soft_reason"] = "coarse_大块并集"
    if all_fields_ok and not inh["symbol_row_verified"]:
        rec["soft_reason"] = ("coarse_大块并集+symbol_无依据跨行继承"
                              if rec["coarse"] else "symbol_无依据跨行继承")

    rec["strict_hit"] = bool(all_fields_ok and not rec["coarse"]
                             and inh["symbol_row_verified"])
    rec["soft_hit"] = bool(all_fields_ok and not rec["strict_hit"])

    rec["flags"] = ",".join(k for k, v in (
        ("page", rec["page_ok"]), ("num", rec["num_ok"]),
        ("unit", rec["unit_ok"])) if not v) or "ok"

    # ---- 语义门槛阶梯（v3.3）---------------------------------------------
    # 三级，逐级更严，全部单列成字段，谁都不许混着引用：
    #   exact_hit                    值/单位/页码/符号在**块级**全过
    #   symbol_gated_strict_hit      再加「符号归属在命中物理行上可证」
    #   condition_gated_strict_hit   再加「condition 落在命中行或按列对齐」
    # 每行给出唯一一条**阻断原因**，顺序即阶梯顺序，先撞上哪道就记哪道。
    rec["symbol_gated_strict_hit"] = rec["strict_hit"]
    cond_txt = (g.get("condition") or "").strip()
    cond_row_ok = bool(rec["condition_row_match"] or rec["condition_header_match"])
    rec["condition_gated_strict_hit"] = bool(
        rec["strict_hit"] and (not cond_txt or cond_row_ok))

    if not rec["hit"]:
        reason = "not_located"
    elif rec["primary"] != "完全一致":
        reason = "field_mismatch"
    elif rec["coarse"]:
        reason = "coarse_block"
    elif not inh["symbol_row_verified"]:
        reason = "symbol_not_on_row"
    elif cond_txt and not cond_row_ok:
        # 具体成因要拿同一样本的全部块去查，judge() 里看不到，留待 main() 补全
        reason = "condition_not_on_row"
    else:
        reason = ""
    rec["semantic_hit_reason"] = reason
    rec["_cond_miss_pending"] = (reason == "condition_not_on_row")
    return rec


def miss_record(g: dict) -> dict:
    rec = {k: "" for k in (
        "sample_no", "batch", "gold_key", "symbol", "gold_page", "min", "typ",
        "max", "unit", "condition", "matched_block_id", "matched_physical_row_id",
        "block_covered_rows", "matched_page", "matched_text", "missing_values",
        "match_mode", "cond_missing", "flags",
        "symbol_inheritance", "symbol_carrier_row", "soft_reason",
        "condition_attribution", "condition_evidence")}
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
        "exact_hit": False, "symbol_row_verified": False,
        "condition_row_match": False, "condition_header_match": False,
        "condition_block_match": False, "condition_unresolved": False,
        "block_rows": 0, "assign_tier": 99, "assign_tier_label": "no_candidate",
        "assign_seq": "", "primary": "漏提", "flags": "miss",
        "symbol_gated_strict_hit": False,
        "condition_gated_strict_hit": False,
        "condition_miss_kind": "",
        "semantic_hit_reason": "not_located", "_cond_miss_pending": False})
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

        # 补全「condition 未落行」的具体成因。judge() 只看到父块，看不到同一样本的
        # 其他块，而「条件其实在另一块里」正是分配错位的证据，必须在这一层判。
        blk_by_id = {b["block_id"]: b for b in blocks}
        for d in samples:
            if d.get("_cond_miss_pending"):
                blk = blk_by_id.get(d["matched_block_id"])
                kind = condition_miss_kind(d["condition"], blk, blocks) if blk else MISS_UNRESOLVED
                d["condition_miss_kind"] = kind
                d["semantic_hit_reason"] = "condition_not_on_row:" + kind
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
    exact_n = sum(1 for d in details if d["exact_hit"])
    row_verified = sum(1 for d in details if d["strict_hit"] and d["row_value_ok"])
    coarse_n = sum(1 for d in details if d["coarse"])
    primary = Counter(d["primary"] for d in details)
    modes = Counter((d["match_mode"] or "none") for d in details)
    cond_ok = sum(1 for d in details if d["hit"] and d["cond_ok"])
    bad_share = [x for x in shared_parents if not x["distinct"]]

    inh_counts = Counter(d["symbol_inheritance"] for d in details if d["hit"])
    ca_counts = Counter(d["condition_attribution"] for d in details if d["hit"])
    demoted = [d for d in details if d["exact_hit"] and not d["strict_hit"]
               and not d["coarse"]]
    soft_reasons = Counter(d["soft_reason"] or "unspecified"
                           for d in details if d["soft_hit"])
    cond_row_level = sum(1 for d in details if d["hit"] and (
        d["condition_row_match"] or d["condition_header_match"]))
    cond_has = sum(1 for d in details if d["hit"] and (d["condition"] or "").strip())
    cond_block_only = sum(1 for d in details if d["hit"] and d["condition_block_match"])
    cond_unres = sum(1 for d in details if d["hit"] and d["condition_unresolved"])

    # 严格命中判定作用域（exact 且非 coarse）内的符号归属分布。
    # 这张表必须能自己配平：82 = 62 直接命中 + 15 跨行借用 + 1 行指派错位 + 4 无符号。
    # 上面的 inh_counts 是按「已定位 104 行」统计的，两者口径不同，不能混着引用。
    def _is_first(d) -> bool:
        cov = (d["block_covered_rows"] or "").split("|")
        return bool(cov[0]) and d["matched_physical_row_id"] == cov[0]

    judged = [d for d in details if d["exact_hit"] and not d["coarse"]]
    inh_scope = {
        "exact_not_coarse_rows": len(judged),
        "同一行直接命中": sum(1 for d in judged if d["symbol_inheritance"] == INH_DIRECT),
        "无依据_命中行非首行": sum(1 for d in judged if not _is_first(d)
                                   and d["symbol_inheritance"] == INH_UNPROVEN),
        "无依据_命中行为首行": sum(1 for d in judged if _is_first(d)
                                   and d["symbol_inheritance"] == INH_UNPROVEN),
        "不适用_无符号": sum(1 for d in judged if d["symbol_inheritance"] == INH_NA),
    }
    # 若把「父块内符号在更靠前的行」也算作可接受继承（不要求几何证据），严格命中会是多少：
    # 只作敏感性参考，不参与任何主指标。
    strict_if_cross_accepted = strict + sum(
        1 for d in demoted if d["symbol_inheritance"] == INH_UNPROVEN and not _is_first(d))

    # ---- 语义门槛（v3.3）：符号门 → 条件门 ---------------------------------
    sym_gated = sum(1 for d in details if d["symbol_gated_strict_hit"])
    cond_gated = sum(1 for d in details if d["condition_gated_strict_hit"])
    sem_reasons = Counter(d["semantic_hit_reason"] or "passed" for d in details)
    miss_kinds = Counter(d["condition_miss_kind"] for d in details if d["condition_miss_kind"])
    cond_fail = [d for d in details if d["semantic_hit_reason"].startswith("condition_not_on_row")]

    metrics = {
        "schema_version": "3.3",
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
        "symbol_gated_strict_hit_rows": sym_gated,
        "symbol_gated_strict_hit_rate": round(sym_gated / n, 4),
        "condition_gated_strict_hit_rows": cond_gated,
        "condition_gated_strict_hit_rate": round(cond_gated / n, 4),
        "semantic_hit_rows": cond_gated,
        "semantic_hit_rate": round(cond_gated / n, 4),
        "soft_hit_rows": soft,
        "soft_hit_rate": round(soft / n, 4),
        "exact_rows": exact_n,
        "exact_rate": round(exact_n / n, 4),
        "row_verified_hit_rows": row_verified,
        "row_verified_hit_rate": round(row_verified / n, 4),
        "coarse_rows": coarse_n,
        "miss_rate": round(1 - located / n, 4),
        "match_mode": dict(modes),
        "attribution": dict(primary),
        "symbol_inheritance": {
            "counts": dict(inh_counts),
            "strict_scope_breakdown": inh_scope,
            "demoted_rows": len(demoted),
            "demoted_detail": [
                {"sample_no": d["sample_no"], "gold_key": d["gold_key"],
                 "symbol": d["symbol"], "parent_block_id": d["matched_block_id"],
                 "matched_row_id": d["matched_physical_row_id"],
                 "is_parent_first_row": _is_first(d),
                 "reason": d["symbol_inheritance"]} for d in demoted],
            "strict_if_cross_row_accepted": strict_if_cross_accepted,
            "strict_if_cross_row_accepted_rate": round(strict_if_cross_accepted / n, 4),
            "note": ("符号归属只认三条证据：符号文字在该行 / 符号单元格 bbox 纵向盖住该行 / "
                     "表级 merge_evidence 显式记录。三者全无即判无依据，从严格命中降级为软命中。"
                     "strict_if_cross_row_accepted 是敏感性参考（假设跨行借用可接受），不进主指标。"),
        },
        "condition_attribution": {
            "counts": dict(ca_counts),
            "rows_with_condition": cond_has,
            "row_level_verified": cond_row_level,
            "header_level_verified": sum(1 for d in details if d["hit"] and d["condition_header_match"]),
            "block_level_only": cond_block_only,
            "unresolved": cond_unres,
            "note": ("四层互斥，优先级 row > header > block > unresolved。"
                     "condition 仍不进命中判定，但 block 级不再等同 row 级。"),
            "reference_only": {
                "condition_match": cond_ok,
                "note": "兼容旧字段；等于 cond_probe 在块文本+表头里的粗定位结果，仅供参考",
            },
        },
        "soft_hit_breakdown": dict(soft_reasons),
        "semantic_gate": {
            "ladder": {
                "exact_rows": exact_n,
                "symbol_gated_strict_hit_rows": sym_gated,
                "condition_gated_strict_hit_rows": cond_gated,
            },
            "dropped_by_symbol_gate": exact_n - sym_gated,
            "dropped_by_condition_gate": sym_gated - cond_gated,
            "reason_counts": dict(sem_reasons),
            "condition_miss_kinds": dict(miss_kinds),
            "condition_failed_rows": [
                {"sample_no": d["sample_no"], "gold_key": d["gold_key"],
                 "symbol": d["symbol"], "condition": d["condition"],
                 "condition_attribution": d["condition_attribution"],
                 "kind": d["condition_miss_kind"],
                 "evidence": d["condition_evidence"]} for d in cond_fail],
            "note": ("三级阶梯逐级更严：exact（块级全过）→ symbol_gated（符号归属在命中行可证）"
                     "→ condition_gated（condition 也落在命中行或按列对齐）。"
                     "每行只记一条**首个**阻断原因，见 eval_detail.semantic_hit_reason。"),
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
            "exact_rows": "值/单位/页码/符号（块级）全过，不问证据形态",
            "strict_hit_rows": "exact 且 NOT coarse 且 符号归属在命中物理行上可证（同一行/几何覆盖/显式合并）",
            "symbol_gated_strict_hit": "同 strict_hit_rows，改名为强调「符号归属约束」",
            "condition_gated_strict_hit": "在 symbol_gated 之上再加：Gold condition 非空时必须落在命中行或按列对齐；这是完全语义命中",
            "semantic_hit_reason": "首个阻断原因：not_located / field_mismatch / coarse_block / symbol_not_on_row / condition_not_on_row:<kind>",
            "soft_hit_rows": "exact 但不满足 strict，需人工复核；原因见 soft_hit_breakdown",
            "row_verified_hit_rows": "strict 且 Gold 的数值确实落在被指派的那一物理行上",
            "symbol_inheritance": "符号从哪来：同一行直接命中 / 跨行合并单元格继承 / 无依据跨行继承",
            "condition_attribution": "条件落在哪一层：命中行 / 表头列对齐 / 仅父块他行 / 未定位",
            "condition_row_match": "条件文本出现在 matched_physical_row_id 这一行上",
            "condition_header_match": "条件在表头，且能按列索引对齐到命中行",
            "condition_block_match": "条件只在父块的其他行/整体文本里出现（evidence 列给出位置）",
            "condition_unresolved": "命中行 / 表头 / 父块他行 均找不到",
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
            "hit", "located", "strict_hit", "soft_hit", "exact_hit", "soft_reason",
            "symbol_gated_strict_hit", "condition_gated_strict_hit",
            "semantic_hit_reason", "condition_miss_kind",
            "page_ok", "num_ok", "unit_ok", "unit_strict",
            "row_value_ok", "coarse", "match_mode", "assign_tier",
            "assign_tier_label", "assign_seq", "by_value",
            "symbol_inheritance", "symbol_row_verified", "symbol_carrier_row",
            "condition_row_match", "condition_header_match",
            "condition_block_match", "condition_unresolved",
            "condition_attribution", "condition_evidence",
            "cond_ok", "cond_missing", "primary", "flags", "missing_values",
            "matched_block_id", "matched_physical_row_id", "block_covered_rows",
            "matched_page", "block_rows", "matched_text"]
    detail_rows = []
    for d in details:
        r = dict(d)
        r["located"] = bool(d["hit"])
        detail_rows.append(r)
    C.write_csv_lf(C.OUT_ROOT / "eval_detail.csv", detail_rows, COLS)

    # 软命中单列：exact 但未达 strict 的全部行，附降级原因
    soft_rows = [r for r in detail_rows if r["soft_hit"]]
    C.write_csv_lf(C.OUT_ROOT / "soft_hits.csv", soft_rows, COLS)

    # 符号继承证据：收录「字段全一致、非 coarse、且符号**不在命中行自身**」的全部行。
    #
    # 口径说明（重要）：Reviewer 的字面筛选是「match_mode=text 且命中行不是父块首行」，
    # 实测那样只有 1 行（V146）。但缺陷与 match_mode 无关 —— 15 条 token 模式的
    # 行同样在跨行借符号。只交 1 行等于用筛选条件把 15 条问题藏起来，所以这里
    # 收录全部「需要做符号归属裁定」的行（含首行命中但符号在后续行的 1 条，
    # 含 Gold 无符号的 4 条），并给出 is_parent_first_row / in_reviewer_filter
    # 两列，让任何人都能按自己的口径复现子集。
    INH_COLS = ["sample_no", "gold_key", "symbol", "match_mode",
                "parent_block_id", "parent_first_row", "matched_row_id",
                "is_parent_first_row", "in_reviewer_filter",
                "row_text", "inheritance_type", "symbol_carrier_row",
                "diagnosis", "strict_after_verification",
                "soft_reason", "symbol_cell_y", "symbol_row_y",
                "merge_evidence_n", "recon_status", "basis"]
    inh_rows = []
    for d in details:
        if not (d["exact_hit"] and not d["coarse"]):
            continue
        if d["symbol_inheritance"] == INH_DIRECT:
            continue
        cov = (d["block_covered_rows"] or "").split("|")
        first = cov[0] if cov else ""
        is_first = bool(first) and d["matched_physical_row_id"] == first
        if d["symbol_inheritance"] == INH_NA:
            diag = "Gold 行本身没有符号，走按值兜底，不存在符号归属问题"
        elif is_first:
            diag = ("命中行是父块首行，但符号只出现在后续行 —— "
                    "符号被指派到了不含它的物理行（行指派错位，非合并继承）")
        else:
            diag = ("符号只在父块更靠前的行，命中行自身不含符号 —— "
                    "跨行借用，且无几何/显式合并证据支撑")
        inh_rows.append({
            "sample_no": d["sample_no"], "gold_key": d["gold_key"],
            "symbol": d["symbol"], "match_mode": d["match_mode"],
            "parent_block_id": d["matched_block_id"],
            "parent_first_row": first,
            "matched_row_id": d["matched_physical_row_id"],
            "is_parent_first_row": is_first,
            "in_reviewer_filter": (d["match_mode"] == "text" and not is_first),
            "row_text": d.get("row_text", ""),
            "inheritance_type": d["symbol_inheritance"],
            "symbol_carrier_row": d.get("symbol_carrier_row", ""),
            "diagnosis": diag,
            "strict_after_verification": bool(d["strict_hit"]),
            "soft_reason": d["soft_reason"],
            "symbol_cell_y": d.get("symbol_cell_y", ""),
            "symbol_row_y": d.get("symbol_row_y", ""),
            "merge_evidence_n": d.get("merge_evidence_n", ""),
            "recon_status": d.get("recon_status", ""),
            "basis": d.get("basis", ""),
        })
    C.write_csv_lf(C.OUT_ROOT / "symbol_inheritance_proof.csv", inh_rows, INH_COLS)

    # condition 归属清单：只列「确实带 condition」的已定位行，其余行在 eval_detail 里
    CA_COLS = ["sample_no", "gold_key", "symbol", "condition",
               "matched_block_id", "matched_physical_row_id", "row_text",
               "condition_row_match", "condition_header_match",
               "condition_block_match", "condition_unresolved",
               "condition_attribution", "condition_evidence", "strict_hit"]
    ca_rows = [{
        "sample_no": d["sample_no"], "gold_key": d["gold_key"],
        "symbol": d["symbol"], "condition": d["condition"],
        "matched_block_id": d["matched_block_id"],
        "matched_physical_row_id": d["matched_physical_row_id"],
        "row_text": d.get("row_text", ""),
        "condition_row_match": d["condition_row_match"],
        "condition_header_match": d["condition_header_match"],
        "condition_block_match": d["condition_block_match"],
        "condition_unresolved": d["condition_unresolved"],
        "condition_attribution": d["condition_attribution"],
        "condition_evidence": d["condition_evidence"],
        "strict_hit": bool(d["strict_hit"]),
    } for d in details if d["hit"] and (d["condition"] or "").strip()]
    C.write_csv_lf(C.OUT_ROOT / "condition_attribution.csv", ca_rows, CA_COLS)

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
