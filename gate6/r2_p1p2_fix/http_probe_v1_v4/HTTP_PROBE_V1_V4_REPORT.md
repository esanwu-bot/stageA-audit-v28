# V1–V4 受控 localhost HTTP 探针报告

- 探针时间：2026-11-11 10:51:53 – 10:51:5x（UTC+8）
- 端点：`POST http://127.0.0.1:8765/api/process`
- 传输：裸 socket / HTTP/1.1 / `Connection: close`，**串行 4 次，无并发**
- 承载代码：`src/icpdf/classification/classifier.py`
  sha256 = `28b9f0bfc1b23f27f6b170b00c4651a0ba5a9baad35c375d2434e9fd07ee7d5b`（G7b / D'）
- 仓库 HEAD：`60a503cc8015ef9bfb27ddef1685e41593f3a75f`（`G7b: D' —— 板级证据足以裁决时抑制 DS_PRODUCT_MODEL_TITLE`）

---

## 1. 结论

**4/4 样本在 Pre-Parse Gate 即被判为 `NON_DATASHEET`，`parse_pdf()` 调用 0 次，
`parse_worker` 0 次启动，`runs/` 零新增目录。**

| 样本 | 文件 | doc_type | route | confidence | conflict | decision | parser_calls | parse_worker |
|---|---|---|---|---|---|---|---|---|
| V1 | ADC08060EVM__slau715a.pdf | EVM | QUARANTINE | high | false | NON_DATASHEET | 0 | false |
| V2 | BQ25570EVM-206__sluuaa7a.pdf | EVM | QUARANTINE | high | false | NON_DATASHEET | 0 | false |
| V3 | DS10CP154TSQX_NOPB__DS10CP154.pdf | EVM | QUARANTINE | high | false | NON_DATASHEET | 0 | false |
| V4 | DRV2700EVM__slyu023.pdf | EVM | QUARANTINE | medium | false | NON_DATASHEET | 0 | false |

四件全部 `classification_status=SUCCESS`、`read_status=OK`、`source_hash_status=success`、
`sha256_matches_upload=true`、`ic_datasheet_extraction=false`、`admit_to_parser=false`。
门禁失败项恒为 `route / doc_type / ic_datasheet_extraction` 三项，与 `route=QUARANTINE`、
`doc_type=EVM` 一致，无矛盾项。

**V4 是本轮最关键的一条**：它在变体 B / F 下会被泄漏成 `DS_STRONG / IC_PARSE`
（见 `_classifier_revision/VARIANT_changes.csv` 中 `B,LEAK_TO_PARSER` 与 `F,LEAK_TO_PARSER` 两行）。
在 D' 下它稳定停在 `EVM / QUARANTINE`，未进入 Parser。

---

## 2. 环境确认

### 2.1 运行时模块（不是文件系统上的文件，而是 Python 真正加载的那个）

预检脚本以 `sys.path.insert(0, "src")` 后 `import icpdf.classification.classifier`，
读取 `C.__file__` 再对该路径求哈希：

```
module __file__ : E:\workspace\icpdf-extractor\src\icpdf\classification\classifier.py
runtime sha256  : 28b9f0bfc1b23f27f6b170b00c4651a0ba5a9baad35c375d2434e9fd07ee7d5b
MATCH           : True
has _board_decisive : True
_BOARD_DECISIVE_TITLE_GROUPS : ['DEV_KIT', 'EVAL_BOARD', 'EVAL_MODULE']
has assert_route_invariant   : True
```

探针结束后再次求同一文件哈希，仍为 `28b9f0bf…`（`probe_record.json` →
`code_state.classifier_sha256_match = true`），**服务进程内使用的代码与
D' 交付件 `classifier_dprime.py` 的哈希一致，运行期无代码漂移**。

### 2.2 启动

