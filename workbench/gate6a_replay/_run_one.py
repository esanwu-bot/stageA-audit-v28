# -*- coding: utf-8 -*-
"""单件回测 worker：装 LLM 硬禁用闸 -> 解析一件 PDF -> 落盘。

由 _run_replay.py 以子进程方式拉起，保证单件 native 崩溃不牵连整批。
用法：
  python _run_one.py --sample V101 --pdf <path> --mpn CD74HCT574 --out-root <dir>
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _no_llm_guard as guard  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", required=True)
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--mpn", default="")
    ap.add_argument("--out-root", required=True)
    args = ap.parse_args()

    # 边界 3：环境锁 + 运行时锁，必须在 import 解析器之前装上
    removed = guard.scrub_env()
    stats = guard.install()

    repo = HERE.parents[1]
    sys.path.insert(0, str(repo / "src"))

    from icpdf.parser.pipeline import parse_pdf

    out_root = Path(args.out_root)
    t0 = time.time()
    record = {"sample_no": args.sample, "pdf": args.pdf, "ok": False}
    try:
        result = parse_pdf(args.pdf, args.mpn or Path(args.pdf).stem,
                           out_root, run_id=args.sample)
        record.update({
            "ok": True,
            "run_dir": str(out_root / args.sample),
            "elapsed_sec": round(time.time() - t0, 2),
            "page_count": result.get("page_count"),
            "parser_version": result.get("parser_version", ""),
        })
    except Exception as exc:                      # noqa: BLE001
        record.update({"ok": False, "error": "%s: %s" % (type(exc).__name__, exc),
                       "elapsed_sec": round(time.time() - t0, 2)})
        raise
    finally:
        record["llm"] = {
            "blocked_events": stats["blocked"],
            "events": stats["events"][:20],
            "env_scrubbed": removed,
        }
        (out_root / args.sample).mkdir(parents=True, exist_ok=True)
        (out_root / args.sample / "_worker_record.json").write_bytes(
            json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")

    print(json.dumps({"sample_no": args.sample,
                      "ok": record["ok"],
                      "elapsed_sec": record["elapsed_sec"],
                      "page_count": record.get("page_count"),
                      "llm_blocked": stats["blocked"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
