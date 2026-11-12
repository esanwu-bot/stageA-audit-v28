# -*- coding: utf-8 -*-
"""Reviewer 边界 1 + 2：环境版本快照、24 件输入清单与哈希校验。

产出（全部落在 runs/gate6a_replay_v1/）：
  env_snapshot.json     Git commit / 脏文件 / Python / 依赖 / parser 配置全文与哈希
  input_manifest.csv    24 件：路径、实算 SHA-256、台账 SHA-256、是否一致
  input_manifest.json   同上，附每件的 Gold 行数与来源批次
"""
from __future__ import annotations

import json
import platform
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _replay_common as C  # noqa: E402


def sh(*args: str) -> str:
    return subprocess.run(args, cwd=str(C.REPO), capture_output=True,
                          text=True, encoding="utf-8").stdout.strip()


def dep_versions() -> dict:
    out = {}
    for mod in ("pymupdf", "pydantic", "typer", "yaml", "rich", "PIL"):
        try:
            m = __import__(mod)
            out[mod] = getattr(m, "__version__", None) or getattr(m, "version", None) \
                or getattr(m, "__doc__", "").strip().splitlines()[0][:60]
        except Exception as exc:                  # noqa: BLE001
            out[mod] = "MISSING: %s" % type(exc).__name__
    return {k: str(v) for k, v in out.items()}


def parser_code_fingerprint() -> dict:
    """解析链路的代码指纹。

    工作区有 197 个未提交改动，但 Reviewer 关心的是「跑的是哪份代码」。
    这里把 src/ 下实际改动列出来，并对 src/icpdf/parser/ 做整体指纹；
    parser_untouched=True 才说明本次回测解析链路与 commit a11131a 逐字节一致。
    """
    changed_src = [x for x in sh("git", "status", "--porcelain", "--", "src/").splitlines()
                   if x.strip()]
    parser_dir = C.REPO / "src" / "icpdf" / "parser"
    items = []
    for p in sorted(parser_dir.glob("*.py")):
        items.append("%s  %s" % (p.name, C.sha256_file(p)))
    return {
        "changed_files_under_src": changed_src,
        "parser_untouched": not any("src/icpdf/parser/" in x for x in changed_src),
        "parser_file_count": len(items),
        "parser_package_sha256": C.sha256_bytes("\n".join(items).encode("utf-8")),
        "files": items,
    }