```
[2026-11-11T10:51:53+08:00] launch: D:\Program Files (x86)\python\python.exe -u ...\workbench\serve_parser.py
[2026-11-11T10:51:53+08:00] env ICEX_WORKBENCH_ALLOW_PARSE=1 ICEX_CLASSIFY_ONLY=1 ICEX_WORKBENCH_PORT=8765
[Parser Lab] frozen=False  port=8765
INFO:     Started server process [63240]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8765 (Press CTRL+C to quit)
```

- PID = **63240**（`startup.log` 原文，非推断）
- 监听 `127.0.0.1:8765`（`serve_parser.py` 中 host 硬编码为 `127.0.0.1`，端口只认 `ICEX_WORKBENCH_PORT`）
- `frozen=False` 由服务自身 `_allow_parse()` 打印，是进程内读取环境变量后的结果

服务端日志完整记录了 **1 次 `GET /api/health` + 恰好 4 次 `POST /api/process`**，
无第 5 次、无并发痕迹：

```
INFO:     127.0.0.1:63447 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:63454 - "POST /api/process HTTP/1.1" 200 OK
INFO:     127.0.0.1:63459 - "POST /api/process HTTP/1.1" 200 OK
INFO:     127.0.0.1:63467 - "POST /api/process HTTP/1.1" 200 OK
INFO:     127.0.0.1:63472 - "POST /api/process HTTP/1.1" 200 OK
```

### 2.3 进程环境块（取自承载探针的真实 PID 63240）

来源：`psutil.Process(63240).environ()`，Windows 下走 PEB 读取，
**不是回显当前 shell 的变量**。

> **本文件已于 2026-11-11 11:5x 重新生成，原始版本含未脱敏的宿主凭据，已从 Git 历史中清除。**
> 详见 `SEC_INCIDENT_01.md`。以下为脱敏后的口径。

采集时共取到 **229** 个环境变量，但父进程即本机 IDE，其中绝大多数与探针无关。
现按**白名单 + 兜底闸**双层策略，只保留证明分类器运行所需的配置项，**4 个**：

| 变量 | 值 |
|---|---|
| `ICEX_WORKBENCH_ALLOW_PARSE` | `1` |
| `ICEX_CLASSIFY_ONLY` | `1` |
| `ICEX_WORKBENCH_PORT` | `8765` |
| `PYTHONIOENCODING` | `utf-8` |

其余 **225 个变量连键名都不进入文件**，仅以「前缀族 → 个数」的聚合形式留痕
（`CODEBUDDY_` 66 个、`WORKBUDDY_` 31 个、`CLIENT_` 9 个、`WECOM_` 6 个……），
用于向 Reviewer 说明「原采集面有多宽」，而不泄漏任何一个变量名或值。

补充说明：脱敏后的 4 个键本身也要过**兜底闸**——若键名命中
`KEY/TOKEN/SECRET/PASS/AUTH` 等模式，或值形如已知凭据（`AIza…`、`sk-…`、
JWT、私钥头、带口令的连接串），或为高熵长串，则值一律替换为 `***`。
本轮 4 个键均未触发兜底闸。

可选开关均未设置，走代码默认值（采集时确认它们不在环境块中）：
`ICEX_WORKBENCH_DEPS`（默认查找 `_deps`）、`ICEX_PARSE_TIMEOUT`（180s）、
`ICEX_CLASSIFY_TIMEOUT`（45s）、`ICEX_WORKBENCH_MAX_CONCURRENCY`（2）。

两个开关同时置 1 后的行为矩阵（`serve_parser.py` 文档字符串原文）：
`ALLOW_PARSE=1 + CLASSIFY_ONLY=1` → 分类结果照常返回，**任何进入 Parser 的尝试都被拦截**。

两个开关同时置 1 后的行为矩阵（`serve_parser.py` 文档字符串原文）：
`ALLOW_PARSE=1 + CLASSIFY_ONLY=1` → 分类结果照常返回，**任何进入 Parser 的尝试都被拦截**。

---

## 3. 逐样本证据

### V1 · `ADC08060EVM__slau715a.pdf`

