# Workbench 后端 P1/P2 修复与双入口架构 · 代码变更记录

**本轮状态：`CODE_READY / P1P2_FIXED / NOT_EXECUTED`**

| 状态项 | 值 |
| --- | --- |
| Workbench 代码 | `CODE_READY`（本轮已修 P1/P2，双入口已落地） |
| localhost UI 冒烟 | `UI_SMOKE_PASSED`（上一轮证据，本轮未重跑） |
| Parser 真实解析 | `PARSER_NOT_EXECUTED` |
| 分类器真实调用 | `CLASSIFIER_NOT_EXECUTED` |
| Gate 6A Benchmark | `NOT_STARTED` |
| 服务器部署 | `NOT_APPROVED` |
| `ICEX_WORKBENCH_ALLOW_PARSE` | `0`（冻结开关保持关闭） |
| `ICPDF_EXTRACTOR_LLM_READY` | `false`（未变） |

> 本轮**只改代码 + 静态验收**。没有启动服务、没有启动 Worker、没有打开任何 PDF、
> 没有调用 `parse_pdf()` 或 `classify_one()`、没有调用 LLM、没有建库、
> 没有生成任何 Parser 产物或 Run ID、没有 git add / commit / push。
> 本文件不声称 `PARSER_VERIFIED`，也不声称 Gate 6A 已执行或通过。

---

## 1. 分类器真实接口静态核查（不执行分类器）

分类门禁的字段一律取自仓库现有 V2 分类器，未新造标签、未伪造证据。
以下均为**只读静态定位**，代码位置为 `E:\workspace\icpdf-extractor` 权威基线。

| 项目 | 真实值 / 位置 |
| --- | --- |
| 官方单份入口 | `src/icpdf/classification/classifier.py:530-534` `classify_one(path, *, rule_version, first_pages=3, mock=False, original=None)` |
| 子进程 worker | `classifier.py:488-527` `_classify_worker()`；`ClassifierV2.classify()` 在 `:829-831` 委托 `classify_one()` |
| 展平口径 | `src/icpdf/classification/cli.py:55-84` `_flatten()`（Gate 1 亦使用） |
| Gate 1 隔离先例 | `runs/_gate1_classify_worker.py`：独立子进程 + `__GATE1_JSON_BEGIN__` / `__GATE1_JSON_END__` 哨兵，父进程超时强杀 |
| 契约版本 | `models.py:36` `RULE_VERSION = "doc-classifier-v2"` |
| 实现版本 | `models.py:38` `CLASSIFIER_VERSION = "docclassifier-2.2.1"` |
| 判定标签 `DocType` | `models.py:54-63`：`DS_STRONG / DS_WEAK / EVM / AN / UG / SMD / UNKNOWN / OCR` |
| 路由档位 `RoutingClass` | `models.py:66-73`：`DS_STRONG / DS_WEAK / EVM / UNKNOWN / ERROR` |
| 流水线 `Route` | `models.py:76-80`：`IC_PARSE / REVIEW / QUARANTINE / OCR` |
| 置信度 `Confidence` | `models.py:135-138`：`high / medium / low`（离散枚举，**没有**数值分数；不伪造 0-1 分数） |
| 路由矩阵 | `models.py:188-206`：`DS_STRONG → IC_PARSE`、`DS_WEAK → REVIEW`、`EVM → QUARANTINE`、`UNKNOWN/ERROR → REVIEW` |
| 输出契约 | `models.py:417-443` `ClassificationResult`：`doc_type / doc_confidence / route / rule_version / classifier_version / matched_rules / rejected_rules / unmatched_rules / evidence_pages / page_evidence / source_sha256 / source_hash_status / review_status / semantic_type / assigned_type / provenance / classification_status / failure_kind / ic_datasheet_extraction / read_status / evidence_conflict` |
| 兼容视图 | `evidence.py:63-91`：`classification` / `routing` 与扁平契约同源派生 |
| **硬不变量** | `models.py:444-456`：`route == IC_PARSE` **当且仅当** `doc_type == DS_STRONG`，违反直接抛 `ValueError`；`:479-522` 另校 `assigned_type / route / ic_datasheet_extraction / classification_status` 五条一致性 |
| 纯规则 / 零 LLM | 全目录 grep `yaml / dashscope / openai / requests / httpx / urllib / api_key / llm` → **0 处真实依赖**（`fullmatch` 属误命中）；分类器只读文件名、元数据、前 3 页文本，不 import `icpdf.parser.*` |

