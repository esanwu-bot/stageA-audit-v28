# Gate 6A 审计证据包 v3

> 本仓库此分支（`feat/gate6a-audit`）仅存放 Gate 6A 的**审计证据、口径说明与可复现脚本**。
> **不含任何 `src/` 源码，不含 PDF，不含 Gold 数据文件，不含凭据。**

本目录不是入口。请从 **审计索引** 开始读：

## 入口

- **[`workbench/gate6a_replay/audit/README.md`](workbench/gate6a_replay/audit/README.md)** — 文件索引、四个口径对照、104 的逐行拆解、五条需求的对应关系
- **[`workbench/gate6a_replay/audit/eval_v3_1to1.md`](workbench/gate6a_replay/audit/eval_v3_1to1.md)** — v3 评估器相对 v2 改了什么、怎么证明改对了

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
| 2 | [`audit/soft_hits.csv`](workbench/gate6a_replay/audit/soft_hits.csv) | 7 条「值在大块里但无法逐行确认」的行，逐条列出块行数与匹配方式 |
| 3 | [`audit/consumption_reassignments.csv`](workbench/gate6a_replay/audit/consumption_reassignments.csv) | v2 → v3 唯一一条块归属变动（V256/G090）及其原因 |
| 4 | [`audit/parent_block_sharing.csv`](workbench/gate6a_replay/audit/parent_block_sharing.csv) | 13 个被多行共用的父块，各自的物理行分配与 `all_distinct` 校验 |
| 5 | [`audit/v256_crash_evidence.md`](workbench/gate6a_replay/audit/v256_crash_evidence.md) | 夹紧公式、实测最大位移 **+33.663 pt**、`0.2 pt` 只是最小行间距阈值、下游不读 `status` 的静态核对 |
| 6 | [`audit/source_fingerprint.md`](workbench/gate6a_replay/audit/source_fingerprint.md) + [`monotonic_lattice.diff`](workbench/gate6a_replay/audit/monotonic_lattice.diff) | 主仓三个 commit 的 `structure.py` blob 指纹、`+47 / -2` 的完整 diff、`core.autocrlf` 行尾陷阱 |
| 7 | [`audit/parser_json_immutability.txt`](workbench/gate6a_replay/audit/parser_json_immutability.txt) | 评估器只读不写的**静态代码证据**（时间戳已降级为辅助） |

## 怎么自行验证

四个脚本都可以直接跑，失败即非零退出：

```bash
# 1. 先证明没换输入：冻结产物能重建 v2 的全部指标
python workbench/gate6a_replay/_verify_v3_faithful.py
#   → 24 样本块组装零漂移；旧逻辑复现 v2 的 104 / 89 / 8 / 7

# 2. v3 的 27 项不变量
python workbench/gate6a_replay/_assert_v3_1to1.py
#   → 全部 27 项断言通过

# 3. 校验拿到的字节和本包一致
cd workbench/gate6a_replay/audit && sha256sum -c SHA256SUMS.txt
#   → 53 个文件全部 OK
```

`audit/**` 与 `artifacts/**` 在 `.gitattributes` 里标为 `-text`，**禁止 git 转换行尾**。
不加这一条，Windows 检出会是 CRLF、Linux 会是 LF，同一份产物的 sha256 就不同，
校验表随之失效 —— v2 踩过这个坑（31 个文件对不上），v3 已修。

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
```

补充：[`audit/pip_freeze.txt`](workbench/gate6a_replay/audit/pip_freeze.txt)（环境）、
[`artifacts/v1_env_snapshot.json`](workbench/gate6a_replay/artifacts/v1_env_snapshot.json) /
[`artifacts/v2_env_snapshot.json`](workbench/gate6a_replay/artifacts/v2_env_snapshot.json)（两次运行的环境快照）。
