"""Ds Bit · Parser Lab 后端（FastAPI，双入口 / Pre-Parse Gate）。

两个入口严格隔离
----------------
* ``POST /api/parse``   —— Gate 6A **Parser-only 测试入口**。
  绝不调用分类器、绝不 import 分类模块；分类结果不混入 Parser-only 质量成绩。
  链路：``validate_pdf() -> parse_pdf()``。
* ``POST /api/process`` —— **正式用户入口**（Pre-Parse Gate）。
  链路：``validate_pdf() -> classify_document() -> DATASHEET only -> parse_pdf()``。
  非 DATASHEET 一律返回 ``NON_DATASHEET`` / ``AMBIGUOUS`` 与真实证据页，
  不创建 Parser Run 目录、不启动 parse_worker。

边界（不可协商）
--------------
1. 只调用 ``icpdf.parser.pipeline.parse_pdf()`` 与
   ``icpdf.classification.classifier.classify_one()`` 两个官方入口；
   不重建解析器、不实现分类规则、不改阈值、不改路由矩阵、不改 Parser 核心代码。
2. 不接入任何 LLM Provider，不建数据库，不写 PostgreSQL。
   分类器是纯规则实现（``src/icpdf/classification/`` 内无 LLM / 网络依赖），
   分类 Token 与调用次数单独记 0；若将来分类器改用 LLM，必须在此处单独计量。
3. ``parser_output`` 只序列化真实 run 目录里的 artifacts；缺失登记 MISSING，
   存在但不可读登记 PARTIAL，不补造、不猜测字段。
4. 冻结期默认 ``ICEX_WORKBENCH_ALLOW_PARSE=0``。两个入口都只返回 FROZEN，
   不读请求体、不落盘、不启动任何 worker。Reviewer 解除冻结后显式设为 1
   才允许真实分类 / 解析。
5. 每次分类与每次解析各在独立子进程中执行，带超时强杀；崩溃、超时、
   worker 启动失败均返回明确状态，不静默降级为「成功」。

Reviewer P1/P2 修复（本轮）
--------------------------
* P1-1 上传改为流式：先查 ``Content-Length``，再异步分块累计，超过
  80 MiB 立即返回 HTTP 413；不再使用 ``await request.body()`` 一次性读入。
* P1-2 ``async def`` 内改用 ``asyncio.create_subprocess_exec()`` +
  ``asyncio.wait()`` 超时强杀，并以信号量限制最大并发 worker 数；
  文件 IO / git 查询走 ``asyncio.to_thread()``，不阻塞事件循环。
* P1-3 ``parse_pdf_calls`` 改为按 worker 的 ``PARSER_CALL_ENTERED`` 阶段
  标记统计；崩溃 / 超时 / 异常时已发生的调用不再被错记为 0。
* P2-1 ``_collect_artifacts()`` 把 MISSING 与 PARTIAL 分开计数，
  ``required_artifact_failure_count = missing + partial``，PARTIAL 不算完整产物。
* P2-2 子进程启动异常单独归为 ``WORKER_START_FAILED``（含 ``worker_kind``）。

启动（冻结期不建议启动）：
    python serve_parser.py
    # 解冻后：
    ICEX_WORKBENCH_ALLOW_PARSE=1 python serve_parser.py

依赖：fastapi / starlette（已有）、uvicorn（隔离目录 workbench/_deps 提供）。
Parser 侧 PyYAML 从隔离目录注入 sys.path，不写入 site-packages、不改依赖声明。
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import os
import re
import secrets
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from starlette.requests import ClientDisconnect

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SRC_DIR = REPO / "src"
WORKER = HERE / "parse_worker.py"
CLASSIFIER_WORKER = HERE / "classify_worker.py"
UPLOAD_DIR = HERE / "uploads"
RUNS_ROOT = HERE / "runs"

MAX_UPLOAD_BYTES = 80 * 1024 * 1024
DEFAULT_TIMEOUT = float(os.getenv("ICEX_PARSE_TIMEOUT", "180"))
CLASSIFY_TIMEOUT = float(os.getenv("ICEX_CLASSIFY_TIMEOUT", "45"))
MAX_CONCURRENT_WORKERS = max(1, int(os.getenv("ICEX_WORKBENCH_MAX_CONCURRENCY", "2")))

BEGIN = "__ICEX_PARSE_JSON_BEGIN__"
END = "__ICEX_PARSE_JSON_END__"
CLS_BEGIN = "__ICEX_CLASSIFY_JSON_BEGIN__"
CLS_END = "__ICEX_CLASSIFY_JSON_END__"

# worker 阶段标记（stdout 上的 [WORKER] 行）。父进程据此统计「是否真的调用」。
STAGE_WORKER_STARTED = "WORKER_STARTED"
STAGE_PARSER_ENTERED = "PARSER_CALL_ENTERED"
STAGE_PARSER_RETURNED = "PARSER_CALL_RETURNED"
STAGE_CLASSIFIER_ENTERED = "CLASSIFIER_CALL_ENTERED"
STAGE_CLASSIFIER_RETURNED = "CLASSIFIER_CALL_RETURNED"

PIPELINE_PARSER_ONLY = "parser_only"
PIPELINE_PROCESS = "preparse_gate_v1"

# Parser 实际写出的 9 个 JSON artifacts（pipeline.py + RunStore）。
ARTIFACT_FILES = (
    ("run_manifest", "run_manifest.json"),
    ("document", "document.json"),
    ("text_blocks", "text_blocks.json"),
    ("tables", "tables.json"),
    ("candidates", "candidates.json"),
    ("boundary_decisions", "boundary_decisions.json"),
    ("product", "product.json"),
    ("run_config", "run_config.json"),
    ("geometry", "pages/geometry.json"),
)

# 工作台 §5 期望的 7 个契约产物 -> 当前 Parser 实际产物映射。
CONTRACT_MAP = (
    ("run_manifest.json", "run_manifest.json", "REAL_GENERATED", ""),
    ("document.json", "document.json", "REAL_GENERATED", ""),
    ("raw_extraction.json", "text_blocks.json", "RENAMED",
     "契约名为 raw_extraction.json，Parser 实际写出 text_blocks.json"),
    ("tables.json", "tables.json", "REAL_GENERATED", ""),
    ("candidates.json", "candidates.json", "REAL_GENERATED",
     "candidates.json 不得充当 evidence.json"),
    ("evidence.json", "", "MISSING",
     "domain.Evidence / FormalParameterSet 在生产链零实例化，无证据页码回溯"),
    ("qc_report.json", "", "MISSING",
     "外部 validate_evidence.py 不等于每次 Run 产出的 qc_report.json"),
)

CONTRACT_GAPS = (
    "当前 Parser 不产出 evidence.json，无法做证据页码回溯，Gate 6A 质量评估会因此受限",
    "当前 Parser 不产出 qc_report.json，不得把外部 validate_evidence.py 当作每次 Run 的 QC 产物",
    "raw_extraction.json 在契约中的实际文件名为 text_blocks.json，属于改名而非缺失",
    "parser_output 是 Parser-only 原始产物，不是标准器件参数抽取结果；"
    "不做单位归一化、不做参数语义归类、不处理多型号歧义",
)

# ---------------------------------------------------------------- Pre-Parse Gate
# 分类标签全部来自 src/icpdf/classification/models.py 的真实枚举值，不新造标签。
# 模型层硬不变量：route == IC_PARSE 当且仅当 doc_type == DS_STRONG
# （ClassificationResult.check_route_invariant / check_cross_field_consistency）。
# 这里再叠一层显式白名单：任何一项不成立都 fail-closed，绝不默认放行。
ADMIT_REQUIRED = {
    "route": "IC_PARSE",
    "doc_type": "DS_STRONG",
    "classification_status": "SUCCESS",
    "read_status": "OK",
    "source_hash_status": "success",
}
NON_DATASHEET_DOC_TYPES = frozenset({"EVM", "AN", "UG", "SMD"})
NON_DATASHEET_SEMANTIC_TYPES = frozenset({
    "EVM", "USER_GUIDE", "APP_NOTE", "REFERENCE_DESIGN",
})
ADMIT_GATE_RULE = (
    "DATASHEET 当且仅当：分类子进程成功返回，且 "
    "route=IC_PARSE、doc_type=DS_STRONG、classification_status=SUCCESS、"
    "read_status=OK、source_hash_status=success、"
    "ic_datasheet_extraction=true、evidence_conflict=false、"
    "source_sha256 与上传字节 SHA-256 逐字节一致。"
    "其余情况一律 NON_DATASHEET 或 AMBIGUOUS，不进入 parse_pdf()。"
)

app = FastAPI(title="Ds Bit · Parser Lab", docs_url=None, redoc_url=None)

_worker_slots: asyncio.Semaphore | None = None


class UploadRejected(Exception):
    """上传校验失败：携带结构化响应体与 HTTP 状态码，由入口统一转成响应。"""

    def __init__(self, payload: dict, http_code: int = 200) -> None:
        super().__init__(str(payload.get("status", "INVALID_FILE")))
        self.payload = payload
        self.http_code = http_code


def _allow_parse() -> bool:
    """冻结开关。默认 0；Reviewer 解除冻结前不得改为 1。

    两个入口共用同一个开关：冻结期内 /api/process 也不得借「只做分类」
    之名打开 PDF。
    """
    return os.getenv("ICEX_WORKBENCH_ALLOW_PARSE", "0") == "1"


def _worker_semaphore() -> asyncio.Semaphore:
    """延迟创建信号量，避免模块导入时绑定到非运行中的事件循环。"""
    global _worker_slots
    if _worker_slots is None:
        _worker_slots = asyncio.Semaphore(MAX_CONCURRENT_WORKERS)
    return _worker_slots


def _pick_deps_dir() -> Path | None:
    """选择隔离依赖目录（含 PyYAML），不修改项目依赖声明。"""
    env = os.getenv("ICEX_WORKBENCH_DEPS")
    candidates: list[Path] = []
    if env:
        candidates.append(Path(env))
    candidates.append(REPO / "runs" / "stage_a_350" / "gate6a" / "_deps")
    candidates.append(HERE / "_deps")
    for path in candidates:
        if (path / "yaml" / "__init__.py").is_file():
            return path
    return None


def _git_head() -> str | None:
    """只读 Git HEAD，供代码版本留痕；不触发任何解析。"""
    try:
        done = subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return done.stdout.strip() if done.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _new_id(prefix: str) -> str:
    return "%s-%s-%s" % (
        prefix, datetime.now().strftime("%Y%m%d-%H%M%S"), secrets.token_hex(2))


def _parser_skipped(status: str = "SKIPPED", reason: str | None = None) -> dict:
    """未调用 Parser 时的统一结构；called 恒为 False，run_id/run_dir 恒为 None。"""
    return {
        "called": False,
        "status": status,
        "reason": reason,
        "run_id": None,
        "run_dir": None,
        "worker_started": False,
        "worker_start_failed": False,
        "parser_call_entered": False,
        "parser_call_returned": False,
        "parser_call_count": 0,
        "stages_seen": [],
    }


def _base_payload(pipeline: str, status: str) -> dict:
    return {
        "pipeline": pipeline,
        "endpoint_kind": ("parser_only_benchmark" if pipeline == PIPELINE_PARSER_ONLY
                          else "production_gate"),
        "llm_called": False,
        "database_written": False,
        "classifier_llm_calls": 0,
        "classifier_token_usage": 0,
        "extraction": None,
        "extraction_note": "第二阶段 LLM 输出使用 extraction 命名空间；本工作台不产出该字段",
        "status": status,
        "gate6a_status": "NOT_STARTED",
        "frozen": not _allow_parse(),
        "classification": None,
        "classifier_called": False,
        "parser": _parser_skipped("NOT_STARTED"),
        "parser_output": {},
        "artifact_inventory": [],
        "contract_gaps": [],
        "code_version": None,
        "diagnostics": {},
    }


def _invalid_payload(pipeline: str, reason: str, *, too_large: bool = False) -> dict:
    payload = _base_payload(pipeline, "INVALID_FILE")
    payload["document"] = None
    payload["parser"] = _parser_skipped("SKIPPED", reason)
    payload["diagnostics"] = {
        "parse_worker_started": False,
        "classifier_worker_started": False,
        "parse_pdf_calls": 0,
        "parser_call_count": 0,
        "reason": reason,
    }
    if too_large:
        # 前端 fetch 对非 2xx 会读 j.detail，保留可读的 413 原因。
        payload["detail"] = reason
    return payload


def _frozen_payload(pipeline: str) -> dict:
    payload = _base_payload(pipeline, "FROZEN")
    payload["document"] = None
    payload["parser"] = _parser_skipped(
        "SKIPPED", "冻结期内不启动 parse_worker，也不启动 classify_worker")
    payload["diagnostics"] = {
        "reason": "Reviewer 冻结期：ICEX_WORKBENCH_ALLOW_PARSE 未设为 1；分类与解析均不执行",
        "parse_worker_started": False,
        "classifier_worker_started": False,
        "parse_pdf_calls": 0,
        "parser_call_count": 0,
        "action_required": "等待 Reviewer 解除 Gate 6A 冻结并确认样本 / Gold / 运行边界",
    }
    return payload


# ---------------------------------------------------------------- 上传 / 校验
def _evidence_filename(raw: str) -> str:
    """把用户提交名压成**分类器证据名**；返回值永不参与磁盘路径拼接。

    只保留原始文件名（分类器要从文件名取 mpn / provenance），
    清除路径分隔符、控制字符与 Windows 保留字符，并剥掉首尾的点与空格，
    使 ``.`` / ``..`` / ``...`` 一律退化为 ``upload.pdf``。
    """
    name = Path(unquote(raw or "")).name.replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"[\x00-\x1f<>:\"/\\|?*]", "_", name).strip(" .")
    if name in ("", ".", ".."):
        name = "upload"
    if len(name) > 180:
        name = name[:180]
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name


def _physical_filename() -> str:
    """磁盘物理名：``<uuid4>.pdf``，与用户输入零耦合。

    用户提交的文件名无论含 ``../``、绝对路径、Unicode 同形字还是 Windows
    设备名（CON/NUL/COM1），都不会出现在路径里；原始名只作为元数据
    交给分类 worker，由它在私有临时目录内以安全名建立硬链接。
    """
    return uuid.uuid4().hex + ".pdf"


def _validate_pdf(body: bytes, headers) -> dict:
    """纯内存校验：字节数、%PDF 魔数、SHA-256、文件名归一化。不打开 PDF。"""
    raw_name = headers.get("x-filename", "")
    submitted = Path(unquote(raw_name)).name if raw_name else ""
    evidence = _evidence_filename(raw_name)
    requested_mpn = unquote(headers.get("x-requested-mpn", "") or "")
    return {
        "submitted_filename": submitted or None,
        "evidence_filename": evidence,
        "physical_filename": _physical_filename(),
        "filename_rewritten": bool(submitted and submitted != evidence),
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "pdf_magic_ok": body.startswith(b"%PDF"),
        "requested_mpn": requested_mpn,
        "requested_mpn_source": "user_input" if requested_mpn else "filename_stem_fallback",
        "mpn_for_parser": requested_mpn or Path(evidence).stem,
        "size_limit_bytes": MAX_UPLOAD_BYTES,
    }


async def _read_body_stream(request: Request) -> tuple[bytes, str | None]:
    """流式接收请求体，绝不调用 ``await request.body()``。

    两道闸：
    1. ``Content-Length`` 预检，声明超限则一个字节都不读，直接 413；
    2. 分块异步累计，累计超限立即返回，不把整包读进内存。
       chunked / 无 Content-Length 的请求同样受第二道闸约束。
    """
    declared_raw = request.headers.get("content-length")
    if declared_raw is not None:
        try:
            declared = int(declared_raw)
        except (TypeError, ValueError):
            return b"", "INVALID_CONTENT_LENGTH"
        if declared < 0:
            return b"", "INVALID_CONTENT_LENGTH"
        if declared > MAX_UPLOAD_BYTES:
            return b"", "TOO_LARGE"

    chunks: list[bytes] = []
    total = 0
    try:
        async for chunk in request.stream():
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                return b"", "TOO_LARGE"
            chunks.append(chunk)
    except ClientDisconnect:
        return b"", "CLIENT_DISCONNECTED"
    return b"".join(chunks), None


async def _receive_pdf(request: Request, pipeline: str) -> tuple[bytes, dict]:
    """``validate_pdf()`` 的统一实现；失败抛 UploadRejected，由入口转响应。"""
    body, err = await _read_body_stream(request)
    if err == "TOO_LARGE":
        raise UploadRejected(_invalid_payload(
            pipeline,
            "上传超过 %d 字节（%d MiB）上限；已在流式读取阶段提前终止，未落盘"
            % (MAX_UPLOAD_BYTES, MAX_UPLOAD_BYTES // (1024 * 1024)),
            too_large=True), 413)
    if err:
        raise UploadRejected(_invalid_payload(
            pipeline, "请求体无效：%s" % err))
    if not body:
        raise UploadRejected(_invalid_payload(pipeline, "空文件，未收到 PDF 字节"))
    if len(body) > MAX_UPLOAD_BYTES:  # 防御性兜底，流式阶段已拦截
        raise UploadRejected(_invalid_payload(
            pipeline, "文件超过 %d 字节上限" % MAX_UPLOAD_BYTES,
            too_large=True), 413)
    meta = _validate_pdf(body, request.headers)
    if not meta["pdf_magic_ok"]:
        raise UploadRejected(_invalid_payload(
            pipeline, "缺少 %PDF 魔数，不是有效 PDF"))
    return body, meta


async def _materialize_upload(body: bytes, meta: dict, request_id: str) -> Path:
    """落盘：``uploads/<request_id>/<uuid4>.pdf``。

    三道防线，任何一道都不依赖「用户输入是否干净」：
    1. 目录名来自服务端 ``_new_id()``，文件名来自服务端 ``uuid4()``；
    2. 用户提交名只进 ``meta``，从不参与 ``/`` 拼接；
    3. 落盘前再做一次 ``is_relative_to()`` 越界断言（防未来改动引入回归）。
    """
    target_dir = UPLOAD_DIR / request_id
    await asyncio.to_thread(target_dir.mkdir, parents=True, exist_ok=True)
    pdf_path = target_dir / meta["physical_filename"]
    resolved = pdf_path.resolve()
    if not resolved.is_relative_to(target_dir.resolve()):
        raise RuntimeError(
            "物理落盘路径越界：%s 不在 %s 内；拒绝写入" % (resolved, target_dir))
    await asyncio.to_thread(pdf_path.write_bytes, body)
    meta["physical_path"] = str(resolved)
    return pdf_path


# ---------------------------------------------------------------- 子进程执行
def _stage_flags(stdout_text: str) -> dict:
    """从 stdout 的 [WORKER] 行还原真实执行阶段。"""
    stages = [
        line.strip()[len("[WORKER] "):].strip()
        for line in stdout_text.splitlines()
        if line.strip().startswith("[WORKER] ")
    ]
    return {
        "stages_seen": stages,
        "worker_started_marker": STAGE_WORKER_STARTED in stages,
        "parser_call_entered": STAGE_PARSER_ENTERED in stages,
        "parser_call_returned": STAGE_PARSER_RETURNED in stages,
        "classifier_call_entered": STAGE_CLASSIFIER_ENTERED in stages,
        "classifier_call_returned": STAGE_CLASSIFIER_RETURNED in stages,
    }


def _extract_sentinels(stdout_text: str, begin: str, end: str) -> dict | None:
    if begin not in stdout_text or end not in stdout_text:
        return None
    chunk = stdout_text.split(begin, 1)[1].split(end, 1)[0].strip()
    try:
        return json.loads(chunk)
    except json.JSONDecodeError:
        return None


async def _run_child(script: Path, spec: dict, timeout: float) -> dict:
    """异步非阻塞子进程；启动失败 / 超时强杀 / 崩溃均如实登记。

    不在 ``async def`` 中使用 ``subprocess.Popen().communicate(timeout=...)``：
    那会阻塞整个事件循环。这里用 ``create_subprocess_exec`` + ``asyncio.wait``，
    超时后 kill 并继续 await 原 communicate 任务，避免二次 communicate。
    """
    cmd = [sys.executable, str(script), json.dumps(spec, ensure_ascii=False)]
    async with _worker_semaphore():
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(REPO),
            )
        except (OSError, ValueError, RuntimeError) as exc:
            # 含 SelectorEventLoop 下的 NotImplementedError（RuntimeError 子类）
            return {
                "start_failed": True,
                "timed_out": False,
                "stdout": "",
                "stderr": "",
                "returncode": None,
                "start_error": "%s: %s" % (type(exc).__name__, exc),
                "stages": _stage_flags(""),
            }

        comm = asyncio.ensure_future(proc.communicate())
        done, _ = await asyncio.wait({comm}, timeout=timeout)
        timed_out = not bool(done)
        out: bytes = b""
        err: bytes = b""
        try:
            if timed_out:
                proc.kill()
                out, err = await asyncio.wait_for(comm, timeout=10)
            else:
                out, err = comm.result()
        except asyncio.TimeoutError:
            if not comm.done():
                comm.cancel()
        except Exception as exc:  # noqa: BLE001  子进程通信异常不得改写成成功
            err = (err or b"") + ("[parent] %s: %s\n" % (
                type(exc).__name__, exc)).encode("utf-8", "replace")
        try:
            await proc.wait()
        except Exception:  # noqa: BLE001  回收失败不影响状态判定
            pass

    stdout_text = out.decode("utf-8", "replace")
    stderr_text = err.decode("utf-8", "replace")
    return {
        "start_failed": False,
        "timed_out": timed_out,
        "stdout": stdout_text,
        "stderr": stderr_text,
        "returncode": proc.returncode,
        "start_error": None,
        "stages": _stage_flags(stdout_text),
    }


def _merge_payload_stages(stages: dict, worker_json: dict | None) -> dict:
    """stdout 标记为主，JSON 载荷里的 stages 作冗余补充。"""
    extra = (worker_json or {}).get("stages")
    if isinstance(extra, list):
        for name in extra:
            if isinstance(name, str) and name not in stages["stages_seen"]:
                stages["stages_seen"].append(name)
        stages["parser_call_entered"] = (
            stages["parser_call_entered"] or STAGE_PARSER_ENTERED in extra)
        stages["parser_call_returned"] = (
            stages["parser_call_returned"] or STAGE_PARSER_RETURNED in extra)
        stages["classifier_call_entered"] = (
            stages["classifier_call_entered"] or STAGE_CLASSIFIER_ENTERED in extra)
        stages["classifier_call_returned"] = (
            stages["classifier_call_returned"] or STAGE_CLASSIFIER_RETURNED in extra)
        stages["worker_started_marker"] = (
            stages["worker_started_marker"] or STAGE_WORKER_STARTED in extra)
    return stages


# ---------------------------------------------------------------- 产物统计
def _collect_artifacts(run_dir: Path) -> dict:
    """原样读取真实 artifacts。

    MISSING=文件不存在；PARTIAL=文件存在但无法作为 JSON 读取。
    两者分开计数，且都计入 ``required_artifact_failure_count``；
    PARTIAL 绝不当作完整产物。
    """
    parser_output: dict = {}
    inventory: list[dict] = []
    missing: list[str] = []
    partial: list[str] = []
    for key, rel in ARTIFACT_FILES:
        path = run_dir / rel
        if not path.is_file():
            inventory.append({
                "artifact": key, "actual_file": rel, "status": "MISSING",
                "sha256": None, "bytes": 0,
                "note": "Parser 本次未写出该产物；不补造字段",
            })
            missing.append(key)
            continue
        note = ""
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
            parser_output[key] = content
            state = "REAL_GENERATED"
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            state = "PARTIAL"
            note = "文件存在但无法作为 JSON 读取：%s: %s" % (type(exc).__name__, exc)
            partial.append(key)
        try:
            digest = _sha256_file(path)
            size = path.stat().st_size
        except OSError:
            digest, size = None, 0
        inventory.append({
            "artifact": key, "actual_file": rel, "status": state,
            "sha256": digest, "bytes": size, "note": note,
        })
    return {
        "parser_output": parser_output,
        "inventory": inventory,
        "missing_artifacts": missing,
        "partial_artifacts": partial,
        "missing_artifact_count": len(missing),
        "partial_artifact_count": len(partial),
        "required_artifact_failure_count": len(missing) + len(partial),
        "required_artifact_complete": not (missing or partial),
    }


# ---------------------------------------------------------------- 分类门禁
def _build_classification(*, record: dict | None, upload_sha: str,
                          classify_status: str, stages: dict,
                          worker: dict, classifier_called: bool) -> tuple[dict, str]:
    """把真实 classify_one() 输出映射成 classification 对象与三出口裁决。

    所有标签 / 置信度 / 证据 / 版本字段都直接取自 ``ClassificationResult``；
    这里只做「是否放行」的显式白名单判断，不发明任何分类依据。
    """
    r = (record or {}).get("result") or {}
    checks: dict[str, dict] = {}

    def check(name: str, ok: bool, actual, expected=None) -> None:
        checks[name] = {"ok": bool(ok), "actual": actual, "expected": expected}

    check("classifier_returned_ok", classify_status == "SUCCESS",
          classify_status, "SUCCESS")
    for field, expected in ADMIT_REQUIRED.items():
        check(field, r.get(field) == expected, r.get(field), expected)
    check("ic_datasheet_extraction", r.get("ic_datasheet_extraction") is True,
          r.get("ic_datasheet_extraction"), True)
    check("evidence_conflict", r.get("evidence_conflict") is False,
          r.get("evidence_conflict"), False)
    check("source_sha256_matches_upload",
          bool(r.get("source_sha256")) and r.get("source_sha256") == upload_sha,
          r.get("source_sha256"), upload_sha)

    failed = [name for name, item in checks.items() if not item["ok"]]

    if classify_status == "SUCCESS" and not failed:
        decision = "DATASHEET"
    elif (classify_status == "SUCCESS"
          and r.get("classification_status") == "SUCCESS"
          and r.get("evidence_conflict") is False
          and r.get("source_hash_status") == "success"
          and checks["source_sha256_matches_upload"]["ok"]
          and (r.get("doc_type") in NON_DATASHEET_DOC_TYPES
               or r.get("semantic_type") in NON_DATASHEET_SEMANTIC_TYPES)):
        decision = "NON_DATASHEET"
    else:
        # DS_WEAK / UNKNOWN / OCR / 低置信度 / 证据冲突 / 读取失败 /
        # 分类异常 / 超时 / 崩溃 / 哈希不一致，一律隔离待审，绝不默认放行。
        decision = "AMBIGUOUS"

    reasons: list[str] = []
    if classify_status != "SUCCESS":
        reasons.append("分类器未成功返回（%s）；fail-closed，禁止默认按 Datasheet 放行"
                       % classify_status)
    if decision == "DATASHEET":
        reasons.append("全部准入条件成立：route=IC_PARSE / doc_type=DS_STRONG / "
                       "证据无冲突 / 源 SHA-256 与上传字节一致")
    elif decision == "NON_DATASHEET":
        reasons.append("分类器明确判定为非 Datasheet 本体（doc_type=%s，semantic_type=%s）；"
                       "立即终止，不进入 Parser" % (
                           r.get("doc_type"), r.get("semantic_type")))
    else:
        reasons.append("不满足 DATASHEET 白名单，且不属于明确非 Datasheet 本体；"
                       "按 fail-closed 隔离待人工复核")
    for name in failed:
        item = checks[name]
        reasons.append("未满足准入项 %s：实际=%r，要求=%r" % (
            name, item["actual"], item["expected"]))

    classification = {
        "called": classifier_called,
        "status": classify_status,
        "decision": decision,
        # is_datasheet 是「本体语义」直取 semantic_type；DS_WEAK 也会是 True，
        # 但只有 is_confirmed_datasheet / admit_to_parser 才代表可进 Parser。
        "is_datasheet": r.get("semantic_type") == "IC_DATASHEET",
        "is_confirmed_datasheet": decision == "DATASHEET",
        "admit_to_parser": decision == "DATASHEET",
        "document_type": r.get("semantic_type"),
        "doc_type": r.get("doc_type"),
        "assigned_type": r.get("assigned_type"),
        "route": r.get("route"),
        "confidence": r.get("doc_confidence"),
        "classifier_version": r.get("classifier_version"),
        "rule_version": r.get("rule_version"),
        "classification_status": r.get("classification_status"),
        "failure_kind": r.get("failure_kind"),
        "read_status": r.get("read_status"),
        "review_status": r.get("review_status"),
        "source_sha256": r.get("source_sha256"),
        "source_hash_status": r.get("source_hash_status"),
        "sha256_matches_upload": checks["source_sha256_matches_upload"]["ok"],
        "evidence_conflict": r.get("evidence_conflict"),
        "ic_datasheet_extraction": r.get("ic_datasheet_extraction"),
        "evidence_pages": r.get("evidence_pages"),
        "matched_rules": r.get("matched_rules"),
        "rejected_rules": r.get("rejected_rules"),
        "unmatched_rules": r.get("unmatched_rules"),
        "page_evidence": r.get("page_evidence"),
        "provenance": r.get("provenance"),
        "evidence_text": (record or {}).get("evidence_text"),
        "document_id": (record or {}).get("document_id"),
        "mpn": (record or {}).get("mpn"),
        "file_path_classified": (record or {}).get("file_path"),
        "gate_rule": ADMIT_GATE_RULE,
        "gate_checks": checks,
        "gate_reasons": reasons,
        "entry_point": "icpdf.classification.classifier.classify_one",
        "classifier_is_pure_rule": True,
        "classifier_llm_calls": 0,
        "classifier_token_usage": 0,
        "classifier_stages": stages["stages_seen"],
        "classifier_worker_timed_out": worker["timed_out"],
        "classifier_worker_returncode": worker["returncode"],
    }
    return classification, decision


# ---------------------------------------------------------------- 解析执行
async def _execute_parse(payload: dict, pdf_path: Path, meta: dict,
                         started: float) -> dict:
    """真正调用 Parser 的唯一路径。/api/parse 与 /api/process 共用。

    仅当调用本函数时才会创建 run_id / 上传副本之外的 Run 目录。
    """
    run_id = _new_id("G6A")
    payload["run_id"] = run_id
    payload["contract_gaps"] = list(CONTRACT_GAPS)
    document = dict(payload.get("document") or {})
    document.update({
        "filename": meta["evidence_filename"],
        "submitted_filename": meta["submitted_filename"],
        "sha256": meta["sha256"],
        "bytes": meta["bytes"],
        "page_count": None,
        "run_id": run_id,
        "requested_mpn": meta["mpn_for_parser"],
        "requested_mpn_source": meta["requested_mpn_source"],
        "requested_mpn_note": "这是调用 parse_pdf 的输入参数，不是 Parser 识别出的型号",
    })
    payload["document"] = document

    deps = _pick_deps_dir()
    spec = {
        "src_dir": str(SRC_DIR),
        "deps_dir": str(deps) if deps else None,
        "pdf_path": str(pdf_path),
        "runs_root": str(RUNS_ROOT),
        "run_id": run_id,
        "requested_mpn": meta["mpn_for_parser"],
    }
    worker = await _run_child(WORKER, spec, DEFAULT_TIMEOUT)
    worker_json = _extract_sentinels(worker["stdout"], BEGIN, END)
    stages = _merge_payload_stages(worker["stages"], worker_json)

    parse_result: dict | None = None
    error_text: str | None = None
    if worker["start_failed"]:
        status = "WORKER_START_FAILED"
        error_text = "解析子进程启动失败：%s" % worker["start_error"]
    elif worker["timed_out"]:
        status = "PARSE_TIMEOUT"
        error_text = "解析超过 %.0f 秒，已强制终止子进程" % DEFAULT_TIMEOUT
    elif worker_json is None:
        status = "PARSE_CRASH"
        error_text = ("解析子进程未返回有效 JSON 载荷，疑似原生崩溃；"
                      "returncode=%s" % worker["returncode"])
    elif worker_json.get("ok") is not True:
        status = "PARSE_ERROR"
        error_text = "Parser 抛出异常：%s: %s" % (
            worker_json.get("error_type", "Exception"),
            worker_json.get("error", ""),
        )
    else:
        status = "PARSE_COMPLETED"
        parse_result = worker_json.get("result")

    # 按「真正进入 parse_pdf()」统计：崩溃 / 超时 / 异常时已发生的调用不再记为 0。
    parser_call_count = 1 if stages["parser_call_entered"] else 0
    payload["status"] = status
    payload["parser"] = {
        "called": stages["parser_call_entered"],
        "status": status,
        "reason": error_text,
        "run_id": run_id,
        "run_dir": str(RUNS_ROOT / run_id),
        "worker_started": not worker["start_failed"],
        "worker_start_failed": worker["start_failed"],
        "parser_call_entered": stages["parser_call_entered"],
        "parser_call_returned": stages["parser_call_returned"],
        "parser_call_count": parser_call_count,
        "stages_seen": stages["stages_seen"],
    }
    payload["diagnostics"] = {
        "parse_worker_started": not worker["start_failed"],
        "classifier_worker_started": False,
        "worker_kind": "parse",
        "worker_start_failed": worker["start_failed"],
        "worker_start_error": worker["start_error"],
        "parse_pdf_calls": parser_call_count,
        "parser_call_count": parser_call_count,
        "parser_call_entered": stages["parser_call_entered"],
        "parser_call_returned": stages["parser_call_returned"],
        "worker_started_marker": stages["worker_started_marker"],
        "stages_seen": stages["stages_seen"],
        "worker_returncode": worker["returncode"],
        "worker_timeout_seconds": DEFAULT_TIMEOUT,
        "elapsed_seconds": round(time.time() - started, 3),
        "worker_stderr_tail": worker["stderr"][-2000:],
        "worker_stdout_noise": (
            worker["stdout"].split(BEGIN, 1)[0][-500:]
            if BEGIN in worker["stdout"] else worker["stdout"][-500:]
        ),
        "parser_error": error_text,
        "parse_summary": parse_result,
    }

    run_dir = RUNS_ROOT / run_id
    artifacts = await asyncio.to_thread(_collect_artifacts, run_dir)
    payload["parser_output"] = artifacts["parser_output"]
    payload["artifact_inventory"] = artifacts["inventory"]
    payload["diagnostics"].update({
        "missing_artifacts": artifacts["missing_artifacts"],
        "missing_artifact_count": artifacts["missing_artifact_count"],
        "partial_artifacts": artifacts["partial_artifacts"],
        "partial_artifact_count": artifacts["partial_artifact_count"],
        "required_artifact_failure_count": artifacts["required_artifact_failure_count"],
        "required_artifact_complete": artifacts["required_artifact_complete"],
        "artifact_accounting_note": (
            "MISSING=文件不存在；PARTIAL=文件存在但不可解析；"
            "两者均计入 required_artifact_failure_count，PARTIAL 绝不算完整产物"),
    })

    manifest = artifacts["parser_output"].get("run_manifest") or {}
    document_artifact = artifacts["parser_output"].get("document") or {}
    boundary = artifacts["parser_output"].get("boundary_decisions") or {}
    totals = boundary.get("totals") if isinstance(boundary, dict) else None
    git_head = await asyncio.to_thread(_git_head)
    payload["code_version"] = {
        "git_head": git_head,
        "project_version": manifest.get("project_version"),
        "parser_version": manifest.get("parser_version"),
        "contract_version": manifest.get("contract_version"),
        "parser_config_sha256": manifest.get("parser_config_sha256"),
        "python_version": manifest.get("python_version"),
        "platform": manifest.get("platform"),
        "manifest_sha256": (parse_result or {}).get("manifest_sha256"),
    }
    if status == "PARSE_COMPLETED":
        payload["document"]["page_count"] = document_artifact.get("page_count")
        payload["document"]["document_id"] = document_artifact.get("document_id")
        payload["document"]["run_dir"] = str(run_dir)
        payload["diagnostics"].update({
            "sha256_cross_check": {
                "upload_sha256": meta["sha256"],
                "manifest_document_sha256": manifest.get("document_sha256"),
                "match": (manifest.get("document_sha256") == meta["sha256"])
                if manifest.get("document_sha256") else None,
                "note": "不一致说明源 PDF 与 run 产物之间发生了路径或字节漂移",
            },
            "boundary_totals": totals,
            "table_count_from_artifact": len(artifacts["parser_output"]["tables"])
            if isinstance(artifacts["parser_output"].get("tables"), list) else None,
            "candidate_count_from_artifact": len(
                (artifacts["parser_output"].get("candidates") or {}).get("candidates", []))
            if isinstance(artifacts["parser_output"].get("candidates"), dict) else None,
            "note": "所有数值均由真实 artifacts 读取；取不到的字段保持 null，不做推断",
        })
    return payload


# ---------------------------------------------------------------- 路由
@app.get("/")
def index() -> FileResponse:
    return FileResponse(HERE / "index.html", media_type="text/html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    """避免浏览器自动请求 favicon 产生 404，保证冒烟测试 Console 干净。"""
    return Response(status_code=204)


@app.get("/api/health")
def health() -> dict:
    """只读状态查询。不启动任何 worker，不打开任何 PDF。"""
    deps = _pick_deps_dir()
    return {
        "service": "Ds Bit · Parser Lab",
        "pipeline": PIPELINE_PARSER_ONLY,
        "llm_called": False,
        "database_written": False,
        "gate6a_status": "NOT_STARTED",
        "frozen": not _allow_parse(),
        "allow_parse": _allow_parse(),
        "note": "冻结期内 /api/parse 与 /api/process 均只返回 FROZEN",
        "endpoints": {
            "/api/parse": {
                "kind": "parser_only_benchmark",
                "calls_classifier": False,
                "chain": "validate_pdf -> parse_pdf",
            },
            "/api/process": {
                "kind": "production_gate",
                "calls_classifier": True,
                "chain": "validate_pdf -> classify_one -> DATASHEET only -> parse_pdf",
                "decisions": ["DATASHEET", "NON_DATASHEET", "AMBIGUOUS"],
                "gate_rule": ADMIT_GATE_RULE,
                "classifier_is_pure_rule": True,
                "classifier_llm_calls": 0,
            },
        },
        "deps_dir": str(deps) if deps else None,
        "modules": {
            "fastapi": importlib.util.find_spec("fastapi") is not None,
            "uvicorn": importlib.util.find_spec("uvicorn") is not None,
            "yaml_in_global": importlib.util.find_spec("yaml") is not None,
            "yaml_in_isolated_deps": deps is not None,
            "pymupdf": importlib.util.find_spec("fitz") is not None,
        },
        "src_dir": str(SRC_DIR),
        "worker": str(WORKER),
        "worker_exists": WORKER.is_file(),
        "classifier_worker": str(CLASSIFIER_WORKER),
        "classifier_worker_exists": CLASSIFIER_WORKER.is_file(),
        "git_head": _git_head(),
        "worker_timeout_seconds": DEFAULT_TIMEOUT,
        "classifier_timeout_seconds": CLASSIFY_TIMEOUT,
        "max_concurrent_workers": MAX_CONCURRENT_WORKERS,
        "max_upload_bytes": MAX_UPLOAD_BYTES,
        "upload_mode": "streaming + content-length precheck + HTTP 413",
        "subprocess_mode": "asyncio.create_subprocess_exec (non-blocking)",
        "artifact_files": [rel for _, rel in ARTIFACT_FILES],
        "contract_map": [
            {"contract_artifact": contract, "actual_file": actual or None,
             "status": status, "note": note}
            for contract, actual, status, note in CONTRACT_MAP
        ],
    }


@app.post("/api/parse")
async def api_parse(request: Request) -> JSONResponse:
    """Gate 6A Parser-only 测试入口。

    绝不调用分类器、绝不 import 分类模块、绝不把分类结果混入 Parser-only
    质量成绩。链路：validate_pdf() -> parse_pdf()。
    """
    started = time.time()
    if not _allow_parse():
        return JSONResponse(_frozen_payload(PIPELINE_PARSER_ONLY))
    try:
        body, meta = await _receive_pdf(request, PIPELINE_PARSER_ONLY)
    except UploadRejected as exc:
        return JSONResponse(exc.payload, status_code=exc.http_code)

    request_id = _new_id("WB")
    pdf_path = await _materialize_upload(body, meta, request_id)
    payload = _base_payload(PIPELINE_PARSER_ONLY, "PARSING")
    payload["request_id"] = request_id
    payload["validation"] = {
        "evidence_filename": meta["evidence_filename"],
        "submitted_filename": meta["submitted_filename"],
        "physical_filename": meta["physical_filename"],
        "physical_path": meta["physical_path"],
        "bytes": meta["bytes"],
        "sha256": meta["sha256"],
        "pdf_magic_ok": True,
    }
    return JSONResponse(await _execute_parse(payload, pdf_path, meta, started))


@app.post("/api/process")
async def api_process(request: Request) -> JSONResponse:
    """正式用户入口（Pre-Parse Gate）。

    validate_pdf() -> classify_document() -> 仅 DATASHEET 才 parse_pdf()。
    NON_DATASHEET / AMBIGUOUS 返回分类对象与真实证据页后立即终止；
    分类器异常、超时、崩溃、证据不足、哈希不一致一律 fail-closed。
    """
    started = time.time()
    if not _allow_parse():
        return JSONResponse(_frozen_payload(PIPELINE_PROCESS))
    try:
        body, meta = await _receive_pdf(request, PIPELINE_PROCESS)
    except UploadRejected as exc:
        return JSONResponse(exc.payload, status_code=exc.http_code)

    request_id = _new_id("WB")
    pdf_path = await _materialize_upload(body, meta, request_id)
    payload = _base_payload(PIPELINE_PROCESS, "CLASSIFYING")
    payload["request_id"] = request_id
    payload["document"] = {
        "filename": meta["evidence_filename"],
        "submitted_filename": meta["submitted_filename"],
        "sha256": meta["sha256"],
        "bytes": meta["bytes"],
        "page_count": None,
    }
    payload["validation"] = {
        "evidence_filename": meta["evidence_filename"],
        "submitted_filename": meta["submitted_filename"],
        "physical_filename": meta["physical_filename"],
        "physical_path": meta["physical_path"],
        "filename_rewritten": meta["filename_rewritten"],
        "bytes": meta["bytes"],
        "sha256": meta["sha256"],
        "pdf_magic_ok": True,
        "path_safety_note": (
            "物理名=<uuid4>.pdf，目录名=<WB 时间戳+随机>；用户提交名只作元数据，"
            "从不参与路径拼接。分类子进程在私有临时目录内以清洗后的证据名"
            "建立硬链接后再分类，分类结束即删除临时目录。"),
    }

    spec = {
        "src_dir": str(SRC_DIR),
        "pdf_path": str(pdf_path),
        "original_filename": meta["evidence_filename"],
        "physical_path": meta["physical_path"],
    }
    worker = await _run_child(CLASSIFIER_WORKER, spec, CLASSIFY_TIMEOUT)
    worker_json = _extract_sentinels(worker["stdout"], CLS_BEGIN, CLS_END)
    stages = _merge_payload_stages(worker["stages"], worker_json)

    if worker["start_failed"]:
        classify_status = "START_FAILED"
        overall_status = "WORKER_START_FAILED"
    elif worker["timed_out"]:
        classify_status = "TIMEOUT"
        overall_status = "CLASSIFICATION_TIMEOUT"
    elif worker_json is None:
        classify_status = "CRASH"
        overall_status = "CLASSIFICATION_CRASH"
    elif worker_json.get("ok") is not True:
        classify_status = "ERROR"
        overall_status = "CLASSIFICATION_ERROR"
    else:
        classify_status = "SUCCESS"
        overall_status = None

    classifier_called = bool(
        stages["classifier_call_entered"]
        or (worker_json or {}).get("classifier_call_entered"))
    record = worker_json.get("record") if (
        worker_json and isinstance(worker_json.get("record"), dict)) else None
    classification, decision = _build_classification(
        record=record, upload_sha=meta["sha256"],
        classify_status=classify_status, stages=stages, worker=worker,
        classifier_called=classifier_called)
    payload["classification"] = classification
    payload["classifier_called"] = classifier_called

    base_diag = {
        "classifier_worker_started": not worker["start_failed"],
        "classifier_worker_start_failed": worker["start_failed"],
        "classifier_worker_start_error": worker["start_error"],
        "classifier_worker_timed_out": worker["timed_out"],
        "classifier_worker_returncode": worker["returncode"],
        "classifier_stages_seen": stages["stages_seen"],
        "classifier_timeout_seconds": CLASSIFY_TIMEOUT,
        "parse_worker_started": False,
        "parse_pdf_calls": 0,
        "parser_call_count": 0,
        "elapsed_seconds": round(time.time() - started, 3),
        "classifier_stderr_tail": worker["stderr"][-2000:],
    }

    if classify_status != "SUCCESS":
        payload["status"] = overall_status
        payload["parser"] = _parser_skipped(
            "SKIPPED", "分类器未成功返回；fail-closed，禁止默认按 Datasheet 放行")
        payload["diagnostics"] = dict(base_diag, **{
            "worker_kind": "classify",
            "reason": "分类未成功（%s）；不创建 Parser Run 目录、不调用 parse_pdf()"
                      % classify_status,
            "classification_error": (worker_json or {}).get("error"),
        })
        return JSONResponse(payload)

    if decision != "DATASHEET":
        payload["status"] = decision
        payload["parser"] = _parser_skipped(
            "SKIPPED", "Pre-Parse Gate 判定 %s；不创建 Parser Run 目录、不调用 parse_pdf()"
                       % decision)
        payload["diagnostics"] = dict(base_diag, **{
            "worker_kind": "classify",
            "gate_decision": decision,
            "evidence_pages": classification["evidence_pages"],
            "reason": "；".join(classification["gate_reasons"][:4]),
            "note": ("NON_DATASHEET 明确终止；AMBIGUOUS 隔离待人工复核。"
                     "两者均不得自动进入 Parser。"),
        })
        return JSONResponse(payload)

    # 只有 DATASHEET 才走到这里：classification 对象保留，parser.called 反映真实调用。
    parsed = await _execute_parse(payload, pdf_path, meta, started)
    # 分类阶段的证据与 Parser 阶段的证据分开存放，不互相覆盖。
    parsed["diagnostics"]["classifier_gate"] = base_diag
    parsed["diagnostics"]["gate_decision"] = "DATASHEET"
    parsed["diagnostics"]["evidence_isolation_note"] = (
        "classification.* 是分类器证据；parser_output / artifact_inventory "
        "是 Parser 证据；两者独立，不得用后者反填分类依据")
    return JSONResponse(parsed)


@app.get("/api/page", response_model=None)
def api_page(run_id: str, page: int):
    """返回 Parser 真实渲染的页面 PNG，用于原文与解析结果联动。

    未渲染的页明确返回 PAGE_NOT_RENDERED，绝不提供伪造预览。
    """
    if not re.fullmatch(r"G6A-\d{8}-\d{6}-[0-9a-f]{4}", run_id):
        return JSONResponse({"status": "INVALID_RUN_ID", "note": "run_id 格式不合法"},
                            status_code=400)
    if page < 1:
        return JSONResponse({"status": "INVALID_PAGE", "note": "页码必须大于 0"},
                            status_code=400)
    image = RUNS_ROOT / run_id / "pages" / ("page-%04d.png" % page)
    if not image.is_file():
        return JSONResponse({
            "status": "PAGE_NOT_RENDERED",
            "run_id": run_id, "page": page,
            "note": "该页未检测到表格，Parser 未渲染 PNG；不提供替代预览图",
        }, status_code=404)
    return FileResponse(image, media_type="image/png")


if __name__ == "__main__":
    if importlib.util.find_spec("uvicorn") is None:
        print("[Parser Lab] 当前环境缺 uvicorn，冻结期不自动安装依赖。")
        print("  启动命令:   ICEX_WORKBENCH_ALLOW_PARSE=1 python serve_parser.py")
        raise SystemExit(2)
    import uvicorn

    print("[Parser Lab] frozen=%s  port=%s" % (
        not _allow_parse(), os.getenv("ICEX_WORKBENCH_PORT", "8765")))
    uvicorn.run(app, host="127.0.0.1",
                port=int(os.getenv("ICEX_WORKBENCH_PORT", "8765")))