因此 `classification` 对象里的 `confidence` 是真实的 `doc_confidence` 枚举值
（`high/medium/low`），不是编造的数值；`evidence_pages`、`matched_rules`、
`page_evidence`、`rejected_rules` 全部原样来自 `ClassificationResult`。

---

## 2. `/api/process` 三出口裁决（显式白名单，fail-closed）

调用链：`validate_pdf()` → `classify_document()`（独立子进程调 `classify_one()`）
→ 仅 `DATASHEET` 才 `parse_pdf()`。

`DATASHEET` **当且仅当**以下全部成立（任一不成立即不放行）：

```
classify_one() 成功返回
AND result.route                     == "IC_PARSE"
AND result.doc_type                  == "DS_STRONG"
AND result.classification_status     == "SUCCESS"
AND result.read_status               == "OK"
AND result.source_hash_status        == "success"
AND result.ic_datasheet_extraction   is True
AND result.evidence_conflict         is False
AND result.source_sha256             == 上传字节 SHA-256
```

| 出口 | 判定条件 | 后续动作 |
| --- | --- | --- |
| `DATASHEET` | 上述白名单全成立 | 允许进入 `parse_pdf()`；`classification` 对象与 Parser 证据分栏保存 |
| `NON_DATASHEET` | 分类成功、无证据冲突、哈希一致，且 `doc_type ∈ {EVM, AN, UG, SMD}` 或 `semantic_type ∈ {EVM, USER_GUIDE, APP_NOTE, REFERENCE_DESIGN}` | 立即终止，返回分类判断 + `evidence_pages` / `matched_rules`；`parser.called=false`，**不创建 Run 目录** |
| `AMBIGUOUS` | 其余一切：`DS_WEAK` / `UNKNOWN` / `OCR` / 低置信度 / 证据冲突 / 读取失败 / 分类异常 / 超时 / 崩溃 / 哈希不一致 | 隔离待人工复核，绝不默认放行；`parser.called=false` |

分类器启动失败 / 超时 / 崩溃 / 抛异常分别归为
`WORKER_START_FAILED`（带 `worker_kind=classify`）/ `CLASSIFICATION_TIMEOUT` /
`CLASSIFICATION_CRASH` / `CLASSIFICATION_ERROR`，全部 fail-closed。

**字段口径说明**：`classification.is_datasheet` 直取 `semantic_type == IC_DATASHEET`
（本体语义，`DS_WEAK` 也会是 `true`）；只有 `is_confirmed_datasheet` 与
`admit_to_parser` 才代表可进 Parser，避免把弱证据当成放行依据。

**分类 Token 隔离**：本分类器为纯规则实现，`classification.classifier_llm_calls = 0`、
`classifier_token_usage = 0`、`llm_called = false`。若将来分类器改用 LLM，
必须在此处单独计量分类 Token，不得再声称整个流程零 Token。

---

## 3. 六项 P1/P2 修复（逐项对照）

