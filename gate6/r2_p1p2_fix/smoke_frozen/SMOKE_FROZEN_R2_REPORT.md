# FROZEN Smoke Test · localhost 冻结复验报告（R2）

- 时间：2026-11-11 07:36–07:38（GMT+8）
- 运行代码：`workbench/` 修复后版本，与审计仓库 `esanwu-bot/stageA-audit-v28` commit
  `e6de9fd` 的 `gate6/r2_p1p2_fix/` blob **逐字节一致**（见 `09_code_version.txt`）
- 冻结开关：`ICEX_WORKBENCH_ALLOW_PARSE=0`（显式设置）
- 结论：**FROZEN_SMOKE: PASS**（8 项核心指标全部符合预期）

---

## 1. 进程记录

### 1.1 旧进程 PID 184116

```
--- taskkill //F //PID 184116 ---
错误: 没有找到进程 "184116"。
exit=128
--- 进程是否仍存在 ---
信息: 没有运行的任务匹配指定标准。
--- 端口 8765 占用 ---
(无监听，端口空闲)
```

**如实说明**：执行 kill 时 PID 184116 **已经不存在**。该进程是上一轮 UI 冒烟启动的，
在两次会话之间（2026-11-10 21:12 之后、2026-11-11 07:36 之前）自行退出，
本轮未观察到它的退出时刻与退出码。因此本轮「杀掉旧进程」实际是一次空操作，
`taskkill` 返回 128（进程不存在）即为证据；端口 8765 在启动新服务前为空闲。

### 1.2 新进程

| 项 | 值 |
| --- | --- |
| PID | **12088**（`INFO: Started server process [12088]` + `netstat` LISTENING 一致） |
| 监听 | `127.0.0.1:8765` |
| 启动命令 | `cd workbench && ICEX_WORKBENCH_ALLOW_PARSE=0 ICEX_WORKBENCH_PORT=8765 py -3.13 serve_parser.py` |
| 解释器 | `py -3.13`（系统 Python，`D:\Program Files (x86)\python\python.exe`，含 fastapi 0.162.0 / uvicorn） |
| 启动日志 | 见 `02_server_stdout.log` |
| `frozen` | `[Parser Lab] frozen=True  port=8765` |

启动日志全文：

```
INFO:     Started server process [12088]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8765 (Press CTRL+C to quit)
[Parser Lab] frozen=True  port=8765
```

---

## 2. 目录前后快照

| 时点 | `workbench/uploads/` | `workbench/runs/` |
| --- | --- | --- |
| 启动前（07:36:34） | `[NOT_EXISTS]` | `[NOT_EXISTS]` |
| 两次请求后（07:37:22） | `[NOT_EXISTS]` | `[NOT_EXISTS]` |

两次快照完全一致，**零新增目录、零新增文件**。补充检查：`workbench/` 下近 10 分钟内
新建的文件为 **0 个**（排除 `__pycache__/` 与本证据目录）。

---

## 3. 请求构造与原始响应

两次请求体均为 12 字节纯文本 `test content`（非 PDF，无 `%PDF` 魔数），
`Content-Type: application/octet-stream`，`x-filename: probe.txt`。

| 请求 | 方法/路径 | HTTP | Content-Length |
| --- | --- | --- | --- |
| 1 | `POST /api/parse` | **200 OK** | 1110 |
| 2 | `POST /api/process` | **200 OK** | 1109 |

原始响应：`04_parse_response.json`、`05_process_response.json`（美化版 `08_response_*_pretty.json`）；
详细传输日志：`04_parse_curl_v.log`、`05_process_curl_v.log`。

服务端访问日志（`02_server_stdout.log`）共 4 条，无第 5 条：

```
INFO:     127.0.0.1:59768 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:59802 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:59804 - "POST /api/parse HTTP/1.1" 200 OK
INFO:     127.0.0.1:59806 - "POST /api/process HTTP/1.1" 200 OK
```

（前两条 health 是就绪探测，不是业务请求。）

---

## 4. 核心指标（全部取自真实响应 JSON，非推断）

| # | 指标 | `/api/parse` | `/api/process` | 期望 | 判定 |
| --- | --- | --- | --- | --- | --- |
| 1 | HTTP 状态 | 200 | 200 | 200 | PASS |
| 2 | `status` | `FROZEN` | `FROZEN` | `FROZEN` | PASS |
| 3 | `frozen` | `true` | `true` | `true` | PASS |
| 4 | `parse_pdf_calls` | 0 | 0 | 0 | PASS |
| 5 | `parser.called` | false | false | false | PASS |
| 6 | `classifier_called` | false | false | false | PASS |
| 7 | `classifier_worker_started` | false | false | false | PASS |
| 8 | `parser.stages_seen` | `[]` | `[]` | `[]` | PASS |

