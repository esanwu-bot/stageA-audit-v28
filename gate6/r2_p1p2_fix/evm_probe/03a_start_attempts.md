# 服务启动过程记录（两次尝试）

## 尝试 1 — 失败（方式错误）

| 项 | 值 |
| --- | --- |
| 命令 | `ICEX_WORKBENCH_ALLOW_PARSE=1 ICEX_CLASSIFY_ONLY=1 py -3.13 workbench/serve_parser.py --host 127.0.0.1 --port 8765 ... &` |
| 观测 PID | `27940` |
| 端口 | 短暂出现 `127.0.0.1:8765 LISTENING` |
| 结果 | **进程随 shell 退出被杀**。随后 `psutil.Process(27940)` 抛 `NoSuchProcess`，`tasklist` 报「没有运行的任务匹配指定标准」，端口释放 |

**原因**：命令末尾的 `&` 让服务进程脱离了任务管理，shell 结束后进程被回收。这是启动方式错误，不是服务本身的问题。

**证据局限（如实披露）**：该次尝试的 stdout 被第二次启动的 `>` 重定向覆盖，`02_server_stdout.log` 中不含此次内容。此处仅保留 PID 与端口观测结果，不作为已归档日志证据。

## 尝试 2 — 成功

| 项 | 值 |
| --- | --- |
| 命令 | `ICEX_WORKBENCH_ALLOW_PARSE=1 ICEX_CLASSIFY_ONLY=1 py -3.13 workbench/serve_parser.py --host 127.0.0.1 --port 8765`（由后台任务托管，无 `&`） |
| PID | `28040` |
| 启动时间 | `2026-11-11T08:34:33.808787` |
| 监听 | `127.0.0.1:8765`（仅 localhost） |
| 环境变量 | `ICEX_WORKBENCH_ALLOW_PARSE=1`、`ICEX_CLASSIFY_ONLY=1`（读自进程环境块） |
| 子进程 | `[]` |
| 日志 | `02_server_stdout.log` |

## 尝试 3 — 冻结态复验

| 项 | 值 |
| --- | --- |
| 命令 | `ICEX_WORKBENCH_ALLOW_PARSE=0 py -3.13 workbench/serve_parser.py --host 127.0.0.1 --port 8765` |
| PID | `25416` |
| 健康检查 | `frozen=true`、`allow_parse=false` |
| 日志 | `50_restore_frozen.log` |
| 结束 | `taskkill /F /PID 25416`，端口最终无 `LISTENING` |

## 最终状态

- 端口 `8765`：无 `LISTENING`（仅已关闭连接的 `TIME_WAIT`）
- `python.exe` 进程：无残留
- 冻结开关：默认 `ICEX_WORKBENCH_ALLOW_PARSE` 未设置 → 下次启动即为 FROZEN