| 编号 | Reviewer 问题 | 修复前 | 修复后 |
| --- | --- | --- | --- |
| P1-1 | `await request.body()` 先读完整包才判 80 MiB | `body = await request.body()` | `_read_body_stream()`：先查 `Content-Length`（超限一个字节都不读），再 `async for chunk in request.stream()` 分块累计，超限立即 `HTTP 413`；不落盘、不建 Run ID、不启动 worker |
| P1-2 | `async def` 里 `Popen().communicate(timeout=...)` 阻塞事件循环 | `subprocess.Popen` + `proc.communicate(timeout=DEFAULT_TIMEOUT)` | `asyncio.create_subprocess_exec()` + `asyncio.wait({task}, timeout=...)`，超时 `kill()` 后继续 await 原 task；`asyncio.Semaphore(MAX_CONCURRENT_WORKERS)` 限并发；文件 IO / git 走 `asyncio.to_thread()` |
| P1-3 | `parse_pdf_calls = 1 if status == "PARSE_COMPLETED" else 0` 把崩溃/超时的已发生调用记成 0 | 按成功状态推断 | `parse_worker.py` 在 `parse_pdf()` **之前**输出 `[WORKER] PARSER_CALL_ENTERED` 并 flush；父进程按 `WORKER_STARTED / PARSER_CALL_ENTERED / PARSER_CALL_RETURNED` 阶段标记统计 `parse_worker_started`、`parser_call_entered`、`parser_call_returned`、`parser_call_count`；JSON 载荷里的 `stages` 作冗余补充。前端原字段 `diagnostics.parse_pdf_calls` 保留为正确值的别名 |
| P2-1 | `_collect_artifacts()` 的 `PARTIAL` 未计入失败统计 | 只返回 `missing` | 分开返回 `missing_artifacts / partial_artifacts / missing_artifact_count / partial_artifact_count / required_artifact_failure_count / required_artifact_complete`；`required_artifact_failure_count = missing + partial`，`PARTIAL` 绝不算完整产物 |
| P2-2 | `Popen()` 启动异常未单独归类 | 无处理 | `create_subprocess_exec()` 的 `OSError / ValueError / RuntimeError`（含 `NotImplementedError`）捕获为 `WORKER_START_FAILED`，`start_error` 留痕，`worker_kind` 区分 parse / classify，不混为 `PARSE_CRASH` |
| P1-0 | 正式入口没有分类器门禁 | 只有 `/api/parse` 直接调 Parser | 新增 `/api/process`，见第 2 节；`/api/parse` 保持 Parser-only，**处理器源码内不出现任何 classifier 引用** |

---

## 4. 双入口隔离

| | `/api/parse` | `/api/process` |
| --- | --- | --- |
| 用途 | Gate 6A Parser-only 测试入口 | 正式用户入口 |
| `pipeline` | `parser_only` | `preparse_gate_v1` |
| 调用分类器 | **否**（`classification: null`、`classifier_called: false`） | 是，独立 `classification` 对象 |
| 调用链 | `validate_pdf → parse_pdf` | `validate_pdf → classify_one → DATASHEET only → parse_pdf` |
| 冻结期 | 返回 `FROZEN`，不读请求体 | 返回 `FROZEN`，不读请求体、不打开 PDF |
| 分类结果 | 绝不进入 Parser-only 质量成绩 | 与 `parser_output` / `artifact_inventory` 分栏，不互相覆盖 |

`index.html` **本轮未改动**（SHA-256 仍为
`76407504af8dbc0eb1ee2214c024e6dc7088f6580616dbef29bc7adb5b63a5bb`），
因此上一轮已提交 Reviewer 的 UI 冒烟截图与证据保持有效。
`/api/process` 目前是后端 API，前端切换开关留待代码审查通过后再单独提交，
避免本轮污染已接受的 UI 证据。

分类器代码**没有**塞进 `src/icpdf/parser/*`，Parser 核心算法零改动；
分类与解析各自在独立子进程中执行（分类也会打开 PDF、加载 PyMuPDF，
损坏文件可能 native 崩溃，必须同样隔离 + 超时强杀）。

---

## 5. 静态验收结果（真实输出）

