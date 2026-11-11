"""只分类哨兵（ICEX_CLASSIFY_ONLY=1）的极简单测。

证明目标（Reviewer 要求的核心命题）：
    **即使强行注入 DATASHEET 分类结果，只要 ICEX_CLASSIFY_ONLY=1，
    `parse_pdf()` 的调用次数恒为 0。**

四条用例分别覆盖三层拦截 + 一个反向对照：
1. L2 `_execute_parse()` 入口：直接抛 `SafetyBlocked`，且 `_run_child` 一次都没被调用；
2. L1 `api_process`：分类结果被强行注入为 DATASHEET，仍返回 `SAFETY_BLOCKED`，
   `parser.called=false`、`parse_pdf_calls=0`、`_execute_parse` 未被调用；
3. L3 `parse_worker.py`：以子进程方式被单独拉起时自行退出（exit 3），
   且 `icpdf.parser.pipeline` 从未被 import —— `parse_pdf` 连符号都没加载；
4. **反向对照**：`ICEX_CLASSIFY_ONLY=0` 时同一注入场景**会**走到 `_execute_parse`，
   证明拦截不是「无条件全拦」的假阳性。

运行：
    py -3.13 -m pytest workbench/_guard/test_classify_only_guard.py -v
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

HERE = Path(__file__).resolve().parent
WORKBENCH = HERE.parent
sys.path.insert(0, str(WORKBENCH))

import serve_parser as srv  # noqa: E402

BODY = b"%PDF-1.4 test-only body"
BODY_SHA = hashlib.sha256(BODY).hexdigest()


def _forced_datasheet_stdout() -> str:
    """构造一份「分类器自信地判 DATASHEET」的假 stdout。"""
    record = {
        "document_id": "doc_fake",
        "mpn": "FAKE",
        "file_path": "fake.pdf",
        "evidence_text": "",
        "result": {
            "route": "IC_PARSE",
            "doc_type": "DS_STRONG",
            "classification_status": "SUCCESS",
            "read_status": "OK",
            "source_hash_status": "success",
            "ic_datasheet_extraction": True,
            "evidence_conflict": False,
            "source_sha256": BODY_SHA,
            "doc_confidence": "high",
            "semantic_type": "IC_DATASHEET",
            "assigned_type": "DS_STRONG",
            "evidence_pages": [1, 2],
            "classifier_version": "docclassifier-2.2.1",
            "rule_version": "doc-classifier-v2",
        },
    }
    payload = {
        "ok": True,
        "classifier_call_entered": True,
        "entry_point": "icpdf.classification.classifier.classify_one",
        "record": record,
    }
    return "%s\n%s\n%s\n" % (
        srv.CLS_BEGIN, json.dumps(payload, ensure_ascii=False), srv.CLS_END)


async def _fake_run_child(script, spec, timeout):  # noqa: ANN001
    return {
        "start_failed": False,
        "timed_out": False,
        "stdout": _forced_datasheet_stdout(),
        "stderr": "",
        "returncode": 0,
        "start_error": None,
        "stages": {
            "stages_seen": ["WORKER_STARTED", "CLASSIFIER_CALL_ENTERED",
                            "CLASSIFIER_CALL_RETURNED"],
            "worker_started_marker": True,
            "parser_call_entered": False,
            "parser_call_returned": False,
            "classifier_call_entered": True,
            "classifier_call_returned": True,
        },
    }


@pytest.fixture()
def classify_only_env(monkeypatch):
    monkeypatch.setenv("ICEX_WORKBENCH_ALLOW_PARSE", "1")
    monkeypatch.setenv("ICEX_CLASSIFY_ONLY", "1")


@pytest.fixture()
def patched_io(monkeypatch, tmp_path):
    """避免任何磁盘副作用：上传副本写到 tmp_path，worker 用假结果。"""
    async def fake_materialize(body, meta, request_id):
        p = tmp_path / meta["physical_filename"]
        p.write_bytes(body)
        meta["physical_path"] = str(p)
        return p

    monkeypatch.setattr(srv, "_materialize_upload", fake_materialize)
    monkeypatch.setattr(srv, "_run_child", _fake_run_child)


def test_L2_execute_parse_raises_and_never_spawns_worker(classify_only_env, monkeypatch):
    calls = {"run_child": 0, "new_id": 0}

    async def boom(*a, **kw):
        calls["run_child"] += 1
        raise AssertionError("_run_child 不得被调用")

    monkeypatch.setattr(srv, "_run_child", boom)
    monkeypatch.setattr(srv, "_new_id",
                        lambda p: calls.__setitem__("new_id", calls["new_id"] + 1))

    with pytest.raises(srv.SafetyBlocked):
        import asyncio
        asyncio.run(srv._execute_parse({}, Path("nope.pdf"), {}, 0.0))

    assert calls["run_child"] == 0, "parse_worker 绝不能被启动"
    assert calls["new_id"] == 0, "连 run_id 都不该被创建"


def test_L1_api_process_forced_datasheet_returns_safety_blocked(
        classify_only_env, patched_io, monkeypatch):
    executed = {"called": 0}

    async def spy_execute(*a, **kw):
        executed["called"] += 1
        return {"status": "SHOULD_NOT_HAPPEN"}

    monkeypatch.setattr(srv, "_execute_parse", spy_execute)

    client = TestClient(srv.app)
    resp = client.post(
        "/api/process",
        content=BODY,
        headers={"x-filename": "fake.pdf", "content-type": "application/pdf"},
    )
    data = resp.json()

    assert resp.status_code == 200
    # 分类照常完成，且确实是 DATASHEET（证明「强行注入」生效）
    assert data["classification"]["decision"] == "DATASHEET"
    assert data["classification"]["doc_type"] == "DS_STRONG"
    # 但 Parser 被物理切断
    assert data["status"] == "SAFETY_BLOCKED"
    assert data["parser"]["called"] is False
    assert data["parser"]["status"] == "SKIPPED"
    assert data["diagnostics"]["parse_pdf_calls"] == 0
    assert data["diagnostics"]["parser_call_count"] == 0
    assert data["diagnostics"]["parse_worker_started"] is False
    assert data["diagnostics"]["safety_blocked"] is True
    assert data["diagnostics"]["safety_guard_layer"] == "L1:api_process"
    assert executed["called"] == 0, "_execute_parse 不得被调用"


def test_L1_api_parse_refused_in_classify_only(classify_only_env):
    client = TestClient(srv.app)
    resp = client.post(
        "/api/parse",
        content=BODY,
        headers={"x-filename": "fake.pdf", "content-type": "application/pdf"},
    )
    data = resp.json()
    assert resp.status_code == 200
    assert data["status"] == "SAFETY_BLOCKED"
    assert data["diagnostics"]["parse_pdf_calls"] == 0
    assert data["diagnostics"]["safety_guard_layer"] == "L1:api_parse"


def test_L3_worker_refuses_and_never_imports_parser(classify_only_env, capsys):
    import runpy

    worker = WORKBENCH / "parse_worker.py"
    before = "icpdf.parser.pipeline" in sys.modules

    old_argv = sys.argv
    sys.argv = [str(worker), "{}"]
    try:
        with pytest.raises(SystemExit) as exc:
            runpy.run_path(str(worker), run_name="__main__")
    finally:
        sys.argv = old_argv

    assert exc.value.code == 3, "SafetyBlocked 必须用专用退出码 3"
    out = capsys.readouterr().out
    assert "[WORKER] SAFETY_BLOCKED" in out
    assert '"safety_blocked": true' in out.replace("True", "true")
    after = "icpdf.parser.pipeline" in sys.modules
    assert before == after, "parse_worker 不得在拦截前 import parser"


def test_reverse_control_normal_mode_still_reaches_execute_parse(
        monkeypatch, patched_io):
    """反向对照：CLASSIFY_ONLY=0 时同一注入场景必须走到 _execute_parse。"""
    monkeypatch.setenv("ICEX_WORKBENCH_ALLOW_PARSE", "1")
    monkeypatch.delenv("ICEX_CLASSIFY_ONLY", raising=False)

    executed = {"called": 0}

    async def spy_execute(payload, pdf_path, meta, started):
        executed["called"] += 1
        # 必须遵守 _execute_parse 的真实返回契约：api_process 在它之后会写
        # parsed["diagnostics"]["classifier_gate"]，缺这个键会掩盖真正的断言。
        return {
            "status": "REACHED_EXECUTE_PARSE",
            "classification": payload["classification"],
            "parser": {"called": True, "status": "DONE"},
            "diagnostics": {},
        }

    monkeypatch.setattr(srv, "_execute_parse", spy_execute)

    client = TestClient(srv.app)
    resp = client.post(
        "/api/process",
        content=BODY,
        headers={"x-filename": "fake.pdf", "content-type": "application/pdf"},
    )
    assert resp.json()["status"] == "REACHED_EXECUTE_PARSE"
    assert executed["called"] == 1, "关闭哨兵时必须恢复原有调度行为"
