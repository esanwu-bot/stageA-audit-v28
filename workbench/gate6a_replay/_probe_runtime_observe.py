# -*- coding: utf-8 -*-
"""运行时「零网络调用」取证：跑一件真实样本，记录审计事件与已加载模块。

回答两个问题：

  1. 解析过程中到底有没有发生网络尝试？
     用「只观察不拦截」的审计钩子记录全部 socket / 子进程事件。
     计数为 0 说明是「根本没发生」，而不是「发生了但被拦住」。

  2. 解析链路是否把网络库拉进了内存？
     解析结束后检查 sys.modules，看有没有 socket-aware 的库被导入。

用法：
  python _probe_runtime_observe.py --sample V256 --pdf <path>
  python _probe_runtime_observe.py --sample V256 --pdf <path> --json
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

import _no_llm_guard as guard  # noqa: E402

# 只要进了内存就值得记录的模块（不是全部都会被用到，但一旦出现必须解释）
SUSPECT = ("socket", "ssl", "http", "urllib", "urllib3", "requests", "httpx",
           "ftplib", "smtplib", "poplib", "imaplib", "telnetlib", "aiohttp",
           "openai", "anthropic", "dashscope", "zhipuai", "cohere", "litellm",
           "grpc", "boto3", "botocore")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", required=True)
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    # 先清凭据，再装「只观察」钩子
    removed = guard.scrub_env()
    seen = guard.observe()

    before = set(sys.modules)

    from icpdf.parser.pipeline import parse_pdf

    import tempfile
    out_root = Path(tempfile.mkdtemp(prefix="observe_%s_" % args.sample))
    result = {}
    try:
        with contextlib.suppress(Exception):
            result = parse_pdf(args.pdf, sample_mpn(args.sample), out_root,
                               run_id=args.sample)
    finally:
        loaded = sorted({m.split(".")[0] for m in sys.modules} & set(SUSPECT))
        # 把事件分成「真正出网」与「本地 socket 调用」两类：
        # gethostname / __new__ / bind / getsockname 都不会产生任何网络 I/O。
        OUTBOUND = {"socket.getaddrinfo", "socket.gethostbyname",
                    "socket.gethostbyaddr", "socket.connect",
                    "socket.create_connection", "urllib.Request",
                    "http.client.connect", "ftplib.connect", "smtplib.connect",
                    "subprocess.Popen", "os.system", "os.exec",
                    "os.posix_spawn", "os.spawn", "os.fork"}
        observed = seen["events"]
        outbound = [e for e in observed if e in OUTBOUND]
        local = [e for e in observed if e not in OUTBOUND]
        payload = {
            "sample": args.sample,
            "env_scrubbed": removed,
            "events_total": seen["count"],
            "outbound_events": outbound,
            "local_events": local,
            "events_all": observed,
            "suspect_modules_loaded": loaded,
            "urllib_submodules": sorted(m for m in sys.modules
                                        if m == "urllib" or m.startswith("urllib.")),
            "modules_loaded_during_parse": sorted(
                {m.split(".")[0] for m in set(sys.modules) - before} & set(SUSPECT)),
            "page_count": result.get("page_count"),
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print("样本 %s" % args.sample)
            print("  凭据清理        : %d 个" % len(removed))
            print("  真正出网事件    : %d 次 %s"
                  % (len(outbound), outbound[:10] or "无"))
            print("  本地 socket 调用: %d 次 %s" % (len(local), local[:10] or "无"))
            print("  urllib 子模块   : %s" % (payload["urllib_submodules"] or "无"))
            print("  可疑模块（全程）: %s" % (loaded or "无"))
            print("  解析期间新加载  : %s"
                  % (payload["modules_loaded_during_parse"] or "无"))
            print("  页数            : %s" % result.get("page_count"))
    return 0


def sample_mpn(sample: str) -> str:
    """从 v1 清单里取 MPN；取不到就用样本号。"""
    from pathlib import Path as _P
    man = REPO / "runs" / "gate6a_replay_v1" / "input_manifest.json"
    if man.exists():
        data = json.loads(man.read_text(encoding="utf-8"))
        for item in data.get("entries", []):
            if item.get("sample_no") == sample:
                return item.get("mpn") or sample
    return sample


if __name__ == "__main__":
    raise SystemExit(main())
