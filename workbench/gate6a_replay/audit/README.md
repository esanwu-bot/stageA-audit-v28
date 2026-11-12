# Gate 6A 内部审计证据包 · 索引

本目录回应 Reviewer 叫停灰度时提出的四项审计要求。每一项都给出**可机检的原始文件**，
不依赖任何口头说明。

- 冻结时间：2026-11-12
- 回测根：`gate6a_replay_v1`（首次受控回测，正式交卷）、`gate6a_replay_v2_postfix`（格线修复后补跑）
- 源码版本：见 [`parser_commit.txt`](parser_commit.txt)

> **本包不含任何 `src/icpdf/` 源码。** 这里只有证据、口径说明与可复现脚本。
> 源码修复请在主仓（私有 CodeUp `icpdf-extractor`）审阅。

---

## 九个主文件（点开即可读）

| # | 文件 | 一句话 | 回答什么 |
| --- | --- | --- | --- |
| 1 | [`error_matrix_105.csv`](error_matrix_105.csv) | 105 行 × 17 列逐行判定 | 到底哪行对、哪行错、错在哪 |
| 2 | [`error_matrix_105_README.md`](error_matrix_105_README.md) | 字段字典与「命中」定义 | 命中/定位两个口径怎么算 |
| 3 | [`error_matrix_105_v1_prefix.csv`](error_matrix_105_v1_prefix.csv) | 修复前的同款矩阵 | 两份表差在哪 |
| 4 | [`evaluator_flips_39.csv`](evaluator_flips_39.csv) | 39 行评估器翻正明细 | 评估器改了哪些、Parser 有没有被改 |
| 5 | [`v256_crash_evidence.md`](v256_crash_evidence.md) | 崩溃 traceback + 夹紧公式 + 逐格不变性 | V256 修得对不对 |
| 6 | [`parser_v1_v2_diff.md`](parser_v1_v2_diff.md) | 24 件逐文件 sha256 对照 | 修复有没有伤到别的样本 |
| 7 | [`network_guard_proof.md`](network_guard_proof.md) | 六层拦截 + 16 个出网向量 | 有没有偷偷联网 |
| 8 | [`postfix_rerun_24.md`](postfix_rerun_24.md) | 修复后 24 件重跑报告 | 修完之后整体怎么样 |
| 9 | [`TECH_DEBT.md`](TECH_DEBT.md) | 四类暂不修的语义缺陷 | 还剩什么问题、为什么不修 |

配套：[`SHA256SUMS.txt`](SHA256SUMS.txt)（全部文件哈希）、[`pdf_sha256_24.csv`](pdf_sha256_24.csv)、
[`pip_freeze.txt`](pip_freeze.txt)、[`parser_json_immutability.txt`](parser_json_immutability.txt)、
[`parser_json_immutability_gate6a_replay_v2_postfix.txt`](parser_json_immutability_gate6a_replay_v2_postfix.txt)、
[`runtime_observe_v256.json`](runtime_observe_v256.json)、
[`evaluator_v1_legacy/`](evaluator_v1_legacy/)、[`evaluator_v2_final/`](evaluator_v2_final/)。

报告与运行产物：`../artifacts/report.md`、`../artifacts/boundary_assertions.txt`、
`../artifacts/v1_metrics.json`、`../artifacts/v2_metrics.json`、
`../artifacts/v1_eval_detail.csv`、`../artifacts/v2_eval_detail.csv`、
`../artifacts/v1_rows_parser.csv`、`../artifacts/v2_rows_parser.csv`。

---

## 三个必须先钉死的数

| 指标 | 分子/分母 | 值 | 定义 |
| --- | --- | --- | --- |
| **定位率** | 104 / 105 | **99.05%** | 只要找到候选块就算，不看值/单位/符号/页码 |
| **命中率（主口径）** | 89 / 105 | **84.76%** | 值 + 单位 + 符号 + 页码 四门全过，condition 作参考 |
| 命中率（保守口径） | 76 / 105 | 72.38% | 把 condition 也当硬门，五门全过 |

**命中定义（写死）：值、单位、符号、条件（参考）、页码全部一致。**

`104` 是**定位率**的分子，不是命中率的分子。它的构成可以逐行数出来：

```
v1 定位 99  +  V256 修复后新增定位 5（G088–G092）  =  v2 定位 104
104（定位）= 89（命中）+ 15（错误匹配）； 105 − 104 = 1（漏提）
```

完整的 104 拆解与那 5 行的值/单位/条件，见
[`error_matrix_105_README.md` §2.1](error_matrix_105_README.md)。

---

## 需求 1：105 行错误矩阵

**要求**：含 `sample_id`、`gold_row_id`、`parser_output_id`、`match_status`、
`value_match`、`unit_match`、`symbol_match`、`condition_match`、`gold_page`、
`parser_page`、`error_category`、`secondary_category`，且能直接看出「命中」定义。

**交付**：[`error_matrix_105.csv`](error_matrix_105.csv)（17 列，含上述全部 + `located`、
`defect_owner`、`match_mode`、`block_rows`、`run_version`）。

- `命中` 定义写在 [README §一](error_matrix_105_README.md)，四门 + 页码，缺一不算。
- `located` 列是定位率的分子标记，让 104 可以逐行数出来。
- `symbol_match` 由 `match_mode` 推出（token/text → 是；by_value → 否；Gold 无符号 → 不适用），
  不是新判据，只是把已有事实显式化。
