# Workbench localhost 启动与 UI 冒烟测试报告（第一阶段证据）

- 时间：2026-11-10
- 授权范围：**仅 localhost 启动 + UI 冒烟测试**，`ICEX_WORKBENCH_ALLOW_PARSE=0`
- 状态：`UI_SMOKE_PASSED` / `PARSER_NOT_EXECUTED`
- 唯一权威基线：`E:\workspace\icpdf-extractor`，分支 `feat/s2b-schema-d4-d6`，HEAD `3ed22a4a83564b36ca238792af4b2328fd966469`（未变）
- 主项目 git `add` / `commit` / `push` = 0

## 0. 授权边界澄清（不隐瞒）

上一条消息曾授权「解除 Workbench 冻结，对 V002 / V022 做 1–3 件真实单件解析探针」；**最新消息把授权收窄为第一阶段只做启动与 UI 冒烟，并明确「不要在这一步测试真实 PDF 解析」**。本轮按最新口径执行：

- 全程 `ICEX_WORKBENCH_ALLOW_PARSE=0`，未设置过 1。
- **V002 / V022 未做任何解析**。只从 `ds_parse_candidates_350_v2.csv` 读取了两行原文用于定位路径，未打开 PDF、未调用 `parse_pdf()`。
- 浏览器里选择/拖放的 PDF 仅用于验证前端交互与冻结开关；后端收到后直接返回 `FROZEN`，文件字节未被读取用于解析。
- 上一条要求的「子进程崩溃注入验证」属于解析流程验证，本阶段**未执行**，如实留待后续阶段。

## 1. 状态口径（按最新表）

| 项目 | 状态 |
| --- | --- |
| Workbench 代码 | `CODE_READY` |
| localhost UI 冒烟测试 | **`UI_SMOKE_PASSED`（本轮完成）** |
| Parser 真实解析 | **`NOT_EXECUTED`** |
| Gate 6A 质量评估 | **`NOT_STARTED`（未改变）** |
| LLM 接入 | `NOT_APPROVED` |
| 服务器部署 | 等待本地证据审查 |

启动成功**不代表** Gate 6A 已执行、Parser 已被验证或 Benchmark 通过。

## 2. 依赖隔离（未污染全局）

`workbench/_deps` 用 `python -m pip install --no-deps --target ... uvicorn python-multipart h11` 安装：

```
uvicorn 0.54.0 / h11 0.16.0 / python-multipart 0.0.33
```

- `--no-deps` 避免把 pydantic / anyio 副本带进隔离目录；隔离环境复用的仍是全局 `fastapi 0.162.0` / `pydantic 2.14.2`。
- 启动前：`uvicorn=False multipart=False h11=False yaml=False`；启动后不带 `PYTHONPATH` 复测：`uvicorn_in_global=False multipart_in_global=False h11_in_global=False`。**全局 site-packages 未被污染**。
- Parser 侧 PyYAML 仍来自 `runs/stage_a_350/gate6a/_deps`（`/api/health` 的 `deps_dir` 已证实），未改用全局、未复制 Parser 逻辑。

## 3. 启动 / 关闭记录（含一次真实失败与修复）

| 次序 | 命令 | 结果 |
| --- | --- | --- |
| 启动 #1 | `PYTHONPATH=workbench/_deps ICEX_WORKBENCH_ALLOW_PARSE=0 python serve_parser.py` | **失败**：`fastapi.exceptions.FastAPIError: Invalid args for response field ... JSONResponse \| FileResponse` |
| 修复 | `/api/page` 的返回类型联合注解被 FastAPI 0.162 当作 response_model 生成，Pydantic 拒绝 | 改为 `@app.get("/api/page", response_model=None)` 并去掉联合注解；另补 `GET /favicon.ico` 返回 204 |
| 启动 #2 | 同上 | 成功，端口 8765 LISTENING |
| 关闭 #2 | 正常终止后台任务 | 端口释放、无 `serve_parser` / `parse_worker` 进程、`runs/` 与 `uploads/` 均不存在 |
| 启动 #3 | 同上（含修复） | 成功，当前仍在运行：`[Parser Lab] frozen=True port=8765` |

**如实说明**：`py_compile` 静态检查无法发现路由注册期的 response_model 错误，这是启动冒烟测试抓到的真实缺陷。该缺陷只影响页面 PNG 预览路由，不影响 `/api/parse` 与冻结开关。

启动 #3 的服务日志（uvicorn）：

```
[Parser Lab] frozen=True  port=8765
INFO:     Started server process [184116]
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8765 (Press CTRL+C to quit)
INFO:     127.0.0.1 - "GET / HTTP/1.1" 200 OK
INFO:     127.0.0.1 - "GET /favicon.ico HTTP/1.1" 204 No Content
INFO:     127.0.0.1 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1 - "POST /api/parse HTTP/1.1" 200 OK
```

