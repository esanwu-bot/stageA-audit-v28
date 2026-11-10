# V002 / V022 单件探针报告（严格受控 · 串行两次请求）

- 执行时间：2026-11-11 07:46:36 – 07:47:56（GMT+8）
- 服务：`127.0.0.1:8765`，`ICEX_WORKBENCH_ALLOW_PARSE=1`（**仅该进程**，进程内联变量，未 export、未改任何配置文件）
- 运行代码：`workbench/` 修复版（`serve_parser.py 32d06672…`，与审计仓库 `e6de9fd` blob 一致）
- 结论：**V002 符合预期（PASS）；V022 未拦截（分类门禁异常，触发停止条件）**

---

## 0. 一句话结论

V002 按预期 `DATASHEET → Parser → PARSE_COMPLETED`，产物齐全。
**V022（EVM 伪装件）被判 `DATASHEET` 并进入了 Parser**，违反预期，已按指令**立即停止**，
不再发第 3 次请求，本篇按「分类门禁异常」提交，**不记为成功**。

---

## 1. 样本核验（请求前）

| 项 | V002 | V022 |
| --- | --- | --- |
| 文件 | `CD4098BE-NG__cd4098b.pdf` | `CC2500EMK__cc2500.pdf` |
| 源路径 | `E:\workspace\IcPdfParser\data\pdfs\` | 同左 |
| 大小 | 803,726 B（785 KiB） | 2,509,323 B（2.39 MiB） |
| SHA-256 | `699241f92bb3178908b6f0e6ef24e57dcf26c726986c2691f97634b957197483` | `27364e9593879ec0c098944c46b90e7243a44e5b34e77b6d9ec3a3610ea25ae4` |
| 页数（清单记录） | 17 | 99 |
| 350 清单 V2 预测 | `DS_STRONG / IC_PARSE` | `DS_STRONG / IC_PARSE` |
| 清单 SHA 复核 | `sha256_match=TRUE`（实测一致） | 同左 |

> 注意：V022 在 `runs/stage_a_350/ds_parse_candidates_350_v2.csv` 里的 V2 预测**本来就是 `DS_STRONG / IC_PARSE`**。
> 这一点对第 5 节的根因判定很关键。

---

## 2. 探针 1：V002（普通文本件）

| 项 | 值 |
| --- | --- |
| 请求 | `POST /api/process`，`x-filename: CD4098BE-NG__cd4098b.pdf` |
| 时间 | 07:46:36.691 → 07:46:56.720（`time_total=19.74s`） |
| HTTP | **200** |
| `request_id` | `WB-20261111-074636-56ea` |
| 响应大小 | 714,585 B |

**分类明细**

| 字段 | 值 |
| --- | --- |
| `decision` | **`DATASHEET`** |
| `doc_type` | `DS_STRONG` |
| `route` | `IC_PARSE` |
| `confidence` | `high` |
| `document_type` / `assigned_type` | `IC_DATASHEET` / `DS_STRONG` |
| `classification_status` / `read_status` | `SUCCESS` / `OK` |
| `source_hash_status` | `success`（与上传字节逐字节一致） |
| `ic_datasheet_extraction` | `true` |
| `evidence_conflict` | `false` |
| `evidence_pages` | `[]`（清单记录为 `NONE`，一致） |
| `gate_checks` 未通过项 | **无**（8/8 通过） |
| `classifier_version` / `rule_version` | `docclassifier-2.2.1` / `doc-classifier-v2` |

**Parser 明细**

| 项 | 值 |
| --- | --- |
| `parser.called` | `true` |
| `parser.status` | `PARSE_COMPLETED` |
| `run_id` | `G6A-20261111-074646-32d1` |
| `stages_seen` | `WORKER_STARTED → DEPS_VERIFIED → PARSER_MODULE_IMPORTED → PARSER_CALL_ENTERED → PARSER_CALL_RETURNED` |
| `PARSER_CALL_ENTERED / RETURNED` | `true / true` |
| `parse_pdf_calls` | `1` |
| `run_manifest.json` SHA-256 | `797537181d223bb7c94f59be686e4f8a83d2a91d1a58fc4c5270f2a247bc7665` |
| 产物文件数 | **16**（9 个 JSON + 6 张 PNG + `source.pdf`） |
| `missing / partial` | `[] / []`，`required_artifact_failure_count = 0` |
| `document.page_count` | 17（与清单一致） |
| 表格数 / 候选数 | 7 / 345 |
| `boundary_totals` | `table_count=7, completed=7, failed=0, keep=42, demote=12, unresolved=0` |
| `sha256_cross_check` | `upload = manifest.document_sha256`，**match=true** |

**判定：符合预期，PASS。**

---

## 3. 探针 2：V022（EVM 伪装件）—— 未拦截

| 项 | 值 |
| --- | --- |
| 请求 | `POST /api/process`，`x-filename: CC2500EMK__cc2500.pdf` |
| 时间 | 07:47:11.397 → 07:47:42.881（`time_total=31.14s`） |
| HTTP | **200** |
| `request_id` | `WB-20261111-074711-97c3` |
| 响应大小 | 13,962,549 B（99 页全文产物，响应体较大） |

**分类明细（异常点）**

| 字段 | 值 |
| --- | --- |
| `decision` | **`DATASHEET`** ← 预期 `NON_DATASHEET` |
| `doc_type` | `DS_STRONG` |
| `route` | `IC_PARSE` |
| `confidence` | **`high`** |
| `document_type` / `assigned_type` | `IC_DATASHEET` / `DS_STRONG` |
| `classification_status` / `read_status` | `SUCCESS` / `OK` |
| `source_hash_status` | `success` |
| `ic_datasheet_extraction` | `true` |
| `evidence_conflict` | `false` |
| `evidence_pages` | `[1, 2]`（分类器在第 1–2 页找到 DS 证据） |
| `gate_checks` 未通过项 | **无**（8/8 通过） |
| `gate_reasons` | `全部准入条件成立：route=IC_PARSE / doc_type=DS_STRONG / 证据无冲突 / 源 SHA-256 与上传字节一致` |

**Parser 明细（已进入解析）**

| 项 | 值 |
| --- | --- |
| `parser.called` | **`true`** ← 预期 `false` |
| `parser.status` | `PARSE_COMPLETED` |
| `run_id` | `G6A-20261111-074715-f8db` |
| `stages_seen` | 同 V002（5 个阶段齐全） |
| `parse_pdf_calls` | `1` |
| `run_manifest.json` SHA-256 | `bbcf5f06155135ba8bf09d0dcd769bfedc242883b062fffe37aeb0a74a0e0224` |
| 产物文件数 | **81** |
| `missing / partial` | `[] / []` |
| `document.page_count` | 99（与清单一致） |
| 表格数 / 候选数 | **128 / 3127** |
| `boundary_totals` | `table_count=128, completed=128, failed=0, keep=658, demote=136, unresolved=1, skipped_groups={outer_group_deferred:23}` |
| `sha256_cross_check` | **match=true** |

**判定：FAIL —— 分类门禁异常，已触发停止条件。**

停止动作：收到响应后**立即** `taskkill //F //PID 10176`（exit=0），未再发任何请求，
未做第 3 次试探，未修改任何代码或阈值。

