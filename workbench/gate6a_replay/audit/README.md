# Gate 6A 内部审计证据包 · 索引

本目录回应 Reviewer 的审查意见。每一项都给出**可机检的原始文件**，不依赖任何口头说明。

- 冻结时间：2026-11-12
- 回测根：`gate6a_replay_v1`（首次受控回测）、`gate6a_replay_v2_postfix`（格线修复后补跑）、
  `gate6a_replay_v3_1to1`（**一对一消费匹配重算，本包主口径**）
- 源码版本：见 [`parser_commit.txt`](parser_commit.txt) 与 [`source_fingerprint.md`](source_fingerprint.md)

> **本包不含 `src/icpdf/` 源码树。** 唯一的源码片段是
> [`monotonic_lattice.diff`](monotonic_lattice.diff) —— 被审的那一处改动本身，
> 供逐行核对公式，不含其他实现。

---

## v3 改了什么（本轮回应）

Reviewer 扒开评估器后指出两个致命伤，两条都成立：

| 指控 | 实际是什么 | 修法 | 证据 |
| --- | --- | --- | --- |
| **假一对一消费** | `eval_gold_row` 让每条 Gold 独立扫全池，同一候选块可被任意多条 Gold 行反复引用（实测 14 个块被 2~3 行共用，V256 的 G089/G090 抢同一个 `n_rows=1` 的单行块） | 引入物理行级消费集合；多行父块按「父块-子行」拆到不同物理行，记 `matched_physical_row_id` | [`v3_consumption_reassignments.csv`](../artifacts/v3_consumption_reassignments.csv)、[`v3_parent_block_sharing.csv`](../artifacts/v3_parent_block_sharing.csv) |
| **软硬命中混算** | `exact_rows` 直接把 `coarse=True`（命中落在 ≥5 行大块里）的行算作完全一致 | 强制剔除，单列 [`v3_soft_hits.csv`](../artifacts/v3_soft_hits.csv)；严格命中 = 82 | [`v3_soft_hits.csv`](../artifacts/v3_soft_hits.csv)、[`error_matrix_105.csv`](error_matrix_105.csv) |

**Parser 一次都没有重跑。** v3 的输入是 v2 冻结在盘上的 `per_sample/` 产物，
只重算评估器侧的块组装与匹配。块组装结果与 v2 冻结的 `param_blocks` 逐块比对，
24 个样本零漂移（见 [`eval_v3_1to1.md`](eval_v3_1to1.md) §1）。

---

## 四个数，必须分开

| 指标 | 分子/分母 | 值 | 定义 |
| --- | --- | --- | --- |
| **严格命中率**（主口径） | **82 / 105** | **78.10%** | 值 + 单位 + 符号 + 页码全过，**且 `coarse=否`** |
| 全字段一致（含软） | 89 / 105 | 84.76% | 同上但含 `coarse=是`（v2 的旧口径） |
| 命中率（保守口径） | 69 / 105 | 65.71% | 严格命中里再把 condition 当硬门 |
| **定位率** | **104 / 105** | **99.05%** | 只要找到候选块就算，不看字段 |

```
定位           104 / 105   99.05%
 ├─ 全字段一致    89 / 105   84.76%
 │   ├─ 严格命中    82 / 105   78.10%   ← 本轮主口径
 │   └─ 软命中       7 / 105    6.67%
 └─ 错误匹配      15 / 105   14.29%
漏提                1 / 105
```

**`104` 是定位率的分子，不是命中率的分子。** `89` 也不是严格命中 —— 它含 7 行软命中。
只有 `82` 是严格命中。完整拆解见
[`error_matrix_105_README.md` §2](error_matrix_105_README.md)。

---

## 文件索引

> 约定：逐行产物统一放 `../artifacts/`，v3 的以 `v3_` 前缀命名
> （`v3_eval_detail.csv`、`v3_metrics.json`、`v3_soft_hits.csv`、
> `v3_consumption_reassignments.csv`、`v3_parent_block_sharing.csv`、`v3_rows_parser.csv`）。
> 本目录只放**说明与结论**，不复制产物，避免两份字节各自漂移。

### 核心（先看这四个）

| # | 文件 | 一句话 | 回答什么 |
| --- | --- | --- | --- |
| 1 | [`error_matrix_105.csv`](error_matrix_105.csv) | 105 行 × 20 列逐行判定 | 哪行严格命中、哪行软命中、哪行错、错在哪、落在哪个物理行 |
| 2 | [`error_matrix_105_README.md`](error_matrix_105_README.md) | 字段字典与四口径定义 | 82 / 89 / 69 / 104 分别怎么算 |
| 3 | [`v3_soft_hits.csv`](../artifacts/v3_soft_hits.csv) | 7 条软命中逐条 | 哪 7 行是靠大块并集撑起来的 |
| 4 | [`eval_v3_1to1.md`](eval_v3_1to1.md) | v3 算法与 v2→v3 差异 | 一对一怎么实现、改了哪几行、为什么 |

### 一对一消费的证据链

