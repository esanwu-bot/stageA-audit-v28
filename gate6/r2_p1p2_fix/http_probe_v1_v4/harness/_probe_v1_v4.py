"""V1-V4 受控 localhost HTTP 探针（一次性，串行，4 个样本，绝不并发）。

设计要点
--------
1. **裸 socket 收发**：不用 requests / urllib，自己拼请求字节、自己从
   socket 读到底。请求头与响应全部按原始字节落盘，不经任何库的再序列化，
   满足「原样保存、不截断」。
2. **进程环境块取证**：服务由本脚本 spawn，拿到真实 PID；随后用 psutil
   读取该 PID 的 ``environ()``（Windows 下走 PEB），而不是回显当前 shell
   的变量——shell 里 export 过什么并不等于子进程真的收到。
3. **故障时也要收尾**：``finally`` 里 taskkill /T，并轮询 netstat 确认
   8765 释放，避免残留监听进程。
4. **前后快照**：启动前与结束后各扫一次 ``workbench/runs`` 与
   ``workbench/uploads``，只比较路径集合，不做任何写入。

用法：py -3.13 -u _probe_v1_v4.py
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
RAW = OUT / "raw"
SNAP = OUT / "snapshots"
ENVDIR = OUT / "env"
for d in (RAW, SNAP, ENVDIR):
    d.mkdir(parents=True, exist_ok=True)

REPO = Path(r"E:\workspace\icpdf-extractor")
SRC_DIR = REPO / "src"
SERVE = REPO / "workbench" / "serve_parser.py"
RUNS = REPO / "workbench" / "runs"
UPLOADS = REPO / "workbench" / "uploads"
PDF_ROOT = Path(r"E:\workspace\IcPdfParser\data\pdfs")

HOST = "127.0.0.1"
PORT = int(os.getenv("ICEX_WORKBENCH_PORT", "8765"))

CLASSIFIER = SRC_DIR / "icpdf" / "classification" / "classifier.py"
EXPECT_SHA = "28b9f0bfc1b23f27f6b170b00c4651a0ba5a9baad35c375d2434e9fd07ee7d5b"

SAMPLES = [
    ("V1", "ADC08060EVM__slau715a.pdf"),
    ("V2", "BQ25570EVM-206__sluuaa7a.pdf"),
    ("V3", "DS10CP154TSQX_NOPB__DS10CP154.pdf"),
    ("V4", "DRV2700EVM__slyu023.pdf"),
]

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


# ---------------------------------------------------------------- 快照
def snapshot(root: Path) -> list[dict]:
    """只读遍历，记录路径 / 大小 / mtime。不写入被遍历目录。"""
    items: list[dict] = []
    if not root.is_dir():
        return items
    for p in sorted(root.rglob("*")):
        if p.is_file():
            try:
                st = p.stat()
                items.append({
                    "rel": p.relative_to(root).as_posix(),
                    "bytes": st.st_size,
                    "mtime": datetime.fromtimestamp(st.st_mtime, CST).isoformat(timespec="seconds"),
                })
            except OSError as exc:
                items.append({"rel": p.relative_to(root).as_posix(), "error": str(exc)})
    return items


def write_snapshot(name: str, items: list[dict]) -> None:
    (SNAP / name).write_text(
        json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- HTTP
def http_post(path: str, headers: list[tuple[str, str]], body: bytes,
              timeout: float = 180.0) -> dict:
    """最小 HTTP/1.1 客户端：自己拼字节，自己读完，返回原始响应。"""
    head = ["%s %s HTTP/1.1" % ("POST", path)]
    head += ["%s: %s" % (k, v) for k, v in headers]
    head.append("Content-Length: %d" % len(body))
    head.append("Connection: close")
    req_head = ("\r\n".join(head) + "\r\n\r\n").encode("latin-1")

    t0 = time.time()
    with socket.create_connection((HOST, PORT), timeout=15) as s:
        s.settimeout(timeout)
        s.sendall(req_head)
        s.sendall(body)
        chunks: list[bytes] = []
        while True:
            b = s.recv(65536)
            if not b:
                break
            chunks.append(b)
    elapsed = time.time() - t0
    raw = b"".join(chunks)

    sep = raw.find(b"\r\n\r\n")
    if sep < 0:
        raise RuntimeError("响应缺少头体分隔符，原始字节前 200：%r" % raw[:200])
    head_raw, body_raw = raw[:sep], raw[sep + 4:]
    status_line = head_raw.split(b"\r\n", 1)[0].decode("latin-1")
    parts = status_line.split(" ", 2)
    status_code = int(parts[1])
    resp_headers = [ln.decode("latin-1") for ln in head_raw.split(b"\r\n")[1:]]

    # 处理 chunked：本服务走 JSONResponse，通常会带 Content-Length；
    # 若上游改为 chunked，这里如实解码，避免把分块边界当成 JSON 内容。
    encoding = ""
    for ln in resp_headers:
        if ln.lower().startswith("transfer-encoding:") and "chunked" in ln.lower():
            encoding = "chunked"
    if encoding == "chunked":
        decoded, rest, pos = [], body_raw, 0
        while True:
            eol = rest.find(b"\r\n", pos)
            if eol < 0:
                break
            size = int(rest[pos:eol].split(b";")[0], 16)
            if size == 0:
                break
            start = eol + 2
            decoded.append(rest[start:start + size])
            pos = start + size + 2
        body_raw = b"".join(decoded)

    return {
        "request_line": "POST %s HTTP/1.1" % path,
        "request_head_bytes": req_head,
        "request_body": body,
        "status_line": status_line,
        "status_code": status_code,
        "response_headers": resp_headers,
        "response_body_raw": body_raw,
        "raw_response": raw,
        "elapsed_seconds": round(elapsed, 3),
    }


def wait_health(deadline: float = 60.0) -> dict:
    t0 = time.time()
    last = None
    while time.time() - t0 < deadline:
        try:
            with socket.create_connection((HOST, PORT), timeout=2) as s:
                s.settimeout(5)
                s.sendall(b"GET /api/health HTTP/1.1\r\nHost: %s\r\nConnection: close\r\n\r\n"
                          % HOST.encode())
                data = b""
                while True:
                    b = s.recv(65536)
                    if not b:
                        break
                    data += b
            sep = data.find(b"\r\n\r\n")
            return json.loads(data[sep + 4:].decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(0.4)
    raise RuntimeError("健康检查在 %.0fs 内未通过：%r" % (deadline, last))


def port_listening() -> bool:
    try:
        with socket.create_connection((HOST, PORT), timeout=1):
            return True
    except OSError:
        return False


def netstat_8765() -> str:
    """按字节捕获再解码。

    中文 Windows 的 netstat 输出是 GBK；``subprocess.run(text=True)`` 会按
    区域默认或 UTF-8 解码而抛 ``UnicodeDecodeError``，使 ``stdout`` 变成
    ``None``——首轮探针正是栽在这里（详见 HTTP_PROBE_V1_V4_REPORT.md 第 8 节）。
    故此处一律取原始字节，再用 cp936 + replace 解。
    """
    try:
        done = subprocess.run(["netstat", "-ano"], capture_output=True, timeout=20)
        text = done.stdout.decode("cp936", "replace")
        rows = [ln.strip() for ln in text.splitlines() if (":%d" % PORT) in ln]
        return "\n".join(rows) if rows else "(none)"
    except (OSError, subprocess.SubprocessError) as exc:
        return "(netstat failed: %s)" % exc


def find_server_pid() -> int | None:
    """扫描是否有 serve_parser.py 存活。任何单个进程的取信息失败都不得中断扫描。"""
    for proc in psutil.process_iter():
        try:
            cmd = " ".join(proc.cmdline())
        except (psutil.NoSuchProcess, psutil.AccessDenied,
                psutil.ZombieProcess, OSError):
            continue
        if "serve_parser.py" in cmd:
            return proc.pid
    return None


# ---------------------------------------------------------------- 主流程
def main() -> int:
    started_at = now()
    # ---- 0. 代码哈希（启动前）
    pre_sha = sha256_file(CLASSIFIER)

    # ---- 1. 快照
    runs_before = snapshot(RUNS)
    uploads_before = snapshot(UPLOADS)
    write_snapshot("runs_before.json", runs_before)
    write_snapshot("uploads_before.json", uploads_before)

    env = dict(os.environ)
    env["ICEX_WORKBENCH_ALLOW_PARSE"] = "1"
    env["ICEX_CLASSIFY_ONLY"] = "1"
    env["ICEX_WORKBENCH_PORT"] = str(PORT)
    # 确保没有被外部意外继承的冻结开关覆盖
    assert env["ICEX_WORKBENCH_ALLOW_PARSE"] == "1"

    log_path = OUT / "startup.log"
    log_f = log_path.open("wb")
    log_f.write(("[%s] launch: %s -u %s\n" % (started_at, sys.executable, SERVE)).encode())
    log_f.write(("[%s] env ICEX_WORKBENCH_ALLOW_PARSE=%s ICEX_CLASSIFY_ONLY=%s ICEX_WORKBENCH_PORT=%s\n"
                 % (now(), env["ICEX_WORKBENCH_ALLOW_PARSE"], env["ICEX_CLASSIFY_ONLY"],
                    env["ICEX_WORKBENCH_PORT"])).encode())
    log_f.flush()

    proc = subprocess.Popen(
        [sys.executable, "-u", str(SERVE)],
        cwd=str(REPO), env=env,
        stdout=log_f, stderr=subprocess.STDOUT,
    )
    pid = proc.pid
    record: dict = {
        "started_at": started_at,
        "python": sys.executable,
        "pid": pid,
        "host": HOST,
        "port": PORT,
        "classifier_sha256_before": pre_sha,
        "classifier_sha256_expected": EXPECT_SHA,
        "classifier_sha256_match_before": pre_sha == EXPECT_SHA,
    }

    results: list[dict] = []
    try:
        health = wait_health()
        record["health"] = health
        record["listening_after_health"] = port_listening()

        # ---- 2. 进程环境块（真实 PID，不是 shell 回显）
        #      【安全】绝不 dump 全量环境。父进程是 IDE，含 GEMINI_API_KEY /
        #      CODEBUDDY_GATEWAY_PASSWORD / WORKBUDDY_*_TOKEN 等与探针无关的凭据。
        #      走 _env_redact.redact_env() 的白名单 + 兜底闸，见该模块文档。
        try:
            p = psutil.Process(pid)
            real_env = p.environ()
            redacted = redact_env(real_env)
            record["process_env_source"] = "psutil.Process(%d).environ() via PEB" % pid
            record["process_env_policy"] = redacted["policy"]
            record["process_env_subset"] = {
                k: v["value"] for k, v in redacted["vars"].items()
            }
            record["process_env_redacted_keys"] = sorted(
                k for k, v in redacted["vars"].items() if v["redacted"])
            record["process_env_omitted_count"] = redacted["omitted_count"]
            record["process_env_omitted_name_prefixes"] = redacted["omitted_name_prefixes"]
            record["process_env_key_count_total"] = len(real_env)
            record["process_cmdline"] = p.cmdline()
            record["process_create_time"] = datetime.fromtimestamp(
                p.create_time(), CST).isoformat(timespec="seconds")
            (ENVDIR / "process_env.json").write_text(
                json.dumps(redacted, ensure_ascii=False, indent=1, sort_keys=True),
                encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            record["process_env_error"] = "%s: %s" % (type(exc).__name__, exc)

        # ---- 3. 串行探针
        for vid, fname in SAMPLES:
            pdf = PDF_ROOT / fname
            body = pdf.read_bytes()
            headers = [
                ("Host", "%s:%d" % (HOST, PORT)),
                ("Content-Type", "application/pdf"),
                ("Accept", "application/json"),
                ("x-filename", fname),
            ]
            r = http_post("/api/process", headers, body)

            (RAW / ("%s.response.raw" % vid)).write_bytes(r["raw_response"])
            (RAW / ("%s.response.body.json" % vid)).write_bytes(r["response_body_raw"])
            (RAW / ("%s.request.head.txt" % vid)).write_text(
                r["request_head_bytes"].decode("latin-1")
                + "<<<BODY: %d bytes, raw PDF bytes sent verbatim, sha256=%s>>>\n"
                % (len(body), sha256_bytes(body)),
                encoding="utf-8")

            try:
                js = json.loads(r["response_body_raw"].decode("utf-8"))
                json_ok = True
            except Exception as exc:  # noqa: BLE001
                js = {}
                json_ok = False
                record.setdefault("json_parse_errors", {})[vid] = "%s: %s" % (
                    type(exc).__name__, exc)

            cls = js.get("classification") or {}
            parser = js.get("parser") or {}
            diag = js.get("diagnostics") or {}
            results.append({
                "id": vid,
                "filename": fname,
                "pdf_path": str(pdf),
                "pdf_bytes": len(body),
                "pdf_sha256": sha256_bytes(body),
                "http_status": r["status_code"],
                "status_line": r["status_line"],
                "json_valid": json_ok,
                "elapsed_seconds": r["elapsed_seconds"],
                "response_bytes": len(r["response_body_raw"]),
                "status": js.get("status"),
                "decision": cls.get("decision"),
                "doc_type": cls.get("doc_type"),
                "route": cls.get("route"),
                "confidence": cls.get("confidence"),
                "evidence_conflict": cls.get("evidence_conflict"),
                "semantic_type": cls.get("document_type"),
                "classification_status": cls.get("classification_status"),
                "read_status": cls.get("read_status"),
                "source_hash_status": cls.get("source_hash_status"),
                "sha256_matches_upload": cls.get("sha256_matches_upload"),
                "ic_datasheet_extraction": cls.get("ic_datasheet_extraction"),
                "admit_to_parser": cls.get("admit_to_parser"),
                "matched_rules": cls.get("matched_rules"),
                "rejected_rules": cls.get("rejected_rules"),
                "unmatched_rules": cls.get("unmatched_rules"),
                "evidence_pages": cls.get("evidence_pages"),
                "classifier_version": cls.get("classifier_version"),
                "rule_version": cls.get("rule_version"),
                "classifier_called": js.get("classifier_called"),
                "gate_failed_checks": [k for k, v in (cls.get("gate_checks") or {}).items()
                                       if not v.get("ok")],
                "parser_called": parser.get("called"),
                "parser_status": parser.get("status"),
                "parser_reason": parser.get("reason"),
                "parser_call_count": parser.get("parser_call_count"),
                "parse_worker_started": diag.get("parse_worker_started"),
                "parse_pdf_calls": diag.get("parse_pdf_calls"),
                "classifier_worker_started": diag.get("classifier_worker_started"),
                "stages_seen": parser.get("stages_seen"),
                "classifier_stages": cls.get("classifier_stages"),
                "safety_blocked": diag.get("safety_blocked"),
                "safety_guard_layer": diag.get("safety_guard_layer"),
                "frozen": js.get("frozen"),
                "llm_called": js.get("llm_called"),
                "database_written": js.get("database_written"),
                "classifier_llm_calls": js.get("classifier_llm_calls"),
            })
            print("[%s] %s -> status=%s decision=%s doc_type=%s route=%s conf=%s conflict=%s "
                  "parser_calls=%s worker_started=%s %ss"
                  % (vid, fname, js.get("status"), cls.get("decision"), cls.get("doc_type"),
                     cls.get("route"), cls.get("confidence"), cls.get("evidence_conflict"),
                     parser.get("parser_call_count"), diag.get("parse_worker_started"),
                     r["elapsed_seconds"]), flush=True)
    finally:
        # ---- 4. 停止（taskkill /T）
        kill_out = ""
        try:
            done = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                                  capture_output=True, text=True, timeout=30)
            kill_out = (done.stdout + done.stderr).strip()
        except Exception as exc:  # noqa: BLE001
            kill_out = "taskkill failed: %s: %s" % (type(exc).__name__, exc)
        try:
            proc.wait(timeout=15)
        except Exception:  # noqa: BLE001
            pass
        log_f.flush()
        log_f.close()

        released = False
        for _ in range(50):
            if not port_listening():
                released = True
                break
            time.sleep(0.2)

        record["stop"] = {
            "taskkill_output": kill_out,
            "returncode": proc.returncode,
            "port_released": released,
            "netstat_after": netstat_8765(),
            "residual_serve_parser_pid": find_server_pid(),
            "stopped_at": now(),
        }

        # ---- 5. 后快照与差异
        runs_after = snapshot(RUNS)
        uploads_after = snapshot(UPLOADS)
        write_snapshot("runs_after.json", runs_after)
        write_snapshot("uploads_after.json", uploads_after)

        def diff(before: list[dict], after: list[dict]) -> dict:
            b = {i["rel"] for i in before}
            a = {i["rel"] for i in after}
            return {"added": sorted(a - b), "removed": sorted(b - a),
                    "added_count": len(a - b), "removed_count": len(b - a),
                    "before_count": len(b), "after_count": len(a)}

        record["snapshot_diff"] = {
            "runs": diff(runs_before, runs_after),
            "uploads": diff(uploads_before, uploads_after),
        }
        record["classifier_sha256_after"] = sha256_file(CLASSIFIER)
        record["classifier_sha256_unchanged"] = (
            record["classifier_sha256_after"] == pre_sha)

    record["results"] = results
    record["finished_at"] = now()
    (OUT / "probe_record.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nDONE  pid=%s  port_released=%s" % (pid, record["stop"]["port_released"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
