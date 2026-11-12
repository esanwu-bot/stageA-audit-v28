# -*- coding: utf-8 -*-
"""回测四条硬边界的机检断言。

报告里的每句话都要能被一条断言支撑。本脚本只读，不修任何东西：

    边界 1  环境与版本：commit / python / parser 包指纹 均与快照一致
    边界 2  输入白名单：24 件、哈希逐一比对、Gold 105 行
    边界 3  LLM 硬禁用：每个成功样本 blocked_events == 0，且装闸自测能拦住出站
    边界 4  输出隔离  ：产物只在 runs/gate6a_replay_v1/，Gold 台账与历史 runs 未被改写

任何一条不满足即非零退出。
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _replay_common as C  # noqa: E402
import _no_llm_guard as G  # noqa: E402

FAIL: list[str] = []


def check(cond: bool, label: str, detail: str = "") -> None:
    print("%s  %s%s" % ("PASS" if cond else "FAIL", label,
                        ("  [%s]" % detail) if detail else ""))
    if not cond:
        FAIL.append(label)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    env = json.loads((C.OUT_ROOT / "env_snapshot.json").read_text(encoding="utf-8"))
    man = json.loads((C.OUT_ROOT / "input_manifest.json").read_text(encoding="utf-8"))
    summ = json.loads((C.OUT_ROOT / "replay_summary.json").read_text(encoding="utf-8"))
    metrics = json.loads((C.OUT_ROOT / "metrics.json").read_text(encoding="utf-8"))

    print("\n=== 边界 1：环境与版本 ===")
    check(len(env["git"]["commit"]) == 40, "commit SHA 完整",
          env["git"]["commit_short"])
    check(env["python"]["version"].startswith("3.13"), "Python 3.13.x",
          env["python"]["version"])
    check(env["parser_code"]["parser_untouched"] is True, "解析链路未改动",
          env["parser_code"]["parser_package_sha256"][:12])
    check(env["parser_code"]["parser_file_count"] == 27, "parser 包文件数 27")
    # 配置哈希与磁盘上的一致性
    cfg = C.REPO / env["parser_config"]["path"]
    check(cfg.is_file() and sha(cfg) == env["parser_config"]["sha256"],
          "parser.yaml 磁盘哈希 == 快照哈希")

    print("\n=== 边界 2：输入白名单 ===")
    entries = man["entries"]
    check(man["sample_count"] == C.EXPECT_SAMPLES == len(entries),
          "样本数 24", str(len(entries)))
    check(man["all_sha256_match"] is True, "全部 SHA-256 与台账一致")
    check(man["gold_row_count"] == C.EXPECT_ROWS, "Gold 行数 105",
          str(man["gold_row_count"]))
    bad = []
    for e in entries:
        p = Path(e["file_path"])
        if not p.is_file() or sha(p) != e["sha256_ledger"]:
            bad.append(e["sample_no"])
    check(not bad, "逐件重算哈希 == 台账哈希", ",".join(bad) or "24/24")

    print("\n=== 边界 3：LLM 硬禁用 ===")
    ok_samples = [r["sample_no"] for r in summ["results"] if r["exit_code"] == 0]
    blocked, missing = [], []
    for sno in ok_samples:
        rec = C.OUT_ROOT / "per_sample" / sno / "_worker_record.json"
        if not rec.is_file():
            missing.append(sno)
            continue
        llm = json.loads(rec.read_text(encoding="utf-8")).get("llm") or {}
        blocked.append(llm.get("blocked_events"))
        if llm.get("env_scrubbed") is None:
            missing.append(sno)
    check(not missing, "每个成功样本都有 llm 记录", ",".join(missing) or "23/23")
    check(set(blocked) == {0}, "blocked_events 全为 0",
          "取值集合 %s，合计 %s" % (sorted(set(blocked)), sum(x or 0 for x in blocked)))
    check(all(not (json.loads((C.OUT_ROOT / "per_sample" / s / "_worker_record.json")
                              .read_text(encoding="utf-8")).get("llm") or {}).get("events")
              for s in ok_samples), "拦截事件明细为空（无任何出站尝试）")
    # 装闸自测：装钩子后主动出站必须被拦
    G.scrub_env()
    G.install()
    try:
        import socket
        socket.getaddrinfo("example.com", 443)
        self_ok = False
    except RuntimeError:
        self_ok = True
    check(self_ok, "装闸自测：主动出站被 RuntimeError 拦下")

    print("\n=== 边界 4：输出隔离 ===")
    check(C.OUT_ROOT.name == "gate6a_replay_v1", "输出根目录名正确")
    # 本断言守的是「v1 那次运行没有溢出到 runs/ 的其它目录」。
    # 之后经授权的产物目录单独登记，不算违规，但要显式列出来，不能被静默忽略。
    #
    # gate6a_replay_v3_1to1 是 v3 评估器的输出根（一对一消费匹配）。
    # 它只读 v2 冻结产物、只写自己这个目录，登记在此是为了让白名单保持穷举，
    # 而不是为了让断言变松 —— 任何未登记的新目录仍然会判失败。
    FOLLOWUP = {"gate6a_replay_v2_postfix", "gate6a_v256_probe",
                "gate6a_replay_v3_1to1"}
    outside = [p for p in (C.REPO / "runs").iterdir()
               if p.is_dir() and p.name not in FOLLOWUP
               and p.name != "gate6a_replay_v1"
               and p.stat().st_mtime > datetime.fromisoformat(
                   env["captured_at"]).timestamp()]
    check(not outside, "runs/ 下其他目录未在本次运行中被改写（已登记后续授权目录）",
          ",".join(sorted(p.name for p in outside)) or "无溢出")
    seen = sorted(p.name for p in (C.REPO / "runs").iterdir()
                  if p.is_dir() and p.name in FOLLOWUP)
    print("       已知后续产物目录：%s" % (",".join(seen) or "无"))
    log_ts = sorted((C.OUT_ROOT / "logs").glob("*.log"))
    t0 = min(p.stat().st_mtime for p in log_ts) if log_ts else \
        datetime.fromisoformat(env["captured_at"]).timestamp()
    touched = [p.name for p in C.PREP.iterdir()
               if p.is_file() and p.stat().st_mtime > t0]
    check(not touched, "Gold 台账目录 _gate6a_prep/ 未被写入",
          ",".join(touched) or "0 个文件")
    for name in ("Batch3_B4_FINAL.xlsx", "Batch3_B4_FINAL.csv",
                 "Gold_Set_v1.1_WORKING.csv"):
        p = C.PREP / name
        check(p.is_file() and p.stat().st_mtime <= t0, "未改写 %s" % name)
    # 签字件与派生 CSV 的哈希是硬事实，不靠 mtime 推断
    check(sha(C.PREP / "Batch3_B4_FINAL.xlsx")
          == "685caff0da9c568658057c5b2d1a4949abea506589de12846709e78d984bd28e",
          "PM 签字件 xlsx 哈希未变")
    check(sha(C.PREP / "Batch3_B4_FINAL.csv")
          == "096ff7c068d01bbedeb0d392e1df9bad12e47baa0c45acfe3fe28ef2618927f9",
          "B4 派生 CSV 哈希未变")

    print("\n=== 指标自洽 ===")
    att = metrics["attribution"]
    # 兼容 v3 改名：hit_rows → located_rows
    _loc = metrics.get("located_rows", metrics.get("hit_rows"))
    check(sum(att.values()) == metrics["gold_rows"],
          "归因各类之和 == Gold 行数",
          "%d == %d" % (sum(att.values()), metrics["gold_rows"]))
    check(_loc >= metrics["exact_rows"], "定位行 >= 严格命中行")
    detail = list(__import__("csv").DictReader(open(
        C.OUT_ROOT / "eval_detail.csv", encoding="utf-8-sig", newline="")))
    check(len(detail) == C.EXPECT_ROWS, "eval_detail 行数 105", str(len(detail)))
    check(sum(1 for r in detail if r["hit"] == "True") == _loc,
          "eval_detail 定位数与 metrics 一致")

    print("\n" + ("全部断言通过" if not FAIL else "失败 %d 项：%s" % (len(FAIL), FAIL)))
    return 0 if not FAIL else 1


if __name__ == "__main__":
    raise SystemExit(main())