| # | 文件 | 一句话 |
| --- | --- | --- |
| 5 | [`v3_parent_block_sharing.csv`](../artifacts/v3_parent_block_sharing.csv) | 13 个被多条 Gold 行共用的父块，及各自分配到的子行（全部互不相同） |
| 6 | [`v3_consumption_reassignments.csv`](../artifacts/v3_consumption_reassignments.csv) | 因消费冲突而改判的行（仅 1 行，V256 G090） |
| 7 | [`../_assert_v3_1to1.py`](../_assert_v3_1to1.py) | 27 项不变量断言脚本，可直接运行 |

### V256 修复

| # | 文件 | 一句话 |
| --- | --- | --- |
| 8 | [`v256_crash_evidence.md`](v256_crash_evidence.md) | traceback + 夹紧公式 + 逐位坐标 + 26 格零位移 + 1/2701 影响面 + `partial` 不被洗白 |
| 9 | [`parser_v1_v2_diff.md`](parser_v1_v2_diff.md) | 24 件逐文件 sha256 对照 |
| 10 | [`source_fingerprint.md`](source_fingerprint.md) | Parser commit、`structure.py` blob 指纹、行尾陷阱 |
| 11 | [`monotonic_lattice.diff`](monotonic_lattice.diff) | `_monotonic_lattice` 的真实 diff（唯一源码片段） |

### 评估器不可变性

| # | 文件 | 一句话 |
| --- | --- | --- |
| 12 | [`parser_json_immutability.txt`](parser_json_immutability.txt) | 185 个 JSON A→B 快照，变化 0 / 消失 0 / 新增 0 |
| 13 | [`evaluator_flips_39.csv`](evaluator_flips_39.csv) | 39 行评估器翻正明细 |
| 14 | [`evaluator_v1_legacy/`](evaluator_v1_legacy/)、[`evaluator_v2_final/`](evaluator_v2_final/)、[`evaluator_v3_1to1/`](evaluator_v3_1to1/) | 三版评估器冻结快照 |

### 网络与环境

| # | 文件 | 一句话 |
| --- | --- | --- |
| 15 | [`network_guard_proof.md`](network_guard_proof.md) | 六层拦截 + 16 个出网向量 + 对照组 |
| 16 | [`pdf_sha256_24.csv`](pdf_sha256_24.csv)、[`pip_freeze.txt`](pip_freeze.txt)、[`parser_commit.txt`](parser_commit.txt) | 输入哈希、依赖、解析器版本 |

### 其余

[`error_matrix_105_v1_prefix.csv`](error_matrix_105_v1_prefix.csv)（修复前矩阵）、
[`postfix_rerun_24.md`](postfix_rerun_24.md)（v1→v2 重跑报告）、
[`TECH_DEBT.md`](TECH_DEBT.md)（16 行残留缺陷归类）、
[`runtime_observe_v256.json`](runtime_observe_v256.json)、
[`SHA256SUMS.txt`](SHA256SUMS.txt)。

### 怎么校验收到的字节和本包一致

在 `audit/` 目录下执行：

```bash
sha256sum -c SHA256SUMS.txt     # 53 个文件应全部 OK
```

已实测：在 `core.autocrlf=true`（Windows 默认）下克隆 GitHub 镜像后执行，
53 / 53 全部 OK。

为此有一项前置约定：`workbench/gate6a_replay/.gitattributes` 把 `audit/**` 与
`artifacts/**` 标记为 `-text`，**禁止 git 做任何行尾转换**。

原因很实际：`SHA256SUMS.txt` 记的是产物字节的 sha256。若检出时把 LF 转成 CRLF
（Windows 上 `core.autocrlf=true` 的默认行为），同一份产物在不同平台算出的哈希就不同，
清单失效。这个坑在本包 v2 里真实踩过 —— 有 31 个文件的工作区哈希与提交树哈希不一致，
Linux 上克隆必然报 FAILED。现在两侧都是 LF，跨平台一致。

脚本（`*.py`）不受此约束，仍按普通文本处理。

### 先决条件：哪些脚本在这个目录里跑得起来

本包按约定**不携带** Parser 冻结产物（`runs/`，体积以 GB 计）与 Gold 台账
（`workbench/_gate6a_prep/`，客户数据）。因此：

| 你手上的东西 | 能跑什么 |
| --- | --- |
| 只有审计仓库副本 | `sha256sum -c SHA256SUMS.txt` —— 核对字节 |
| 完整工作区 | 另加 `_verify_v3_faithful.py`（复现 v2 的 104/89/8/7）、<br>`_assert_v3_1to1.py`（27 项不变量） |

在仓库副本里跑后两个脚本，会打印缺哪几个输入并以退出码 2 结束。
这是脚本主动拦的，不是崩溃 —— 目的是别让复核者对着一屏 traceback 猜。

---

## 需求对应

### 需求 1：真正的「一对一消费」