补充证据（同源）：

- `parser.status = SKIPPED`（两侧一致），`classification = null`，`classifier_called = false`。
- `pipeline` 分别为 `parser_only` / `preparse_gate_v1`，证明两次请求命中的是**不同入口**，
  而不是被同一个处理分支吞掉。
- **Worker 启动次数 = 0** 的三重证据：
  1. 响应 `stages_seen = []`，没有任何 `[WORKER]` 阶段标记；
  2. 服务进程 PID 12088 **没有任何子进程**（`Get-CimInstance Win32_Process -Filter "ParentProcessId=12088"` 返回空）；
  3. 服务日志中不含任何 `[WORKER]` 行。
- 代码层证据：`api_parse` / `api_process` 的**第一句**就是
  `if not _allow_parse(): return JSONResponse(_frozen_payload(...))`，
  该分支在读请求体、落盘、启动 worker 之前返回；`_frozen_payload()` 里
  `parse_worker_started` / `classifier_worker_started` 恒为 `False`、
  `parse_pdf_calls` / `parser_call_count` 恒为 `0`（`serve_parser.py:290-303`）。

---

## 5. 代码版本核验

```
--- 工作区文件 SHA-256 ---
32d066727d5f775a6be588a88add3bfb7330fca6b3a756256d6c7f6f12c18f83 *workbench/serve_parser.py
6f9336d5aa434b1a75a5907c321e4ce29436639949624ce62053bc9a09e58c20 *workbench/classify_worker.py
4fb0e1e57f8f9d3a9fd2d063cae0b38e33ff24985532b9505f75315b7c75d380 *workbench/parse_worker.py
--- 审计仓库 commit e6de9fd 对应 blob SHA-256 ---
serve_parser.py        32d06672…（一致）
classify_worker.py     6f9336d5…（一致）
parse_worker.py        4fb0e1e5…（一致）
--- 主项目 HEAD ---
3ed22a4a83564b36ca238792af4b2328fd966469
```

即：**本次运行的就是 Reviewer 已收到的修复版代码**，不是旧代码。
主项目 CodeUp 仓库 HEAD 未变，本轮零 add / commit / push。

---

## 6. 证据文件清单

| 文件 | 内容 |
| --- | --- |
| `00_dir_before.txt` | 启动前目录快照 + 端口占用 |
| `01_old_pid_kill.txt` | `taskkill` 结果、进程查询、端口查询 |
| `02_server_stdout.log` | 服务启动日志 + 访问日志 |
| `03_health.json` / `03_health_code.txt` | `/api/health` 原始响应与状态码 |
| `04_parse_response.json` / `04_parse_code.txt` / `04_parse_headers.txt` / `04_parse_curl_v.log` | `/api/parse` 原始响应、状态码、响应头、`curl -v` 全文 |
| `05_process_response.json` / `05_process_code.txt` / `05_process_headers.txt` / `05_process_curl_v.log` | `/api/process` 同上 |
| `06_dir_after.txt` | 请求后目录快照 + 新增文件检查 |
| `07_metrics.txt` | 8 项核心指标提取结果与 PASS 判定 |
| `08_response_parse_pretty.json` / `08_response_process_pretty.json` | 响应美化版（便于逐字段核对） |
| `09_code_version.txt` | 运行代码与审计仓库 blob 的哈希比对 |
| `SHA256SUMS.txt` | 本目录全部证据文件哈希 |

---

## 7. 边界声明

- 未上传任何真实 PDF；两次请求体均为 12 字节纯文本，且**未被读取**（frozen 分支在读取前返回）。
- `parse_pdf()` 调用 0 次、`classify_one()` 调用 0 次、两类 worker 启动 0 次、LLM 0 次、
  数据库 0 次、Run ID 与产物 0 个。
- 状态未升级：仍为 `CODE_READY / P1P2_FIXED`，`PARSER_NOT_EXECUTED`，
  `GATE6A_BENCHMARK=NOT_STARTED`，服务器部署 `NOT_APPROVED`。
- 服务当前仍在 `127.0.0.1:8765` 运行（PID 12088，`frozen=True`）。
  停止命令：`taskkill //F //PID 12088`。