---

## 4. 目录差异

| 时点 | `workbench/uploads/` | `workbench/runs/` |
| --- | --- | --- |
| 探针前（07:46:11） | 不存在 | 不存在 |
| 探针后（07:48:03） | 2 个请求目录 / 2 个文件 | 2 个 run 目录 / 97 个文件 |

```
uploads/WB-20261111-074636-56ea/0c011cace66e4e31ac7f7e9061ea28f3.pdf
uploads/WB-20261111-074711-97c3/408f6dce24964b7a9bce259d29314d8f.pdf
runs/G6A-20261111-074646-32d1     (V002, 16 files)
runs/G6A-20261111-074715-f8db     (V022, 81 files)
```

**两条副产物证据**：

1. 上传副本 SHA-256 与源文件**逐字节一致**（`699241f9…` / `27364e95…`），
   证明「UUID 物理名 + 硬链接证据名」链路没有破坏字节。
2. 物理文件名确实是 `0c011cac…pdf` / `408f6dce…pdf` 这种 UUID，
   用户提交名只出现在 `validation.submitted_filename` / `evidence_filename` 里 ——
   R2 的路径穿越加固在真实链路上生效。

---

## 5. 根因分析（为什么 V022 没被拦住）

**直接原因**：分类器 `classify_one()` 自己对 V022 给出 `doc_type=DS_STRONG / route=IC_PARSE / confidence=high`。
Workbench 的 8 项白名单全部是**与分类器自身标签的一致性检查**
（`route`、`doc_type`、`classification_status`、`read_status`、`source_hash_status`、
`ic_datasheet_extraction`、`evidence_conflict`、`source_sha256` 与上传字节一致），
分类器说是 DS_STRONG，白名单必然全过。

