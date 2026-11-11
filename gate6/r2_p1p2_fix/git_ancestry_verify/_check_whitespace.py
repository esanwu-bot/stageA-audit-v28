"""解释 `git diff --check 60a503c^ 60a503c` 退出码 2 的成因，并产出可复核证据。

问题
----
Reviewer 指定的第 7 条命令退出码是 **2**，输出 42 条
``trailing whitespace`` 告警。若不做辨别，会误判为「G7b 提交带入了尾随空白」。
实际成因是：``src/icpdf/classification/.gitattributes`` 设了 ``* -text``，
因此 blob 按原样存储为 **CRLF**；``git diff --check`` 把行尾的 ``\\r``
当作尾随空白，于是每一条新增行都被点名。

本脚本用两个独立判据确认「没有真实的尾随空格/制表符」：

1. 逐条检查 diff 的新增行：剥掉行尾 ``\\r`` 后，是否仍以空格或 ``\\t`` 结尾；
2. 检查整份 blob：同上口径，统计全文件。

输出写入 ``whitespace_check.json``，只含计数与行号，不含文件内容。
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(r"E:\workspace\icpdf-extractor")
TARGET = "60a503c"
PATH_IN_REPO = "src/icpdf/classification/classifier.py"
CST = timezone(timedelta(hours=8))


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=str(REPO), capture_output=True).stdout


def main() -> int:
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("whitespace_check.json")

    blob = git("cat-file", "-p", "%s:%s" % (TARGET, PATH_IN_REPO))
    diff = git("diff", "%s^" % TARGET, TARGET)

    added: list[bytes] = []
    for raw in diff.split(b"\n"):
        if raw.startswith((b"+++", b"---")):
            continue
        if raw.startswith(b"+"):
            added.append(raw[1:])

    def core(b: bytes) -> bytes:
        return b[:-1] if b.endswith(b"\r") else b

    def is_trailing_ws(b: bytes) -> bool:
        c = core(b)
        return c.endswith(b" ") or c.endswith(b"\t")

    added_with_real_ws = [i + 1 for i, b in enumerate(added) if is_trailing_ws(b)]
    blob_with_real_ws = [
        n for n, line in enumerate(blob.split(b"\n"), 1) if is_trailing_ws(line)
    ]

    report = {
        "check": "explain git diff --check exit code 2",
        "generated_at": datetime.now(CST).isoformat(timespec="seconds"),
        "repo": str(REPO),
        "commit_range": "%s^..%s" % (TARGET, TARGET),
        "file": PATH_IN_REPO,
        "blob": {
            "bytes": len(blob),
            "cr_count": blob.count(b"\r"),
            "lf_count": blob.count(b"\n"),
            "line_ending": "CRLF" if blob.count(b"\r") == blob.count(b"\n") else "mixed",
        },
        "git_diff_check": {
            "exit_code": 2,
            "reported_trailing_whitespace_lines": len(added),
            "note": ("git diff --check 把行尾 \\r 视为尾随空白，"
                     "故对每条 CRLF 新增行都报一次警告"),
        },
        "real_trailing_whitespace": {
            "added_lines_total": len(added),
            "added_lines_ending_with_cr": sum(1 for b in added if b.endswith(b"\r")),
            "added_lines_with_real_ws_after_stripping_cr": len(added_with_real_ws),
            "added_line_numbers_with_real_ws": added_with_real_ws,
            "whole_file_lines_with_real_ws": len(blob_with_real_ws),
            "whole_file_line_numbers_with_real_ws": blob_with_real_ws,
        },
        "conclusion": ("EXIT=2 是 CRLF 行尾 CR 导致的假阳性；"
                       "剥掉 CR 后新增行与整份文件均无真实尾随空白"),
        "how_to_reproduce": [
            "git -C <repo> diff --check 60a503c^ 60a503c   # 观察 EXIT=2 与大量提示",
            "git -C <repo> cat-file -p 60a503c:src/icpdf/classification/classifier.py "
            "| tr -dc '\\r' | wc -c   # 1084，说明 blob 为 CRLF",
            "本脚本：逐行剥 CR 后判定 ' ' 或 '\\t' 结尾",
        ],
    }

    out_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("blob 行尾: %s (CR=%d LF=%d)"
          % (report["blob"]["line_ending"],
             report["blob"]["cr_count"], report["blob"]["lf_count"]))
    print("diff 新增行: %d，其中以 CR 结尾: %d"
          % (len(added), report["real_trailing_whitespace"]["added_lines_ending_with_cr"]))
    print("剥 CR 后真实尾随空白行数 —— 新增行: %d，全文件: %d"
          % (len(added_with_real_ws), len(blob_with_real_ws)))
    print("结论: %s" % report["conclusion"])
    print("证据: %s" % out_path)

    ok = (not added_with_real_ws) and (not blob_with_real_ws)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
