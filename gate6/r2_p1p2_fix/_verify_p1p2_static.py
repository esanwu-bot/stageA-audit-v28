"""P1/P2 修复的静态验收脚本（冻结期可运行，零解析 / 零服务 / 零 LLM）。

本脚本只做四件事：
1. ``py_compile`` 三个 Python 文件；
2. AST / 源码文本静态断言（不看运行结果，不需要启动服务）；
3. 仅 import ``serve_parser`` 检查路由能否注册（不调用 uvicorn.run，
   不打开 PDF，不调用 parse_pdf() / classify_one()）；
4. 比对冻结基线副本与 index.html 的 SHA-256。

运行：
    python workbench/_verify_p1p2_static.py

注意：本脚本**不证明** Parser 解析能力、分类准确率或 Gate 6A 质量，
也**不把代码状态升级为 PARSER_VERIFIED**。当前状态仍为
CODE_READY / UI_SMOKE_PASSED / PARSER_NOT_EXECUTED。
"""

from __future__ import annotations

import ast
import hashlib
import py_compile
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASELINE = HERE / "_diff" / "baseline"

RESULTS: list[tuple[str, str, bool, str]] = []


def check(cid: str, desc: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((cid, desc, bool(ok), detail))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def func_node(tree: ast.Module, name: str) -> ast.AST | None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def calls(tree: ast.AST) -> list[ast.Call]:
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call)]


def has_attr_call(tree: ast.AST, obj: str, attr: str,
                  keyword: str | None = None) -> bool:
    """AST 判定是否调用了 obj.attr(...)；可选要求带某个关键字参数。

    只查真实可执行节点，文档字符串里描述旧代码的文字不会被误判。
    """
    for node in calls(tree):
        fn = node.func
        if not isinstance(fn, ast.Attribute) or fn.attr != attr:
            continue
        if obj is not None and not (
                isinstance(fn.value, ast.Name) and fn.value.id == obj):
            continue
        if keyword is not None and not any(k.arg == keyword for k in node.keywords):
            continue
        return True
    return False


def imported_modules(tree: ast.AST) -> list[str]:
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.append(node.module)
    return out


