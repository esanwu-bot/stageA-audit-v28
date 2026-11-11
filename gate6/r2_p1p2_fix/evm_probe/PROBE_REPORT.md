# 真实 EVM 样本只分类探针 — 报告

**执行时刻**：2026-11-11 08:34:33（服务启动）→ 08:36:40（完全停服）
**模式**：`ICEX_WORKBENCH_ALLOW_PARSE=1` + `ICEX_CLASSIFY_ONLY=1`，仅 `127.0.0.1:8765`
**样本**：A `ADC08060EVM__slau715a.pdf`、B `BQ25570EVM-206__sluuaa7a.pdf`（SHA-256 均与 Reviewer 给定值一致）

---

## 0. 结论

**判定：`PROBE_PASS`。**

| 维度 | 结果 |
| --- | --- |
| 安全前提（5 项字段 + 产物零新增） | **两份全绿**。`parse_pdf` 调用 0 次，`runs/` 97 → 97 且 rollup 指纹未变 |
| 分类门禁 | **B 完美**（`NON_DATASHEET` / `doc_type=EVM` / `route=QUARANTINE`）；**A 为 `AMBIGUOUS`**（fail-closed 转人工复核，未进 Parser） |
| 是否触发 `PROBE_SAFETY_FAIL` | 否 |
| 是否触发 `CLASSIFIER_GATE_FAIL` | 否（A 未返回 `DATASHEET`） |

一句话：**门禁对两份真 EVM 都拦住了，但拦住的方式不同**——B 是被明确判为 EVM 后自动终止，A 是因为证据冲突被隔离待复核。两者都符合 fail-closed 设计，但 A 的 `UNKNOWN` 归因暴露了一个分类器规则缺陷（见 §5）。

---

## 1. 执行条件

| 项 | 值 | 证据 |
| --- | --- | --- |
| 服务 PID | `28040` | `03_server_proc_info.json` |
| 启动时间 | `2026-11-11T08:34:33.808787` | 同上（`psutil.create_time()`） |
| 监听地址 | `127.0.0.1:8765`（仅 localhost） | 同上 `cmdline` |
| `ICEX_WORKBENCH_ALLOW_PARSE` | `1` | 同上（读自**进程环境块**，非 shell 回显） |
| `ICEX_CLASSIFY_ONLY` | `1` | 同上 |
| 就绪探测 | `GET /api/health` → 200，`allow_parse=true`、`frozen=false`、`llm_called=false` | `04_health.json` |
| 子进程 | 启动后 `children=[]` | `03_server_proc_info.json` |

> **启动过程如实记录**：第一次启动用了 `&` 把进程脱离任务管理，导致 PID 27940 在 shell 退出时被一并杀掉（当时 `netstat` 短暂看到 LISTENING，随即 `psutil` 报 `NoSuchProcess`）。
> 第二次改用受任务管理的后台进程重启（PID 28040），并以**进程环境块**核验开关值。
> **需要说明的是**：第一次尝试的 stdout 日志被第二次启动的 `>` 重定向覆盖了，因此 `02_server_stdout.log` 里只有成功那次的内容。第一次尝试的残留信息仅有 PID 27940 与端口短暂 LISTENING 的观测记录（见 `03a_start_attempts.md`）。这里没有保留原始日志，特此披露，不当作已归档证据。

---

## 2. 运行前后快照

| 目录 | 前 | 后 | 变化 | 判定 |
| --- | --- | --- | --- | --- |
| `uploads/` | 2 文件 / 3,313,049 B / rollup `e84ebaad…` | 4 文件 / 5,713,736 B / rollup `3bf56ea4…` | **+2 文件** | 预期内（分类前必须落盘上传件） |
| `runs/` | 97 文件 / 46,726,465 B / rollup `e2f035f0…` | 97 文件 / 46,726,465 B / rollup `e2f035f0…` | **零变化** | **PASS（关键断言）** |

