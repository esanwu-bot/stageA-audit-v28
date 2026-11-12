# Gate 6A 审计证据包 v2

> 本仓库此分支（`feat/gate6a-audit`）仅存放 Gate 6A 的**审计证据、口径说明与可复现脚本**。
> **不含任何 `src/` 源码，不含 PDF、不含 Gold 数据文件、不含凭据。**

本目录不是入口。请从 **审计索引** 开始读：

## 入口

- **[`workbench/gate6a_replay/audit/README.md`](workbench/gate6a_replay/audit/README.md)** — 九文件索引、三个口径对照、104 的逐行拆解、四条需求的对应关系

## 七个核心证据文件

| # | 文件 | 回答哪个问题 |
|---|---|---|
| 1 | [`audit/error_matrix_105.csv`](workbench/gate6a_replay/audit/error_matrix_105.csv) | 105 行逐行的 `value_match` / `unit_match` / `symbol_match` / `condition_match` / `page_match` |
| 2 | [`audit/v256_crash_evidence.md`](workbench/gate6a_replay/audit/v256_crash_evidence.md) | 夹紧公式、容差理由、p057 修复前后坐标序列、26 格零位移证明、1/2701 影响面 |
| 3 | [`audit/network_guard_proof.md`](workbench/gate6a_replay/audit/network_guard_proof.md) | 六层拦截、16/16 出网向量被拦、对照组能出网、运行时出网 0 次 |
| 4 | [`artifacts/report.md`](workbench/gate6a_replay/artifacts/report.md) | 完整复盘报告（§0 定位率 / §4 命中率定义） |
| 5 | [`audit/TECH_DEBT.md`](workbench/gate6a_replay/audit/TECH_DEBT.md) | 16 行残留问题的归类 |
| 6 | [`audit/parser_commit.txt`](workbench/gate6a_replay/audit/parser_commit.txt) | 解析器 commit 与 v1→v2 的逐文件变更 |
| 7 | [`audit/parser_json_immutability.txt`](workbench/gate6a_replay/audit/parser_json_immutability.txt) | v1/v2 两次解析产物的逐字节不变性 |

补充：[`audit/pip_freeze.txt`](workbench/gate6a_replay/audit/pip_freeze.txt)（环境）、
[`artifacts/v1_env_snapshot.json`](workbench/gate6a_replay/artifacts/v1_env_snapshot.json) /
[`artifacts/v2_env_snapshot.json`](workbench/gate6a_replay/artifacts/v2_env_snapshot.json)（两次运行的环境快照）。

## 一句话把口径说清楚

| 口径 | 值 | 定义 |
|---|---|---|
| 定位率 | **104 / 105 = 99.05%** | 能定位到候选块（`located`），**不含**值/单位/符号/条件的正确性 |
| 命中率（主口径） | **89 / 105 = 84.76%** | 值、单位、符号、参考字段、页码**全部**一致 |
| 命中率（保守口径） | **76 / 105 = 72.38%** | 把 `condition_match` 也算作硬门 |

`104` 是**定位率**的分子，不是命中率的分子：

```
104 = 89 命中 + 15 错误匹配
105 - 104 = 1 漏提（V319 / IO）
```

v1 定位 99，修 V256 后新增 5 行定位（G088–G092），`99 + 5 = 104`。

> 早期报告把 94.3% 写成「命中率 / 召回率」，那是 **v1 的定位率**（99/105 = 94.29%）的误标。
> v2 已把三个口径完全拆开，不再混用。

## 修 V256 到底改善了什么（不夸大）

| 版本 | `located` | 命中 | 错误匹配 | 漏提 |
|---|---|---|---|---|
| v1（格线修复**前**） | 99 | **89** | 10 | 6 |
| v2（格线修复**后**） | 104 | **89** | 15 | 1 |

**命中数没有变，都是 89。** 修复新增的 5 行（V256 / G088–G092）从「漏提」变成「错误匹配」，
`value_match`、`unit_match`、`gold_page=parser_page=13` 全对，只有 `symbol_match=否`。

所以修复的价值不是提分，而是：

- 消除**整件崩溃**：v1 第 57 页 `grid_ys` 非严格递增 → 校验抛错 → V256 整件零输出；
- 把「Parser 崩了、无可诊断」变成「值和页都抽对了、只是合并符号单元没随行下传」——
  一个可归因、可进 Tech Debt（TD-02）的具体缺陷；
- 定位率 94.29% → 99.05%，漏提 6 → 1。

详见 [`audit/error_matrix_105_README.md` 第八节](workbench/gate6a_replay/audit/error_matrix_105_README.md)。

## 复现脚本

`workbench/gate6a_replay/` 下 20 个 `_*.py`：

- `_make_error_matrix.py` — 生成 105 行矩阵，内置三条自洽断言与口径冲突熔断
- `_v256_crash_evidence.py` — 复算夹紧、逐格比对、全量扫描影响面
- `_probe_network_guard.py` — 16 个出网向量 + 对照组
- `_probe_runtime_observe.py` — 只观察不拦截跑真实样本
- `_no_llm_guard.py` — 六层拦截钩子
- `_make_env_evidence.py` — 生成环境与网络证据文档

脚本通过 `from icpdf.*` 引用解析器模块——这里只出现**模块路径**，不含实现。无源码时无法直接运行，属预期。

## 分支说明

- 默认分支 `main` 存放的是**上一版 v1.1** 审计包（`gate6/`、`r3/`、`r4/`）。
- 本次 v2 全部证据在 **`feat/gate6a-audit`** 分支，请以分支链接为准。
