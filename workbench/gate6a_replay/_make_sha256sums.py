"""重生成 audit/SHA256SUMS.txt。

为什么要有这个脚本：手工维护清单一定会漂移。审计包的价值在于「别人能复算」，
所以清单本身也必须是可复算产物，而不是一次性的手工快照。

分组规则（顺序固定，保证两次运行逐字节相同）：
  1. 冻结评估器快照（每个版本的 .py）
  2. 审计证据文件（audit/ 顶层，不含本清单自身）
  3. v3 产物（artifacts/v3_*）
  4. 回测对照产物（artifacts/ 其余文件）
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

AUDIT = Path(__file__).resolve().parent / "audit"
ARTIFACTS = AUDIT.parent / "artifacts"
OUT = AUDIT / "SHA256SUMS.txt"

EVAL_DIRS = ["evaluator_v1_legacy", "evaluator_v2_final", "evaluator_v3_1to1"]

HEADER = """\
# 冻结评估器与审计产物的 SHA-256
# 由 workbench/gate6a_replay/_make_sha256sums.py 生成，请勿手工编辑。
# 校验方式（在 audit/ 目录下执行）：sha256sum -c SHA256SUMS.txt
# 注意：清单内路径均相对于 audit/，artifacts/ 是兄弟目录，故写作 ../artifacts/。
# 本文件不含空行：sha256sum 会把空行报成 increasingly formatted，干扰人工判读。
"""


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def emit(lines: list[str], title: str, entries: list[tuple[str, Path]]) -> None:
    """写一个分段。entries 已按 rel 路径排好序。"""
    if not entries:
        return
    lines.append(f"# {title}")
    for rel, path in entries:
        lines.append(f"{sha256(path)}  {rel}")


def main() -> int:
    if not AUDIT.is_dir():
        print(f"找不到审计目录：{AUDIT}", file=sys.stderr)
        return 2

    lines = [HEADER.rstrip("\n")]

    # 1. 冻结评估器快照
    for d in EVAL_DIRS:
        base = AUDIT / d
        if not base.is_dir():
            print(f"警告：缺少评估器快照目录 {d}", file=sys.stderr)
            continue
        files = sorted(p for p in base.rglob("*.py") if p.is_file())
        emit(lines, f"冻结评估器快照：{d}", [(str(p.relative_to(AUDIT)).replace("\\", "/"), p) for p in files])

    # 2. 审计证据文件（顶层，只取文件，不含子目录、不含本清单）
    top = sorted(
        p for p in AUDIT.iterdir()
        if p.is_file() and p.name != OUT.name and not p.name.startswith(".")
    )
    emit(lines, "审计证据文件（本目录）", [(p.name, p) for p in top])

    # 3. v3 产物
    if ARTIFACTS.is_dir():
        v3 = sorted(p for p in ARTIFACTS.glob("v3_*") if p.is_file())
        emit(lines, "v3 评估产物（一对一消费匹配）", [(f"../artifacts/{p.name}", p) for p in v3])

        # 4. 回测对照产物
        others = sorted(
            p for p in ARTIFACTS.iterdir()
            if p.is_file() and not p.name.startswith("v3_") and not p.name.startswith(".")
        )
        emit(lines, "回测对照产物（v1 / v2 冻结，作为比对输入）",
             [(f"../artifacts/{p.name}", p) for p in others])

    text = "\n".join(lines) + "\n"
    OUT.write_text(text, encoding="utf-8", newline="\n")

    n = sum(1 for ln in text.splitlines() if ln and not ln.startswith("#"))
    print(f"SHA256SUMS.txt 已重写：{n} 个文件 -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