`runs/` 的 `rollup_sha256` 前后完全一致——不只是文件数相同，逐个文件的 SHA-256 集合也相同，排除「删一个补一个」。

新增的两份上传副本：

| 样本 | 物理名（UUID） | SHA-256 | 与源样本一致 |
| --- | --- | --- | --- |
| A | `uploads/WB-20261111-083501-561e/938d90a7087b4c7b8753b256976a487a.pdf` | `09fabc24…4c02ca` | PASS |
| B | `uploads/WB-20261111-083551-ac06/69e9840756e148d7ada388a99ad417c3.pdf` | `60aac1d0…bb8d2e` | PASS |

物理名是 `uuid4().hex`，用户提交名只作元数据——路径安全设计在真实流量下生效。

---

## 3. 安全字段核对

完整表见 `60_safety_matrix.md`。核心 5 项：

| # | 字段 | 期望 | A | B |
| --- | --- | --- | --- | --- |
| 1 | `parser.called` | `false` | `false` | `false` |
| 2 | `diagnostics.parse_pdf_calls` | `0` | `0` | `0` |
| 3 | `diagnostics.parse_worker_started` | `false` | `false` | `false` |
| 4 | `llm_called` | `false` | `false` | `false` |
| 5 | `parser.stages_seen` | `[]` | `[]` | `[]` |

补充不变量同样全绿：`parser.status=SKIPPED`、`parser.run_id=null`、`parser.run_dir=null`、`parser_call_count=0`、`parser_output={}`、`classifier_llm_calls=0`。

### 3.1 第 5 项必须换判据，否则是空话

任务原文要求「无 `[PARSER_CALL_ENTERED]` 等阶段标记」。**不能看服务日志**——worker 的 stdout 走 `create_subprocess_exec` 的管道、被父进程解析，**不继承到服务 stdout**。

反证：上一轮确实解析过的 V002 样本，其 `02_server_stdout.log` 里同样是 **0 条** `[WORKER]` 行。也就是说「日志无标记」这个条件恒真、零鉴别力。

本次采用的权威判据是响应里的 `parser.stages_seen`（父进程从管道解析出的真实阶段序列）：两份均为 `[]`。作为对照，同一次响应里 `classifier_stages_seen` 有 5 个阶段（`WORKER_STARTED → EVIDENCE_LINK_READY → CLASSIFIER_CALL_ENTERED → CLASSIFIER_CALL_RETURNED → EVIDENCE_LINK_REMOVED`）——证明管道采集机制本身工作正常，`[]` 不是采集失败。

### 3.2 `safety_blocked` 字段为空，不是哨兵失效

两份响应的 `diagnostics.safety_blocked` 都是 `null`。原因是：**哨兵根本没轮到出手**。

`ICEX_CLASSIFY_ONLY` 的 L1 拦截位于 `api_process` 中 `decision == DATASHEET` 之后。而 A 判 `AMBIGUOUS`、B 判 `NON_DATASHEET`，两者在更早的 `if decision != "DATASHEET"` 分支就返回了。

这是**比 SAFETY_BLOCKED 更强的结果**：门禁不是「差点放行、被哨兵拉住」，而是「分类阶段就判定不该进 Parser」。哨兵的价值在下一层——如果哪天分类器把某份 EVM 判成 `DATASHEET`，它才会显形（`guarantee` 见 `classify_only_guard/GUARD_REPORT.md`）。

---

## 4. 分类结果

| 项 | A | B |
| --- | --- | --- |
| `status` / `decision` | `AMBIGUOUS` | `NON_DATASHEET` |
| `document_type` / `doc_type` | `UNKNOWN` / `UNKNOWN` | `EVM` / `EVM` |
| `route` | `REVIEW` | `QUARANTINE` |
| `confidence` | `low` | `high` |
| `evidence_conflict` | **`true`** | `false` |
| `ic_datasheet_extraction` | `false` | `false` |
| `evidence_pages` | `[1,2,3]` | `[1,2,3]` |
| `classification_status` / `read_status` | `SUCCESS` / `OK` | `SUCCESS` / `OK` |
| 分类器阶段 | 5 阶段完整 | 5 阶段完整 |