- 两份矩阵**只有 V256 的 G088–G092 五行不同**，其余 100 行逐字段一致。

## 需求 2：39 行评估器翻正证据

**交付**：[`evaluator_flips_39.csv`](evaluator_flips_39.csv)、
[`evaluator_v1_legacy/`](evaluator_v1_legacy/)、[`evaluator_v2_final/`](evaluator_v2_final/)、
[`SHA256SUMS.txt`](SHA256SUMS.txt)、
[`parser_json_immutability.txt`](parser_json_immutability.txt)。

- 两版评估器脚本冻结 + SHA-256 登记。
- 不可变性用「跑两遍再比对」证：185 个 JSON 快照 A → 跑两版评估 → 快照 B，
  **变化 0 / 消失 0 / 新增 0**；v2 侧另有 192 个 JSON 的同款证明。
- **两版 `_evaluate.py` 哈希相同不是抄错**：口径开关是 `_replay_common.py` 的 `LEGACY` 常量，
  差异落在那个文件（两个哈希确实不同）。

## 需求 3：修复 V256 崩溃

**交付**：[`v256_crash_evidence.md`](v256_crash_evidence.md)、
[`parser_v1_v2_diff.md`](parser_v1_v2_diff.md)、[`postfix_rerun_24.md`](postfix_rerun_24.md)。

- 真实 traceback + 第 57 页 `grid_ys` 逐位前后对照（11 条边界，3 处倒序）。
- 夹紧公式与容差：`gap = min(0.2, (hi-lo)/(n-1))`，只上推不下拉，**不排序**。
- 单元格映射逐格证明：26 格不变、`(text,row,column)` 序列一致、每行格数分布一致、
  `left`/`right` 零改动、**零个单元格位移**。
- **影响面：24 件 2701 张表里只有 1 张（`V256 p057-t01`）触发夹紧**，
  其余 2700 张严格恒等变换。
- 修复后 24/24 成功，其余 23 件 **115 个文件逐字节 sha256 相同**。

## 需求 4：环境与零网络调用证据

**交付**：[`network_guard_proof.md`](network_guard_proof.md)、
[`pdf_sha256_24.csv`](pdf_sha256_24.csv)、[`parser_commit.txt`](parser_commit.txt)、
[`pip_freeze.txt`](pip_freeze.txt)、[`runtime_observe_v256.json`](runtime_observe_v256.json)。

六层拦截，不是只有 socket：

| 层 | 拦什么 | 实测 |
| --- | --- | --- |
| L1 凭据 | 删 18 个 API key / base_url / model 环境变量 | 实际清掉 1 个（`GEMINI_API_KEY`） |
| L2 DNS | `getaddrinfo` / `gethostbyname` / `gethostbyaddr` | 已拦 |
| L3 传输 | `socket.connect` / `create_connection` / `connect_ex` | 已拦 |
| L4 协议库 | `urllib` / `http.client` / `ftplib` / `smtplib` / `requests` / `httpx` | 已拦 |
| L5 子进程 | `subprocess.Popen` / `os.system` / `os.exec*` / `os.fork` | 已拦 |
| L6 Provider | `openai` / `anthropic` 等 11 个 SDK 导入即抛错 | 已拦 |

- **16 个出网向量 16/16 全部被拦**，含 DNS、子进程 curl、SDK 导入。
- **对照组（不装闸）能出网** → 拦截是闸干的，不是机器断网。
- 运行时观测：跑 V256 全程 **出网事件 0 次**（仅 1 次本地 `gethostname`），
  说明是「根本没发生」而不是「发生了被拦」。

---

## 附：Tech Debt 台账

[`TECH_DEBT.md`](TECH_DEBT.md) 记录四类**本轮不修**的 Parser 语义缺陷：

| 编号 | 问题 | 受影响行数 |
| --- | --- | --- |
| TD-01 | 档位串行：同一列参数值错行归属 | 4 |
| TD-02 | 合并单元格：跨行单元格未随行下传 | 6 |
| TD-03 | 同名抢匹配：同页同名符号跨页/多语境抢匹配 | 5 |
| TD-04 | 同格未拆分：一格多参数值未拆成多行 | 0（与 TD-01 重叠） |
| 待归类 | 行未成块：该页不存在同时含两条件的块（`V319 / IO`） | 1 |

合计 16 行 = 105 − 89 命中，逐行对得上矩阵。

---

## 一句话总结

| Reviewer 的问题 | 答案 | 证据 |
| --- | --- | --- |
| 94.3% / 99.05% 是怎么算的 | 那是**定位率**；命中率是 84.76%（主口径）或 72.38%（condition 也算硬门） | [`error_matrix_105_README.md`](error_matrix_105_README.md) |
| 104 的分子能核对吗 | 能：v1 的 99 + V256 的 G088–G092 五行 | 同上 §2.1 |
| 39 行翻正是否动了 Parser | 没动，185/192 个 JSON 哈希全同 | [`parser_json_immutability.txt`](parser_json_immutability.txt) |
| V256 修得对不对、有没有伤到别人 | 23 件 115 个文件逐字节不变；2701 表里只有 1 表受影响 | [`parser_v1_v2_diff.md`](parser_v1_v2_diff.md) |
| 有没有偷偷联网 | 出网事件 0 次；16 向量全拦；对照组能出网 | [`network_guard_proof.md`](network_guard_proof.md) |