- 判定档位：**档 1（board_strong → EVM/HIGH）**
- 决胜板级证据：`EVM_BOARD_TITLE` = `Evaluation Module` + `User's Guide`，
  `_board_description` 归组为 `CONNECTOR/EVAL_MODULE/JUMPER/USER_GUIDE`，其中
  **`EVAL_MODULE` 属于三个决胜组之一**。
- **D' 生效**：抑制 1 条 `DS_PRODUCT_MODEL_TITLE`
  （命中文本 `ADC08xx0 Evaluation Module User's Guide (Rev. A)…`）
- 另由档 1 既有逻辑抑制 1 条 `DS_ELECTRICAL_SECTIONS`（`features`）
- 结果：`EVM / QUARANTINE / high / conflict=false`
- 离线对照：`UNKNOWN/REVIEW/low/conflict=true` → `EVM/QUARANTINE/high/conflict=false`，**一致**

### V2 · `BQ25570EVM-206__sluuaa7a.pdf`

- 判定档位：**档 1（board_strong → EVM/HIGH）**
- 决胜板级证据：`EVM_BOARD_SCHEMATIC` = `EVM Schematic`
- **D' 未参与**：该文档根本没有 `DS_PRODUCT_MODEL_TITLE` 命中，故无可抑制项
  （`rejected_rules` 中只有 3 条 `DS_ELECTRICAL_SECTIONS`，来自档 1 既有逻辑）
- 结果：`EVM / QUARANTINE / high / conflict=false`
- 离线对照：不在 193 条变化集，即 A 与 D' 相同 → **一致**（本件不是 D' 的受益样本，是回归保护样本）

### V3 · `DS10CP154TSQX_NOPB__DS10CP154.pdf`

- 判定档位：**档 1（board_strong → EVM/HIGH）**
- 决胜板级证据：`EVM_BOARD_SCHEMATIC` = `board layout`。
  **这是只有 `EVM_BOARD_SCHEMATIC`、没有 `EVM_BOARD_TITLE` 的路径**，
  正是 D（260 条）与 D'（193 条）之间那「多出来的 1 条」——D 漏掉、D' 补上的样本。
- **D' 生效**：抑制 1 条 `DS_PRODUCT_MODEL_TITLE`
  （`DS10CP154 1.5 Gbps 4x4 LVDS Crosspoint Switch…`）
- 另抑制 3 条 `DS_ELECTRICAL_SECTIONS`（`pinout` / `Features` / `General Description`）
- 结果：`EVM / QUARANTINE / high / conflict=false`
- 离线对照：`UNKNOWN/REVIEW/low/conflict=true` → `EVM/QUARANTINE/high/conflict=false`，**一致**

### V4 · `DRV2700EVM__slyu023.pdf`

- 判定档位：**档 2（board_body → EVM/MEDIUM）**。`board_strong` 为空
  （无 `EVM_BOARD_TITLE`、无 `EVM_BOARD_SCHEMATIC`），但
  `EVM_BOARD_TERMS` 命中 `jumper` / `connector` / `header` 共 3 类，达到
  `BOARD_TERM_MIN_GROUPS`，因此 `board_body=true`。这解释了置信度是 `medium` 而非 `high`。
- **D' 未参与**：无 `DS_PRODUCT_MODEL_TITLE` 命中，`rejected_rules` 为空数组
  （该文档没有任何 DS 侧证据可被推翻）
- 结果：`EVM / QUARANTINE / medium / conflict=false`
- 离线对照：不在 193 条变化集，A 与 D' 相同 → **一致**
- **风险说明**：本件是变体 B / F 下 `LEAK_TO_PARSER` 的当事样本
  （`EVM → DS_STRONG`、`QUARANTINE → IC_PARSE`）。D' 不抑制板级词汇证据，
  因此该件仍稳在 EVM。这条探针的价值在于：**证明 D' 的抑制范围没有扩大到
  「板级词汇」这一类，从而没有制造新的泄漏面**。

### 规则归属澄清（避免误记）