## 4. 页面截图

| 文件 | 内容 |
| --- | --- |
| `_smoke/01_landing_frozen.png` | Landing：Google 风格 logo、Parser-only 说明、冻结状态条 `[WAITING] 后端已连接，但处于 Reviewer 冻结期`、后端状态行（Gate 6A: NOT_STARTED / HEAD） |
| `_smoke/02_results_frozen.png` | 上传后：左侧真实 JSON（`status: FROZEN`、`parser_output: {}`、`document: null`），右侧 `[FROZEN]` 状态条与 Diagnostics 卡片，无 LM358、无假进度 |

截图由 Edge 157 无头浏览器 CDP `Page.captureScreenshot` 生成，1440x900。

## 5. `/api/parse` 的 FROZEN 响应

`curl --noproxy 127.0.0.1 -X POST ... --data-binary @CD4098BE-NG__cd4098b.pdf`（带真实 PDF 字节），HTTP 200，1,046 字节，耗时 0.005 秒：

```json
{
  "pipeline": "parser_only",
  "llm_called": false,
  "database_written": false,
  "extraction": null,
  "status": "FROZEN",
  "gate6a_status": "NOT_STARTED",
  "frozen": true,
  "parser_output": {},
  "artifact_inventory": [],
  "diagnostics": {
    "reason": "Reviewer 冻结期：ICEX_WORKBENCH_ALLOW_PARSE 未设为 1",
    "parse_worker_started": false,
    "parse_pdf_calls": 0,
    "action_required": "等待 Reviewer 解除 Gate 6A 冻结并确认样本 / Gold / 运行边界"
  },
  "document": null
}
```

`/api/health` 关键字段：`frozen=true`、`allow_parse=false`、`llm_called=false`、`database_written=false`、`gate6a_status=NOT_STARTED`、`git_head=3ed22a4a...`、`worker_exists=true`、`uvicorn=true`、`yaml_in_isolated_deps=true`；`contract_map` 如实列出 `evidence.json` / `qc_report.json` 为 `MISSING`，`raw_extraction.json` 为 `RENAMED`。

原始证据：`_smoke/frozen_response.json`、`_smoke/health.json`。

## 6. 浏览器 Console / Network 检查

CDP 采集（`_smoke/cdp_report.json`）：

| 项 | 结果 |
| --- | --- |
| `Runtime.consoleAPICalled` | **0** |
| `Runtime.exceptionThrown` | **0** |
| `Log.entryAdded` | **0**（修复 favicon 404 后） |
| Network 请求 | `GET /` 200、`GET /api/health` 200、`POST /api/parse` 200；无 4xx/5xx、无失败请求 |

首轮曾出现两条需要收口的问题，均已修复并如实记录：`favicon.ico` 404（后端补 204 路由 + 前端内联 `<link rel="icon" href="data:,">`）；CDP 脚本里 `setFileInputFiles` 已触发 change 又手动 dispatch 一次造成 2 次 POST（改为条件补发，最终单轮 1 次 POST）。

## 7. 前端交互与冻结保护逐项验证

| 验收项 | 结果 | 证据 |
| --- | --- | --- |
| 页面可打开、静态资源正常 | PASS | `GET /` 200 / 30,019 字节 / `text/html`；favicon 204；无外部 CDN |
| PDF 选择、文件名展示 | PASS | 选中 `CD4098BE-NG__cd4098b.pdf` 后 `uploadText` 正确更新 |
| 拖放交互 | PASS | `dragover` → `upload-box dragover`，`dragleave` → 还原，drop 后 `status=FROZEN`、`parse_pdf_calls=0` |
| `/api/parse` 返回明确 FROZEN | PASS | 见第 5 节 |
| 前端正确展示冻结状态 | PASS | 结果页 `[FROZEN] ...（parse_pdf 调用 0 次）`，`jsonHasFrozen=true` |
| 无假进度 / 假成功 / LM358 | PASS | `hasMockVar=false`、`hasShowResultsFake=false`（无 setTimeout）、`hasLM358=false`、`jsonHasLM358=false`；无 `.process-bar` |
| Copy JSON 为实际后端响应 | PASS（含口径说明） | `copiedEqualsLastResponse=true`、`copyMatchesBackendObject=true`。复制文本 1,149 字节 vs 后端响应 1,046 字节，**字节不同**（前端 `JSON.stringify(..., null, 2)` 缩进重序列化），但对象逐字段深比较一致 |
| 上传不触发 `parse_pdf()`、无产物 | PASS | `parse_worker_started=false`、`parse_pdf_calls=0`、`parser_output` 为空；`workbench/runs/`、`workbench/uploads/` 不存在；无 `run_manifest.json` / `tables.json` / `candidates.json` / `*.jsonl` / `*.log` |
| 服务启动、关闭正常，无遗留 Parser 子进程 | PASS | 启动 #2 正常关闭后端口释放；`ps -W` 仅见旧项目常驻 `pythonw.exe` PID 3736（08:31 启动，非本轮），无 `serve_parser` / `parse_worker` |

