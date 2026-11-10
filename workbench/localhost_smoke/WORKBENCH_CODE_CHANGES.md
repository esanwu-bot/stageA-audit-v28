# Workbench 代码变更记录（第二个独立交付结果）

- 代码状态：**`CODE_READY`**；UI 冒烟状态：**`UI_SMOKE_PASSED`**；解析状态：**`PARSER_NOT_EXECUTED`**
- 明确 **不是** `PARSER_VERIFIED`；不表示解析质量通过，不表示 Gate 6A 已启动，不表示 Benchmark PASS
- 本文件为**代码冻结时点记录**；后续 localhost 启动与 UI 冒烟测试证据见 `workbench/LOCALHOST_SMOKE_REPORT.md`（第一阶段），两者状态严格区分
- 时间：2026-11-10
- 唯一权威基线：`E:\workspace\icpdf-extractor`，分支 `feat/s2b-schema-d4-d6`，HEAD `3ed22a4a83564b36ca238792af4b2328fd966469`（未变）
- 本轮 git `add` / `commit` / `push` = 0

---

## 0. 两个独立交付结果（严格隔离，不得互相替代）

| 结果 | 路径 | 状态 | 说明 |
| --- | --- | --- | --- |
| 结果一：Gate 6A 状态登记记录 | `runs/stage_a_350/gate6a_status/` | `NOT_STARTED` 澄清完毕 | 7 个问题书面回复 + 4 项整改待办；不含任何解析结果 |
| 结果二：Workbench 代码变更记录 | `workbench/` | `CODE_READY` | 真实 Parser 调试台前后端代码；本文件为代码冻结时点记录 |
| 结果三：localhost UI 冒烟证据 | `workbench/LOCALHOST_SMOKE_REPORT.md` + `_smoke/` | `UI_SMOKE_PASSED` / `PARSER_NOT_EXECUTED` | 后续阶段交付，保持 `ALLOW_PARSE=0`，只证启动与冻结保护 |

**状态隔离**：`UI_SMOKE_PASSED` 只证明调试台能启动、能呈现真实接口状态、不会越过冻结开关；**不得**据此把 `GATE6A_BENCHMARK` 从 `NOT_STARTED` 改掉，也不得标记为 `PARSER_VERIFIED`。

`gate6a_status/` 位于 `.gitignore:18` 的 `runs/` 下，不进入 git status；`workbench/` 为新增未跟踪目录 `?? workbench/`。仓库根原有的 `workbench.html` 是历史文件，**未被本轮修改或引用**。

---

## 1. 新增文件清单

| 文件 | 用途 |
| --- | --- |
| `workbench/PARSER_CALL_CHAIN.md` | 真实 Parser 调用链与输出对象定位（先提交，再定适配层） |
| `workbench/serve_parser.py` | FastAPI 后端：`/`、`/api/health`、`/api/parse`、`/api/page` |
| `workbench/parse_worker.py` | 单件解析子进程，哨兵包裹 JSON，显式注入隔离依赖 |
| `workbench/index.html` | 改造后的 Parser Lab 单页（内联 CSS/JS，无外部 CDN） |
| `workbench/WORKBENCH_CODE_CHANGES.md` | 本记录 |
| `workbench/SHA256SUMS.txt` | 交付件校验清单 |

静态编译产物 `workbench/__pycache__/`（2 个 `.pyc`）由 `python -m py_compile` 生成，**是语法编译缓存，不是解析产物**；本轮如实保留，未清理。

---

## 2. 从 Ds Bit 原型清除的内容（逐项）

来源：`D:/Documents/Downloads/deepseek_html_20261110_973dd5.html`（351 行 / 15,742 字节）。保留 Google 风格 logo、左右分栏、搜索过滤、Copy JSON、拖拽上传。

| 原型内容 | 处理 |
| --- | --- |
| `const mockJSON = {...}`（LM358 / Texas Instruments / SOIC-8 / Supply Voltage 等假参数） | **彻底删除**；页面无任何预置解析数据 |
| 3 个 `setTimeout` 假装「Uploading / Extracting / Generating JSON」 | **彻底删除**；状态由后端响应驱动 |
| `.process-bar` 假进度动画与 `loading` 关键帧 | **彻底删除**；改为明确文字状态条 |
| `renderCards()` 里的 `basic_info` / `specs.thermal` / `specs.electrical` / `pin_configuration` | **彻底删除**；改为 Parser 真实产物卡片 |
| `copyJSON()` 复制 `mockJSON` | 改为复制 `JSON.stringify(lastResponse, null, 2)`，与后端返回逐字一致 |
| `filterData()` 重新渲染 `mockJSON` | 改为基于 `lastResponse` 的按行过滤，且注明「过滤只影响显示，复制仍为完整响应」 |

