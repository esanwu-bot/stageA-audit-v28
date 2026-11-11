"""在权威仓库执行 Reviewer 指定的 7 条只读核验，原样落盘。

只读保证
--------
本脚本只执行 git 的查询类子命令（remote/status/branch/rev-parse/merge-base/
diff），**不写工作区、不改索引、不建提交、不 push**。``git status`` 会刷新
索引缓存的时间戳（git 自身行为），除此外无任何副作用。

输出格式
--------
每条命令前打印 ``$ <命令>``，紧随其后是合并的 stdout+stderr 原文，
再打印 ``[EXIT=<code>]``。命令之间的分隔线不进入被引用的输出片段，
便于 Reviewer 逐条对照。
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(r"E:\workspace\icpdf-extractor")
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("git_verify_raw.log")
CST = timezone(timedelta(hours=8))

# Reviewer 指定的 7 条，顺序不可改
COMMANDS = [
    ["git", "remote", "-v"],
    ["git", "status", "--short"],
    ["git", "branch", "--show-current"],
    ["git", "rev-parse", "HEAD"],
    ["git", "rev-parse", "main"],
    ["git", "merge-base", "--is-ancestor", "main", "60a503c"],
    ["git", "diff", "--check", "60a503c^", "60a503c"],
]

# 为解释 diff --check 的告警而追加的佐证命令（明确标注为补充项）
SUPPLEMENT = [
    ["git", "merge-base", "main", "60a503c"],
    ["git", "log", "--format=%H %P %s", "-1", "60a503c"],
    ["git", "rev-list", "--count", "main..60a503c"],
    ["git", "log", "--oneline", "-3", "60a503c"],
    ["git", "config", "--get", "core.autocrlf"],
    ["git", "ls-tree", "HEAD", "src/icpdf/classification/.gitattributes"],
]


def run(cmd: list[str]) -> tuple[str, int]:
    done = subprocess.run(cmd, cwd=str(REPO), capture_output=True)
    out = done.stdout + done.stderr
    text = out.decode("utf-8", "replace")
    return text, done.returncode


def main() -> int:
    lines: list[str] = []
    lines.append("Git 祖先关系核验 · 权威仓库 %s" % REPO)
    lines.append("执行时间：%s" % datetime.now(CST).isoformat(timespec="seconds"))
    lines.append("执行方式：只读查询，未写工作区 / 未改索引 / 未提交 / 未 push")
    lines.append("说明：git status 会刷新索引 stat 缓存，属 git 自身行为")
    lines.append("=" * 78)
    lines.append("")
    lines.append("## 一、Reviewer 指定的 7 条命令（顺序原样）")
    lines.append("")

    results: list[tuple[str, int]] = []
    for cmd in COMMANDS:
        text, code = run(cmd)
        shown = " ".join(cmd)
        lines.append("$ " + shown)
        lines.append(text.rstrip("\n") if text.strip() else "(无输出)")
        lines.append("[EXIT=%d]" % code)
        lines.append("")
        results.append((shown, code))

    lines.append("=" * 78)
    lines.append("")
    lines.append("## 二、补充佐证命令（用于解释第 7 条告警，非 Reviewer 要求）")
    lines.append("")
    for cmd in SUPPLEMENT:
        text, code = run(cmd)
        shown = " ".join(cmd)
        lines.append("$ " + shown)
        lines.append(text.rstrip("\n") if text.strip() else "(无输出)")
        lines.append("[EXIT=%d]" % code)
        lines.append("")

    lines.append("=" * 78)
    lines.append("")
    lines.append("## 三、退出码汇总")
    lines.append("")
    for shown, code in results:
        lines.append("%-58s EXIT=%d" % (shown, code))

    body = "\n".join(lines) + "\n"
    OUT.write_text(body, encoding="utf-8", newline="\n")
    print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