**这不是接线 bug，而是门禁的设计边界**：

- 8 项里**只有两项是独立于分类器结论的客观校验**：源 SHA-256 与上传字节一致、
  `evidence_conflict=false`。这两项 V022 都通过。
- 其余六项都是在问「分类器自己的各个字段是否自洽」，无法证伪分类器的语义判断。
- 换句话说：**Workbench 门禁能挡住「分类器自相矛盾 / 崩溃 / 超时 / 哈希漂移」，
  挡不住「分类器自信地判错」。**

**可复现性**：`ds_parse_candidates_350_v2.csv` 里 V022 的 V2 预测本来就是
`DS_STRONG / IC_PARSE`，说明这是分类器 v2.2.1 的**稳定判定**，不是本次偶发。
所以根因在分类器侧（A1 `logical_identity` / A2 `logical_assembly` 属冻结面），
不在 W1 接线。

**风险兑现情况**：V022 被当作 Datasheet 送进 Parser 后，产出了 128 张「表」、
3127 个候选、1 条 `unresolved` 边界决策。这正是 `PAIN-11（EVM 板卡混入）` /
`PAIN-12（板级指南被当成芯片手册）` 描述的场景 —— 产物「看起来完整」，
但语义上不是芯片参数表，下游若不做 QC 会直接污染 Gold Set。

**需要 Reviewer 裁定的三个方向**（我不预设结论）：

1. 判为**分类器缺陷**：在分类器里加 EVM/板卡特征规则（如 `EMK`/`EVM` 型号后缀、
   板载阻容表特征），属冻结面改动，需另行授权；
2. 判为**样本标签问题**：V022 的预期标签 `NON_DATASHEET` 与分类器 v2.2.1 的既有判定冲突，
   需修订样本预期或换样本；
3. 判为**门禁能力缺口**：承认 Workbench 门禁只能做一致性校验，
   在 Gate 6A 之外另设独立 QC（例如表格内容语义校验）作为第二道闸。

---

## 6. 环境与进程记录

| 项 | 值 |
| --- | --- |
| 启动命令 | `cd workbench && ICEX_WORKBENCH_ALLOW_PARSE=1 ICEX_WORKBENCH_PORT=8765 py -3.13 serve_parser.py` |
| 服务 PID | 10176 |
| 健康检查 | `frozen=false, allow_parse=true`，`deps_dir=runs/stage_a_350/gate6a/_deps` |
| 监听 | `127.0.0.1:8765`（仅本机回环，未绑定 0.0.0.0） |
| 访问日志 | 3 条：1×`GET /api/health`（就绪探测）+ 2×`POST /api/process`（V002、V022 各一次），无其他请求 |
| 停止 | 07:47:56 `taskkill //F //PID 10176`，exit=0 |
| 停止后端口 | 无 LISTENING，仅 3 条 TIME_WAIT |
| 环境变量持久化 | 无。变量以 `VAR=1 cmd` 形式内联，仅作用于该进程；当前 shell 中 `ICEX_WORKBENCH_ALLOW_PARSE` 为空串，未写任何配置文件 |
| **冻结态复原验证** | 07:48 以**不带** `ALLOW_PARSE` 的方式重启一次（PID 10164），`/api/health` 返回 `frozen=true, allow_parse=false`（见 `61_restore_health.json`），随即停止，端口已释放。证明默认态仍是冻结，无需人工改回任何配置 |
| 外部依赖 | 未接 LLM、未接数据库、未调外部 API（分类器为纯规则，Parser 只读本地 PDF） |

---

## 7. 边界声明

- 本结果**仅作探针**，不构成 Gate 6A 正式成绩，**严禁据此反推 Gold Set**。
- 本次实际调用 `parse_pdf()` **2 次**（V002 + V022 各 1 次），产生 2 个 run 目录 —— 如实登记，不写 0。
- `classify_one()` 实际调用 2 次；LLM 调用 0 次；数据库写入 0 次。
- 未修改任何代码、阈值、路由矩阵；未手工绕过门禁；未重试、未换样本。
- 服务已停止，`ALLOW_PARSE` 已回到默认冻结态（进程级变量随进程消失）。