`rejected_rules` 里两种 `code` 相同的条目分属两层，不能混为一谈：

| 来源 | 规则 | reason 文本 | 归属 |
|---|---|---|---|
| 档 1 既有逻辑（G7a） | `DS_ELECTRICAL_SECTIONS` 等剩余 `ds_hits` | `overridden by board evidence (…); IC 参数不能代表整板` | **非 D'** |
| D' 新增块（G7b） | 仅 `DS_PRODUCT_MODEL_TITLE` | `overridden by board evidence (…); 评估板标题里的芯片型号不代表本文档是 Datasheet` | **D'** |

`classifier.py` 中 `overridden_by_board_evidence` 出现两处：第 357 行为 D' 块内，
第 381 行为档 1 既有块。以 `reason` 文本可逐条区分。

---

## 4. Parser 调用计数与守卫分层

| 指标 | V1 | V2 | V3 | V4 |
|---|---|---|---|---|
| `parser.called` | false | false | false | false |
| `parser.parser_call_count` | 0 | 0 | 0 | 0 |
| `diagnostics.parse_pdf_calls` | 0 | 0 | 0 | 0 |
| `diagnostics.parse_worker_started` | false | false | false | false |
| `parser.stages_seen` | `[]` | `[]` | `[]` | `[]` |
| `parser.status` | SKIPPED | SKIPPED | SKIPPED | SKIPPED |
| `classification.classifier_stages` | WORKER_STARTED / EVIDENCE_LINK_READY / CLASSIFIER_CALL_ENTERED / CLASSIFIER_CALL_RETURNED / EVIDENCE_LINK_REMOVED | 同左 | 同左 | 同左 |

`parser.stages_seen` 为空数组、且不含 `WORKER_STARTED`，说明 **parse_worker 子进程
从未被捞出**，不是「启动了但没调 parse_pdf」。

分类子进程的阶段链完整（`CLASSIFIER_CALL_ENTERED` → `CLASSIFIER_CALL_RETURNED`），
证明分类确实执行，不是异常短路。

**关于 `CLASSIFY_ONLY=1` 是否被真正用到**：4 个样本全部在 Pre-Parse Gate 的
`decision != "DATASHEET"` 分支返回，**根本没有走到 `_classify_only()` 的 L1 拦截点**。
也就是说，`CLASSIFY_ONLY=1` 这一轮是「置位但未触发」的第二道保险，
`diagnostics.safety_blocked` / `safety_guard_layer` 均为 `null`——这是正常且预期的情况，
不应解读为哨兵失效。哨兵在此前 `_smoke` 里已有独立的 SAFETY_BLOCKED 用例覆盖。

---

## 5. 目录差异（探针前 → 探针后）

### `workbench/runs/`

```
added_count = 0    removed_count = 0
```

**零新增**。`serve_parser.py` 只在 `_execute_parse()` 内创建 `G6A-*` run 目录，
Parser 未被调用即无目录产生。这是「Parser 调用 0 次」最硬的物证。

### `workbench/uploads/`

```
added_count = 4    removed_count = 0
+ WB-20261111-105156-7724/8dd72a0bccd94151b2995209c6ec2a26.pdf
+ WB-20261111-105201-27be/cfd1badac9744723b6ff5edfb25910f0.pdf
+ WB-20261111-105206-3fd5/cc29549f91414f129a6b98a65297cff2.pdf
+ WB-20261111-105211-bf8e/43cfdc90f76f4d1daab925df861bc23b.pdf
```

恰好 4 个请求目录、每个 1 份 PDF，命名规则为 `WB-<时间戳>-<rand>/<uuid4>.pdf`，
与 `_materialize_upload()` 一致。目录时间戳 `105156 / 105201 / 105206 / 105211`
间隔约 5 秒，**从磁盘侧面印证串行执行、无并发**。

上传副本与源文件逐字节一致（4/4）：