### 4.1 B：教科书式的正确拦截

B 命中了 **5 条** `DS_ELECTRICAL_SECTIONS`（"Features"、"General Description" 等），如果只看这一侧，很可能误判成 Datasheet。但分类器把其中 **3 条显式否决**：

```
rule_id=DS_ELECTRICAL_SECTIONS  code=overridden_by_board_evidence
reason="overridden by board evidence (BOM/EVAL_MODULE/JUMPER/SCHEMATIC/
        TEST_POINTS/USER_GUIDE); IC 参数不能代表整板"
```

B 具备 `EVM_BOARD_SCHEMATIC` 这个强板级信号，触发了「板级证据压倒 IC 段落证据」的覆盖规则，最终 `doc_type=EVM`、`evidence_conflict=false`、`route=QUARANTINE`。

这条路径说明分类器不是简单数关键词，而是有**方向性裁决**的。

### 4.2 A：为什么是 `UNKNOWN` 而不是 `EVM`

A 的规则命中分布：

```
EVM_BOARD_TERMS        3   （jumper / connector）
EVM_BOARD_TITLE        2   （User's Guide / Evaluation Module）
EVM_FILENAME_SUFFIX    1   （EVM）
DOCNUMBER_UG           1   （slau7 → User Guide 文档号）
EVM_BODY_MENTION       1
DS_PRODUCT_MODEL_TITLE 1   ← 问题在这里
DS_ELECTRICAL_SECTIONS 1   （features）
EVIDENCE_CONFLICT      1
```

**根因**：A 的 PDF 元数据 `Title` 是

```
ADC08xx0 Evaluation Module User's Guide (Rev. A)
```

`DS_PRODUCT_MODEL_TITLE` 这条规则在**元数据标题**里正则匹配到了型号 `ADC08xx0`，于是作为「强」DS 证据记了一票。可这个字符串明明写着 `Evaluation Module User's Guide`——`ADC08xx0` 是**板上的那颗 IC**，不是文档的主语。

于是出现两个 `strength=strong` 的信号指向相反方向：

- `EVM_BOARD_TITLE`「Evaluation Module」→ 强 EVM 证据
- `DS_PRODUCT_MODEL_TITLE`「ADC08xx0…」→ 强 DS 证据

冲突无法裁决 → `evidence_conflict=true` → `UNKNOWN` / `REVIEW` / `confidence=low`。

**为什么 B 没这个问题**：B 有 `EVM_BOARD_SCHEMATIC`，能触发 §4.1 的板级覆盖规则，把 DS 侧证据否决掉。A 的 `matched_rules` 里没有 `EVM_BOARD_SCHEMATIC`（也没有 BOM / TEST_POINTS），所以覆盖规则没被激活，`DS_PRODUCT_MODEL_TITLE` 无人压制。

**这是分类器规则缺陷，不是门禁缺陷**：A 仍然被安全地挡在 Parser 之外（fail-closed），代价只是多一次人工复核。

---

## 5. 建议（不属本轮改动范围，交 Reviewer 决策）

1. **`DS_PRODUCT_MODEL_TITLE` 应排除元数据标题路径，或至少降权。**
   元数据 `Title` 是出版方填写的自由文本，常把「板名 + 板载 IC 型号」写在一起。在这条路径上匹配到型号，不能证明文档本体是 Datasheet。可考虑：元数据来源的 `DS_PRODUCT_MODEL_TITLE` 一律降为 `medium`，或要求同一型号在**正文**（非元数据）也出现。

