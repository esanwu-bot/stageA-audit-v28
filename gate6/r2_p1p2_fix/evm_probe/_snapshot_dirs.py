"""目录快照：记录文件数、总字节、逐个文件的 sha256/size/mtime，并给出汇总指纹。

前后两次快照必须用同一脚本，避免口径不一致。
用法：py -3.13 _snapshot_dirs.py <输出文件>
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKBENCH = HERE.parent          # uploads/ 与 runs/ 都在 workbench/ 下
TARGETS = {
    "uploads": WORKBENCH / "uploads",
    "runs": WORKBENCH / "runs",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def snap(root: Path) -> dict:
    if not root.exists():
        return {"exists": False, "file_count": 0, "total_bytes": 0,
                "dir_count": 0, "files": [], "rollup_sha256": None}
    files = []
    dirs = 0
    for p in sorted(root.rglob("*")):
        if p.is_dir():
            dirs += 1
            continue
        st = p.stat()
        files.append({
            "rel": str(p.relative_to(root)).replace("\\", "/"),
            "size": st.st_size,
            "mtime": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(st.st_mtime)),
            "sha256": sha256_file(p),
        })
    # 汇总指纹：对 (rel, sha256) 排序后拼接再取 sha256，任何增删改都会改变它
    rollup = hashlib.sha256(
        "\n".join("%s %s" % (f["rel"], f["sha256"]) for f in files).encode()
    ).hexdigest()
    return {
        "exists": True,
        "file_count": len(files),
        "total_bytes": sum(f["size"] for f in files),
        "dir_count": dirs,
        "files": files,
        "rollup_sha256": rollup,
    }


def main(argv: list[str]) -> int:
    out = Path(argv[1]) if len(argv) > 1 else HERE / "_snapshot.json"
    data = {
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
        "captured_at_epoch": int(time.time()),
        "root": str(WORKBENCH),
        "targets": {name: snap(path) for name, path in TARGETS.items()},
    }
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    for name, s in data["targets"].items():
        print("%-8s exists=%s files=%d dirs=%d bytes=%d rollup=%s"
              % (name, s["exists"], s["file_count"], s["dir_count"],
                 s["total_bytes"], (s["rollup_sha256"] or "-")[:16]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
