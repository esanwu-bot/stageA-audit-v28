"""从两份原始响应中抽取安全字段与分类明细，生成核对表。

只读：不启动服务、不调用任何解析/分类入口。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKBENCH = HERE.parent

SAMPLES = {
    "A": {
        "label": "ADC08060EVM__slau715a.pdf",
        "src": Path(r"E:\workspace\IcPdfParser\data\pdfs\ADC08060EVM__slau715a.pdf"),
        "expect_sha": "09fabc2407fc5834f77c40b6f8a2b5bfb012caa983ac2724c950f9224a4c02ca",
        "resp": HERE / "10_A_response.json",
        "upload": WORKBENCH / "uploads/WB-20261111-083501-561e/938d90a7087b4c7b8753b256976a487a.pdf",
    },
    "B": {
        "label": "BQ25570EVM-206__sluuaa7a.pdf",
        "src": Path(r"E:\workspace\IcPdfParser\data\pdfs\BQ25570EVM-206__sluuaa7a.pdf"),
        "expect_sha": "60aac1d0cad5e571feac7949f882b25a8eaaad814b190cbec333e7c0b5bb8d2e",
        "resp": HERE / "20_B_response.json",
        "upload": WORKBENCH / "uploads/WB-20261111-083551-ac06/69e9840756e148d7ada388a99ad417c3.pdf",
    },
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pick(d: dict, key: str, default="-"):
    return d.get(key, default)


def extract(tag: str, meta: dict) -> dict:
    raw = meta["resp"].read_bytes()
    d = json.loads(raw.decode("utf-8"))
    p = d.get("parser") or {}
    diag = d.get("diagnostics") or {}
    c = d.get("classification") or {}
    return {
        "tag": tag,
        "sample": meta["label"],
        "source_sha256": sha256_file(meta["src"]),
        "expect_sha256": meta["expect_sha"],
        "source_sha_match": sha256_file(meta["src"]) == meta["expect_sha"],
        "upload_path": str(meta["upload"].relative_to(WORKBENCH)).replace("\\", "/"),
        "upload_sha256": sha256_file(meta["upload"]),
        "upload_sha_match_source": sha256_file(meta["upload"]) == sha256_file(meta["src"]),
        "response_file": meta["resp"].name,
        "response_bytes": len(raw),
        "response_sha256": hashlib.sha256(raw).hexdigest(),
        "request_id": d.get("request_id"),
        "status": d.get("status"),
        "frozen": d.get("frozen"),
        # --- 5 项安全字段 ---
        "s_parser_called": p.get("called"),
        "s_parser_status": p.get("status"),
        "s_parse_pdf_calls": diag.get("parse_pdf_calls"),
        "s_parser_call_count": diag.get("parser_call_count"),
        "s_parse_worker_started": diag.get("parse_worker_started"),
        "s_llm_called": d.get("llm_called"),
        "s_classifier_llm_calls": d.get("classifier_llm_calls"),
        "s_parser_stages_seen": p.get("stages_seen"),
        "s_parser_run_id": p.get("run_id"),
        "s_parser_run_dir": p.get("run_dir"),
        "s_parser_output": d.get("parser_output"),
        # --- 分类明细 ---
        "c_decision": c.get("decision"),
        "c_doc_type": c.get("doc_type"),
        "c_route": c.get("route"),
        "c_status": c.get("classification_status"),
        "c_read_status": c.get("read_status"),
        "c_hash_status": c.get("source_hash_status"),
        "c_ic_ds": c.get("ic_datasheet_extraction"),
        "c_conflict": c.get("evidence_conflict"),
        "c_source_sha": c.get("source_sha256"),
        "c_pages": c.get("evidence_pages"),
        "c_version": c.get("classifier_version"),
        "c_semantic": c.get("semantic_type"),
        "c_assigned": c.get("assigned_type"),
        "gate_decision": diag.get("gate_decision"),
        "gate_reason": diag.get("reason"),
        "classifier_stages": diag.get("classifier_stages_seen"),
        "safety_blocked": diag.get("safety_blocked"),
        "safety_guard_layer": diag.get("safety_guard_layer"),
    }


def main() -> int:
    rows = [extract(tag, meta) for tag, meta in SAMPLES.items()]
    (HERE / "05_extracted.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    def ok(v, expect):
        return "PASS" if v == expect else "FAIL"

    lines = []
    lines.append("# 安全字段核对表（两份 EVM 样本，`ALLOW_PARSE=1` + `CLASSIFY_ONLY=1`）")
    lines.append("")
    lines.append("判据来源：响应 JSON 内字段。**不采信「服务日志无 `[WORKER]` 行」**——")
    lines.append("worker 的 stdout 走管道被父进程解析、不继承到服务 stdout，该条件恒真，无鉴别力")
    lines.append("（已用上一轮确实解析过的 V002 日志反证：其日志同样 0 条 `[WORKER]`）。")
    lines.append("")
    lines.append("| # | 安全字段 | 期望 | A (`%s`) | B (`%s`) |" % (rows[0]["sample"], rows[1]["sample"]))
    lines.append("| --- | --- | --- | --- | --- |")

    def row(idx, name, expect, a, b, fmt=str):
        lines.append("| %s | `%s` | `%s` | `%s` | `%s` |"
                     % (idx, name, fmt(expect), fmt(a), fmt(b)))

    row(1, "parser.called", False, rows[0]["s_parser_called"], rows[1]["s_parser_called"])
    row(2, "diagnostics.parse_pdf_calls", 0, rows[0]["s_parse_pdf_calls"], rows[1]["s_parse_pdf_calls"])
    row(3, "diagnostics.parse_worker_started", False, rows[0]["s_parse_worker_started"], rows[1]["s_parse_worker_started"])
    row(4, "llm_called", False, rows[0]["s_llm_called"], rows[1]["s_llm_called"])
    row(5, "parser.stages_seen（无 PARSER_CALL_* 标记）", [], rows[0]["s_parser_stages_seen"], rows[1]["s_parser_stages_seen"])

    lines.append("")
    lines.append("## 补充不变量")
    lines.append("")
    lines.append("| 项 | 期望 | A | B |")
    lines.append("| --- | --- | --- | --- |")
    for name, key, expect in [
        ("`parser.status`", "s_parser_status", "SKIPPED"),
        ("`parser.run_id`", "s_parser_run_id", None),
        ("`parser.run_dir`", "s_parser_run_dir", None),
        ("`diagnostics.parser_call_count`", "s_parser_call_count", 0),
        ("`parser_output`", "s_parser_output", {}),
        ("`classifier_llm_calls`", "s_classifier_llm_calls", 0),
    ]:
        lines.append("| %s | `%s` | `%s` | `%s` |"
                     % (name, expect, rows[0][key], rows[1][key]))

    lines.append("")
    lines.append("## 哈希链")
    lines.append("")
    lines.append("| 项 | A | B |")
    lines.append("| --- | --- | --- |")
    lines.append("| 源样本 SHA-256 | `%s` | `%s` |" % (rows[0]["source_sha256"], rows[1]["source_sha256"]))
    lines.append("| 与 Reviewer 给定值一致 | %s | %s |"
                 % (ok(rows[0]["source_sha256"], rows[0]["expect_sha256"]),
                    ok(rows[1]["source_sha256"], rows[1]["expect_sha256"])))
    lines.append("| 上传副本 SHA-256 | `%s` | `%s` |" % (rows[0]["upload_sha256"], rows[1]["upload_sha256"]))
    lines.append("| 上传副本 == 源样本 | %s | %s |"
                 % (ok(rows[0]["upload_sha_match_source"], True),
                    ok(rows[1]["upload_sha_match_source"], True)))
    lines.append("| 响应 SHA-256 | `%s` | `%s` |" % (rows[0]["response_sha256"], rows[1]["response_sha256"]))
    lines.append("| 响应字节数 | %d | %d |" % (rows[0]["response_bytes"], rows[1]["response_bytes"]))

    lines.append("")
    lines.append("## 分类结果")
    lines.append("")
    lines.append("| 项 | A | B |")
    lines.append("| --- | --- | --- |")
    for name, key in [
        ("`status`", "status"),
        ("`classification.decision`", "c_decision"),
        ("`classification.doc_type`", "c_doc_type"),
        ("`classification.route`", "c_route"),
        ("`classification.classification_status`", "c_status"),
        ("`classification.read_status`", "c_read_status"),
        ("`classification.source_hash_status`", "c_hash_status"),
        ("`classification.ic_datasheet_extraction`", "c_ic_ds"),
        ("`classification.evidence_conflict`", "c_conflict"),
        ("`classification.evidence_pages`", "c_pages"),
        ("`classification.source_sha256`", "c_source_sha"),
        ("`diagnostics.gate_decision`", "gate_decision"),
        ("`diagnostics.safety_blocked`", "safety_blocked"),
        ("`diagnostics.safety_guard_layer`", "safety_guard_layer"),
    ]:
        lines.append("| %s | `%s` | `%s` |" % (name, rows[0][key], rows[1][key]))

    text = "\n".join(lines) + "\n"
    (HERE / "60_safety_matrix.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
