# Gate 6A 审计证据包 v3 + Stage B 血缘 Demo

> 本仓库此分支（`feat/gate6a-audit`）仅存放**审计证据、口径说明与可复现脚本**。
> **不含任何 `src/` 源码，不含 PDF，不含 Gold 数据文件，不含凭据。**

本目录不是入口。请从 **审计索引** 开始读：

## 入口

- **[`workbench/gate6a_replay/audit/README.md`](workbench/gate6a_replay/audit/README.md)** — 文件索引、四个口径对照、104 的逐行拆解、五条需求的对应关系
- **[`workbench/gate6a_replay/audit/eval_v3_1to1.md`](workbench/gate6a_replay/audit/eval_v3_1to1.md)** — v3 评估器相对 v2 改了什么、怎么证明改对了
- **[`lake/README.md`](lake/README.md)** — Stage B 三层血缘（raw / parse / eval），单件 V101 的四个绑定与两重身份
- **[`docs/New_Gate_受控灰度方案.md`](docs/New_Gate_受控灰度方案.md)** — 公网灰度前的限流、50 MB、180 秒强杀，以及 §8「明确没验证的事」
- **[`docs/demo/README.md`](docs/demo/README.md)** — Ds Bit 工作台本地端到端截图（**来自 `127.0.0.1:8000`，不是服务器**）

## v3 改了什么

Reviewer 指出两处致命伤，本轮针对性修复，**Parser 未重跑**，全部基于 v2 冻结产物重算：

| 缺陷 | v2 的表现 | v3 的修法 |
|---|---|---|
| **假一对一消费** | `eval_gold_row(g, blocks)` 让每条 Gold 行独立扫全池。实测 14 个父块被 2~3 条 Gold 行共用；V256 的 G089/G090 抢同一个 `n_rows=1` 的单行块 | 候选单位下沉到 **(块, 物理行)** 对，引入 `consumed_rows` 集合；`eval_detail` 新增 `matched_physical_row_id` |
| **软硬命中混算** | `exact_rows` 直接把 `coarse=True`（命中落在 ≥5 行大块内）的行算作完全一致 | 强制剔除，7 条单列 `soft_hits.csv`；严格命中 = 82 |

## 口径（v3）

| 口径 | 值 | 定义 |
|---|---|---|
| **严格命中率**（主口径） | **82 / 105 = 78.10%** | 值 + 单位 + 符号 + 页码全过，**且 `coarse=否`** |
| 全字段一致（含软） | 89 / 105 = 84.76% | 同上但含 `coarse=是`（v2 的旧口径） |
| 命中率（保守口径） | 69 / 105 = 65.71% | 严格命中里再把 `condition` 当硬门 |
| 定位率 | 104 / 105 = 99.05% | 只要找到候选块就算，不看字段 |

```
105 行 Gold
├─ 定位            104      99.05%
│   ├─ 全字段一致     89      84.76%
│   │   ├─ 严格命中   82      78.10%   ← 本轮主口径
│   │   └─ 软命中      7       6.67%   落在 ≥5 行大块内，无法逐行确认
│   └─ 错误匹配       15      14.29%
└─ 漏提               1             V319 / IO
```

**`104` 不是命中率的分子，`89` 也不是严格命中。** 只有 `82` 是。

## 七个核心证据文件

| # | 文件 | 回答哪个问题 |
|---|---|---|
| 1 | [`audit/error_matrix_105.csv`](workbench/gate6a_replay/audit/error_matrix_105.csv) | 105 行逐行的 `value_match` / `unit_match` / `symbol_match` / `condition_match` / `page_match`，含四态 `match_status` 与 `matched_physical_row_id` |
| 2 | [`artifacts/v3_soft_hits.csv`](workbench/gate6a_replay/artifacts/v3_soft_hits.csv) | 7 条「值在大块里但无法逐行确认」的行，逐条列出块行数与匹配方式 |
| 3 | [`artifacts/v3_consumption_reassignments.csv`](workbench/gate6a_replay/artifacts/v3_consumption_reassignments.csv) | v2 → v3 唯一一条块归属变动（V256/G090）及其原因 |
| 4 | [`artifacts/v3_parent_block_sharing.csv`](workbench/gate6a_replay/artifacts/v3_parent_block_sharing.csv) | 13 个被多行共用的父块，各自的物理行分配与 `all_distinct` 校验 |
| 5 | [`audit/v256_crash_evidence.md`](workbench/gate6a_replay/audit/v256_crash_evidence.md) | 夹紧公式、实测最大位移 **+33.663 pt**、`0.2 pt` 只是最小行间距阈值、下游不读 `status` 的静态核对 |
| 6 | [`audit/source_fingerprint.md`](workbench/gate6a_replay/audit/source_fingerprint.md) + [`monotonic_lattice.diff`](workbench/gate6a_replay/audit/monotonic_lattice.diff) | 主仓三个 commit 的 `structure.py` blob 指纹、`+47 / -2` 的完整 diff、`core.autocrlf` 行尾陷阱 |
| 7 | [`audit/parser_json_immutability.txt`](workbench/gate6a_replay/audit/parser_json_immutability.txt) | 评估器只读不写的**静态代码证据**（时间戳已降级为辅助） |

## 怎么自行验证

### 在这个仓库里能做的：核对字节

```bash
cd workbench/gate6a_replay/audit && sha256sum -c SHA256SUMS.txt
#   → 57 个文件全部 OK
```

已实测：在 `core.autocrlf=true`（Windows 默认）下克隆本仓库后执行，57 / 57 通过。

