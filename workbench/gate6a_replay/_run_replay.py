# -*- coding: utf-8 -*-
"""24 件 PDF 回测编排器（Reviewer 边界 4：输出隔离）。

每个样本一个子进程（native 崩溃隔离），结果只写
runs/gate6a_replay_v1/per_sample/<sample_no>/，不碰既有 runs 与 Gold 数据。
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _replay_common as C  # noqa: E402

HERE = Path(__file__).resolve().parent
WORKER = HERE / "_run_one.py"


def main() -> int:
    src = C.OUT_ROOT if (C.OUT_ROOT / "input_manifest.json").is_file() else C.BASELINE_ROOT
    manifest = json.loads((src / "input_manifest.json").read_text(encoding="utf-8"))
    entries = manifest["entries"]
    assert len(entries) == C.EXPECT_SAMPLES
    assert manifest["all_sha256_match"], "输入清单哈希不一致，拒绝开跑"

    # `--only V101,V256`：只补跑指定样本，并把结果合并回既有 replay_summary.json。
    # 用于「某件因残留产物/单件预跑需要重跑」的场景，避免整批 24 件重来。
    only: list[str] = []
    if "--only" in sys.argv:
        only = [x.strip() for x in sys.argv[sys.argv.index("--only") + 1].split(",") if x.strip()]
        entries = [e for e in entries if e["sample_no"] in only]
        assert entries, "--only 没有匹配到任何样本：%s" % only

    per_sample = C.OUT_ROOT / "per_sample"
    logs = C.OUT_ROOT / "logs"
    per_sample.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)

    # 边界 4 自检：输出根必须独立，且不得是既有 runs 的一个样本目录。
    # v2 是「修 Parser 后的复跑」，与 v1 基线并存，互不覆盖。
    assert C.OUT_ROOT.name in {"gate6a_replay_v1", "gate6a_replay_v2_postfix"}
    assert C.OUT_ROOT.parent.name == "runs"

    results, t_all = [], time.time()
    for i, e in enumerate(entries, 1):
        sno = e["sample_no"]
        cmd = [sys.executable, str(WORKER),
               "--sample", sno, "--pdf", e["file_path"],
               "--mpn", e["device_model"] or Path(e["file_path"]).stem,
               "--out-root", str(per_sample)]
        t0 = time.time()
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              cwd=str(C.REPO))
        wall = round(time.time() - t0, 2)
        (logs / ("%s.log" % sno)).write_bytes(
            ("CMD: %s\n\nSTDOUT:\n%s\n\nSTDERR:\n%s\n"
             % (" ".join(cmd), proc.stdout, proc.stderr)).encode("utf-8"))
        rec = {"sample_no": sno, "exit_code": proc.returncode,
               "wall_sec": wall, "pages": e["page_count_ledger"],
               "stdout_tail": proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "",
               "stderr_tail": proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else ""}
        results.append(rec)
        flag = "OK " if proc.returncode == 0 else "ERR"
        print("[%2d/%d] %-5s %s %6.2fs  %s" % (i, len(entries), sno, flag, wall,
                                               rec["stdout_tail"][:90]
                                               if proc.returncode == 0
                                               else rec["stderr_tail"][:90]))

    total = round(time.time() - t_all, 2)
    ok = [r for r in results if r["exit_code"] == 0]
    print()
    print("回测完成：%d/%d 成功，总耗时 %.1fs" % (len(ok), len(results), total))

    summary_path = C.OUT_ROOT / "replay_summary.json"
    if only and summary_path.is_file():
        merged = json.loads(summary_path.read_text(encoding="utf-8"))
        fresh = {r["sample_no"]: r for r in results}
        merged["results"] = [fresh.get(r["sample_no"], r) for r in merged["results"]]
        assert len(merged["results"]) == C.EXPECT_SAMPLES
        merged["rerun"] = sorted(fresh)
        merged["ok_count"] = sum(1 for r in merged["results"] if r["exit_code"] == 0)
        merged["total_wall_sec"] = round(merged["total_wall_sec"] + total, 2)
        C.write_json(summary_path, merged)
        results = merged["results"]
    else:
        C.write_json(summary_path, {
            "sample_count": len(results),
            "ok_count": len(ok),
            "total_wall_sec": total,
            "out_root": str(C.OUT_ROOT),
            "results": results,
        })
    with open(C.OUT_ROOT / "replay_log.jsonl", "wb") as fh:
        for r in results:
            fh.write(json.dumps(r, ensure_ascii=False).encode("utf-8") + b"\n")

    bad = [r for r in results if r["exit_code"] != 0]
    if bad:
        print("失败件：%s" % [r["sample_no"] for r in bad])
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