def main() -> int:
    files = {
        "serve": HERE / "serve_parser.py",
        "parse_worker": HERE / "parse_worker.py",
        "classify_worker": HERE / "classify_worker.py",
    }
    for label, path in files.items():
        check("C-%s" % label, "%s 存在" % path.name, path.is_file(), str(path))
        if not path.is_file():
            continue
        try:
            py_compile.compile(str(path), doraise=True, cfile=str(
                HERE / "__pycache__" / (path.stem + ".verify.pyc")))
            check("P-%s" % label, "%s 通过 py_compile" % path.name, True)
        except py_compile.PyCompileError as exc:
            check("P-%s" % label, "%s 通过 py_compile" % path.name, False, str(exc))

    serve_text = source(files["serve"])
    serve_tree = ast.parse(serve_text)

    # --- P1-1 流式上传 ---
    # 用 AST 判定：文档字符串里描述旧实现（"不再使用 request.body()"）的文字
    # 不能算作真实调用，也不能把修复误判成 FAIL。
    check("F-01", "AST 中不存在任何 request.body() 调用",
          not has_attr_call(serve_tree, "request", "body"))
    await_body = False
    for node in ast.walk(serve_tree):
        if isinstance(node, ast.Await) and isinstance(node.value, ast.Call):
            fn = node.value.func
            if isinstance(fn, ast.Attribute) and fn.attr == "body":
                await_body = True
    check("F-02", "AST 中无 request.body() 的 await 调用", not await_body)
    check("F-03", "使用 request.stream() 分块异步读取",
          has_attr_call(serve_tree, "request", "stream"))
    check("F-04", "预检 Content-Length",
          'headers.get("content-length")' in serve_text)
    check("F-05", "超限返回 HTTP 413",
          "413" in serve_text and "TOO_LARGE" in serve_text)

    # --- P1-2 异步非阻塞 ---
    check("F-06", "AST 中无 subprocess.Popen 调用",
          not has_attr_call(serve_tree, "subprocess", "Popen"))
    check("F-07", "AST 中无 communicate(timeout=...) 同步等待",
          not any(
              isinstance(n.func, ast.Attribute) and n.func.attr == "communicate"
              and any(k.arg == "timeout" for k in n.keywords)
              for n in calls(serve_tree)))
    check("F-08", "使用 asyncio.create_subprocess_exec",
          has_attr_call(serve_tree, "asyncio", "create_subprocess_exec"))
    check("F-09", "使用 asyncio.to_thread 处理文件 IO / git",
          has_attr_call(serve_tree, "asyncio", "to_thread"))
    check("F-10", "有最大并发 worker 闸门",
          "MAX_CONCURRENT_WORKERS" in serve_text
          and "asyncio.Semaphore" in serve_text)

    # --- P1-3 阶段标记统计 ---
    check("F-11", "parse_pdf_calls 由 parser_call_entered 推导",
          "parser_call_count = 1 if stages[\"parser_call_entered\"] else 0"
          in serve_text)
    check("F-12", "不再按成功状态错记调用次数",
          '1 if status == "PARSE_COMPLETED" else 0' not in serve_text)
    check("F-13", "worker 启动失败单独归类 WORKER_START_FAILED",
          '"WORKER_START_FAILED"' in serve_text
          and "start_failed" in serve_text)
    worker_text = source(files["parse_worker"])
    entered = worker_text.find('_stage("PARSER_CALL_ENTERED")')
    call = worker_text.find("result = parse_pdf(")
    check("F-14", "parse_worker 在 parse_pdf() 前打印 PARSER_CALL_ENTERED",
          0 <= entered < call, "entered@%d call@%d" % (entered, call))
    check("F-15", "parse_worker 有 PARSER_CALL_RETURNED",
          '_stage("PARSER_CALL_RETURNED")' in worker_text)

    # --- P2-1 MISSING / PARTIAL 分离 ---
    for cid, token in (
        ("F-16", "missing_artifact_count"),
        ("F-17", "partial_artifact_count"),
        ("F-18", "required_artifact_failure_count"),
        ("F-19", "required_artifact_complete"),
    ):
        check(cid, "%s 已单独统计" % token, token in serve_text)
    check("F-20", "PARTIAL 计入失败总数",
          'len(missing) + len(partial)' in serve_text)

    # --- 双入口隔离 ---
    parse_fn = func_node(serve_tree, "api_parse")
    process_fn = func_node(serve_tree, "api_process")
    parse_src = ast.get_source_segment(serve_text, parse_fn) if parse_fn else ""
    process_src = ast.get_source_segment(serve_text, process_fn) if process_fn else ""
    check("G-01", "/api/parse 存在", parse_fn is not None)
    check("G-02", "/api/process 存在", process_fn is not None)
    check("G-03", "/api/parse 处理器不引用分类器",
          parse_fn is not None and "classif" not in parse_src.lower(),
          "Parser-only 入口不得混入分类结果")
    check("G-04", "/api/parse 仍调用 Parser 执行路径",
          "_execute_parse" in parse_src)
    check("G-05", "/api/process 先分类再按 DATASHEET 决定是否解析",
          "CLASSIFIER_WORKER" in process_src
          and "_build_classification" in process_src
          and "_execute_parse" in process_src)
    check("G-06", "/api/process 三出口齐全",
          all(t in process_src or t in serve_text
              for t in ("DATASHEET", "NON_DATASHEET", "AMBIGUOUS")))
    check("G-07", "分类器字段来自真实入口",
          "icpdf.classification.classifier.classify_one" in serve_text
          or "from icpdf.classification.classifier import classify_one"
          in source(files["classify_worker"]))
    cls_tree = ast.parse(source(files["classify_worker"]))
    cls_imports = imported_modules(cls_tree)
    forbidden_imports = [m for m in cls_imports if any(
        bad in m for bad in ("icpdf.parser", "dashscope", "openai",
                             "httpx", "requests", "urllib"))]
    check("G-08", "分类器 worker AST 中无 parser / LLM / 网络 import",
          not forbidden_imports, ",".join(forbidden_imports))
    def has_name_or_attr(tree: ast.AST, name: str) -> bool:
        return any(
            (isinstance(n, ast.Name) and n.id == name)
            or (isinstance(n, ast.Attribute) and n.attr == name)
            for n in ast.walk(tree))

    check("G-08b", "分类器 worker 只引用官方分类入口",
          "icpdf.classification.classifier" in cls_imports
          and has_name_or_attr(cls_tree, "classify_one")
          and not has_name_or_attr(cls_tree, "parse_pdf"),
          ",".join(cls_imports))
    check("G-09", "Gate 6A Parser-only 不启动分类 worker",
          "CLASSIFIER_WORKER" not in parse_src)
    check("G-10", "冻结开关默认关闭且两入口共用",
          'os.getenv("ICEX_WORKBENCH_ALLOW_PARSE", "0") == "1"' in serve_text
          and serve_text.count("if not _allow_parse():") >= 2)

    # --- R2 红线：路径穿越 / 文件名安全 ---
    check("S-01", "物理落盘名由 uuid4 生成（与用户输入零耦合）",
          "uuid.uuid4().hex" in serve_text)
    check("S-02", "落盘路径用 physical_filename 拼接",
          'target_dir / meta["physical_filename"]' in serve_text)
    check("S-03", "UPLOAD_DIR 只与服务端生成的 request_id 拼接",
          re.findall(r"UPLOAD_DIR / [A-Za-z_\"\[]+", serve_text)
          == ["UPLOAD_DIR / request_id"]
          and "stored_filename" not in serve_text,
          ",".join(re.findall(r"UPLOAD_DIR / [A-Za-z_\"\[]+", serve_text)))
    check("S-04", "落盘前有 is_relative_to 越界断言",
          "is_relative_to" in serve_text)
    check("S-05", "证据名清洗会剥掉首尾点号与空格",
          'strip(" .")' in serve_text)
    check("S-06", "分类 worker 用 os.link 建立证据名硬链接",
          has_attr_call(cls_tree, "os", "link"))
    check("S-07", "硬链接失败时退回复制（字节不变）",
          has_attr_call(cls_tree, "shutil", "copyfile"))
    check("S-08", "分类 worker 只把临时链接路径交给 classify_one",
          any(isinstance(n.func, ast.Name) and n.func.id == "classify_one"
              and len(n.args) == 1 and isinstance(n.args[0], ast.Call)
              and isinstance(n.args[0].func, ast.Name)
              and n.args[0].func.id == "str"
              for n in calls(cls_tree)))
    check("S-09", "分类结束删除临时目录",
          has_attr_call(cls_tree, "shutil", "rmtree"))
    check("S-10", "分类 worker 也做证据名越界断言",
          "is_relative_to" in source(files["classify_worker"]))

    # --- 仅 import 的路由注册检查（不启动服务）---
    sys.path.insert(0, str(HERE))
    try:
        import serve_parser as srv  # noqa: PLC0415  静态验证：模块级代码不启动服务
        routes = {r.path for r in srv.app.routes}
        check("R-01", "路由可注册（含 /api/process）",
              {"/api/parse", "/api/process"}.issubset(routes),
              ",".join(sorted(routes)))
        check("R-02", "导入后冻结开关仍为关闭", not srv._allow_parse())
        check("R-03", "导入后 classify worker 文件存在",
              srv.CLASSIFIER_WORKER.is_file())
    except Exception as exc:  # noqa: BLE001
        check("R-01", "路由可注册（含 /api/process）", False,
              "%s: %s" % (type(exc).__name__, exc))

    # --- 冻结基线与未改动文件 ---
    expected = {
        "serve_parser.py": "215e9a8b627671f6f2145ae95c8eaa84c8a3d9c956d03063127e4dc7c2cf5815",
        "parse_worker.py": "9efc699e1429c1d34a6a04bc13198cb6c2f49be07234f6ad2f9ae0af67ec5c79",
    }
    for name, digest in expected.items():
        actual = sha256_file(BASELINE / name)
        check("B-%s" % name, "基线副本 %s 与冒烟轮记录一致" % name,
              actual == digest, actual)
    index_hash = sha256_file(HERE / "index.html")
    check("B-index", "index.html 未被本轮改动（UI 冒烟证据保持有效）",
          index_hash == "76407504af8dbc0eb1ee2214c024e6dc7088f6580616dbef29bc7adb5b63a5bb",
          index_hash)

    passed = sum(1 for r in RESULTS if r[2])
    failed = [r for r in RESULTS if not r[2]]
    print("P1P2_STATIC_VERIFY: %d/%d PASS, %d FAIL" % (
        passed, len(RESULTS), len(failed)))
    for cid, desc, ok, detail in RESULTS:
        print("  %s %-4s %s%s" % (
            "OK  " if ok else "FAIL", cid, desc,
            (" | " + detail) if detail and not ok else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
