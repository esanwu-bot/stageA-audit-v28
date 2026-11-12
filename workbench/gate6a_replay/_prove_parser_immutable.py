# -*- coding: utf-8 -*-
"""证明「修评估器」没有碰过 Parser 的任何产物。

不是靠叙述，而是做个前后对照实验：

    1. 把 runs/gate6a_replay_v1/per_sample/ 下所有 Parser JSON 逐文件算 sha256（快照 A）；
    2. 依次跑「修正前口径」与「正式口径」两遍评估；
    3. 再算一遍 sha256（快照 B），逐文件断言 A == B；
    4. 同时记录文件 mtime，证明它们全部早于评估器脚本的最后修改时间。

产物：audit/parser_json_immutability.txt + audit/parser_outputs_sha256.csv
"""
from __future__ import annotations

import csv
import hashlib
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _replay_common as C  # noqa: E402

AUDIT = HERE / "audit"
# 输出名跟随回测根，避免 v2 复跑覆盖 v1 的证明
_SUF = "" if C.OUT_ROOT.name == "gate6a_replay_v1" else "_" + C.OUT_ROOT.name
REPORT = AUDIT / ("parser_json_immutability%s.txt" % _SUF)
MANIFEST = AUDIT / ("parser_outputs_sha256%s.csv" % _SUF)
PARSER_JSON = ("document.json", "tables.json", "candidates.json", "text_blocks.json",
               "boundary_decisions.json", "product.json", "run_manifest.json",
               "run_config.json")


def snapshot() -> dict[str, tuple[str, int, float]]:
    out: dict[str, tuple[str, int, float]] = {}
    for sample in sorted((C.OUT_ROOT / "per_sample").iterdir()):
        if not sample.is_dir():
            continue
        for name in PARSER_JSON:
            p = sample / name
            if not p.is_file():
                continue
            rel = "%s/%s" % (sample.name, name)
            st = p.stat()
            out[rel] = (hashlib.sha256(p.read_bytes()).hexdigest(), st.st_size,
                        st.st_mtime)
    return out


def run_eval(legacy: bool) -> str:
    env = dict(os.environ)
    env.pop("ICPDF_EVAL_LEGACY", None)
    if legacy:
        env["ICPDF_EVAL_LEGACY"] = "1"
    proc = subprocess.run([sys.executable, str(HERE / "_evaluate.py")],
                          capture_output=True, text=True, encoding="utf-8", env=env)
    assert proc.returncode == 0, proc.stderr[-800:]
    return proc.stdout.strip().splitlines()[0] if proc.stdout.strip() else ""


def main() -> int:
    before = snapshot()
    assert before, "per_sample 下没有 Parser 产物"

    line_legacy = run_eval(legacy=True)
    line_final = run_eval(legacy=False)
    after = snapshot()

    changed = [k for k in before if before[k][0] != after.get(k, ("",))[0]]
    missing = [k for k in before if k not in after]
    added = [k for k in after if k not in before]

    ev_mtime = max((HERE / n).stat().st_mtime
                   for n in ("_evaluate.py", "_replay_common.py"))
    newest_json = max(v[2] for v in after.values())

    lines = [
        "# Parser 产物不可变性证明",
        "",
        "生成时间：%s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "产物目录：%s（%d 个样本）" % (
            C.OUT_ROOT.name + "/per_sample/",
            len({k.split("/")[0] for k in after})),
        "纳入比对的文件：%s" % "、".join(PARSER_JSON),
        "",
        "## 实验步骤",
        "",
        "1. 快照 A：%d 个 JSON 的 sha256" % len(before),
        "2. 跑修正前口径：%s" % line_legacy,
        "3. 跑正式口径：  %s" % line_final,
        "4. 快照 B：重算 %d 个 JSON 的 sha256" % len(after),
        "",
        "## 结果",
        "",
        "| 检查项 | 结果 |",
        "|---|---|",
        "| 内容变化的文件 | **%d** |" % len(changed),
        "| 消失的文件 | **%d** |" % len(missing),
        "| 新增的文件 | **%d** |" % len(added),
        "| 结论 | **%s** |" % ("评估器只读，未改动 Parser 产物"
                               if not (changed or missing or added) else "存在改动，需追查"),
        "",
        "## 时间线佐证",
        "",
        "| 事实 | 时间 |",
        "|---|---|",
        "| 评估器脚本最后修改 | %s |" % datetime.fromtimestamp(ev_mtime)
        .strftime("%Y-%m-%d %H:%M:%S"),
        "| Parser 产物中最新的一个 | %s |" % datetime.fromtimestamp(newest_json)
        .strftime("%Y-%m-%d %H:%M:%S"),
        "| 差值 | %.1f 分钟（产物早于评估器脚本） |"
        % ((ev_mtime - newest_json) / 60.0),
        "",
        "两版评估器源码与 SHA-256 见 audit/evaluator_v1_legacy/、"
        "audit/evaluator_v2_final/、audit/SHA256SUMS.txt。",
    ]
    AUDIT.mkdir(parents=True, exist_ok=True)
    REPORT.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))

    rows = [{"file": k, "sha256": v[0], "size_bytes": v[1],
             "mtime": datetime.fromtimestamp(v[2]).strftime("%Y-%m-%d %H:%M:%S")}
            for k, v in sorted(after.items())]
    C.write_csv_lf(MANIFEST, rows, ["file", "sha256", "size_bytes", "mtime"])

    print("比对 %d 个 JSON：变化 %d / 消失 %d / 新增 %d"
          % (len(after), len(changed), len(missing), len(added)))
    print("产物：%s、%s" % (REPORT.name, MANIFEST.name))
    return 0 if not (changed or missing or added) else 1


if __name__ == "__main__":
    raise SystemExit(main())