## 8. 日志与产物目录检查

- 服务日志见第 3 节；访问日志全部为 200/204。
- `workbench/runs/`：**不存在**。`workbench/uploads/`：**不存在**。
- `workbench/_smoke/` 仅含 UI 冒烟证据（截图、JSON、CDP 脚本、Edge 临时 profile），**不含任何 Parser 产物**。
- `_smoke/` 当前未被 `.gitignore` 忽略（`git check-ignore` 返回 NOT_IGNORED），会随 `?? workbench/` 一起出现在 git status；是否需要忽略由审查方决定，本轮未擅自改 `.gitignore`。

## 9. Git diff 与文件 SHA-256

Git 基线：HEAD `3ed22a4a83564b36ca238792af4b2328fd966469` 未变；`git status --short` 中相关项为 `?? workbench.html`（历史文件，本轮未改）与 `?? workbench/`（本轮新增）。主项目零 add / commit / push。`gate6a_status/` 位于被忽略的 `runs/` 下。

核心代码文件 SHA-256（本轮最终版本）：

```
eaf5e7e83261cd6087791e40e0c5881e8fa93c5db56e6d988ce49f2b39598997  PARSER_CALL_CHAIN.md
76407504af8dbc0eb1ee2214c024e6dc7088f6580616dbef29bc7adb5b63a5bb  index.html
9efc699e1429c1d34a6a04bc13198cb6c2f49be07234f6ad2f9ae0af67ec5c79  parse_worker.py
215e9a8b627671f6f2145ae95c8eaa84c8a3d9c956d03063127e4dc7c2cf5815  serve_parser.py
f3e3c8d6c203720b140528dbb33f60745da3aa5b867e6fdaa9cbded331e6a6d8  WORKBENCH_CODE_CHANGES.md
```

本报告自身与其余交付件的最终哈希统一记录在 `SHA256SUMS.txt`（含 6 份交付件），`sha256sum -c` 结果 **6 OK / 0 FAILED**。

证据文件 SHA-256：

```
5d54cb2ab4f45a31200d406c8bac0d5928b9aebfa831aee3a545a9140c2bfc1c  cdp_report.json
a08fa6a1685a2147afb829626d77017db4d5ae62fc13192e3973c561655d2c3f  health.json
0bbca34edf4cbd2087e06006a915314ba0988a09bc99d55a744c384e3ce29a5e  frozen_response.json
bc28e5de381eec43ee4312ad625ad53cf99d7c1b45ba7e2d367293cde93005c5  copied.json
ff76f841b7069d0ea0208f906329a5f98616bd45e2e8c872189c6d043b8f35e7  cdp_smoke.mjs
7edf5b9b550e47692c42ae89d56911223aa246bb247cb520e909758f05bb931b  01_landing_frozen.png
4713291c2cea5dd818380c350e26805aae6cc4d304405f356a5b0a36a31dff6d  02_results_frozen.png
```

`SHA256SUMS.txt` 覆盖上述 5 份代码/文档交付件加本报告共 6 份，`sha256sum -c` 结果 6 OK / 0 FAILED。

## 10. 零调用声明（硬底线）

| 项 | 次数 |
| --- | --- |
| `parse_pdf()` | **0** |
| `parse_worker.py` 子进程启动 | **0** |
| LLM Provider / qwen-flash 调用 | **0** |
| 数据库操作（DDL / 连接 / 写入） | **0** |
| 新建 Parser 产物 / Run ID | **0** |
| 主项目 git add / commit / push | **0** |

## 11. 证据边界（不能越界解读）

本轮**只证明**：Workbench 能启动、页面能打开、前端交互正常、冻结开关有效、上传不会越过冻结开关、Console/Network 干净、服务可正常关闭且无遗留子进程。

本轮**不证明**：PDF 解析能力、Parser 输出质量、子进程解析流程与崩溃保护是否正确、9 个 artifacts 的真实内容、Gate 6A 任何质量指标。

第三阶段服务器部署仍须保持 `ICEX_WORKBENCH_ALLOW_PARSE=0`，不得因换环境默认解冻；真实解析探针需另行授权。