| 检查 | 结果 |
| --- | --- |
| `python -m py_compile serve_parser.py parse_worker.py classify_worker.py` | `PY_COMPILE_OK` |
| `workbench/_verify_p1p2_static.py` | **`53/53 PASS, 0 FAIL`**（日志：`workbench/_smoke/_p1p2_static_verify.log`） |
| 仅 import `serve_parser` 的路由注册 | 路由 `['/openapi.json','/','/favicon.ico','/api/health','/api/parse','/api/process','/api/page']`；`frozen=True`；未调用 `uvicorn.run` |
| `WORKBENCH_P1P2_FIX.diff` 可应用性 | `git -c core.autocrlf=false apply --check -p1` **OK**；应用后 4 个文件与工作区**逐字节一致**（`REBUILD_ALL_IDENTICAL True`） |
| 冻结基线副本 | 与冒烟轮记录一致：`serve_parser.py 215e9a8b…`、`parse_worker.py 9efc699e…` |
| `index.html` | 未改动（哈希一致） |
| Git HEAD | `3ed22a4a83564b36ca238792af4b2328fd966469`，未变；主项目零 add / commit / push |

> 说明：本机 `core.autocrlf=true`，直接 `git apply` 会把 LF 写成 CRLF，
> 导致重建文件只是换行符不同。用 `git -c core.autocrlf=false apply` 后逐字节一致，
> 证明 diff 本身无缺陷。这是环境设置，不是交付件问题。

**验收边界**：`53/53 PASS` 只证明代码语法、AST 结构、路由可注册、基线与哈希一致；
**不证明** Parser 解析质量、分类准确率、Gold Set、Gate 6A 通过或可发布。

---

## 6. 零调用声明与遗留状态

本轮真实计数：

```
启动服务                     0（未启动新服务）
parse_worker 子进程           0
classify_worker 子进程        0
parse_pdf() 调用              0
classify_one() 调用           0
打开的 PDF                   0
LLM / qwen-flash 调用        0
数据库 / PostgreSQL 操作     0
新建 Parser 产物 / Run ID    0
主项目 git add/commit/push   0
```

本轮实际做过的「非纯文本」动作只有五项，均不构成解析：
`py_compile` 生成 `.pyc`、静态验证脚本 import 了 `serve_parser` 模块
（仅注册路由，未启动 uvicorn）、在临时目录用 `git apply` 验证 diff 可重建、
把传输包 clone / commit / push 到 GitHub 审计仓库、在全新克隆上复跑
`sha256sum -c` 与 `git apply`。全程未打开任何 PDF、未启动服务、未调用
`parse_pdf()` / `classify_one()`。

**遗留服务如实披露**：上一轮 localhost UI 冒烟阶段启动的
`python.exe serve_parser.py`（`PID 184116`）仍在 `127.0.0.1:8765` 监听，
`ICEX_WORKBENCH_ALLOW_PARSE=0`、`frozen=True`，内存中仍是**修复前**的旧代码。
本轮**未启动、未重启、未停止、未向它发送任何请求**，按「冻结期仅改代码」的
边界原样保留。后续任何验证前必须由获授权步骤重启，否则会命中旧代码。

---

## 7. 本轮交付文件

| 文件 | 说明 |
| --- | --- |
| `workbench/serve_parser.py` | 重写：双入口、流式上传、异步子进程、阶段标记统计、missing/partial 分离、WORKER_START_FAILED |
| `workbench/parse_worker.py` | 新增 5 个阶段标记，`PARSER_CALL_ENTERED` 在 `parse_pdf()` 之前 |
| `workbench/classify_worker.py` | **新增**：分类子进程，只调 `classify_one()`，哨兵隔离，零 LLM |
| `workbench/_verify_p1p2_static.py` | **新增**：53 项静态验收脚本（可复跑，不启动服务） |
| `workbench/WORKBENCH_P1P2_FIX.diff` | 统一 diff（2 改 + 2 新增，1,771 行 / 79,407 字节） |
| `workbench/_diff/baseline/` | 改动前冻结副本，供 diff 复现 |
| `workbench/_smoke/_p1p2_static_verify.log` | 静态验收原始输出 |
| `workbench/WORKBENCH_P1P2_FIX_REPORT.md` | 本文件 |
| `workbench/SHA256SUMS.txt` | 全部交付件哈希重算 |

---

## 8. 仍未解决 / 等待授权

- Reviewer 代码审查（传输包已推送 GitHub `esanwu-bot/stageA-audit-v28` 的
  `gate6/r2_p1p2_fix/` 目录；主项目 CodeUp 仓库零 add / commit / push）。
