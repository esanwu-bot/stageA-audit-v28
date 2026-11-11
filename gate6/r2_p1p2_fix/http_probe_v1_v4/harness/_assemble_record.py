"""从原始字节装配 probe_record.json（不重发任何请求）。

背景：首轮探针在 ``finally`` 里调用 ``netstat`` 时，因 Windows 中文控制台输出为
GBK、而 ``subprocess.run(text=True)`` 默认按 UTF-8 解码而抛
``UnicodeDecodeError``，导致 ``probe_record.json`` 未落盘。**4 次 HTTP 请求本身
已全部成功且原始响应字节已落盘**，故本脚本只做「从证据重新计算」：

* results  ← ``raw/V*.response.body.json``（响应的原始字节，未经任何重写）
* 环境块   ← ``env/process_env.json``（崩溃前已写入，取自承载探针的 PID 63240）
* after 快照 / 差异 ← 现在扫描（自探针结束以来无新写入，可用 startup.log 佐证）
* 停止记录 ← 以当前实测状态如实登记，并显式标注 taskkill 的 stdout 文本已丢失

任何一项取不到就写 null + note，不补造。
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
RAW = OUT / "raw"
SNAP = OUT / "snapshots"
REPO = Path(r"E:\workspace\icpdf-extractor")
CLASSIFIER = REPO / "src" / "icpdf" / "classification" / "classifier.py"
RUNS = REPO / "workbench" / "runs"
UPLOADS = REPO / "workbench" / "uploads"
PORT = 8765
CST = timezone(timedelta(hours=8))


def now() -> str:
    return datetime.now(CST).isoformat(timespec="seconds")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot(root: Path) -> list[dict]:
    items: list[dict] = []
    if not root.is_dir():
        return items
    for p in sorted(root.rglob("*")):
        if p.is_file():
            st = p.stat()
            items.append({
                "rel": p.relative_to(root).as_posix(),
                "bytes": st.st_size,
                "mtime": datetime.fromtimestamp(st.st_mtime, CST).isoformat(timespec="seconds"),
            })
    return items


def diff(before: list[dict], after: list[dict]) -> dict:
    b = {i["rel"] for i in before}
    a = {i["rel"] for i in after}
    return {
        "added": sorted(a - b), "removed": sorted(b - a),
        "added_count": len(a - b), "removed_count": len(b - a),
        "before_count": len(b), "after_count": len(a),
    }


def netstat_8765() -> str:
    """按字节捕获再解码，避开中文 Windows 的 GBK/UTF-8 冲突。"""
    try:
        done = subprocess.run(["netstat", "-ano"], capture_output=True, timeout=30)
        text = done.stdout.decode("cp936", "replace")
        rows = [ln.strip() for ln in text.splitlines() if (":%d" % PORT) in ln]
        return "\n".join(rows) if rows else "(none)"
    except (OSError, subprocess.SubprocessError) as exc:
        return "(netstat failed: %s)" % exc


def port_listening() -> bool:
    import socket
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=1):
            return True
    except OSError:
        return False


def find_server_pid() -> list[int]:
    found: list[int] = []
    for p in psutil.process_iter():
        try:
            cmd = " ".join(p.cmdline())
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError):
            continue
        if "serve_parser.py" in cmd:
            found.append(p.pid)
    return found


SAMPLES = [
    ("V1", "ADC08060EVM__slau715a.pdf"),
    ("V2", "BQ25570EVM-206__sluuaa7a.pdf"),
    ("V3", "DS10CP154TSQX_NOPB__DS10CP154.pdf"),
    ("V4", "DRV2700EVM__slyu023.pdf"),
]

# 离线全量回归（_d_prime/regression.jsonl）中的既有结论，仅用于对照，不参与断言
OFFLINE_EXPECT = {
    "V1": {"A_before": ("UNKNOWN", "REVIEW", "low", True),
           "D_prime": ("EVM", "QUARANTINE", "high", False),
           "in_193": True, "note": "A→D' 有变化：EVAL_MODULE 组触发抑制"},
    "V2": {"A_before": None, "D_prime": None, "in_193": False,
           "note": "不在 193 条变化集，A 与 D' 相同；响应中无 DS_PRODUCT_MODEL_TITLE 抑制"},
    "V3": {"A_before": ("UNKNOWN", "REVIEW", "low", True),
           "D_prime": ("EVM", "QUARANTINE", "high", False),
           "in_193": True, "note": "A→D' 有变化：SCHEMATIC 单证据即决胜"},
    "V4": {"A_before": None, "D_prime": None, "in_193": False,
           "note": "不在 193 条变化集；但变体 B/F 会把此件泄漏成 DS_STRONG/IC_PARSE"},
}


def main() -> int:
    before_runs = json.loads((SNAP / "runs_before.json").read_text(encoding="utf-8"))
    before_up = json.loads((SNAP / "uploads_before.json").read_text(encoding="utf-8"))
    after_runs = snapshot(RUNS)
    after_up = snapshot(UPLOADS)
    (SNAP / "runs_after.json").write_text(
        json.dumps(after_runs, ensure_ascii=False, indent=1), encoding="utf-8")
    (SNAP / "uploads_after.json").write_text(
        json.dumps(after_up, ensure_ascii=False, indent=1), encoding="utf-8")

    env_full = json.loads((OUT / "env" / "process_env.json").read_text(encoding="utf-8"))
    env_keys = ("ICEX_WORKBENCH_ALLOW_PARSE", "ICEX_CLASSIFY_ONLY", "ICEX_WORKBENCH_PORT",
                "ICEX_WORKBENCH_DEPS", "ICEX_PARSE_TIMEOUT", "ICEX_CLASSIFY_TIMEOUT",
                "ICEX_WORKBENCH_MAX_CONCURRENCY")

    startup = (OUT / "startup.log").read_text(encoding="utf-8", errors="replace")
    post_lines = [ln for ln in startup.splitlines() if "POST /api/process" in ln]
    health_lines = [ln for ln in startup.splitlines() if "GET /api/health" in ln]
    pid_line = next((ln for ln in startup.splitlines() if "Started server process" in ln), "")

    results = []
    for vid, fname in SAMPLES:
        body_raw = (RAW / ("%s.response.body.json" % vid)).read_bytes()
        raw_response = (RAW / ("%s.response.raw" % vid)).read_bytes()
        head_txt = (RAW / ("%s.request.head.txt" % vid)).read_text(encoding="utf-8")
        j = json.loads(body_raw.decode("utf-8"))
        c = j.get("classification") or {}
        p = j.get("parser") or {}
        d = j.get("diagnostics") or {}
        status_line = raw_response.split(b"\r\n", 1)[0].decode("latin-1")
        results.append({
            "id": vid,
            "filename": fname,
            "http_status": int(status_line.split(" ")[1]),
            "status_line": status_line,
            "response_bytes": len(body_raw),
            "raw_response_bytes": len(raw_response),
            "response_sha256": sha256_bytes(body_raw),
            "request_head_sha256": sha256_bytes(head_txt.encode("utf-8")),
            "service_status": j.get("status"),
            "frozen": j.get("frozen"),
            "llm_called": j.get("llm_called"),
            "database_written": j.get("database_written"),
            "classifier_llm_calls": j.get("classifier_llm_calls"),
            "decision": c.get("decision"),
            "doc_type": c.get("doc_type"),
            "route": c.get("route"),
            "confidence": c.get("confidence"),
            "evidence_conflict": c.get("evidence_conflict"),
            "semantic_type": c.get("document_type"),
            "assigned_type": c.get("assigned_type"),
            "classification_status": c.get("classification_status"),
            "read_status": c.get("read_status"),
            "source_hash_status": c.get("source_hash_status"),
            "sha256_matches_upload": c.get("sha256_matches_upload"),
            "source_sha256": c.get("source_sha256"),
            "ic_datasheet_extraction": c.get("ic_datasheet_extraction"),
            "is_confirmed_datasheet": c.get("is_confirmed_datasheet"),
            "admit_to_parser": c.get("admit_to_parser"),
            "classifier_version": c.get("classifier_version"),
            "rule_version": c.get("rule_version"),
            "matched_rules": c.get("matched_rules"),
            "rejected_rules": c.get("rejected_rules"),
            "unmatched_rules": c.get("unmatched_rules"),
            "evidence_pages": c.get("evidence_pages"),
            "gate_failed_checks": [k for k, v in (c.get("gate_checks") or {}).items()
                                   if not v.get("ok")],
            "gate_reasons": c.get("gate_reasons"),
            "parser_called": p.get("called"),
            "parser_status": p.get("status"),
            "parser_reason": p.get("reason"),
            "parser_call_count": p.get("parser_call_count"),
            "parse_pdf_calls": d.get("parse_pdf_calls"),
            "parse_worker_started": d.get("parse_worker_started"),
            "parser_stages_seen": p.get("stages_seen"),
            "classifier_stages": c.get("classifier_stages"),
            "classifier_worker_started": d.get("classifier_worker_started"),
            "safety_blocked": d.get("safety_blocked"),
            "safety_guard_layer": d.get("safety_guard_layer"),
            "offline_expect": OFFLINE_EXPECT[vid],
            "offline_match": (
                None if OFFLINE_EXPECT[vid]["D_prime"] is None else
                (c.get("doc_type"), c.get("route"), c.get("confidence"),
                 c.get("evidence_conflict")) == OFFLINE_EXPECT[vid]["D_prime"]),
        })

    record = {
        "probe": "V1-V4 controlled localhost HTTP probe",
        "generated_at": now(),
        "endpoint": "POST http://127.0.0.1:8765/api/process",
        "transport": "raw socket, HTTP/1.1, Connection: close, 串行 4 次，无并发",
        "phase_a": {
            "role": "承载 4 次探针的服务进程",
            "pid": 63240,
            "pid_evidence": pid_line,
            "launch": "python -u workbench/serve_parser.py",
            "startup_log": "startup.log",
            "health_requests": len(health_lines),
            "process_requests": len(post_lines),
            "process_request_lines": post_lines,
            "python": "3.13.15 (MSC v.1944 64 bit)",
            "frozen_flag_from_startup": "frozen=False",
            "process_env_file": "env/process_env.json",
            "process_env_key_count": len(env_full),
            "process_env_subset": {k: env_full.get(k) for k in env_keys},
            "process_env_source": "psutil.Process(63240).environ()（PEB 读取，非 shell 回显）",
        },
        "phase_a_failure": {
            "what": "harness 在 finally 中调用 netstat 时崩溃",
            "cause": ("subprocess.run(['netstat','-ano'], text=True) 在中文 Windows 上"
                      "以 UTF-8 解码 GBK 输出，抛 UnicodeDecodeError → stdout=None → "
                      "AttributeError，probe_record.json 未落盘"),
            "what_was_lost": ["taskkill 的 stdout 文本", "GET /api/health 的响应体",
                             "首轮内存中的 record 字典"],
            "what_was_not_lost": ["4 次 /api/process 的原始请求头与原始响应字节",
                                  "进程环境块（崩溃前已写入 process_env.json）",
                                  "startup.log（含 PID 与 4 条 POST 记录）",
                                  "before 快照"],
            "remediation": "未重发任何请求；本文件由原始字节重新计算得出",
            "disclosed": True,
        },
        "phase_b": {
            "role": "停止与端口释放的实测状态（探针结束后采集）",
            "collected_at": now(),
            "taskkill_stdout": None,
            "taskkill_note": ("taskkill /PID 63240 /T /F 已在 finally 内执行（该行代码先于崩溃点），"
                              "但其 stdout 文本随崩溃丢失，未做二次执行以免误杀他人进程"),
            "evidence_process_gone": find_server_pid() == [],
            "residual_serve_parser_pids": find_server_pid(),
            "port_listening": port_listening(),
            "netstat_snapshot": netstat_8765(),
            "port_released_conclusion": (not port_listening()) and find_server_pid() == [],
        },
        "snapshot_diff": {
            "runs": diff(before_runs, after_runs),
            "uploads": diff(before_up, after_up),
        },
        "code_state": {
            "repo": str(REPO),
            "git_head": subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                                       capture_output=True, text=True).stdout.strip(),
            "classifier_sha256_now": sha256_file(CLASSIFIER),
            "classifier_sha256_expected": ("28b9f0bfc1b23f27f6b170b00c4651a0"
                                           "ba5a9baad35c375d2434e9fd07ee7d5b"),
        },
        "results": results,
    }
    record["code_state"]["classifier_sha256_match"] = (
        record["code_state"]["classifier_sha256_now"]
        == record["code_state"]["classifier_sha256_expected"])

    (OUT / "probe_record.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    print("port_listening=%s  residual=%s  released=%s"
          % (record["phase_b"]["port_listening"],
             record["phase_b"]["residual_serve_parser_pids"],
             record["phase_b"]["port_released_conclusion"]))
    print("runs  added=%d removed=%d" % (record["snapshot_diff"]["runs"]["added_count"],
                                         record["snapshot_diff"]["runs"]["removed_count"]))
    print("uploads added=%d removed=%d" % (record["snapshot_diff"]["uploads"]["added_count"],
                                           record["snapshot_diff"]["uploads"]["removed_count"]))
    print("classifier match=%s" % record["code_state"]["classifier_sha256_match"])
    for r in results:
        print("%s %s doc_type=%s route=%s conf=%s conflict=%s parser_calls=%s offline_match=%s"
              % (r["id"], r["http_status"], r["doc_type"], r["route"], r["confidence"],
                 r["evidence_conflict"], r["parser_call_count"], r["offline_match"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
