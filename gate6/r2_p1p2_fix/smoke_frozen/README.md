# smoke_frozen — localhost 冻结复验证据包（R2）

- 复验时间：2026-11-11 07:36–07:38（GMT+8）
- 运行代码：与 `gate6/r2_p1p2_fix/` 下同名文件**逐字节一致**（见 `09_code_version.txt`）
- 冻结开关：`ICEX_WORKBENCH_ALLOW_PARSE=0`
- 结论：**FROZEN_SMOKE: PASS**（8 项核心指标全部符合预期）

## 1. 包内文件索引

| 文件 | 内容 |
| --- | --- |
| `00_dir_before.txt` | 启动前目录快照 + 端口占用 |
| `01_old_pid_kill.txt` | `taskkill` 结果、进程查询、端口查询 |
| `02_server_stdout.log` | 服务启动日志 + 访问日志（共 4 条请求，无第 5 条） |
| `03_health.json` / `03_health_code.txt` | `/api/health` 原始响应与状态码 |
| `04_parse_response.json` / `04_parse_code.txt` / `04_parse_headers.txt` / `04_parse_curl_v.log` | `/api/parse` 原始响应、状态码、响应头、`curl -v` 全文 |
| `05_process_response.json` / `05_process_code.txt` / `05_process_headers.txt` / `05_process_curl_v.log` | `/api/process` 同上 |
| `06_dir_after.txt` | 请求后目录快照 + 新增文件检查 |
| `07_metrics.txt` | 8 项核心指标提取与 PASS 判定 |
| `08_response_*_pretty.json` | 响应美化版（逐字段核对用） |
| `09_code_version.txt` | 运行代码与 `e6de9fd` blob 的哈希比对 |
| `SMOKE_FROZEN_R2_REPORT.md` | 完整复验报告 |
| `SHA256SUMS.txt` | 本目录全部文件哈希（`sha256sum -c` 可直接校验） |

## 2. 结论摘要

| 指标 | `/api/parse` | `/api/process` |
| --- | --- | --- |
| HTTP 状态 | 200 | 200 |
| `status` | `FROZEN` | `FROZEN` |
| `frozen` | `true` | `true` |
| `parse_pdf_calls` | 0 | 0 |
| `parser.called` | false | false |
| `classifier_called` | false | false |
| `classifier_worker_started` | false | false |
| `parser.stages_seen` | `[]` | `[]` |

`workbench/uploads/`、`workbench/runs/` 在请求前后均不存在；`workbench/` 下零新增文件。

---

## 3. 遗留问题整改计划（下一迭代，本轮不动代码）

> 以下两项是本轮安全复核中确认的**真实缺陷**（不是理论风险），
> 但在冻结期按「只改已授权范围」原则未处理。这里给出可执行的整改方案与验收口径，
> 供 Reviewer 决定是否纳入下一迭代。**本节只是方案文本，本轮未改任何代码。**

### 3.1 流式上传只做到「流式读取」，尚未「分块落盘」

**现状与缺陷**

`_read_body_stream()` 已经不用 `await request.body()`，但它是把每个 chunk
`chunks.append(chunk)` 攒在内存里，读完后 `return b"".join(chunks)`，再由
`_materialize_upload()` 一次性 `write_bytes(body)`。也就是说：

- 内存峰值 ≈ 单文件大小（上限 80 MiB），**不是常数**；
- 并发 N 个请求时峰值 ≈ N × 80 MiB，`Semaphore` 只约束 worker 子进程，不约束上传；
- 413 路径虽然提前 return，但已读入的 chunk 仍占着内存直到请求对象被回收。

所以「流式」目前只兑现了「不会一次性 `await body()` 把整包读进内存两次」，
没有兑现「磁盘写入是增量的」。

**整改方案（推荐 A，零新依赖可用 B）**

- **方案 A：`aiofiles` + `tempfile` 分块直写**
  1. 在 `UPLOAD_DIR/<request_id>/` 下开 `<uuid>.part`（`tempfile.NamedTemporaryFile(delete=False, dir=...)` 或直接 `open("wb")`）；
  2. `async for chunk in request.stream(): await handle.write(chunk)`，边收边写；
  3. 每写一块同步 `hashlib.sha256().update(chunk)`，**不再对整包 bytes 求哈希**；
  4. 累计字节数超 `MAX_UPLOAD_BYTES` → `close()` + `unlink(.part)` + 返回 413，**磁盘上不留残片**；
  5. 收完 `flush()` → `os.fsync(fd)` → `os.replace(part, final)`（与 A3-W1 的 D4 持久化契约保持同一套语义）；
  6. 首块到达时用前 4 字节判 `%PDF` 魔数，非 PDF 立即终止，不必等 80 MiB 传完。

- **方案 B：不引入依赖**
  用 `await asyncio.to_thread(handle.write, chunk)` 把每块写盘丢到线程池，
  语义与 A 等价，代价是每块一次线程切换（80 MiB / 64 KiB ≈ 1280 次，可接受）。
  若 Reviewer 不希望新增第三方依赖，选 B。

**接口影响**：`_validate_pdf(body: bytes, ...)` 的入参需要从「整包 bytes」改成
「`.part` 路径 + 已算好的 sha256 + 首块前 4 字节」，`meta` 结构不变，
`validation.sha256` / `pdf_magic_ok` 字段语义不变，前端零改动。

