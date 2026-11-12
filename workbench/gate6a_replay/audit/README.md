# Gate 6A 内部审计证据包 · 索引

本目录回应 Reviewer 的审查意见。每一项都给出**可机检的原始文件**，不依赖任何口头说明。

- 冻结时间：2026-11-12
- 回测根：`gate6a_replay_v1`（首次受控回测）、`gate6a_replay_v2_postfix`（格线修复后补跑）、
  `gate6a_replay_v3_1to1`（**一对一消费匹配 + 物理行级符号/condition 归属，本包主口径**）
- 源码版本：见 [`parser_commit.txt`](parser_commit.txt) 与 [`source_fingerprint.md`](source_fingerprint.md)

> **⚠️ 口径更新（v3.2，最新）**：硬命中由 **82 修正为 66 / 105 = 62.86%**。
> 上一版只校验「符号挂上了这个块」，没校验「符号属于这一行」；下沉到物理行后
> 16 行因**无依据跨行继承**降级为软命中。一对一消费与块组装**完全没动**
> （两份 CSV 逐字节相同可证）。**引用硬命中请用 66。**
> 详见 [`eval_v3_2_row_level.md`](eval_v3_2_row_level.md)。

> **本包不含 `src/icpdf/` 源码树。** 唯一的源码片段是
> [`monotonic_lattice.diff`](monotonic_lattice.diff) —— 被审的那一处改动本身，
> 供逐行核对公式，不含其他实现。

---

## v3 改了什么（本轮回应）

Reviewer 扒开评估器后指出两个致命伤，两条都成立：

| 指控 | 实际是什么 | 修法 | 证据 |
| --- | --- | --- | --- |
| **假一对一消费** | `eval_gold_row` 让每条 Gold 独立扫全池，同一候选块可被任意多条 Gold 行反复引用（实测 14 个块被 2~3 行共用，V256 的 G089/G090 抢同一个 `n_rows=1` 的单行块） | 引入物理行级消费集合；多行父块按「父块-子行」拆到不同物理行，记 `matched_physical_row_id` | [`v3_consumption_reassignments.csv`](../artifacts/v3_consumption_reassignments.csv)、[`v3_parent_block_sharing.csv`](../artifacts/v3_parent_block_sharing.csv) |
| **软硬命中混算** | `exact_rows` 直接把 `coarse=True`（命中落在 ≥5 行大块里）的行算作完全一致 | 强制剔除，单列 [`v3_soft_hits.csv`](../artifacts/v3_soft_hits.csv)；当时严格命中 = 82（v3.2 再降至 66，见文首口径更新） | [`v3_soft_hits.csv`](../artifacts/v3_soft_hits.csv)、[`error_matrix_105.csv`](error_matrix_105.csv) |

**Parser 一次都没有重跑。** v3 的输入是 v2 冻结在盘上的 `per_sample/` 产物，
只重算评估器侧的块组装与匹配。块组装结果与 v2 冻结的 `param_blocks` 逐块比对，
24 个样本零漂移（见 [`eval_v3_1to1.md`](eval_v3_1to1.md) §1）。

---

## 四个数，必须分开

| 指标 | 分子/分母 | 值 | 定义 |
| --- | --- | --- | --- |
| **严格命中率**（主口径） | **66 / 105** | **62.86%** | 值 + 单位 + 符号 + 页码全过，**且 `coarse=否`，且符号归属在命中物理行上可证** |
| 全字段一致（含软） | 89 / 105 | 84.76% | 同上但含 `coarse=是` 与符号无依据的行（v2 的旧口径） |
| 命中率（保守口径） | 69 / 105 | 65.71% | 严格命中里再把 condition 当硬门（v3 旧算法，仅作对照） |
| **定位率** | **104 / 105** | **99.05%** | 只要找到候选块就算，不看字段 |

```
定位             104 / 105   99.05%
 ├─ 全字段一致      89 / 105   84.76%
 │   ├─ 严格命中      66 / 105   62.86%   ← 本轮主口径
 │   └─ 软命中        23 / 105   21.90%   （coarse 7 + 符号无依据 16）
 └─ 错误匹配        15 / 105   14.29%
漏提                  1 / 105
```

**`104` 是定位率的分子，不是命中率的分子。** `89` 也不是严格命中 —— 它含 23 行软命中。
只有 `66` 是严格命中。完整拆解见
[`eval_v3_2_row_level.md` §1](eval_v3_2_row_level.md) 与
[`error_matrix_105_README.md` §2](error_matrix_105_README.md)。