| 样本 | 源文件 sha256 | 上传副本 sha256 | 一致 |
|---|---|---|---|
| V1 | `09fabc2407fc5834…` | `09fabc2407fc5834…` | 是 |
| V2 | `60aac1d0cad5e571…` | `60aac1d0cad5e571…` | 是 |
| V3 | `abeef5bb85c37803…` | `abeef5bb85c37803…` | 是 |
| V4 | `5affb226c8921348…` | `5affb226c8921348…` | 是 |

---

## 6. 历史修改未被混入

探针前后对 7 个跟踪文件求哈希，**全部未变**：

| 文件 | 状态 |
|---|---|
| `src/icpdf/cli.py` | 未变（`c288bffa1d0ac87d…`） |
| `workbench/_classifier_revision/R1_PRIME_SUPPLEMENT.md` | 未变（`e9c766500d3d28e2…`） |
| `src/icpdf/classification/classifier.py` | 未变（`28b9f0bf…`） |
| `src/icpdf/classification/rules.py` | 未变（`091a54ed7eea5b4b…`） |
| `workbench/serve_parser.py` | 未变（`05b9885a08e6fc60…`） |
| `workbench/classify_worker.py` | 未变（`6f9336d5aa434b1a…`） |
| `workbench/parse_worker.py` | 未变（`5c599e77031283c6…`） |

`git status --short` 行数探针前后均为 **65** 行，`HEAD` 前后均为 `60a503c`。
`cli.py` 的 +38 行与 `R1_PRIME_SUPPLEMENT.md` 的 +40 行是**探针之前就存在**的未提交改动，
本轮未触碰，也未纳入本次证据包（本包只增 `_http_probe_v1_v4/` 一个目录）。

---

## 7. 与离线全量回归的一致性

V1 / V3 在 `_d_prime/regression.jsonl` 中的记录与本轮 HTTP 结果**逐字段相同**：

| 样本 | 离线 A_before | 离线 D_prime | HTTP 实测 | 一致 |
|---|---|---|---|---|
| V1 | UNKNOWN / REVIEW / low / conflict=true | EVM / QUARANTINE / high / conflict=false | 同 D_prime | 是 |
| V3 | UNKNOWN / REVIEW / low / conflict=true | EVM / QUARANTINE / high / conflict=false | 同 D_prime | 是 |

V2 / V4 不在 193 条变化集内（A 与 D' 结论相同），离线侧无 D' 记录可比；
本轮 HTTP 给出的 `EVM / QUARANTINE` 与 `VARIANT_changes.csv` 中这两件的「原 doc_type=原 route=EVM/QUARANTINE」一致。

**意义**：离线扫描走的是 `_decide_matrix` 纯函数模拟，本轮走的是真实
`validate_pdf → classify_worker 子进程 → classify_one → _build_classification 白名单`
全链 HTTP 路径。两条完全不同的执行路径给出逐字段相同的结果，
说明 D' 的修订在**生产门禁链路上同样成立**，不只是离线模拟里成立。

---

## 8. 首轮 harness 崩溃的如实披露

首轮探针（本报告全部 `raw/`、`startup.log`、`env/process_env.json` 的来源）
在收尾阶段崩溃，**4 次 HTTP 请求本身全部成功**：

- 崩溃点：`finally` 块中 `netstat_8765()` 调用
- 直接原因：`subprocess.run(["netstat","-ano"], text=True)` 在中文 Windows 上
  按 UTF-8 解码 GBK 输出，抛 `UnicodeDecodeError` → `stdout=None` →
  `AttributeError: 'NoneType' object has no attribute 'splitlines'`
- 后果：`probe_record.json` 未落盘

| 丢失 | 未丢失 |
|---|---|
| `taskkill` 的 stdout 文本 | 4 次 `/api/process` 的原始请求头与原始响应字节 |
| `GET /api/health` 的响应体 | 进程环境块（崩溃前已写入 `env/process_env.json`） |
| 内存中的 record 字典 | `startup.log`（含 PID 与 4 条 POST 记录） |
| | `runs/uploads` 的 before 快照 |