`audit/**` 与 `artifacts/**` 在 `.gitattributes` 里标为 `-text`，**禁止 git 转换行尾**。
不加这一条，Windows 检出是 CRLF、Linux 是 LF，同一份产物的 sha256 就不同，
校验表随之失效 —— v2 踩过这个坑（31 个文件对不上），v3 已修。

### 需要完整工作区才能做的：复算指标

本仓库按约定**不含** `runs/`（Parser 冻结产物，GB 级）与 `workbench/_gate6a_prep/`
（Gold 台账，客户数据）。所以下面两个脚本在**只含审计证据的副本里跑不起来**，
它们会打印缺失的输入并以退出码 2 结束：

```bash
python workbench/gate6a_replay/_verify_v3_faithful.py
#   → 24 样本块组装零漂移；旧逻辑复现 v2 的 104 / 89 / 8 / 7

python workbench/gate6a_replay/_assert_v3_1to1.py
#   → 全部 27 项断言通过
```

## Stage B：三层血缘（`lake/`）

单件 V101 从原始字节走到评估结论，每层可独立校验。本仓库收录**脚本 + 清单 + 评估输出**，
按上面的约定**不收录** PDF 本体、`_blobs/`、`catalog.duckdb` 与 Gold 数据文件。

| 绑定 | 值（V101） | 作用 |
| --- | --- | --- |
| `source_sha256` | `059d448c5a34a4b1f45f02038f5076b82633f372372a15c395940803dc7f3a2b` | 输入内容身份 |
| `parser_fingerprint` | `7e70c1f801004c54667b062934efdce28fb5624f461da9bd1625d62872132dca` | 27 个 `.py` 合并哈希 |
| `config_hash` | `ab9f12527767c7dffe670f4b49e516202f224902af996a73eb155aaa420d3d5c` | `configs/parser.yaml` 快照 |
| `run_id` | `V101-20261112T231416Z-ff12` / `…231418Z-4ff6` | **执行身份**（两个） |

前三个合起来是**可复现条件**（`reproducibility_key = 8a88bf9479cfcd2f…`，两条记录相同），
`run_id` 是**执行身份**（两条不同）。`parse_runs` 表刻意只有 PRIMARY KEY、
没有 UNIQUE 约束 —— 同条件重复执行必须全部保留，不能被数据库拒绝。

为什么 `parser_fingerprint` 不用 commit SHA：那次复跑跑在「修复已写好但未提交」的工作树上
（`dirty_files` 199 项），commit SHA 描述不了那份字节，27 文件合并哈希可以。

`lake/.gitattributes` 同样是 `* -text`：这些文件的 sha256 被写进
`run_manifest.json`（`dependency_lock_sha256`）与 `GOLD_MANIFEST.json`，
一旦 git 转换行尾，干净 clone 上校验就会假失败。

在本仓库里**能**做的：读 `run_manifest.json` 核对四个绑定、读 `eval.json` 看指标与
Gold 版本、读 `attribution.csv` 看逐行归因（`gold_row_id` + 判定，**不含值**）。

**不能**做的：直接跑 `lake/_verify_lineage.py`。它要实算 raw PDF 与 Gold 文件的哈希，
而这两类文件按约定不在本仓库。脚本会明确报缺哪个输入，不做尽力而为。

> V101 的 `semantic_hit_rate` 是 **0.00%**（9 行语义命中全为 0）。逐行原因在
> `eval.json.reason_counts`：6 行 `symbol_not_on_row`、3 行
> `condition_not_on_row:grouped_subheader`。这是真实结果，不是 bug：V101 正是当初用来
> 暴露「符号不在命中行」的样本。全库口径 58 / 105 = 55.24% 记在 `eval.json` 的
> `global_reference`。

## 目录

```
workbench/gate6a_replay/
├── .gitattributes          # 证据文件禁止行尾转换
├── _verify_v3_faithful.py  # 忠实性基线
├── _assert_v3_1to1.py      # 27 项不变量
├── _diff_v2_v3_assignment.py   # 隔离排序差异 vs 消费效应
├── _make_sha256sums.py     # 重生成校验清单
├── _make_source_fingerprint.py # 源码指纹
├── audit/                  # 证据本体 + 三个版本的冻结评估器快照
└── artifacts/              # v1 / v2 / v3 的逐行评估产物

lake/
├── .gitattributes          # 同上，sha256 已写进 manifest
├── README.md               # 三层结构、四个绑定、三个反例
├── _build_lake.py          # 建湖（raw 内容寻址 / blob 去重 / eval 绑定）
├── _verify_lineage.py      # 跨层引用自洽校验（需完整工作区）
├── _query_demo.py          # DuckDB 四条 SQL
├── _negative_tests.py      # 三个反例
├── _s3_connectivity_test.py    # 同一段 SQL 可切 --local / --s3
├── _dependency_lock.txt    # 依赖锁（内网源已过滤）
├── raw_layer/<sha256>/RAW.json # 只收录清单，不含 PDF 本体
├── parse_layer/<run_id>/   # run_manifest + config_snapshot + candidates.parquet
└── eval_layer/<run_id>/    # eval.json + attribution.csv（不含 Gold 值）

docs/
├── New_Gate_受控灰度方案.md  # 限流 / 50 MB / 180 秒强杀 + §8 未验证项
└── demo/                   # Ds Bit 本地端到端截图（127.0.0.1:8000）
```

补充：[`audit/pip_freeze.txt`](workbench/gate6a_replay/audit/pip_freeze.txt)（环境）、
[`artifacts/v1_env_snapshot.json`](workbench/gate6a_replay/artifacts/v1_env_snapshot.json) /
[`artifacts/v2_env_snapshot.json`](workbench/gate6a_replay/artifacts/v2_env_snapshot.json)（两次运行的环境快照）。