- 服务器部署仍 `NOT_APPROVED`；服务器必须保持 `ALLOW_PARSE=0` 并补访问控制。
- Gate 6A Benchmark 仍 `NOT_STARTED`；Gold Set 未创建；V002/V022 单件探针未执行。
- Gate 6B / 6C / 6D、剩余 320 件、LLM 接入全部 `NOT_APPROVED`。
- `CLASSIFIER_AUDIT` 仍 `FAIL`，`CONTENT_QC` 仍 `PENDING`（服务器侧 1,729 件未补跑）。
- 数据侧 8 个哈希冻结，未改任何数据文件。

---

## 9. R2 安全复核：Reviewer 四大红线逐条对照

> 本轮新增改动只做一件事：**把磁盘物理名与用户输入彻底解耦**（`<uuid4>.pdf`），
> 并把分类器需要的文件名证据改成「私有临时目录内硬链接」注入。
> Parser 核心、分类规则、阈值、路由矩阵、`index.html` 均未改动。

### 9.1 红线一：路径穿越与文件名安全

**结论：PASS。用户输入已完全不参与任何路径拼接。**

| 环节 | 实现 | 位置 |
| --- | --- | --- |
| 物理文件名 | `uuid.uuid4().hex + ".pdf"`，与请求内容无关 | `serve_parser.py:325-332` |
| 请求目录 | `UPLOAD_DIR / request_id`，`request_id = _new_id("WB")`（服务端生成） | `serve_parser.py:226-229, 415-434` |
| 落盘路径 | `target_dir / meta["physical_filename"]` | `serve_parser.py:425` |
| 越界断言 | `resolved.is_relative_to(target_dir.resolve())`，不成立直接抛错、拒绝写入 | `serve_parser.py:427-429` |
| 用户提交名 | 只进 `meta`（`submitted_filename` / `evidence_filename`），从不参与 `/` 拼接 | `serve_parser.py:335-354` |
| 证据名清洗 | `Path(...).name` → 反斜杠归一 → `rsplit("/")` → 剔除控制符/保留字符 → `strip(" .")` → 空则 `upload.pdf` | `serve_parser.py:307-322` |

静态验收断言：`S-01`~`S-05` 全部 PASS，其中 `S-03` 用正则枚举
`UPLOAD_DIR / ...` 的全部拼接点，结果只有 `UPLOAD_DIR / request_id` 一处。

### 9.2 文件名证据如何不丢（这是 UUID 化的代价，已用硬链接补回）

分类器 `classify_one()` 从 `path.name` 取 `mpn` / `provenance`，物理名改成
UUID 后不能直接把 uuid 路径交给它。处理方式：

1. 父进程把清洗后的**证据名**通过 `spec["original_filename"]` 传给 worker；
2. worker 在 `tempfile.mkdtemp()` 私有目录内 `os.link(物理文件, 证据名)`
   建硬链接（跨卷 `OSError` 时退 `shutil.copyfile`，字节完全相同）；
3. 再对链接路径做一次 `is_relative_to()` 越界断言；
4. `classify_one(str(link))` → `finally: shutil.rmtree(tmp_dir)`；
5. 硬链接不复制字节，`source_sha256` 仍是同一份上传字节的哈希，
   `_build_classification` 的 `source_sha256_matches_upload` 语义不变。

位置：`classify_worker.py:66-95`（`_evidence_name` / `_link_for_evidence`）、
`classify_worker.py:111-119`（阶段标记与清理顺序）。

### 9.3 红线二：分类器与 Workbench 双重校验

**结论：PASS。两层互相独立，任一不成立即 fail-closed。**

- 第一层（模型层，不可绕过）：`ClassificationResult.check_route_invariant`
  断言 `route == IC_PARSE ⟺ doc_type == DS_STRONG`；`assemble_record()` 另调
  `assert_route_invariant()`。worker 只透传 `record`，不合成、不改写任何标签。