def main() -> int:
    C.OUT_ROOT.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(C.REPO / "src"))

    import fitz
    import icpdf
    from icpdf.parser.config import load_config

    cfg_path = C.REPO / "configs" / "parser.yaml"
    cfg, cfg_sha = load_config(cfg_path)

    # ---------------- 环境快照 ----------------
    snapshot = {
        "captured_at": __import__("datetime").datetime.now().astimezone().isoformat(),
        "git": {
            "repo": str(C.REPO),
            "branch": sh("git", "rev-parse", "--abbrev-ref", "HEAD"),
            "commit": sh("git", "rev-parse", "HEAD"),
            "commit_short": sh("git", "rev-parse", "--short", "HEAD"),
            "commit_subject": sh("git", "log", "-1", "--pretty=%s"),
            "dirty_files": [x for x in sh("git", "status", "--porcelain").splitlines()
                            if x.strip()],
        },
        "python": {
            "version": sys.version.split()[0],
            "full": sys.version.replace("\n", " "),
            "executable": sys.executable,
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "dependencies": dep_versions(),
        "pymupdf": {
            # PyMuPDF 2.x 的包版本与底层 binding 版本不是一个数，两个都记下来，
            # 免得上游复现时按错的那个去装。
            "package_version": str(getattr(__import__("pymupdf"), "__version__", "")),
            "version": str(getattr(fitz, "version", None)),
            "binding": str(getattr(fitz, "VersionBind", "")),
        },
        "icpdf": {
            "package_version": getattr(icpdf, "__version__", ""),
            "parser_version": getattr(icpdf, "PARSER_VERSION", ""),
            "contract_version": "data-contract/v0.2",
        },
        "parser_config": {
            "path": str(cfg_path.relative_to(C.REPO)).replace("\\", "/"),
            "sha256": cfg_sha,
            "content": cfg_path.read_text(encoding="utf-8"),
        },
        "parser_code": parser_code_fingerprint(),
        "llm": {
            "disabled_by": "audit_hook + env_scrub",
            "env_vars_present": [v for v in
                                 ("DASHSCOPE_API_KEY", "OPENAI_API_KEY",
                                  "ICPDF_LLM_MODEL", "ICPDF_LLM_BASE_URL")
                                 if v in __import__("os").environ],
        },
        "output_root": str(C.OUT_ROOT),
    }
    C.write_json(C.OUT_ROOT / "env_snapshot.json", snapshot)
    print("环境快照：%s" % (C.OUT_ROOT / "env_snapshot.json"))
    print("  commit   %s %s" % (snapshot["git"]["commit_short"],
                                snapshot["git"]["commit_subject"]))
    print("  python   %s（%s）" % (snapshot["python"]["version"],
                                   snapshot["python"]["executable"]))
    print("  pymupdf  %s" % snapshot["pymupdf"]["version"])
    print("  config   %s sha256=%s…" % (snapshot["parser_config"]["path"],
                                        cfg_sha[:16]))
    pc = snapshot["parser_code"]
    print("  parser   %d 个 .py 包指纹 %s…  解析链路未改动=%s"
          % (pc["parser_file_count"], pc["parser_package_sha256"][:16],
             pc["parser_untouched"]))
    if pc["changed_files_under_src"]:
        print("  src/ 下未提交改动：%s" % pc["changed_files_under_src"])
    if snapshot["git"]["dirty_files"]:
        print("  注意：工作区有 %d 个未提交改动" % len(snapshot["git"]["dirty_files"]))
        for d in snapshot["git"]["dirty_files"][:5]:
            print("         %s" % d)

    # ---------------- 输入清单 ----------------
    ledger = C.load_ledger()
    gold = C.load_gold()
    per_sample: dict[str, list[dict]] = {}
    for r in gold:
        per_sample.setdefault(r["sample_no"], []).append(r)

    rows, problems = [], []
    for sno in sorted(per_sample):
        meta = ledger.get(sno)
        if not meta:
            problems.append("%s 不在台账里" % sno)
            continue
        path = Path(meta["file_path"])
        if not path.is_file():
            problems.append("%s PDF 不存在：%s" % (sno, path))
            continue
        actual = C.sha256_file(path)
        expect = (meta.get("pdf_sha256") or "").strip().lower()
        device = ""
        for r in per_sample[sno]:
            if r.get("device_model"):
                device = r["device_model"]
                break
        rows.append({
            "sample_no": sno,
            "file_name": path.name,
            "file_path": str(path),
            "size_bytes": path.stat().st_size,
            "page_count_ledger": meta.get("page_count", ""),
            "sha256_actual": actual,
            "sha256_ledger": expect,
            "sha256_match": "TRUE" if actual == expect else "FALSE",
            "device_model": device,
            "gold_rows": len(per_sample[sno]),
            "gold_batches": "+".join(sorted({r["_batch"] for r in per_sample[sno]})),
        })
        if actual != expect:
            problems.append("%s 哈希不符：实际 %s / 台账 %s" % (sno, actual[:16],
                                                              expect[:16] or "(空)"))

    cols = ["sample_no", "file_name", "file_path", "size_bytes",
            "page_count_ledger", "sha256_actual", "sha256_ledger",
            "sha256_match", "device_model", "gold_rows", "gold_batches"]
    C.write_csv_lf(C.OUT_ROOT / "input_manifest.csv", rows, cols)
    C.write_json(C.OUT_ROOT / "input_manifest.json", {
        "generated_at": __import__("datetime").datetime.now().astimezone().isoformat(),
        "sample_count": len(rows),
        "gold_row_count": sum(r["gold_rows"] for r in rows),
        "all_sha256_match": all(r["sha256_match"] == "TRUE" for r in rows),
        "entries": rows,
    })

    print()
    print("输入清单：%d 件 / %d 行 Gold → %s"
          % (len(rows), sum(r["gold_rows"] for r in rows),
             C.OUT_ROOT / "input_manifest.csv"))
    if problems:
        print("发现问题 %d 项：" % len(problems))
        for p in problems:
            print("  ! %s" % p)
        return 1

    assert len(rows) == C.EXPECT_SAMPLES, "样本数 %d ≠ 24" % len(rows)
    assert sum(r["gold_rows"] for r in rows) == C.EXPECT_ROWS
    assert all(r["sha256_match"] == "TRUE" for r in rows)
    print("校验：24 件全部存在，SHA-256 与台账逐一一致，Gold 合计 105 行")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
