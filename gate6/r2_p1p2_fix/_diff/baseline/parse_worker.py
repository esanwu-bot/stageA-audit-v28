"""Ds Bit · Parser Lab 单件解析子进程（冻结期只写代码，不执行）。

职责：
1. 以显式路径注入隔离依赖与仓库源码，调用唯一正式入口
   icpdf.parser.pipeline.parse_pdf()，不复制、不改写任何 Parser 逻辑。
2. 用唯一哨兵包裹 JSON 载荷，避免 PyMuPDF C 层把 "MuPDF error: ..."
   写到 fd 1 时污染 stdout（Gate 0/1 已实测过该问题）。
3. 脚本本身不负责超时；由 serve_parser.py 的父进程 communicate(timeout)
   + kill() 强杀，崩溃时父进程按「无有效载荷」判为 PARSE_CRASH。

本文件不 import fastapi、不接入 LLM、不连数据库、不写 PostgreSQL。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BEGIN = "__ICEX_PARSE_JSON_BEGIN__"
END = "__ICEX_PARSE_JSON_END__"


def _emit(payload: dict) -> None:
    """载荷写入后立即 flush，保证父进程能拿到完整 JSON。"""
    sys.stdout.write(BEGIN + "\n")
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.write(END + "\n")
    sys.stdout.flush()


def main(argv: list[str]) -> None:
    spec = json.loads(argv[1])
    src_dir = Path(spec["src_dir"])
    deps_raw = spec.get("deps_dir")
    deps_dir = Path(deps_raw) if deps_raw else None

    # 红线：PyYAML 必须来自隔离目录，禁止悄悄回退到全局 site-packages。
    if deps_dir is None or not (deps_dir / "yaml" / "__init__.py").is_file():
        raise RuntimeError(
            "隔离依赖目录不可用：PyYAML 必须来自 runs/stage_a_350/gate6a/_deps；"
            "拒绝回退到全局环境，也拒绝在冻结期安装依赖"
        )
    sys.path.insert(0, str(deps_dir))
    sys.path.insert(0, str(src_dir))

    import yaml  # noqa: F401  仅用于核实加载路径

    loaded = Path(yaml.__file__).resolve()
    if deps_dir.resolve() not in loaded.parents:
        raise RuntimeError(
            "yaml 实际加载自 %s，不在隔离目录 %s 内；拒绝执行解析"
            % (loaded, deps_dir.resolve())
        )

    from icpdf.parser.pipeline import parse_pdf

    result = parse_pdf(
        pdf_path=spec["pdf_path"],
        requested_mpn=spec["requested_mpn"],
        runs_root=spec["runs_root"],
        run_id=spec["run_id"],
    )
    _emit({"ok": True, "result": result})


if __name__ == "__main__":
    try:
        main(sys.argv)
    except Exception as exc:  # noqa: BLE001  需把异常类型与文本回传给父进程分类
        _emit({"ok": False, "error_type": type(exc).__name__, "error": str(exc)})
        sys.exit(1)