**处置：未重发任何请求**（严格遵守「只发这 4 个」）。`probe_record.json` 由
`harness/_assemble_record.py` 从原始字节重新计算生成，不在证据之外补任何数值。
`taskkill` 确实执行过（该行代码先于崩溃点），但其输出文本无法追溯，
故 `phase_b.taskkill_stdout` 记为 `null` 并附说明，不做二次执行以免误杀无关进程。

端口释放以**实测状态**登记（非日志推断）：

```
port_listening          = False
residual_serve_parser   = []
netstat 8765            = 仅 TIME_WAIT 残留（属 TCP 正常回收，非监听）
port_released_conclusion = True
```

---

## 9. 证据清单

| 文件 | 内容 |
|---|---|
| `probe_record.json` | 全部结构化记录：环境块、四样本全字段、快照差异、停止状态、代码哈希 |
| `safety_matrix.csv` | 4 行 × 26 列安全矩阵，由 `_build_matrix.py` 从 record 派生，零手填 |
| `startup.log` | 服务原始 stdout（PID、frozen 标志、5 条请求访问日志） |
| `env/process_env.json` | PID 63240 的环境块**脱敏版**：229 个变量中仅保留 4 个配置项，其余 225 个只留前缀族计数（见 §2.3） |
| `harness/_env_redact.py` | 脱敏模块：白名单为主闸 + 敏感名/高熵值兜底闸 |
| `harness/_regenerate_env.py` | 从已捕获环境块就地重算脱敏版，并回读校验无残留 |
| `SEC_INCIDENT_01.md` | 安全事件说明：泄露范围、根因、处置、遗留动作 |
| `raw/V{1..4}.request.head.txt` | 请求行与请求头原文 + body 字节数与 sha256 |
| `raw/V{1..4}.response.raw` | 从 socket 读到的**完整原始响应字节**（含状态行与头） |
| `raw/V{1..4}.response.body.json` | 响应体原始字节，未经重排或美化 |
| `snapshots/runs_{before,after}.json` | `workbench/runs` 前后全量文件清单 |
| `snapshots/uploads_{before,after}.json` | `workbench/uploads` 前后全量文件清单 |
| `repo_state_pre.json` | 探针前 HEAD / git status / 7 个跟踪文件哈希与 mtime |
| `harness/_probe_v1_v4.py` | 探针执行器（裸 socket、串行、finally 收尾） |
| `harness/_assemble_record.py` | 崩溃后的记录装配器（只从原始字节重算） |
| `harness/_build_matrix.py` | 安全矩阵派生器 |

原始响应体大小：V1 10544 B、V2 11327 B、V3 10639 B、V4 9299 B（均为完整 JSON，未截断）。

---

## 10. 复现方法

```bash
cd E:/workspace/icpdf-extractor

# 1. 确认运行时哈希（只读 import，不打开 PDF）
py -3.13 -c "import sys,hashlib,pathlib; sys.path.insert(0,'src'); \
import icpdf.classification.classifier as C; \
print(hashlib.sha256(pathlib.Path(C.__file__).read_bytes()).hexdigest())"
# 期望 28b9f0bfc1b23f27f6b170b00c4651a0ba5a9baad35c375d2434e9fd07ee7d5b

# 2. 重建记录（从已落盘的原始字节，不重发请求）
py -3.13 -u workbench/_classifier_revision/_http_probe_v1_v4/harness/_assemble_record.py
py -3.13 -u workbench/_classifier_revision/_http_probe_v1_v4/harness/_build_matrix.py

# 3. 若要重跑探针本身（会真实发送 4 次请求、真实分类、真实打开 PDF）
py -3.13 -u workbench/_classifier_revision/_http_probe_v1_v4/harness/_probe_v1_v4.py
```

注意：若重跑 `_probe_v1_v4.py`，请先修掉 `netstat_8765()` 的编码问题
（第 3 步脚本内已改为按字节捕获 + `cp936` 解码，本包内版本可用）。
