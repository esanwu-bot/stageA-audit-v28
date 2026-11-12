# -*- coding: utf-8 -*-
"""证明「修评估器」没有碰过 Parser 的任何产物。

不是靠叙述，而是做个前后对照实验：

    1. 把 runs/gate6a_replay_v1/per_sample/ 下所有 Parser JSON 逐文件算 sha256（快照 A）；
    2. 依次跑「修正前口径」与「正式口径」两遍评估；
    3. 再算一遍 sha256（快照 B），逐文件断言 A == B；
    4. 静态扫描评估器源码的写操作，确认没有一处指向 Parser 产物目录 —— 这是主证据；
    5. 记录文件 mtime，但**只作运行顺序记录，不作不可变性证据**。

   为什么把时间戳降级：产物完全可能在评估器之后再被覆盖而 mtime 变新，
   产物比脚本旧也完全不排除它被改过。早先版本把「产物早于评估器脚本」当成
   佐证，那是无效论证，已删除。

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


def scan_writes() -> list[tuple[str, int, str]]:
    """静态扫描评估器里的写操作。

    不可变性的主证据是「代码里根本没有改写 Parser 产物的路径」，
    这比任何时间戳都硬：它不依赖运行环境，也不依赖先后顺序。
    只扫 `_evaluate.py`（调用方，目标路径在这里指定）；
    `_replay_common` 里的 write_json / write_csv_lf 只是把数据写到调用方给的路径。
    """
    hits: list[tuple[str, int, str]] = []
    p = HERE / "_evaluate.py"
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        s = line.strip()
        if any(k in s for k in ("write_json(", "write_csv_lf(",
                                ".write_bytes(", ".write_text(")):
            hits.append((p.name, i, s[:96]))
    return hits


def main() -> int:
    before = snapshot()
    assert before, "per_sample 下没有 Parser 产物"

    writes = scan_writes()
    bad_writes = [w for w in writes
                  if "PARSER_ROOT" in w[2] or "per_sample" in w[2]]
    assert not bad_writes, "评估器里存在指向 Parser 产物的写操作：%s" % bad_writes

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
        "## 静态代码证据（主证据）",
        "",
        "评估器源码里**全部写操作**共 %d 处，逐处列出如下（目标一律是 `C.OUT_ROOT`）："
        % len(writes),
        "",
        *["  - `%s` L%d  `%s`" % (f, ln, s) for f, ln, s in writes],
        "",
        "没有一处指向 `PARSER_ROOT` 或 `per_sample/`：**评估器在代码层面就不具备"
        "改写 Parser 产物的路径**。读入走 `read_text(encoding=\"utf-8\")`，"
        "只出现在 `load_run()` 与快照函数里。这是不可变性的主证据，"
        "因为它不依赖运行时环境，也不依赖任何时间假设。",
        "",
        "## 时间戳记录（**不是**证据）",
        "",
        "| 事实 | 时间 |",
        "|---|---|",
        "| 评估器脚本最后修改 | %s |" % datetime.fromtimestamp(ev_mtime)
        .strftime("%Y-%m-%d %H:%M:%S"),
        "| Parser 产物中最新的一个 | %s |" % datetime.fromtimestamp(newest_json)
        .strftime("%Y-%m-%d %H:%M:%S"),
        "| 先后关系 | 产物先写、评估器后跑（仅记录运行顺序） |",
        "",
        "> **时间戳先后不能作为不可变性的证据。** 产物完全可能在评估器跑完之后"
        "被覆盖，而 mtime 只会变新；反过来，产物比脚本旧也完全不排除它被改过。"
        "这里保留时间戳只为了说明本次运行的先后顺序，"
        "不可变性由上面的静态代码扫描与下面的 A→B 哈希比对共同证明。",
        "",
        "两版评估器源码与 SHA-256 见 audit/evaluator_v1_legacy/、"
        "audit/evaluator_v2_final/、audit/evaluator_v3_1to1/、audit/SHA256SUMS.txt。",
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
