#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨层血缘验证：给定 run_id，把 eval → parse → raw 串起来并逐层校验。

校验的不是「文件存在」，而是「四层引用是否自洽」：

    eval.json.run_id            == parse_layer/<run_id>/run_manifest.json.run_id
    parse.run_manifest.source_sha256 == raw_layer/<sha256>/RAW.json.source_sha256
    raw 文件实际 sha256          == 该目录名（内容寻址，目录名即哈希）
    eval.gold_version           == eval_layer/gold/<version>/ 存在
    eval.evaluator_fingerprint  == 当前 _evaluate.py 的 sha256

任何一条不成立就退出码 1。用法：
    py -3.13 lake/_verify_lineage.py                 # 校验全部 run
    py -3.13 lake/_verify_lineage.py --run-id XXXX
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

LAKE = Path(__file__).resolve().parent
REPO = LAKE.parent
EVALUATOR = REPO / "workbench" / "gate6a_replay" / "audit" / "evaluator_v3_1to1" / "_evaluate.py"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Fail(Exception):
    pass


def check(cond: bool, msg: str) -> None:
    if not cond:
        raise Fail(msg)
    print(f"  ok   {msg}")


def verify(run_id: str) -> None:
    print(f"\n== run_id = {run_id}")
    pdir = LAKE / "parse_layer" / run_id
    man_p = pdir / "run_manifest.json"
    check(man_p.is_file(), f"parse_layer/{run_id}/run_manifest.json 存在")
    man = json.loads(man_p.read_text(encoding="utf-8"))

    check(man["run_id"] == run_id, "manifest.run_id 与目录名一致")
    check(man["source_sha256"] == man["reproducibility"]["source_sha256"],
          "source_sha256 在顶层与 reproducibility 块中一致")

    # raw 层：内容寻址，目录名就是哈希
    sha = man["source_sha256"]
    raw_dir = LAKE / "raw_layer" / sha
    check(raw_dir.is_dir(), f"raw_layer/{sha[:12]}… 存在（目录名 = 内容哈希）")
    pdfs = [p for p in raw_dir.iterdir() if p.suffix.lower() == ".pdf"]
    check(len(pdfs) == 1, "raw 层该哈希下恰有 1 个 PDF")
    actual = sha256(pdfs[0])
    check(actual == sha, "raw 文件实算 sha256 == 目录名（未被篡改）")
    raw_meta = json.loads((raw_dir / "RAW.json").read_text(encoding="utf-8"))
    check(raw_meta["source_sha256"] == sha, "RAW.json 记录的哈希与目录名一致")

    # eval 层：版本引用
    ev_p = LAKE / "eval_layer" / run_id / "eval.json"
    check(ev_p.is_file(), f"eval_layer/{run_id}/eval.json 存在")
    ev = json.loads(ev_p.read_text(encoding="utf-8"))
    check(ev["run_id"] == run_id, "eval.run_id 与 parse.run_id 一致（跨层主键）")
    check(ev["source_sha256"] == sha, "eval.source_sha256 指回 raw（跨层外键）")

    gdir = LAKE / "eval_layer" / "gold" / ev["gold_version"]
    check(gdir.is_dir(), f"Gold 版本目录 {ev['gold_version']} 存在")
    gman = json.loads((gdir / "GOLD_MANIFEST.json").read_text(encoding="utf-8"))
    for f in gman["files"]:
        got = sha256(gdir / f["file"])
        if got != f["sha256"]:
            raise Fail(f"Gold 文件被改动：{f['file']}")

    check(sha256(EVALUATOR) == ev["evaluator_fingerprint"],
          "评估器指纹与当前 _evaluate.py 一致（评估层可复现）")

    print(f"  链条：{run_id} → raw {sha[:12]}… → {ev['gold_version']} → "
          f"semantic {ev['metrics']['semantic_hit_rate']:.2%}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args()

    if args.run_id:
        ids = [args.run_id]
    else:
        ids = sorted(p.name for p in (LAKE / "parse_layer").iterdir()
                     if (p / "run_manifest.json").is_file())
    if not ids:
        print("没有可校验的 run", file=sys.stderr)
        return 1

    failed = 0
    for rid in ids:
        try:
            verify(rid)
        except Fail as e:
            print(f"  FAIL {e}", file=sys.stderr)
            failed += 1
    print(f"\n校验 {len(ids)} 个 run，失败 {failed} 个")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