2. **`EVM_BOARD_SCHEMATIC` 不应是板级覆盖的唯一钥匙。**
   A 已具备 `EVM_BOARD_TITLE`（2 条，含 1 条 strong）+ `EVM_BOARD_TERMS`（3 条）+ `DOCNUMBER_UG`，证据量并不比 B 弱，只因缺 schematic 一条就被判 `UNKNOWN`。建议把覆盖条件从「必须含 SCHEMATIC」放宽为「板级 strong 证据 ≥ N 条」，或把 `DOCNUMBER_UG`（`slau7`/`slau4` 这类 TI 用户指南文档号）也计入板级强证据。

3. **`AMBIGUOUS` 与 `NON_DATASHEET` 在运维上应可区分处置。**
   两者都不进 Parser，但前者需要人工复核、后者可以自动丢弃。当前 `status` 已经区分，建议复核队列直接按 `status` 分流。

---

## 6. 停服与恢复

| 步骤 | 结果 | 证据 |
| --- | --- | --- |
| `taskkill /F /PID 28040` | 成功，exit=0 | `40_stop.txt` |
| 端口 8765 监听 | 无 `LISTENING`（仅 `TIME_WAIT`） | 见下 |
| 残留 python 进程 | 无 | `tasklist` |
| 冻结态复验（`ALLOW_PARSE=0` 重启 PID 25416） | `frozen=true`、`allow_parse=false` | `50_restore_frozen.log`、`51_restore_health.json` |
| 关闭复验进程 | 成功，端口最终无 `LISTENING` | `40_stop.txt` 追加段 |

停服后端口检查：

```
TCP  127.0.0.1:65038  127.0.0.1:8765  TIME_WAIT   （已关闭连接的客户端套接字）
TCP  127.0.0.1:65053  127.0.0.1:8765  TIME_WAIT
TCP  127.0.0.1:65162  127.0.0.1:8765  TIME_WAIT
```

无任何 `LISTENING` 条目——服务确实已停止，`TIME_WAIT` 是 TCP 正常回收状态，不代表进程存活。

---

## 7. 本轮未做的事

- 未调用 `/api/parse`（Parser-only 入口）。
- 未跑第 3 份样本。
- 未修改任何代码；`src/icpdf/parser/pipeline.py`、`src/icpdf/classification/`、`index.html` 时间戳均早于本轮。
- 未删除上传副本（保留作为证据；`uploads/` 无 TTL 回收是已披露的遗留问题）。

---

## 8. 文件清单

| 文件 | 说明 |
| --- | --- |
| `PROBE_REPORT.md` | 本报告 |
| `README.md` | 目录索引 |
| `00_samples.txt` | 样本清单与哈希 |
| `01_snapshot_before.json` | 运行前 `uploads/`+`runs/` 快照（含逐文件 SHA-256/mtime） |
| `02_server_stdout.log` | 服务启动与访问日志 |
| `03_server_proc_info.json` | PID / 启动时间 / 进程环境变量 / 子进程 |
| `03a_start_attempts.md` | 三次启动尝试的如实记录（含第一次失败） |
| `04_health.json` | 启动后健康检查 |
| `10_A_request.txt` / `10_A_headers.txt` / `10_A_curl_meta.txt` | A 的请求记录 |
| `10_A_response.json` | **A 完整原始响应** |
| `11_A_summary.txt` | A 可读摘要 |
| `20_B_request.txt` / `20_B_headers.txt` / `20_B_curl_meta.txt` | B 的请求记录 |
| `20_B_response.json` | **B 完整原始响应** |
| `21_B_summary.txt` | B 可读摘要 |
| `30_snapshot_after.json` | 运行后快照 |
| `40_stop.txt` | 停服记录 |
| `50_restore_frozen.log` / `51_restore_health.json` | 冻结态恢复证据 |
| `60_safety_matrix.md` | 安全字段核对表（含哈希链） |
| `05_extracted.json` | 从响应中抽取的结构化字段（生成核对表的中间产物） |
| `_snapshot_dirs.py` / `_extract_safety.py` | 生成上述证据的脚本（前后用同一套逻辑） |
| `SHA256SUMS.txt` | 本目录校验和 |
