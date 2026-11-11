# -*- coding: utf-8 -*-
"""远端推送前只读核验：记录 Reviewer 指定的九条命令的完整输出与退出码。

约束
----
* 只读：不 fetch、不改任何 ref、不动工作区。
  因此 `origin/main` 是**上次 fetch 时**的快照，结果里显式打印其提交时间，
  并用 `git ls-remote`（纯查询，不写 ref）取远端当前真实指向作为对照。
* `git remote -v` 的输出若含凭据，一律脱敏为 `https://***@host/...`。
  脱敏在**写盘之前**完成，因此落盘文件里不含明文。
"""
from __future__ import print_function

import datetime
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(r"E:\workspace\icpdf-extractor")
OUT = Path(__file__).resolve().parent
LOG = OUT / "push_review_raw.log"

# 形如 <scheme>://<userinfo>@<host> 的 URL：把 userinfo 整段替换为 ***。
# 注意这里不写具体的 userinfo 样例字符串，避免本文件自身被凭据扫描器命中，
# 从而使"0 命中"保持可信信号。
CRED_RE = re.compile(r"(https?://)[^/@\s]+@")


def redact(text):
    return CRED_RE.sub(r"\1***@", text)


def run(args):
    """执行命令，返回 (合并后的输出, 退出码)。"""
    proc = subprocess.run(args, cwd=str(REPO), shell=False,
                          capture_output=True)
    out = proc.stdout.decode("utf-8", "replace")
    err = proc.stderr.decode("utf-8", "replace")
    merged = out
    if err.strip():
        merged += ("\n[STDERR]\n" if merged.strip() else "") + err
    return redact(merged).rstrip("\n"), proc.returncode


COMMANDS = [
    ("1", ["git", "remote", "-v"],
     "列出远端及其 URL（已脱敏）"),
    ("2", ["git", "branch", "--show-current"],
     "当前分支"),
    ("3", ["git", "rev-parse", "main"],
     "本地 main 指向"),
    ("4", ["git", "rev-parse", "origin/main"],
     "远端跟踪分支 origin/main 指向（上次 fetch 快照）"),
    ("5", ["git", "merge-base", "--is-ancestor", "origin/main", "main"],
     "origin/main 是否为 main 的祖先；0=是（可快进），1=否"),
    ("6", ["git", "log", "--oneline", "--decorate", "origin/main..main"],
     "领先远端的提交清单"),
    ("7", ["git", "diff", "--stat", "origin/main..main"],
     "领先提交的改动统计"),
    ("8", ["git", "diff", "--name-status", "origin/main..main"],
     "领先提交的逐文件状态"),
    ("9", ["git", "status", "--porcelain=v1"],
     "工作区状态"),
]

SUPPLEMENT = [
    ("S1", ["git", "ls-remote", "origin", "main"],
     "远端真实指向（纯查询，不写 ref），用于校验 origin/main 是否过期"),
    ("S2", ["git", "log", "-1", "--format=%H%n%ci%n%s", "origin/main"],
     "origin/main 的提交哈希/时间/标题"),
    ("S3", ["git", "rev-list", "--count", "origin/main..main"],
     "领先提交数"),
    ("S4", ["git", "rev-list", "--count", "main..origin/main"],
     "落后提交数（应为 0）"),
]


def main():
    lines = []
    w = lines.append
    w("=" * 78)
    w("远端推送前只读核验")
    w("repo     : %s" % REPO)
    w("recorded : %s" % datetime.datetime.now().isoformat(timespec="seconds"))
    w("note     : 本次未执行 git fetch；origin/main 为上次 fetch 的快照，")
    w("           远端真实指向见补充项 S1。remote URL 中的凭据已脱敏。")
    w("=" * 78)

    codes = {}
    for tag, args, desc in COMMANDS:
        w("")
        w("### [%s] %s" % (tag, desc))
        w("$ %s" % " ".join(args))
        out, rc = run(args)
        if out:
            w(out)
        else:
            w("(no output)")
        w("[EXIT=%d]" % rc)
        codes[tag] = rc

    w("")
    w("-" * 78)
    w("### 补充核验（用于判断 origin/main 是否过期，不改任何 ref）")
    for tag, args, desc in SUPPLEMENT:
        w("")
        w("### [%s] %s" % (tag, desc))
        w("$ %s" % " ".join(args))
        out, rc = run(args)
        if out:
            w(out)
        else:
            w("(no output)")
        w("[EXIT=%d]" % rc)
        codes[tag] = rc

    text = "\n".join(lines) + "\n"
    LOG.write_text(text, encoding="utf-8", newline="\n")

    print(redact(text))
    print()
    print("exit_codes:", codes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
