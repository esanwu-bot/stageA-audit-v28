# probe_v002_v022 — 单件探针证据包（精简版）

- 执行时间：2026-11-11 07:46:36 – 07:48（GMT+8）
- 环境：`127.0.0.1:8765`，`ICEX_WORKBENCH_ALLOW_PARSE=1`（仅该进程的内联变量）
- 运行代码：`workbench/` 修复版（`serve_parser.py 32d06672…`，与 `gate6/r2_p1p2_fix/` 同名文件一致）
- 结论：**V002 符合预期（PASS）；V022 未拦截（分类门禁异常，已触发停止条件）**

## 1. 结论速览

| | V002 | V022 |
| --- | --- | --- |
| 文件 | `CD4098BE-NG__cd4098b.pdf` | `CC2500EMK__cc2500.pdf` |
| SHA-256 | `699241f92bb3178908b6f0e6ef24e57dcf26c726986c2691f97634b957197483` | `27364e9593879ec0c098944c46b90e7243a44e5b34e77b6d9ec3a3610ea25ae4` |
| 大小 / 页数 | 803,726 B / 17 | 2,509,323 B / 99 |
| HTTP / 耗时 | 200 / 19.74s | 200 / 31.14s |
| `decision` | **DATASHEET** ✅ | **DATASHEET** ❌（预期 `NON_DATASHEET`） |
| `doc_type` / `route` / `confidence` | `DS_STRONG` / `IC_PARSE` / `high` | `DS_STRONG` / `IC_PARSE` / `high` |
| `evidence_pages` | `[]` | `[1, 2]` |
| `parser.called` | `true` | **`true`**（预期 `false`） |
| `run_id` | `G6A-20261111-074646-32d1` | `G6A-20261111-074715-f8db` |
| 产物文件数 | 16 | 81 |
| 规模 | 7 表 / 345 候选 / 0 failed | 128 表 / 3127 候选 / 1 unresolved |
| 判定 | PASS | **FAIL（分类门禁异常）** |

**根因一句话**：8 项白名单全部是对分类器自身标签的一致性检查，只有
`source_sha256` 与上传字节一致、`evidence_conflict=false` 两项独立于分类器结论。
分类器说 `DS_STRONG / IC_PARSE / high`，白名单必然全过 ——
**门禁能挡「分类器自相矛盾 / 崩溃 / 超时 / 哈希漂移」，挡不住「分类器自信地判错」**。
V022 在 `ds_parse_candidates_350_v2.csv` 里的 V2 预测本来就是 `DS_STRONG / IC_PARSE`，
属分类器稳定判定（冻结面），不是接线 bug。

详见 `PROBE_REPORT.md` 第 5 节（含三个待 Reviewer 裁定的方向）。

## 2. 本包是精简版（重要）

`parser_output` 字段内联了 9 个解析产物的全量文本，占响应体积 99% 以上
（V002 753 KB / V022 15.0 MB）。按 Reviewer 要求，本包**移除该字段**，
只保留响应头部、`classification`、`parser` 状态与 `diagnostics`。

被移除的内容与完整版去向，已写入每个响应文件的 `_trimmed` 字段：

```json
"_trimmed": {
  "is_full_response": false,
  "removed_keys": {"parser_output": 14998774},
  "full_response_bytes": 13962549,
  "full_response_sha256": "…",
  "full_response_location": "本地 workbench/_probe_v002_v022/…（未推送）"
}
```

因此 **本包的 JSON 不是逐字节原始响应**，不能用于重算响应哈希；
需要原始响应时以 `_trimmed.full_response_sha256` 核对本地文件。

| 本包文件 | 对应的完整版文件 |
| --- | --- |
| `10_v002_response.slim.json` | `workbench/_probe_v002_v022/10_v002_response.json` |
| `20_v022_response.slim.json` | `workbench/_probe_v002_v022/20_v022_response.json` |

## 3. 文件索引

| 文件 | 内容 |
| --- | --- |
| `PROBE_REPORT.md` | 主报告（含根因分析、环境记录、边界声明） |
| `00_samples.txt` | 两件样本的实测 SHA-256 / 大小，与 350 清单记录比对 |
| `01_before_probe.txt` | 探针前目录快照 + 环境变量确认 |
| `02_server_stdout.log` | 服务启动日志 + 访问日志（1×health + 2×process，无其他请求） |
| `03_health_allow1.json` | 解冻态健康检查（`frozen=false, allow_parse=true`） |
| `10_v002_code.txt` / `10_v002_headers.txt` / `10_v002_curl_v.log` | V002 请求时间、HTTP 状态、响应头、`curl -v` 全文 |
| `10_v002_response.slim.json` | V002 响应（精简） |
| `11_v002_summary.txt` | V002 分件档案：分类明细 + Parser 明细 + 16 个产物逐个 SHA-256 |
| `20_v022_code.txt` / `20_v022_headers.txt` / `20_v022_curl_v.log` | V022 同上 |
| `20_v022_response.slim.json` | V022 响应（精简） |
| `21_v022_summary.txt` | V022 分件档案：分类明细 + Parser 明细 + 81 个产物逐个 SHA-256 |
| `30_stop.txt` | 触发停止条件后的停止动作与端口状态 |
| `40_after_dirs.txt` | 探针后 `uploads/`、`runs/` 目录清单 |
| `50_artifacts.txt` | 上传副本字节一致性 + 两个 Run 的全部产物哈希 |
| `60_restore_frozen.log` / `61_restore_health.json` | 冻结态复原验证（不带 env 重启 → `frozen=true`） |
| `SHA256SUMS.txt` | 本包全部文件哈希 |

## 4. 关键旁证

- **上传副本与源文件逐字节一致**：`699241f9…` / `27364e95…`（见 `50_artifacts.txt`）。
- **物理名确实是 UUID**：`0c011cace66e4e31ac7f7e9061ea28f3.pdf` / `408f6dce24964b7a9bce259d29314d8f.pdf`，
  用户提交名只出现在 `validation.submitted_filename` 与 `evidence_filename` 中 ——
  R2 的路径穿越加固在真实链路上生效。
- **停止是即时的**：收到 V022 响应后 `taskkill //F //PID 10176`（exit=0），
  未发第 3 次请求、未重试、未换样本、未改阈值（见 `30_stop.txt`）。
- **冻结态已复原**：不带 `ALLOW_PARSE` 重启（PID 10164）→ `frozen=true, allow_parse=false`，
  随即停止，端口释放（见 `61_restore_health.json`）。

## 5. 边界声明

- 本结果**仅作探针**，不构成 Gate 6A 正式成绩，**严禁据此反推 Gold Set**。
- 如实登记：`parse_pdf()` 实际调用 **2 次**（V002 + V022 各 1 次），
  产生 2 个 run 目录与 2 个上传目录 —— 不写 0。
- `classify_one()` 调用 2 次；LLM 0 次；数据库 0 次；外部 API 0 次。
- 未修改任何代码、阈值、路由矩阵；未手工绕过门禁。
