# Workbench localhost 启动与 UI 冒烟测试（第一阶段证据）

BASE: `https://raw.githubusercontent.com/esanwu-bot/stageA-audit-v28/main/workbench/localhost_smoke`

## 0. 状态口径（严格隔离）

| 项目 | 状态 |
| --- | --- |
| Workbench 代码 | `CODE_READY` |
| localhost UI 冒烟测试 | `UI_SMOKE_PASSED`（本轮完成） |
| Parser 真实解析 | **`NOT_EXECUTED`** |
| Gate 6A 质量评估 | **`NOT_STARTED`（未改变）** |
| LLM 接入 | `NOT_APPROVED` |
| 服务器部署 | 等待本地证据审查 |

启动成功**不代表** Gate 6A 已执行、Parser 已验证或 Benchmark 通过。

## 1. 授权边界（不隐瞒）

上一条消息曾授权「解除 Workbench 冻结、对 V002 / V022 做 1–3 件真实单件解析探针」；
最新消息把授权收窄为**只做 localhost 启动与 UI 冒烟**，并保持
`ICEX_WORKBENCH_ALLOW_PARSE=0`，明确「不要在这一步测试真实 PDF 解析」。

本轮按最新口径执行：V002 / V022 只从清单读取路径原文，未打开 PDF、未调用
`parse_pdf()`；子进程崩溃注入验证属解析流程，本阶段未执行。

零调用：`parse_pdf()` 0、worker 子进程 0、LLM 0、数据库 0、Parser 产物 / Run ID 0、
主项目 git add / commit / push 0。

## 2. 请先读

- `LOCALHOST_SMOKE_REPORT.md` —— 本轮主报告（11 节：启动/关闭记录、截图、
  FROZEN 响应、Console/Network、日志与产物目录、Git diff、SHA-256、零调用声明、证据边界）
- `WORKBENCH_CODE_CHANGES.md` —— Workbench 代码变更记录（代码冻结时点快照）
- `PARSER_CALL_CHAIN.md` —— 真实 Parser 调用链与输出对象定位（静态阅读，未执行）
- `GATE6A_STATUS_CLARIFICATION.md` / `GATE6A_TODO.md` —— 上一阶段 Gate 6A 状态登记与 4 项整改

## 3. 页面截图

- `01_landing_frozen.png` —— Landing 页与冻结状态条
- `02_results_frozen.png` —— 上传后左侧真实 FROZEN JSON 与右侧 Diagnostics

## 4. 原始证据

- `frozen_response.json` —— `POST /api/parse` 的真实 FROZEN 响应
- `health.json` —— `GET /api/health` 响应
- `cdp_report.json` —— Edge CDP 采集的 Console / Log / Network / 交互结果
- `copied.json` —— Copy JSON 实际复制的文本
- `cdp_smoke.mjs` —— 冒烟测试脚本（可复现）
- `serve_parser.py` / `parse_worker.py` / `index.html` —— 本轮最终代码，供核对 diff

## 5. 完整性校验

```sh
BASE=https://raw.githubusercontent.com/esanwu-bot/stageA-audit-v28/main/workbench/localhost_smoke
curl -fL -O "$BASE/SHA256SUMS.txt"
# 下载下列文件后执行：
sha256sum -c SHA256SUMS.txt
```

`SHA256SUMS.txt` 覆盖本目录除自身外的全部交付件。

## 6. 证据边界

本轮**只证明**：Workbench 能启动、页面能打开、前端交互正常、冻结开关有效、
上传不会越过冻结开关、Console/Network 干净、服务可正常关闭且无遗留子进程。

本轮**不证明**：PDF 解析能力、Parser 输出质量、子进程解析流程与崩溃保护、
9 个 artifacts 的真实内容、Gate 6A 任何质量指标。

如实记录的真实缺陷：首次启动因 `/api/page` 的联合返回注解被 FastAPI 0.162
当成 response_model 而失败（静态 `py_compile` 查不出），已修复并重启验证。

## 7. 权威基线

本仓库只是文件传输通道，不是审计依据。唯一权威基线为本地
`E:\workspace\icpdf-extractor`，分支 `feat/s2b-schema-d4-d6`，
HEAD `3ed22a4a83564b36ca238792af4b2328fd966469`（本轮未变）。
服务器部署仍须保持 `ICEX_WORKBENCH_ALLOW_PARSE=0`，不得因换环境默认解冻。
