# -*- coding: utf-8 -*-
"""记录 G7b 合入的终端证据（只读命令，逐条记录退出码）。

在本地权威仓库 E:\\workspace\\icpdf-extractor 执行，输出写入本目录
g7b_merge_raw.log。合并前的数值来自合并动作当时的人工记录，写在本脚本的
PRE_MERGE 常量中；合并后数值由本脚本现场执行取得。
"""
from __future__ import print_function

import datetime
import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(r"E:\workspace\icpdf-extractor")
OUT = Path(__file__).resolve().parent / "g7b_merge_raw.log"

# 合并动作发生当时现场记录的值（不可事后重算，只能引用）
PRE_MERGE = {
    "main_sha": "6f3e58d51e6e4278e623171251f055474de8ae0a",
    "head_sha": "60a503cc8015ef9bfb27ddef1685e41593f3a75f",
    "branch": "feat/s2b-schema-d4-d6",
    "commits_ahead": "17",
    "commits_behind": "0",
    "classifier_py_sha256":
        "28b9f0bfc1b23f27f6b170b00c4651a0ba5a9baad35c375d2434e9fd07ee7d5b",
    "cli_py_sha256":
        "c288bffa1d0ac87d31624b3b9727dc23f5f3c51f7d8905625cb68d77c7f3a2a4",
    "r1_supplement_sha256":
        "e9c766500d3d28e292d302465b95b5c4c3018e9ac710c50c51314c52c2311ae7",
}

COMMANDS = [
    ("1", "git rev-parse main"),
    ("2", "git rev-parse HEAD"),
    ("3", "git rev-parse --abbrev-ref HEAD"),
    ("4", "git status --porcelain=v1"),
    ("5", "git -c core.whitespace=cr-at-eol diff --check 60a503c^ 60a503c"),
    ("6", "git merge-base --is-ancestor 60a503c main"),
    ("7", "git rev-list --count main..60a503c"),
    ("8", "git rev-list --count 60a503c..main"),
    ("9", "git log -1"),
    ("10", "git log --oneline -5"),
]


def sha256_of(path):
    p = REPO / path
    if not p.exists():
        return "MISSING"
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    lines = []
    w = lines.append
    w("=" * 78)
    w("G7b 合入终端证据（只读命令逐条执行）")
    w("repo      : %s" % REPO)
    w("recorded  : %s" % datetime.datetime.now().isoformat(timespec="seconds"))
    w("=" * 78)
    w("")
    w("### 合并动作发生当时现场记录（PRE-MERGE，不可事后重算）")
    for k, v in PRE_MERGE.items():
        w("  %-24s %s" % (k, v))
    w("")

    w("### 合并后现场执行（POST-MERGE）")
    rc_all = 0
    for tag, cmd in COMMANDS:
        w("")
        w("$ %s" % cmd)
        proc = subprocess.run(cmd, cwd=str(REPO), shell=True,
                              capture_output=True)
        out = proc.stdout.decode("utf-8", "replace")
        err = proc.stderr.decode("utf-8", "replace")
        if out:
            w(out.rstrip("\n"))
        if err:
            w("[STDERR]")
            w(err.rstrip("\n"))
        w("[EXIT=%d]" % proc.returncode)
        if proc.returncode != 0:
            rc_all = rc_all or proc.returncode

    w("")
    w("### 合并后关键文件 SHA-256（工作区实测）")
    for rel in ("src/icpdf/classification/classifier.py",
                "src/icpdf/cli.py",
                "workbench/_classifier_revision/R1_PRIME_SUPPLEMENT.md"):
        w("  %-56s %s" % (rel, sha256_of(rel)))

    w("")
    w("### HEAD 中 classifier.py 对象哈希（不读工作区）")
    proc = subprocess.run("git rev-parse HEAD:src/icpdf/classification/classifier.py",
                          cwd=str(REPO), shell=True, capture_output=True)
    w("  %s" % proc.stdout.decode("utf-8", "replace").strip())

    text = "\n".join(lines) + "\n"
    OUT.write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