前端禁用项扫描结果：`mockJSON|setTimeout|basic_info|specs.electrical|specs.thermal|pin_configuration|LM358|Texas Instruments|SOIC-8|process-bar` = **0 命中**。

---

## 3. 新增的真实能力

### 后端（`serve_parser.py`，FastAPI）

- `GET /api/health`：只读状态。返回冻结开关、依赖可用性、Git HEAD、契约产物映射；**不打开 PDF、不启动 worker**。
- `POST /api/parse`：
  - 输入用 `Request.body()` 接原始 PDF 二进制 + `X-Filename` / `X-Requested-Mpn` 请求头，**不使用 `UploadFile` / `File`**，规避缺失的 `python-multipart`。
  - 校验：空文件、超过 80 MiB、缺 `%PDF` 魔数分别返回 `INVALID_FILE`。
  - 冻结开关 `ICEX_WORKBENCH_ALLOW_PARSE` 默认 `0`，此时只返回 `FROZEN`，`parse_pdf_calls=0`，**不启动子进程**。
  - 解冻后：落盘 PDF、算 SHA-256、生成 `G6A-YYYYMMDD-HHMMSS-xxxx` Run ID，启动 `parse_worker.py` 子进程；父进程 `communicate(timeout=180)` + `kill()` 强杀。
  - 状态机：`FROZEN` / `INVALID_FILE` / `PARSE_TIMEOUT` / `PARSE_CRASH` / `PARSE_ERROR` / `PARSE_COMPLETED`，互相独立，绝不统一伪装成功。
  - 输出 `parser_output` 下 9 个真实 artifacts 的原样 JSON；`extraction: null` 明确第二阶段命名空间。
  - 元数据：`run_id`、上传 SHA-256、`code_version`（`project_version` / `parser_version` / `contract_version` / `parser_config_sha256` / `git_head`）、`llm_called=false`、`database_written=false`。
  - 上传 SHA 与 `run_manifest.json.document_sha256` 交叉核对，不一致记入 diagnostics。
  - `artifact_inventory` 逐项 `REAL_GENERATED` / `RENAMED` / `PARTIAL` / `MISSING`；`contract_gaps` 明写 evidence/qc 缺失。
- `GET /api/page`：返回 Parser **真实渲染**的页面 PNG；未渲染页返回 `PAGE_NOT_RENDERED`，不提供替代图。

### 子进程（`parse_worker.py`）

- 显式 `sys.path.insert` 注入隔离 `_deps`（PyYAML 6.0.3）与仓库 `src/`，并校验 `yaml.__file__` 位于隔离目录内，否则拒绝执行；**不回退全局环境、不安装依赖、不复制 Parser 逻辑**。
- 唯一调用 `icpdf.parser.pipeline.parse_pdf(pdf_path, requested_mpn, runs_root, run_id)`。
- 哨兵 `__ICEX_PARSE_JSON_BEGIN__/END__` 包裹载荷，规避 PyMuPDF C 层写 fd 1 污染 stdout。
- 异常时回传 `error_type` / `error`，供父进程分类为 `PARSE_ERROR`；原生崩溃不返回载荷，父进程判 `PARSE_CRASH`。

### 前端（`index.html`）

- `fetch('/api/parse')` 上传，`fetch('/api/health')` 探测；无后端时只显示「未连接后端」，不显示任何解析结果。
- 左侧 4 个页签：完整响应 JSON / Tables / Candidates / Diagnostics；`parser_output` 命名空间原始展示。
- 错误状态红色状态条，明确「解析超时，已强制终止子进程」「解析崩溃」「Parser 抛出异常」。
- 右侧卡片改为 Parser 真实产物：`Document`（文件名 / SHA / 页数 / Run ID）、`Code Version`、`Tables`（数量 / 页码 / 行列 / 重建状态）、`Candidates`（类型 / 页码 / 识别状态）、`Structure`（表头 / 行列 / 单元格原文）、`Diagnostics`（失败表格 / 未决边界 / 缺失产物 / 崩溃信息）、`Artifact Mapping / Contract Gaps`。
- PDF 原文预览联动：点击表格或候选条目加载对应页真实渲染 PNG；未渲染页明确提示。
- 分层红线：`parser_output` 是纯代码 Parser 原始结构，`extraction` 留给后续 LLM/Domain；**绝不把 candidates 包成器件参数**。

---

## 4. 依赖现状（只读探测，未安装任何依赖）