**敏感性参考（不是主指标）**：若把「父块内符号在更靠前的行」也算通过，
严格命中为 **81 / 105 = 77.14%**（`metrics.symbol_inheritance.strict_if_cross_row_accepted`）。
我们不用它当结论，但把它算好放在那里。

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
| 2 | [`error_matrix_105_README.md`](error_matrix_105_README.md) | 字段字典与四口径定义 | 66 / 89 / 69 / 104 分别怎么算 |
| 3 | [`v3_soft_hits.csv`](../artifacts/v3_soft_hits.csv) | 23 条软命中逐条 | 哪 23 行没进严格命中，各自是什么原因 |
| 4 | [`eval_v3_2_row_level.md`](eval_v3_2_row_level.md) | **本轮主文档**：符号继承 + condition 四层 | 82 为什么降到 66、16 行逐条、V077/V256 深挖 |

### 物理行级归属（本轮新增，回应 19:08 意见）

| # | 文件 | 一句话 |
| --- | --- | --- |
| 5 | [`symbol_inheritance_proof.csv`](symbol_inheritance_proof.csv) | 20 行 = 16 行无依据跨行继承 + 4 行无符号；含 `is_parent_first_row` / `in_reviewer_filter` 两列，可按字面口径复现子集 |
| 6 | [`condition_attribution.csv`](condition_attribution.csv) | 31 条带 condition 的行，四层归属逐条（row 12 / header 0 / block 2 / unresolved 17） |
| 7 | [`v3_metrics.json`](../artifacts/v3_metrics.json) | `schema_version=3.2`，含 `strict_scope_breakdown` 配平表与 `strict_if_cross_row_accepted` |

### 一对一消费的证据链

| # | 文件 | 一句话 |
| --- | --- | --- |
| 8 | [`v3_parent_block_sharing.csv`](../artifacts/v3_parent_block_sharing.csv) | 13 个被多条 Gold 行共用的父块，及各自分配到的子行（全部互不相同） |
| 9 | [`v3_consumption_reassignments.csv`](../artifacts/v3_consumption_reassignments.csv) | 因消费冲突而改判的行（仅 1 行，V256 G090） |
| 10 | [`../_assert_v3_1to1.py`](../_assert_v3_1to1.py) | 37 项不变量断言脚本，可直接运行 |

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
| 完整工作区 | 另加 `_verify_v3_faithful.py`（复现 v2 的 104/89/8/7）、<br>`_assert_v3_1to1.py`（37 项不变量） |

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

- `exact_rows` 只表示「值/单位/页码/符号在块级全过」，**含 coarse、含软命中**，等于 严格 + 软 = 66 + 23 = 89。
- 23 条被剔出的行单列 [`v3_soft_hits.csv`](../artifacts/v3_soft_hits.csv)：7 条是 `n_rows` 为 5/6/8 的大块 + `text` 匹配，16 条是**符号无依据跨行继承**。
- 严格硬命中率 **66 / 105 = 62.86%**。

### 需求 3：指标命名统一

`metrics.json` 已改名并附 `definitions` 字段：

| 旧名 | 新名 | 含义 |
| --- | --- | --- |
| `recall` | `location_rate` | 定位率，不是召回率 |
| `hit_rows` | `located_rows` | 定位到候选块的行数 |
| `exact_rows` | `strict_hit_rows`（**不再同值**） | `exact_rows` = 全字段一致（含软）；`strict_hit_rows` = 66，只含符号归属可证的行 |
| — | `soft_hit_rows` | 软命中，新增 |
| — | `row_verified_hit_rows` | 严格命中且值确实落在被指派物理行 |
| `condition_match` | `condition_attribution.reference_only.condition_match` | 明确标注仅参考 |
| — | `symbol_inheritance` | 符号从哪来，新增（v3.2） |
| — | `condition_attribution` | 条件落在哪一层，新增（v3.2） |

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
| 软命中和硬命中混算了 | 已拆：89 里 23 行是软命中，严格命中 66 / 105 = 62.86% | [`v3_soft_hits.csv`](../artifacts/v3_soft_hits.csv) |
| 符号只在首行、值在后续行，也算命中？ | 不算。15 行跨行借用 + 1 行行指派错位全部降级，逐行给出几何/结构证据缺失的原因 | [`symbol_inheritance_proof.csv`](symbol_inheritance_proof.csv) |
| condition 是不是父块里出现过就放行？ | 不是。拆成 row/header/block/unresolved 四层，12 行落到命中行，V256 五行 5/5 行级可证 | [`condition_attribution.csv`](condition_attribution.csv) |
| V256 的 G089/G090 抢同一行 | 已修：改落 `r03` / `r04`，且与各自 condition 吻合（condition 未参与分配） | [`v3_consumption_reassignments.csv`](../artifacts/v3_consumption_reassignments.csv) |
| 94.3% / 99.05% 怎么算的 | 都是**定位率**；命中率是 66（严格）/ 89（含软）/ 69（condition 硬门，v3 旧算法） | [`error_matrix_105_README.md`](error_matrix_105_README.md) |
| 39 行翻正是否动了 Parser | 没动，185/192 个 JSON 哈希全同 | [`parser_json_immutability.txt`](parser_json_immutability.txt) |
| V256 修得对不对、有没有伤到别人 | 23 件 115 个文件逐字节不变；2701 表里只有 1 表受影响；最大边界位移 +33.663pt 但单元格位移 0 | [`v256_crash_evidence.md`](v256_crash_evidence.md) |
| 有没有偷偷联网 | 出网事件 0 次；16 向量全拦；对照组能出网 | [`network_guard_proof.md`](network_guard_proof.md) |
| 你们声明的夹紧公式是真代码吗 | 是，diff 逐行可核，且新增行里没有排序、没有下拉 | [`monotonic_lattice.diff`](monotonic_lattice.diff) |