**验收口径**

1. 上传 80 MiB 文件时进程 RSS 增量 < 8 MiB（当前约 +80 MiB）；
2. 触发 413 后 `uploads/<request_id>/` 下**不存在** `.part` 残留；
3. `validation.sha256` 与 `sha256sum` 对同一文件的计算结果逐字符一致；
4. 非 PDF 首块即拒绝，服务端读取字节数 < 4 KiB；
5. 并发 2 个 80 MiB 上传，内存增量 < 16 MiB。

**风险与对策**：`aiofiles` 属新增依赖 → 走隔离 `_deps` 注入，不改 `pyproject.toml`；
Windows 上 `os.replace` 要求目标可替换 → 物理名是 uuid，天然不重名，无需先 `unlink`。

### 3.2 子进程清理只覆盖「直接子进程」，Windows 下孙进程会残留

**现状与缺陷**

`_run_child()` 超时后调 `proc.kill()`。在 Windows 上它等价于
`TerminateProcess(handle)`，**只作用于 `create_subprocess_exec` 直接创建的那个进程**。
当前 `parse_worker.py` / `classify_worker.py` 都是单进程纯 Python，暂时不会 spawn 孙进程，
所以这条今天不是活跃缺陷；但一旦 Parser 侧引入 `multiprocessing`、
外部命令行工具（如 `pdftoppm`）或任何 `subprocess`，孙进程就会在父进程被 kill 后
成为孤儿，继续占 CPU / 句柄 / 内存，`Semaphore` 也拦不住。

**整改方案：`psutil` 进程树递归终止**

1. 超时分支改为调用统一的 `_kill_tree(pid)`：
   - `parent = psutil.Process(pid)`
   - `children = parent.children(recursive=True)`（**先取快照，再动手**）
   - 对 children 逐个 `terminate()`，`psutil.wait_procs(children, timeout=3)`
   - 仍存活的逐个 `kill()`
   - 最后 `parent.kill()` + `parent.wait(timeout=3)`
2. **顺序必须是「先子后父」**：先杀父会导致子进程被 reparent，Windows 上虽仍可按
   PPID 查到，但不保证稳定；
3. 每个进程单独 `try/except psutil.NoSuchProcess / AccessDenied` 忽略——
   竞态下子进程可能已自行退出，不能因此中断清理流程；
4. 清理动作放在 `finally`，让「超时」「通信异常」「正常返回」三条路径共用同一套回收逻辑；
5. 保留现有 `await proc.wait()`，确保 asyncio 侧也完成 `waitpid`，不留僵尸句柄。

**验收口径**

1. 造一个故意 spawn 孙进程的假 worker（例如 `subprocess.Popen([sys.executable, "-c", "import time;time.sleep(600)"])`），
   触发超时后 `psutil.Process(pid).children(recursive=True)` 返回空；
2. 连续 20 次超时，`tasklist` 中 python.exe 数量回到基线，无 PID 泄漏；
3. 子进程在清理过程中自行退出的竞态下，不抛未捕获异常、父进程仍返回 `PARSE_TIMEOUT`；
4. 清理耗时 < 5 秒（不把请求拖死）。

**风险与对策**：`psutil` 属新增依赖 → 同样走隔离 `_deps`；若 Reviewer 不接受新依赖，
退路是 Windows 下改用 `taskkill /T /F /PID <pid>`（`/T` 即终止进程树），
POSIX 下用 `os.killpg`（需 worker 以 `start_new_session=True` 启动），
两条退路都不引入第三方库，但可移植性差于 `psutil`。

### 3.3 另外两条残余风险的处理状态

| 残余风险 | 状态 | 计划 |
| --- | --- | --- |
| Windows 设备名（`CON`/`NUL`/`COM1`）未拦截 | 影响面已缩到 worker 私有临时目录，最坏 fail-closed 为 `AMBIGUOUS` | 与 3.1 同批处理：在 `_evidence_name()` 里加保留名黑名单（命中则前缀 `_`），约 3 行 |
| `uploads/` 无 TTL 回收 | 只增不删，长期占盘 | 解冻后加启动时清理（删除 mtime > 24h 的 `<request_id>/` 目录），不进请求路径，避免影响延迟 |

---

## 4. 复现校验

```bash
cd gate6/r2_p1p2_fix/smoke_frozen
sha256sum -c SHA256SUMS.txt     # 期望全部 OK
```

> 本目录随父目录 `.gitattributes`（`* -text`）按字节原样入库，
> 任何平台克隆后哈希都成立，不受 `core.autocrlf` 影响。

## 5. 边界声明

- 未上传任何真实 PDF；两次请求体均为 12 字节纯文本，且**未被读取**（frozen 分支在读取前返回）。
- `parse_pdf()` 0 次、`classify_one()` 0 次、两类 worker 0 次、LLM 0 次、DB 0 次、Run ID 与产物 0 个。
- 状态未升级：`CODE_READY / P1P2_FIXED`、`PARSER_NOT_EXECUTED`、`GATE6A_BENCHMARK=NOT_STARTED`、
  服务器部署 `NOT_APPROVED`。
