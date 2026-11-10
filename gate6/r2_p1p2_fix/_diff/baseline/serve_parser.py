"""Ds Bit · Parser Lab 后端（FastAPI，Parser-only 观察工具）。

边界（不可协商）：
1. 只调用 icpdf.parser.pipeline.parse_pdf()，不重建解析器、不修改 Parser 核心算法。
2. 不接入任何 LLM Provider，不建数据库，不写 PostgreSQL。
3. parser_output 只序列化真实 run 目录里的 artifacts；缺失即登记 MISSING，
   不补造、不猜测字段，不用预设器件参数填充。
4. 冻结期默认 ICEX_WORKBENCH_ALLOW_PARSE=0，/api/parse 只返回 FROZEN，
   不启动 parse_worker 子进程。Reviewer 解除冻结后显式设为 1 才允许真实解析。
5. 每次解析在独立子进程中执行，带超时强杀；崩溃、超时、异常均返回明确状态。

启动（冻结期不建议启动）：
    python serve_parser.py
    # 解冻后：
    ICEX_WORKBENCH_ALLOW_PARSE=1 python serve_parser.py

依赖：fastapi（已有）、uvicorn（当前环境缺失，冻结期不自动安装）。
Parser 侧 PyYAML 从隔离目录 runs/stage_a_350/gate6a/_deps 注入 sys.path，
不写入 site-packages、不改项目依赖声明。
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import secrets
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SRC_DIR = REPO / "src"
WORKER = HERE / "parse_worker.py"
UPLOAD_DIR = HERE / "uploads"
RUNS_ROOT = HERE / "runs"

MAX_UPLOAD_BYTES = 80 * 1024 * 1024
DEFAULT_TIMEOUT = float(os.getenv("ICEX_PARSE_TIMEOUT", "180"))
BEGIN = "__ICEX_PARSE_JSON_BEGIN__"
END = "__ICEX_PARSE_JSON_END__"

# Parser 实际写出的 9 个 JSON artifacts（pipeline.py + RunStore）。
# key = 返回给前端 parser_output 的字段名；path = run 目录内相对路径。
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
# 这张表同时落实 Reviewer 整改 D：区分真实生成 / 改名 / 完全缺失。
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

app = FastAPI(title="Ds Bit · Parser Lab", docs_url=None, redoc_url=None)


def _allow_parse() -> bool:
    """冻结开关。默认 0， Reviewer 解除冻结前不得改为 1。"""
    return os.getenv("ICEX_WORKBENCH_ALLOW_PARSE", "0") == "1"


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


def _base_payload(status: str) -> dict:
    return {
        "pipeline": "parser_only",
        "llm_called": False,
        "database_written": False,
        "extraction": None,
        "extraction_note": "第二阶段 LLM 输出使用 extraction 命名空间；本工作台不产出该字段",
        "status": status,
        "gate6a_status": "NOT_STARTED",
        "frozen": not _allow_parse(),
        "parser_output": {},
        "artifact_inventory": [],
        "contract_gaps": list(CONTRACT_GAPS),
        "diagnostics": {},
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(HERE / "index.html", media_type="text/html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    """避免浏览器自动请求 favicon 产生 404，保证冒烟测试 Console 干净。"""
    return Response(status_code=204)


@app.get("/api/health")
def health() -> dict:
    """只读状态查询。不启动 parse_worker，不打开任何 PDF。"""
    deps = _pick_deps_dir()
    return {
        "service": "Ds Bit · Parser Lab",
        "pipeline": "parser_only",
        "llm_called": False,
        "database_written": False,
        "gate6a_status": "NOT_STARTED",
        "frozen": not _allow_parse(),
        "allow_parse": _allow_parse(),
        "note": "Reviewer 冻结期内 /api/parse 只返回 FROZEN，不执行解析",
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
        "git_head": _git_head(),
        "worker_timeout_seconds": DEFAULT_TIMEOUT,
        "max_upload_bytes": MAX_UPLOAD_BYTES,
        "artifact_files": [rel for _, rel in ARTIFACT_FILES],
        "contract_map": [
            {"contract_artifact": contract, "actual_file": actual or None,
             "status": status, "note": note}
            for contract, actual, status, note in CONTRACT_MAP
        ],
    }


def _collect_artifacts(run_dir: Path) -> tuple[dict, list[dict], list[str]]:
    """原样读取真实 artifacts。缺失项不进入 parser_output，只登记 MISSING。"""
    parser_output: dict = {}
    inventory: list[dict] = []
    missing: list[str] = []
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
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
            parser_output[key] = content
            state = "REAL_GENERATED"
            note = ""
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            state = "PARTIAL"
            note = "文件存在但无法作为 JSON 读取：%s: %s" % (type(exc).__name__, exc)
        inventory.append({
            "artifact": key, "actual_file": rel, "status": state,
            "sha256": _sha256_file(path), "bytes": path.stat().st_size,
            "note": note,
        })
    return parser_output, inventory, missing


def _frozen_payload() -> dict:
    payload = _base_payload("FROZEN")
    payload["document"] = None
    payload["diagnostics"] = {
        "reason": "Reviewer 冻结期：ICEX_WORKBENCH_ALLOW_PARSE 未设为 1",
        "parse_worker_started": False,
        "parse_pdf_calls": 0,
        "action_required": "等待 Reviewer 解除 Gate 6A 冻结并确认样本 / Gold / 运行边界",
    }
    return payload


@app.post("/api/parse")
async def api_parse(request: Request) -> JSONResponse:
    """单文件受控解析入口。绝不批量、绝不调用 LLM、绝不写数据库。"""
    started = time.time()
    if not _allow_parse():
        return JSONResponse(_frozen_payload())

    body = await request.body()
    if not body:
        return JSONResponse(_invalid("INVALID_FILE", "空文件，未收到 PDF 字节"))
    if len(body) > MAX_UPLOAD_BYTES:
        return JSONResponse(_invalid(
            "INVALID_FILE", "文件超过 %d 字节上限" % MAX_UPLOAD_BYTES))
    if not body.startswith(b"%PDF"):
        return JSONResponse(_invalid(
            "INVALID_FILE", "缺少 %PDF 魔数，不是有效 PDF"))

    filename = Path(unquote(request.headers.get("x-filename", "upload.pdf"))).name
    requested_mpn = unquote(request.headers.get("x-requested-mpn", "") or "")
    mpn_value = requested_mpn or Path(filename).stem
    mpn_source = "user_input" if requested_mpn else "filename_stem_fallback"
    upload_sha = hashlib.sha256(body).hexdigest()

    run_id = "G6A-" + datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(2)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = UPLOAD_DIR / (run_id + ".pdf")
    pdf_path.write_bytes(body)

    deps = _pick_deps_dir()
    worker_payload = {
        "src_dir": str(SRC_DIR),
        "deps_dir": str(deps) if deps else None,
        "pdf_path": str(pdf_path),
        "runs_root": str(RUNS_ROOT),
        "run_id": run_id,
        "requested_mpn": mpn_value,
    }

    payload = _base_payload("PARSING")
    payload["run_id"] = run_id
    payload["document"] = {
        "filename": filename,
        "sha256": upload_sha,
        "bytes": len(body),
        "page_count": None,
        "run_id": run_id,
        "requested_mpn": mpn_value,
        "requested_mpn_source": mpn_source,
        "requested_mpn_note": "这是调用 parse_pdf 的输入参数，不是 Parser 识别出的型号",
    }

    proc = subprocess.Popen(
        [sys.executable, str(WORKER), json.dumps(worker_payload, ensure_ascii=False)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(REPO),
    )
    timed_out = False
    try:
        out, err = proc.communicate(timeout=DEFAULT_TIMEOUT)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
        timed_out = True

    stdout_text = out.decode("utf-8", "replace")
    stderr_text = err.decode("utf-8", "replace")
    worker_json: dict | None = None
    if BEGIN in stdout_text and END in stdout_text:
        chunk = stdout_text.split(BEGIN, 1)[1].split(END, 1)[0].strip()
        try:
            worker_json = json.loads(chunk)
        except json.JSONDecodeError:
            worker_json = None

    parse_result: dict | None = None
    error_text: str | None = None
    if timed_out:
        status = "PARSE_TIMEOUT"
        error_text = "解析超过 %.0f 秒，已强制终止子进程" % DEFAULT_TIMEOUT
    elif worker_json is None:
        status = "PARSE_CRASH"
        error_text = ("解析子进程未返回有效 JSON 载荷，疑似原生崩溃；"
                      "returncode=%s" % proc.returncode)
    elif worker_json.get("ok") is not True:
        status = "PARSE_ERROR"
        error_text = "Parser 抛出异常：%s: %s" % (
            worker_json.get("error_type", "Exception"),
            worker_json.get("error", ""),
        )
    else:
        status = "PARSE_COMPLETED"
        parse_result = worker_json.get("result")

    payload["status"] = status
    payload["diagnostics"] = {
        "parse_worker_started": True,
        "parse_pdf_calls": 1 if status == "PARSE_COMPLETED" else 0,
        "worker_returncode": proc.returncode,
        "worker_timeout_seconds": DEFAULT_TIMEOUT,
        "elapsed_seconds": round(time.time() - started, 3),
        "worker_stderr_tail": stderr_text[-2000:],
        "worker_stdout_noise": (
            stdout_text.split(BEGIN, 1)[0][-500:]
            if BEGIN in stdout_text else stdout_text[-500:]
        ),
        "parser_error": error_text,
        "parse_summary": parse_result,
    }

    if status != "PARSE_COMPLETED":
        payload["diagnostics"]["missing_artifact_count"] = None
        return JSONResponse(payload)

    run_dir = RUNS_ROOT / run_id
    parser_output, inventory, missing = _collect_artifacts(run_dir)
    payload["parser_output"] = parser_output
    payload["artifact_inventory"] = inventory

    manifest = parser_output.get("run_manifest") or {}
    document_artifact = parser_output.get("document") or {}
    boundary = parser_output.get("boundary_decisions") or {}
    totals = boundary.get("totals") if isinstance(boundary, dict) else None

    payload["document"]["page_count"] = document_artifact.get("page_count")
    payload["document"]["document_id"] = document_artifact.get("document_id")
    payload["document"]["run_dir"] = str(run_dir)
    payload["code_version"] = {
        "git_head": _git_head(),
        "project_version": manifest.get("project_version"),
        "parser_version": manifest.get("parser_version"),
        "contract_version": manifest.get("contract_version"),
        "parser_config_sha256": manifest.get("parser_config_sha256"),
        "python_version": manifest.get("python_version"),
        "platform": manifest.get("platform"),
        "manifest_sha256": (parse_result or {}).get("manifest_sha256"),
    }
    payload["diagnostics"].update({
        "missing_artifacts": missing,
        "missing_artifact_count": len(missing),
        "sha256_cross_check": {
            "upload_sha256": upload_sha,
            "manifest_document_sha256": manifest.get("document_sha256"),
            "match": (manifest.get("document_sha256") == upload_sha)
            if manifest.get("document_sha256") else None,
            "note": "不一致说明源 PDF 与 run 产物之间发生了路径或字节漂移",
        },
        "boundary_totals": totals,
        "table_count_from_artifact": len(parser_output["tables"])
        if isinstance(parser_output.get("tables"), list) else None,
        "candidate_count_from_artifact": len(
            (parser_output.get("candidates") or {}).get("candidates", []))
        if isinstance(parser_output.get("candidates"), dict) else None,
        "note": "所有数值均由真实 artifacts 读取；取不到的字段保持 null，不做推断",
    })
    return JSONResponse(payload)


def _invalid(status: str, reason: str) -> dict:
    payload = _base_payload(status)
    payload["document"] = None
    payload["diagnostics"] = {
        "parse_worker_started": False,
        "parse_pdf_calls": 0,
        "reason": reason,
    }
    return payload


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
        print("  解冻后执行: python -m pip install uvicorn")
        print("  启动命令:   ICEX_WORKBENCH_ALLOW_PARSE=1 python serve_parser.py")
        raise SystemExit(2)
    import uvicorn

    print("[Parser Lab] frozen=%s  port=%s" % (
        not _allow_parse(), os.getenv("ICEX_WORKBENCH_PORT", "8765")))
    uvicorn.run(app, host="127.0.0.1",
                port=int(os.getenv("ICEX_WORKBENCH_PORT", "8765")))