---

## Security Note

**本次推送触发了 GitGuardian 针对 `@` 符号与内网 URL 的规则告警。经排查无真实凭据泄露，已剔除内网域名的历史记录。保留的 40 位 commit SHA 为代码溯源锚点，非敏感信息。**

**内网地址已脱敏，源哈希保留。** 完整根因、排查过程、清理动作与验证结果见 [`SECURITY_INCIDENT.md`](SECURITY_INCIDENT.md)。

### 告警定位

| 触发位置 | 原始形态 | 命中规则 | 性质 |
| --- | --- | --- | --- |
| `audit/pip_freeze.txt:20` | 可编辑安装行：`-e git+<内网主机>/<组织ID>/<repo>.git@<40位SHA>#egg=<包名>` | Generic Password（`.git` 后的 `@` 被解析为 userinfo 分隔符）、High Entropy Secret | 误报：`@` 后是 commit SHA，不是密码；该 URL 无 userinfo 段 |
| `gate6/r2/GIT_BASELINE.json`、`gate6/r2/*.md`、`git_verify_raw.log`、`gate6a-plan/**` 等 13 个文件 | 裸 remote URL：`<内网主机>/<组织ID>/<repo>.git` | High Entropy Secret（24 位组织 ID） | 真实的信息暴露：泄露内网仓库主机名与组织 ID，但**不含凭据** |

### 排查结论：无真实凭据

- **全历史 blob 逐字节扫描**（1247 个 blob，111 个提交，非浅克隆）：AWS `AKIA` / GitHub `gh[pousr]_` / OpenAI `sk-` / Slack `xox` / 阿里云 `LTAI` / URL 内嵌凭据（userinfo 段）/ 赋值型 `password`、`secret`、`api_key` —— **命中 0 条**。
- **环境快照**：`v1_env_snapshot.json`、`v2_env_snapshot.json` 的 `llm.env_vars_present` 均为 `[]`，无 env 字典、无凭据键。
- **本地残留**：`~/.git-credentials`、`~/.netrc` 均不存在；git 凭据走 Windows 凭据管理器；`~/.npmrc` 仅含 registry 地址，无 token。
- **推送脚本** `gate6/r2/_push_r2_github.py`：token 由 `git credential fill` 运行时取得，无硬编码。

### 已执行的清理

1. **内网地址脱敏**：全历史将内网 Git 主机的完整仓库地址（`<内网主机>/<组织ID>/<repo>.git`）替换为 `[REDACTED-INTERNAL-REPO]`；`pip_freeze.txt` 该行改为 `icpdf-extractor==[REDACTED-LOCAL-VCS]`。
2. **高熵噪声剔除**：`r3/b64_parts_r3/` 的 3 个 Base64 分卷（`audit_minimal_v28_r3.zip` 的分片，45.8 KB）已从历史移除。还原后 SHA-256 `866cc36f6dc263e3efa89869a251957a77b2fd30f72ce916aa0b3df8faf65f9e`、34049 字节、6 个文件，与本包无关的重复副本。
3. **历史重写**：`git filter-repo` 重写全部 111 个提交与 4 个分支，旧 commit SHA 全部失效，已强推。

### 保留项与理由

`parser_commit.txt`、`source_fingerprint.md`、`monotonic_lattice.diff` 中保留 40 位 commit SHA。理由：这是审计溯源的锚点——「本包产物出自哪个 commit」是本包可复算性的前提。commit hash 是 git 对象标识符，不含任何凭据，脱离仓库不可反推内容。纯十六进制串理论熵上限为 4.0 bit/char，低于高熵检测阈值。

### 推送前脱敏关卡

此后每次推送前固定执行：

```bash
grep -rn "key\|token\|password\|secret" --include='*.md' --include='*.txt' --include='*.json' --include='*.py' .
git grep -n -E '://[^/[:space:]]+:[^/[:space:]]+@'   # 内嵌凭据 URL
git grep -n -E '(AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{36}|sk-[A-Za-z0-9]{20,}|LTAI[0-9A-Za-z]{12,})'
```
