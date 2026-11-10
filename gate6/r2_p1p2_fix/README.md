# gate6 / r2_p1p2_fix — Workbench 后端 P1/P2 修复 + Pre-Parse Gate 双入口

本目录是**冻结期只改代码、零执行**的传输包。不含 PDF、不含 Run 产物、不含服务日志。

## 1. 这次交付解决什么

| 项 | 内容 |
| --- | --- |
| 双入口 | `POST /api/parse`（Gate 6A Parser-only，处理器内零 classifier 引用）；`POST /api/process`（正式入口：`validate_pdf → classify_one → DATASHEET only → parse_pdf`） |
| 三出口 | `DATASHEET` / `NON_DATASHEET` / `AMBIGUOUS`，非 DATASHEET 不建 Run 目录、`parser.called=false` |
| P1-1 | 上传改流式（`Content-Length` 预检 + `request.stream()` 分块累计 → HTTP 413），不再 `await request.body()` |
| P1-2 | `asyncio.create_subprocess_exec` + `asyncio.wait` 超时强杀 + 全局 `Semaphore` 限并发 |
| P1-3 | `parse_pdf_calls` 改按 `[WORKER] PARSER_CALL_ENTERED` 阶段标记统计，崩溃/超时不再错记 0 |
| P2-1 | `MISSING` 与 `PARTIAL` 分离计数，`required_artifact_failure_count = missing + partial` |
| P2-2 | `WORKER_START_FAILED` 单独归类 |
| **R2 加固** | 落盘物理名 = `uuid4().hex + ".pdf"`，用户提交名只作元数据、永不参与路径拼接；分类器需要的文件名证据由 worker 在私有临时目录内以硬链接注入 |

## 2. Reviewer 四大红线对照结论

| 红线 | 结论 | 关键证据 |
| --- | --- | --- |
| 1 路径穿越 / 文件名安全 | **PASS** | `serve_parser.py:_physical_filename()` 生成 UUID 物理名；`_materialize_upload()` 用 `is_relative_to()` 做越界断言；`UPLOAD_DIR / ...` 全仓只有 `UPLOAD_DIR / request_id` 一处拼接 |
| 2 分类器 × Workbench 双重校验 | **PASS** | 模型层 `check_route_invariant`（`route == IC_PARSE ⟺ doc_type == DS_STRONG`）+ Workbench 8 项白名单，缺一项即 `AMBIGUOUS` |
| 3 子进程彻底清理 | **PASS** | 超时 `proc.kill()` → `await proc.wait()`；`Semaphore` 为模块级单例，`/api/parse` 与 `/api/process` 共用 |
| 4 审计标记可靠性 | **PASS** | `_stage()` 写完即 `sys.stdout.flush()`；`PARSER_CALL_ENTERED` 在 `parse_pdf()` 之前；父进程布尔判定，重复标记只计 1 次 |

残余风险（未在冻结期处理，已写入报告 §9.6）：Windows 设备名未拦截（影响面已缩到 worker 临时目录，fail-closed）、硬链接跨卷退化为复制、上传目录无 TTL 回收、信号量不覆盖上传阶段。

## 3. 文件清单

| 文件 | 说明 |
| --- | --- |
| `serve_parser.py` | 后端全文（FastAPI 双入口） |
| `classify_worker.py` | 分类子进程（**新增**，只调 `classify_one()`，零 LLM） |
| `parse_worker.py` | 解析子进程（阶段标记） |
| `_verify_p1p2_static.py` | 静态验收脚本（53 项，可复跑，不启动服务） |
| `WORKBENCH_P1P2_FIX.diff` | 统一 diff（2 改 + 2 新增，基线 → 现文件） |
| `WORKBENCH_P1P2_FIX_REPORT.md` | 主报告（含 §9 四大红线逐条对照） |
| `WORKBENCH_CODE_CHANGES.md` | 累计变更记录 |
| `LOCALHOST_SMOKE_REPORT.md` | 上一轮 UI 冒烟报告（frozen 态） |
| `PARSER_CALL_CHAIN.md` | 生产调用链静态说明 |
| `index.html` | 前端（**本轮未改动**，哈希与冒烟轮一致） |
| `SHA256SUMS.txt` | 13 个文件的 SHA-256（`sha256sum -b` 格式） |
| `_diff/baseline/` | 改动前冻结副本，供 diff 复现 |
| `_smoke/_p1p2_static_verify.log` | 静态验收原始输出（`53/53 PASS, 0 FAIL`） |

## 4. 复现校验

```bash
cd gate6/r2_p1p2_fix
sha256sum -c SHA256SUMS.txt          # 期望 13 OK / 0 FAILED

# 用基线副本 + diff 重建四个文件，应与本目录逐字节一致
mkdir -p /tmp/rebuild/workbench
cp _diff/baseline/serve_parser.py _diff/baseline/parse_worker.py /tmp/rebuild/workbench/
cd /tmp/rebuild && git -c core.autocrlf=false apply -p1 <path>/WORKBENCH_P1P2_FIX.diff
```

> 本机 `core.autocrlf=true`，直接 `git apply` 会把 LF 写成 CRLF；必须加
> `-c core.autocrlf=false`。这是环境设置，不是 diff 缺陷。

## 5. 边界声明

- 主项目 CodeUp 仓库**零 add / commit / push**，HEAD 仍为 `3ed22a4a83564b36ca238792af4b2328fd966469`。
- `parse_pdf()` / `classify_one()` / 两类 worker / LLM / DB / 服务启动次数均为 **0**。
- 未重启、未停止、未向 `127.0.0.1:8765`（PID 184116，frozen，内存中是修复前代码）发送任何请求。
- 状态仍为 `CODE_READY / P1P2_FIXED / NOT_EXECUTED`，`GATE6A_BENCHMARK=NOT_STARTED`，服务器部署 `NOT_APPROVED`。