```
fastapi=True uvicorn=False multipart=False yaml=False fitz=True
```

- `uvicorn` 缺失：不妨碍编写 ASGI 应用；`__main__` 检测到缺失时只打印解冻后的安装命令并退出，**冻结期不启动服务**。
- `python-multipart` 缺失：用 `Request.body()` 规避，路由注册不依赖 multipart。
- `yaml` 只在隔离 `runs/stage_a_350/gate6a/_deps`（PyYAML 6.0.3），由 worker 显式注入；全局不可用。
- `configs/parser.yaml` 存在（1,079 字节），`load_config()` 的 `DEFAULT_CONFIG_PATH` 指向此处。

---

## 5. 本轮实际动作与冻结边界对照

| 工作 | 本轮是否执行 | 证据 |
| --- | --- | --- |
| 登记 Gate 6A 实际状态、残留物 | 已执行 | `gate6a_status/` 两份文件 |
| 静态阅读原型、`pipeline.py`、`pipeline_sandbox.py`、`run_store.py`、domain 模型 | 已执行 | `PARSER_CALL_CHAIN.md` |
| 创建 `workbench/` 并编写前后端 | 已执行 | 5 份交付文件 |
| 静态检查代码、核对 diff | 已执行 | 见第 6 节 |
| 安装依赖 | **未执行** | 依赖探测值未变 |
| 启动服务 | **未执行** | 无 uvicorn 进程 |
| 上传 PDF | **未执行** | `workbench/uploads/` 不存在 |
| 调用 `parse_pdf()` / 触发解析的单测 | **未执行** | `workbench/runs/` 不存在，`parse_pdf_calls` 无实例 |
| 生成 Gate 6A 解析结果或宣称质量通过 | **未执行** | 无 `run_manifest.json` 等任何产物 |

另外：`python -m py_compile` 只做语法编译，未 import、未执行任何模块；未调用 LLM、未连数据库、未写 PostgreSQL、未改 Parser 核心算法、未改数据侧文件。

**受限事项如实披露**：本轮最后一次进程复查命令被沙箱策略拒绝，按规则未重试、未绕过、未用等价命令替代。冻结期早些时候的一次只读进程核查结果为：仅 1 个旧项目常驻进程 `PID 3736 pythonw.exe ...\IcPdfParser\algorithm_lab\daemon.py`，按 `parse_pdf|gate6a|_parser_worker|qwen|dashscope|_gate2a_run|pipeline.py` 匹配为 0；该结论与「workbench 代码从未运行」的事实一致。

---

## 6. 静态检查结果（真实输出）

| 检查 | 结果 |
| --- | --- |
| `python -m py_compile serve_parser.py parse_worker.py` | `COMPILE_OK` |
| 前端 10 项禁用词扫描 | `NO_FORBIDDEN_TERMS`（0 命中） |
| `fetch('/api/parse')` | 1 处 |
| `fetch('/api/health')` | 1 处 |
| `parser_output` 出现次数 | 6 |
| 后端路由 | `/`、`/api/health`、`/api/parse`、`/api/page` |
| 冻结开关默认值 | `os.getenv("ICEX_WORKBENCH_ALLOW_PARSE", "0") == "1"`（`serve_parser.py:95`） |
| `workbench/runs/`、`workbench/uploads/` | 均不存在 |
| Git HEAD | 未变；`?? workbench/` 为新增未跟踪目录 |
| `gate6a_status/` | 被 `.gitignore:18 runs/` 忽略 |

---

## 7. 解冻后启用步骤（本轮不执行，仅供 Reviewer 审阅）

1. Reviewer 解除 Gate 6A 冻结，并确认样本扫描型画像（整改 A）、Gold Set（整改 B）、Failure / Unresolved 指标（整改 C）、产物映射表（整改 D）、运行保护壳边界。
2. 安装 `uvicorn`（隔离环境），确认 `ICEX_WORKBENCH_DEPS` 指向隔离 `_deps`。
3. `ICEX_WORKBENCH_ALLOW_PARSE=1 python serve_parser.py`，浏览器打开 `http://127.0.0.1:8765/`。
4. **人工单件上传** 30 件样本，肉眼观察表格、候选、坐标与结构；每次解析保留 Run ID、PDF SHA、代码版本与 9 个原始 artifacts。
5. 单文件观察不等于 Gate 6A 正式 Benchmark；正式跑批仍需单独授权。

剩余 320 件、Gate 6B / 6C / 6D 全部 `NOT_APPROVED`；`ICPDF_EXTRACTOR_LLM_READY` 保持 `false`。