- 候选单位从「块」下沉到 **(块, 物理行)**。一个物理行被占用后不可再分配。
- 多行父块（合并单元格）按父块-子行拆分：`parser_output_id` 记父块，
  `matched_physical_row_id` 记子行，`block_covered_rows` 列出父块覆盖的全部行。
- **V256 G089/G090 不再共用 `p013-t01-r03`**，改为 `r03` / `r04` 两个不同物理行。
- 分配顺序：证据档位 → 行级数值覆盖 → 候选数 → 文档序。**condition 不参与分配**。
- 13 个共用父块，子行全部互不相同；重复行数 **0**。

### 需求 2：硬/软命中分离

- `exact_rows` 只表示严格全字段一致，`coarse=True` 一律剔除。
- 7 条被剔出的行单列 [`v3_soft_hits.csv`](../artifacts/v3_soft_hits.csv)，全部是 `n_rows` 为 5/6/8 的大块 + `text` 匹配。
- 严格硬命中率 **82 / 105 = 78.10%**。

### 需求 3：指标命名统一

`metrics.json` 已改名并附 `definitions` 字段：

| 旧名 | 新名 | 含义 |
| --- | --- | --- |
| `recall` | `location_rate` | 定位率，不是召回率 |
| `hit_rows` | `located_rows` | 定位到候选块的行数 |
| `exact_rows` | `strict_hit_rows`（同值） | 仅严格全字段一致，已剔除 coarse |
| — | `soft_hit_rows` | 软命中，新增 |
| — | `row_verified_hit_rows` | 严格命中且值确实落在被指派物理行 |
| `condition_match` | `reference_only.condition_match` | 明确标注仅参考 |

### 需求 4：证据表述修正

- [`parser_json_immutability.txt`](parser_json_immutability.txt)：删掉「产物早于评估器脚本 17.7 分钟」
  这类把时间戳当证据的说法，改为**静态代码扫描**（评估器全部写操作的目标都是 `OUT_ROOT`，
  没有一处指向 `per_sample/`）+ A→B 哈希比对；时间戳降级为「仅记录运行顺序」。
- [`v256_crash_evidence.md`](v256_crash_evidence.md)：如实写明**最大边界位移 `+33.663 pt`**，
  `0.2 pt` 只是 `MIN_ROW_GAP_PT` 最小间距阈值、不是位移量；并补 §7 静态核对证明
  下游候选生成**完全不读 `status`**，所以 `partial` 无法被洗白。

### 需求 5：主仓源码指纹

- [`source_fingerprint.md`](source_fingerprint.md)：三个 commit 上 `structure.py` 的
  git blob SHA-1 与 LF 内容 sha256；并写清**回测跑在 `a11131a` + 199 个脏文件的工作树上**，
  修复事后以 `bede1f5` 提交，故字节归属由「基线 + diff + 产物哈希链」三者共同确定。
- [`monotonic_lattice.diff`](monotonic_lattice.diff)：`bede1f5` 对该文件的完整 diff（+47 / −2）。
- 附带行尾陷阱说明：本机 `core.autocrlf=true`，工作区是 CRLF、blob 是 LF，
  对工作区文件算 sha256 会得到不同值，必须以 `git cat-file blob` 为准。

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

合计 16 行 = 105 − 89（全字段一致），逐行对得上矩阵。

---

## 一句话总结

| Reviewer 的问题 | 答案 | 证据 |
| --- | --- | --- |
| 你们的一对一是假的吧 | 是假的，已修：块/物理行消费唯一，14→13 个共用父块全部落在不同子行，重复行 0 | [`v3_parent_block_sharing.csv`](../artifacts/v3_parent_block_sharing.csv) |
| 软命中和硬命中混算了 | 已拆：89 里 7 行是软命中，严格命中 82 / 105 = 78.10% | [`v3_soft_hits.csv`](../artifacts/v3_soft_hits.csv) |
| V256 的 G089/G090 抢同一行 | 已修：改落 `r03` / `r04`，且与各自 condition 吻合（condition 未参与分配） | [`v3_consumption_reassignments.csv`](../artifacts/v3_consumption_reassignments.csv) |
| 94.3% / 99.05% 怎么算的 | 都是**定位率**；命中率是 82（严格）/ 89（含软）/ 69（condition 硬门） | [`error_matrix_105_README.md`](error_matrix_105_README.md) |
| 39 行翻正是否动了 Parser | 没动，185/192 个 JSON 哈希全同 | [`parser_json_immutability.txt`](parser_json_immutability.txt) |
| V256 修得对不对、有没有伤到别人 | 23 件 115 个文件逐字节不变；2701 表里只有 1 表受影响；最大边界位移 +33.663pt 但单元格位移 0 | [`v256_crash_evidence.md`](v256_crash_evidence.md) |
| 有没有偷偷联网 | 出网事件 0 次；16 向量全拦；对照组能出网 | [`network_guard_proof.md`](network_guard_proof.md) |
| 你们声明的夹紧公式是真代码吗 | 是，diff 逐行可核，且新增行里没有排序、没有下拉 | [`monotonic_lattice.diff`](monotonic_lattice.diff) |