- 第二层（Workbench 白名单，8 项全成立才 DATASHEET）：
  `route=IC_PARSE`、`doc_type=DS_STRONG`、`classification_status=SUCCESS`、
  `read_status=OK`、`source_hash_status=success`、`ic_datasheet_extraction=true`、
  `evidence_conflict=false`、`source_sha256` 与上传字节 SHA-256 逐字节一致
  （`serve_parser.py:141-158`、`599-707`）。
- 即使分类器返回 `IC_PARSE`，只要白名单缺一项，`decision` 只能是
  `AMBIGUOUS`，`_execute_parse` 不会被调用，不建 Run 目录。

### 9.4 红线三：子进程清理（防僵尸）

**结论：直接子进程回收已实现；进程树清理未验证/待整改。**

- 超时路径：`asyncio.wait(timeout)` → `proc.kill()`（`serve_parser.py:498`）
  → `await asyncio.wait_for(comm, timeout=10)` 回收管道 → 无论成败
  `await proc.wait()`（`serve_parser.py:509`）确保 waitpid 完成、不留僵尸。
- 通信任务异常不会把状态改写成成功（`except Exception` 只追加 stderr 标记）。
- 并发闸门是**模块级单例信号量** `_worker_semaphore()`（`serve_parser.py:184-189`），
  `_run_child` 整体包在 `async with` 内（`serve_parser.py:471`），
  `/api/parse` 与 `/api/process` 都经由 `_run_child`，因此全局生效；
  默认 `MAX_CONCURRENT_WORKERS=2`，可用环境变量调整。
- **未闭合的部分**：`proc.kill()` 在 Windows 上等价 `TerminateProcess`，
  只作用于 `create_subprocess_exec` 的**直接子进程**。当前两个 worker 均为单进程
  纯 Python，暂无孙进程；但一旦 Parser 引入 `multiprocessing` 或外部工具，
  孙进程会在父进程被 kill 后残留。该风险**未验证**，整改方案（`psutil` 进程树
  递归 kill，先子后父）见 `gate6/r2_p1p2_fix/smoke_frozen/README.md` §3.2。

### 9.5 红线四：审计标记可靠性

**结论：PASS。**

- 两个 worker 的 `_stage()` 都是 `sys.stdout.write("[WORKER] %s\n")` 紧跟
  `sys.stdout.flush()`（`classify_worker.py:47-52`、`parse_worker.py:33-38`），
  不依赖进程退出时的缓冲区刷写，native 崩溃前已写出的行父进程能读到。
- `parse_worker.py` 的 `PARSER_CALL_ENTERED` 在 `parse_pdf()` **之前**输出
  （`parse_worker.py:80-81`）。
- 去重：父进程把 stdout 解析成列表后只做布尔判定
  `parser_call_count = 1 if stages["parser_call_entered"] else 0`
  （`serve_parser.py:770`），同一 Run 的标记重复出现也只计 1 次；
  `_merge_payload_stages()` 用 `not in stages_seen` 去重后并入 JSON 冗余标记。
- 每个 Run 的 stdout 是各自子进程的独立管道，不存在跨 Run 共用日志导致串号。

### 9.6 本轮仍存在的残余风险（如实登记，未在冻结期处理）

1. **Windows 设备名**：`_evidence_name()` 未拦截 `CON`/`NUL`/`COM1` 等保留名。
   影响面已从「落盘」缩小到「worker 私有临时目录内的链接名」，最坏结果是
   分类失败 → `AMBIGUOUS`（fail-closed），不构成越界或数据泄露。
2. **硬链接跨卷退化为复制**：系统临时目录与 `E:` 不同卷时每个文件会多一次
   最多 80 MiB 的临时复制，分类结束即删除。属性能成本，不影响正确性。
3. **上传目录无回收策略**：`workbench/uploads/<request_id>/` 只增不删，
   需在解冻后加 TTL 清理（本轮冻结期不动运维逻辑）。
4. **信号量不覆盖上传阶段**：并发上传仍可同时占用内存（每请求 ≤ 80 MiB），
   信号量只约束子进程数量。若需抗压，应在反向代理层加并发上限。

