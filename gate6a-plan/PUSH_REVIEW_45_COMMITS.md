# 远端推送前的 45 个提交审查

> **结论：可以快进推送（`origin/main` 是 `main` 的祖先），但本轮没有推。**
> 以下全部为只读命令，未执行 `git fetch`、未改动任何 ref、未触碰工作区。

## 1. 核对结果

| 项 | 值 |
|---|---|
| 仓库 | `E:\workspace\icpdf-extractor` |
| 远端 URL | `[REDACTED-INTERNAL-REPO]`（**不含凭据**，无需脱敏） |
| 当前分支 | `main` |
| 本地 `main` | `60a503cc8015ef9bfb27ddef1685e41593f3a75f` |
| `origin/main` | `853a80dd664c79ef90baaac53eefb9bbc2155dde` |
| `origin/main` 提交时间 | 2026-11-05 20:30:55 +0800 |
| `origin/main` 提交标题 | feat: initialize icpdf-extractor with Phase 0 contract and Phase 1 deterministic parser |
| `merge-base --is-ancestor origin/main main` | **`EXIT=0`**（0 = 是祖先，可快进） |
| 领先提交数 | **45** |
| 落后提交数 | **0**（无分叉） |
| 远端真实指向（`ls-remote`） | `853a80dd664c79ef90baaac53eefb9bbc2155dde` |

**`origin/main` 没有过期**：`git ls-remote`（纯查询，不写 ref）返回的远端 `refs/heads/main` 与本地 `origin/main` 指向同一个提交 `853a80dd664c79ef90baaac53eefb9bbc2155dde`。因此下面基于 `origin/main..main` 的统计是可信的，不存在「本地以为领先 45 个、远端其实已经变了」的情况。

## 2. 45 个提交改了 475 个文件

`475 files changed, 90610 insertions(+), 229 deletions(-)`

| 状态 | 文件数 |
|---|---|
| 新增 | 459 |
| 修改 | 16 |

| 顶层目录 | 文件数 |
|---|---|
| `gold` | 209 |
| `docs` | 156 |
| `tests` | 43 |
| `src` | 42 |
| `tools` | 18 |
| `workbench` | 4 |
| `(root)` | 2 |
| `configs` | 1 |

### 2.1 `src/` 是唯一的生产代码改动面（42 个文件）

| 状态 | 文件 |
|---|---|
| A | `src/icpdf/classification/.gitattributes` |
| A | `src/icpdf/classification/__init__.py` |
| A | `src/icpdf/classification/classifier.py` |
| A | `src/icpdf/classification/cli.py` |
| A | `src/icpdf/classification/evidence.py` |
| A | `src/icpdf/classification/models.py` |
| A | `src/icpdf/classification/report.py` |
| A | `src/icpdf/classification/rules.py` |
| M | `src/icpdf/cli.py` |
| M | `src/icpdf/domain/__init__.py` |
| M | `src/icpdf/domain/candidate.py` |
| M | `src/icpdf/domain/table.py` |
| A | `src/icpdf/domain/visual.py` |
| A | `src/icpdf/eval/__init__.py` |
| A | `src/icpdf/eval/jsonio.py` |
| A | `src/icpdf/eval/manifests.py` |
| M | `src/icpdf/parser/candidate_registry.py` |
| A | `src/icpdf/parser/config.py` |
| M | `src/icpdf/parser/coords.py` |
| A | `src/icpdf/parser/header_semantics.py` |
| A | `src/icpdf/parser/header_sides.py` |
| A | `src/icpdf/parser/layout.py` |
| A | `src/icpdf/parser/logical_assembly.py` |
| A | `src/icpdf/parser/logical_attribution.py` |
| A | `src/icpdf/parser/logical_boundary.py` |
| A | `src/icpdf/parser/logical_candidates.py` |
| A | `src/icpdf/parser/logical_canopy.py` |
| A | `src/icpdf/parser/logical_decision.py` |
| A | `src/icpdf/parser/logical_evidence.py` |
| A | `src/icpdf/parser/logical_identity.py` |
| A | `src/icpdf/parser/logical_projection.py` |
| M | `src/icpdf/parser/pipeline.py` |
| A | `src/icpdf/parser/pipeline_sandbox.py` |
| A | `src/icpdf/parser/rule_primitives.py` |
| A | `src/icpdf/parser/structure.py` |
| M | `src/icpdf/parser/table_detector.py` |
| M | `src/icpdf/parser/table_rebuilder.py` |
| A | `src/icpdf/parser/table_regions.py` |
| M | `src/icpdf/parser/text_blocks.py` |
| A | `src/icpdf/parser/visual_structure.py` |
| M | `src/icpdf/storage/artifact_store.py` |
| M | `src/icpdf/storage/run_store.py` |

其中 `src/icpdf/classification/` 下 8 个文件（含 `classifier.py`）整包新增——这是 G7a 基线提交 `35cd8a1` 带进来的，`classifier.py` 的内容哈希在 G7b 合入前后均为 `28b9f0bf…`，本次合并未改动它。

### 2.2 清单里 209 个 `gold/` 文件要单独看

`gold/` 占 475 个文件的 44%，但它**不是**本轮 Gate 6A 的 Gold Set。它是 Phase 1.2 / 1.3 阶段冻结的 `gold/generalization/` 泛化测试集（三份 PDF 的表级标注 + overlay 图），随 Phase 1.4 设计提交一并上主干。

Gate 6A 的 Gold Set 至今**一份都没建**，只交付了模板。两者不要混淆。

## 3. 工作区状态

已跟踪的改动只有 2 个，且都不属于这 45 个提交：

- `M src/icpdf/cli.py`
- `M workbench/_classifier_revision/R1_PRIME_SUPPLEMENT.md`

未跟踪路径 67 条（含 `.workbuddy/`、`workbench/`、`tools/stage_a|b/` 等）。它们**不在** Git 索引里，推送不会带上。

## 4. 推送前仍需 Reviewer 注意的三件事

1. **这是一次 45 个提交的合并推送，不是单提交**。`origin/main` 停在 `853a80dd…`（项目初始化提交），之后全部 Phase 1.1–1.4 的工作都还没上远端。推上去等于**一次性公开整个演进过程**，包括中途被后续提交修正过的设计文档。
2. **`gold/` 含 209 个文件、大量 PNG overlay**，仓库体积会明显增加。若对体积敏感，应先在推送前决定是否把这批 overlay 移出主仓。
3. **两个未提交的已跟踪改动（`cli.py`、`R1_PRIME_SUPPLEMENT.md`）会被留在本地**，推送的是它们在 `60a503c` 里的已提交版本，与工作区版本不同。如果这两处改动是必需的，需要在推送前先决定提交还是丢弃。

## 5. 本轮执行边界

- **未执行 `git push`**，本地与远端均无任何写入。
- 未执行 `git fetch`，`origin/main` 保持上次拉取时的状态（已用 `ls-remote` 交叉确认未过期）。
- 未改动工作区、未暂存、未提交。

## 6. 原始终端输出（逐字嵌入，未编辑）

```text
==============================================================================
远端推送前只读核验
repo     : E:\workspace\icpdf-extractor
recorded : 2026-11-11T12:41:50
note     : 本次未执行 git fetch；origin/main 为上次 fetch 的快照，
           远端真实指向见补充项 S1。remote URL 中的凭据已脱敏。
==============================================================================

### [1] 列出远端及其 URL（已脱敏）
$ git remote -v
origin	[REDACTED-INTERNAL-REPO] (fetch)
origin	[REDACTED-INTERNAL-REPO] (push)
[EXIT=0]

### [2] 当前分支
$ git branch --show-current
main
[EXIT=0]

### [3] 本地 main 指向
$ git rev-parse main
60a503cc8015ef9bfb27ddef1685e41593f3a75f
[EXIT=0]

### [4] 远端跟踪分支 origin/main 指向（上次 fetch 快照）
$ git rev-parse origin/main
853a80dd664c79ef90baaac53eefb9bbc2155dde
[EXIT=0]

### [5] origin/main 是否为 main 的祖先；0=是（可快进），1=否
$ git merge-base --is-ancestor origin/main main
(no output)
[EXIT=0]

### [6] 领先远端的提交清单
$ git log --oneline --decorate origin/main..main
60a503c (HEAD -> main, feat/s2b-schema-d4-d6) G7b: D' —— 板级证据足以裁决时抑制 DS_PRODUCT_MODEL_TITLE
35cd8a1 G7a: 纳入 classification 包基线（D' 之前的原始状态）
55da906 (origin/feat/s2b-schema-d4-d6) G6: replace R1 blacklist with parameter-source fix (R1' supplement)
3ed22a4 C6: never let a failed cleanup mask the original write error
a48c771 C5: clean up the temp file when write_json fails to rename
4c5b04a C4: pin the D4 durability and failure semantics with regression tests
a919945 C3: document the A3-W1 design and its evidence pack
2bb1c78 C2: wire the evidence layer into parse_pdf
18ddb3e C1: add an atomic byte-exact write channel
9797b3e C0b: drop identity collision and DTO contract errors from the table whitelist
8779a53 B0: land accepted S2b / A1 / A2 / A3-E0 / A3-E1 slices
717dd89 fix(s2b): bind ownership per object and document the threat model
9bced1a fix(s2b): make source instance ownership unforgeable
d9c9516 fix(s2b): bind source_instance_owner to evidence
d63d1de feat(s2b): gate keep/demote conflicts on source instance identity
02aa386 feat(s2b): preserve word assignments and row lattice
d7c674b feat(s2b): add schema snapshot and manifest validation
6f3e58d docs: revise Phase 1.4 S2b design for review r3
eac55f4 docs: revise Phase 1.4 S2b design for review r2
cf59799 docs: add Phase 1.4 S2b logical boundary design
f70b625 docs: freeze Phase 1.4 S2a review baseline
89ac0cd docs: record S2a frozen S1 baseline handoff
432cf4a fix(parser): bind S2a audit tolerance to the frozen S1 baseline
a59c105 docs: record S2a r2 GRID_TOL and artifact-completeness handoff
d02e690 fix(parser): bind S2a audit to S1 component tolerance and required artifacts
6962126 docs: record S2a r2 identity hardening handoff
ff38d2e fix(parser): harden S2a primitive audit identity and rebuild checks
9571756 docs: record S2a review r2 commit sha
4246c41 test(parser): audit S2a visual evidence against raw PDF primitives
044e1ee docs: record S2a review r1 commit sha
f48ecd5 fix(parser): address S2a review r1 provenance and status precedence
15a3200 docs: record S2a implementation commit sha
e6cba6b feat(parser): Phase 1.4 S2a visual boundary lattice
85c0065 docs: Phase 1.4 S2 design r1 - P0 data-model fixes and ConditionContext
cfcaa82 docs: Phase 1.4 S2 design and data-model proposal
ff52189 docs: S1 review response bundle
3fc4519 fix(parser): S1 review - caption-text gate and narrower label grid
003311f feat(parser): Phase 1.4 S1 - ruling primitives, components, table regions
a0b777e Gold v2 spec, independently reviewed generalization set, structure design
ee456ab feat(gold): evaluate frozen parser on three untuned vendor PDFs
f77ccb1 chore(gold): freeze parser params and generalization PDFs before testing
f8032cc (tag: phase1.3-evidence-slice1) feat(evidence): add header-cell references, role provenance and run validator
b8c2d3b (tag: phase1.2-round2) feat(parser): Phase 1.2 round 2 gold review and header/role semantics
ad6f9cb feat(parser): add Phase 1.2 gold set and five-layer table pipeline
1d8c722 (tag: phase1.1-baseline) feat(parser): freeze coordinate chain and config-driven thresholds
[EXIT=0]

### [7] 领先提交的改动统计
$ git diff --stat origin/main..main
 HANDOFF.md                                         |  831 +++
 configs/parser.yaml                                |   27 +-
 docs/GOLD_SPEC.md                                  |  179 +
 docs/PHASE1_1_DIAGNOSIS.md                         |  212 +
 docs/PHASE1_2_ARCHITECTURE.md                      |  181 +
 docs/PHASE1_3_EVIDENCE.md                          |   76 +
 docs/PHASE1_3_GENERALIZATION.md                    |  230 +
 docs/PHASE1_4_S1.md                                |  306 +
 docs/PHASE1_4_S2.md                                | 1007 +++
 docs/PHASE1_4_S2A.md                               |  634 ++
 docs/PHASE1_4_S2B_A2_EVIDENCE.md                   | 1025 +++
 docs/PHASE1_4_S2B_A3_E1_EVIDENCE.md                |  408 ++
 docs/PHASE1_4_S2B_A3_E1_HEAD_PARITY.md             |   78 +
 docs/PHASE1_4_S2B_A3_E1_R2_PARITY.md               |   91 +
 docs/PHASE1_4_S2B_A3_W1_DESIGN.md                  |  450 ++
 docs/PHASE1_4_S2B_A3_W1_EVIDENCE.md                |  397 ++
 docs/PHASE1_4_S2B_DESIGN.md                        | 5272 ++++++++++++++
 docs/PHASE1_4_S2B_DESIGN_r21.md                    | 5272 ++++++++++++++
 docs/PHASE1_4_S2B_DESIGN_r22.md                    | 5323 +++++++++++++++
 docs/PHASE1_4_STRUCTURE_MODEL.md                   |  301 +
 docs/S2A_FREEZE.md                                 |   79 +
 docs/SLICE6_INTEGRATION_PLAN.md                    |  204 +
 .../evidence/phase14_s1/ds10cp152_p13_detected.png |  Bin 0 -> 25247 bytes
 docs/evidence/phase14_s1/micrf103_p03_detected.png |  Bin 0 -> 198818 bytes
 docs/phase1_1/ADC12DJ5200/audit_candidates.csv     |   21 +
 docs/phase1_1/ADC12DJ5200/contact_sheet.png        |  Bin 0 -> 38038 bytes
 docs/phase1_1/ADC12DJ5200/page_stats.csv           |  158 +
 .../ADC12DJ5200/pages/page-0001-annotated.png      |  Bin 0 -> 501063 bytes
 docs/phase1_1/ADC12DJ5200/pages/page-0001.png      |  Bin 0 -> 398516 bytes
 .../ADC12DJ5200/pages/page-0002-annotated.png      |  Bin 0 -> 203894 bytes
 docs/phase1_1/ADC12DJ5200/pages/page-0002.png      |  Bin 0 -> 169982 bytes
 .../ADC12DJ5200/pages/page-0004-annotated.png      |  Bin 0 -> 417215 bytes
 docs/phase1_1/ADC12DJ5200/pages/page-0004.png      |  Bin 0 -> 346999 bytes
 .../ADC12DJ5200/pages/page-0016-annotated.png      |  Bin 0 -> 247733 bytes
 docs/phase1_1/ADC12DJ5200/pages/page-0016.png      |  Bin 0 -> 203875 bytes
 .../ADC12DJ5200/pages/page-0029-annotated.png      |  Bin 0 -> 384781 bytes
 docs/phase1_1/ADC12DJ5200/pages/page-0029.png      |  Bin 0 -> 316180 bytes
 .../ADC12DJ5200/pages/page-0030-annotated.png      |  Bin 0 -> 235714 bytes
 docs/phase1_1/ADC12DJ5200/pages/page-0030.png      |  Bin 0 -> 199522 bytes
 .../ADC12DJ5200/pages/page-0059-annotated.png      |  Bin 0 -> 236053 bytes
 docs/phase1_1/ADC12DJ5200/pages/page-0059.png      |  Bin 0 -> 203862 bytes
 .../ADC12DJ5200/pages/page-0065-annotated.png      |  Bin 0 -> 457026 bytes
 docs/phase1_1/ADC12DJ5200/pages/page-0065.png      |  Bin 0 -> 391156 bytes
 .../ADC12DJ5200/pages/page-0066-annotated.png      |  Bin 0 -> 412570 bytes
 docs/phase1_1/ADC12DJ5200/pages/page-0066.png      |  Bin 0 -> 351049 bytes
 .../ADC12DJ5200/pages/page-0074-annotated.png      |  Bin 0 -> 334195 bytes
 docs/phase1_1/ADC12DJ5200/pages/page-0074.png      |  Bin 0 -> 288597 bytes
 .../ADC12DJ5200/pages/page-0075-annotated.png      |  Bin 0 -> 378687 bytes
 docs/phase1_1/ADC12DJ5200/pages/page-0075.png      |  Bin 0 -> 325140 bytes
 .../ADC12DJ5200/pages/page-0081-annotated.png      |  Bin 0 -> 213338 bytes
 docs/phase1_1/ADC12DJ5200/pages/page-0081.png      |  Bin 0 -> 179123 bytes
 .../ADC12DJ5200/pages/page-0085-annotated.png      |  Bin 0 -> 199837 bytes
 docs/phase1_1/ADC12DJ5200/pages/page-0085.png      |  Bin 0 -> 163924 bytes
 .../ADC12DJ5200/pages/page-0100-annotated.png      |  Bin 0 -> 415754 bytes
 docs/phase1_1/ADC12DJ5200/pages/page-0100.png      |  Bin 0 -> 329379 bytes
 .../ADC12DJ5200/pages/page-0111-annotated.png      |  Bin 0 -> 259334 bytes
 docs/phase1_1/ADC12DJ5200/pages/page-0111.png      |  Bin 0 -> 210820 bytes
 .../ADC12DJ5200/pages/page-0113-annotated.png      |  Bin 0 -> 318616 bytes
 docs/phase1_1/ADC12DJ5200/pages/page-0113.png      |  Bin 0 -> 263178 bytes
 .../ADC12DJ5200/pages/page-0120-annotated.png      |  Bin 0 -> 282604 bytes
 docs/phase1_1/ADC12DJ5200/pages/page-0120.png      |  Bin 0 -> 233322 bytes
 .../ADC12DJ5200/pages/page-0131-annotated.png      |  Bin 0 -> 293977 bytes
 docs/phase1_1/ADC12DJ5200/pages/page-0131.png      |  Bin 0 -> 243408 bytes
 .../ADC12DJ5200/pages/page-0143-annotated.png      |  Bin 0 -> 285229 bytes
 docs/phase1_1/ADC12DJ5200/pages/page-0143.png      |  Bin 0 -> 232713 bytes
 .../ADC12DJ5200/pages/page-0155-annotated.png      |  Bin 0 -> 225370 bytes
 docs/phase1_1/ADC12DJ5200/pages/page-0155.png      |  Bin 0 -> 182082 bytes
 docs/phase1_1/ADC12DJ5200/table_stats.csv          |  892 +++
 docs/phase1_1/ADS1299/audit_candidates.csv         |   21 +
 docs/phase1_1/ADS1299/contact_sheet.png            |  Bin 0 -> 42090 bytes
 docs/phase1_1/ADS1299/page_stats.csv               |   73 +
 .../phase1_1/ADS1299/pages/page-0001-annotated.png |  Bin 0 -> 467115 bytes
 docs/phase1_1/ADS1299/pages/page-0001.png          |  Bin 0 -> 376616 bytes
 .../phase1_1/ADS1299/pages/page-0006-annotated.png |  Bin 0 -> 376935 bytes
 docs/phase1_1/ADS1299/pages/page-0006.png          |  Bin 0 -> 309468 bytes
 .../phase1_1/ADS1299/pages/page-0010-annotated.png |  Bin 0 -> 253473 bytes
 docs/phase1_1/ADS1299/pages/page-0010.png          |  Bin 0 -> 210382 bytes
 .../phase1_1/ADS1299/pages/page-0013-annotated.png |  Bin 0 -> 267790 bytes
 docs/phase1_1/ADS1299/pages/page-0013.png          |  Bin 0 -> 218587 bytes
 .../phase1_1/ADS1299/pages/page-0016-annotated.png |  Bin 0 -> 325332 bytes
 docs/phase1_1/ADS1299/pages/page-0016.png          |  Bin 0 -> 274823 bytes
 .../phase1_1/ADS1299/pages/page-0017-annotated.png |  Bin 0 -> 268107 bytes
 docs/phase1_1/ADS1299/pages/page-0017.png          |  Bin 0 -> 228794 bytes
 .../phase1_1/ADS1299/pages/page-0026-annotated.png |  Bin 0 -> 346856 bytes
 docs/phase1_1/ADS1299/pages/page-0026.png          |  Bin 0 -> 308897 bytes
 .../phase1_1/ADS1299/pages/page-0040-annotated.png |  Bin 0 -> 450265 bytes
 docs/phase1_1/ADS1299/pages/page-0040.png          |  Bin 0 -> 377338 bytes
 .../phase1_1/ADS1299/pages/page-0044-annotated.png |  Bin 0 -> 237750 bytes
 docs/phase1_1/ADS1299/pages/page-0044.png          |  Bin 0 -> 206319 bytes
 .../phase1_1/ADS1299/pages/page-0046-annotated.png |  Bin 0 -> 218843 bytes
 docs/phase1_1/ADS1299/pages/page-0046.png          |  Bin 0 -> 179181 bytes
 .../phase1_1/ADS1299/pages/page-0048-annotated.png |  Bin 0 -> 246973 bytes
 docs/phase1_1/ADS1299/pages/page-0048.png          |  Bin 0 -> 201519 bytes
 .../phase1_1/ADS1299/pages/page-0053-annotated.png |  Bin 0 -> 251094 bytes
 docs/phase1_1/ADS1299/pages/page-0053.png          |  Bin 0 -> 206990 bytes
 .../phase1_1/ADS1299/pages/page-0056-annotated.png |  Bin 0 -> 278697 bytes
 docs/phase1_1/ADS1299/pages/page-0056.png          |  Bin 0 -> 230195 bytes
 .../phase1_1/ADS1299/pages/page-0066-annotated.png |  Bin 0 -> 259214 bytes
 docs/phase1_1/ADS1299/pages/page-0066.png          |  Bin 0 -> 214889 bytes
 .../phase1_1/ADS1299/pages/page-0074-annotated.png |  Bin 0 -> 363750 bytes
 docs/phase1_1/ADS1299/pages/page-0074.png          |  Bin 0 -> 301319 bytes
 docs/phase1_1/ADS1299/table_stats.csv              |  392 ++
 docs/phase1_1/LM358/audit_candidates.csv           |   21 +
 docs/phase1_1/LM358/contact_sheet.png              |  Bin 0 -> 53155 bytes
 docs/phase1_1/LM358/page_stats.csv                 |   56 +
 docs/phase1_1/LM358/pages/page-0001-annotated.png  |  Bin 0 -> 518120 bytes
 docs/phase1_1/LM358/pages/page-0001.png            |  Bin 0 -> 415254 bytes
 docs/phase1_1/LM358/pages/page-0005-annotated.png  |  Bin 0 -> 248264 bytes
 docs/phase1_1/LM358/pages/page-0005.png            |  Bin 0 -> 199677 bytes
 docs/phase1_1/LM358/pages/page-0006-annotated.png  |  Bin 0 -> 304490 bytes
 docs/phase1_1/LM358/pages/page-0006.png            |  Bin 0 -> 234496 bytes
 docs/phase1_1/LM358/pages/page-0011-annotated.png  |  Bin 0 -> 295300 bytes
 docs/phase1_1/LM358/pages/page-0011.png            |  Bin 0 -> 231901 bytes
 docs/phase1_1/LM358/pages/page-0014-annotated.png  |  Bin 0 -> 299311 bytes
 docs/phase1_1/LM358/pages/page-0014.png            |  Bin 0 -> 227734 bytes
 docs/phase1_1/LM358/pages/page-0015-annotated.png  |  Bin 0 -> 316238 bytes
 docs/phase1_1/LM358/pages/page-0015.png            |  Bin 0 -> 262037 bytes
 docs/phase1_1/LM358/pages/page-0017-annotated.png  |  Bin 0 -> 315910 bytes
 docs/phase1_1/LM358/pages/page-0017.png            |  Bin 0 -> 265505 bytes
 docs/phase1_1/LM358/pages/page-0020-annotated.png  |  Bin 0 -> 254694 bytes
 docs/phase1_1/LM358/pages/page-0020.png            |  Bin 0 -> 220228 bytes
 docs/phase1_1/LM358/pages/page-0022-annotated.png  |  Bin 0 -> 269138 bytes
 docs/phase1_1/LM358/pages/page-0022.png            |  Bin 0 -> 228228 bytes
 docs/phase1_1/LM358/pages/page-0031-annotated.png  |  Bin 0 -> 473441 bytes
 docs/phase1_1/LM358/pages/page-0031.png            |  Bin 0 -> 398261 bytes
 docs/phase1_1/LM358/pages/page-0032-annotated.png  |  Bin 0 -> 217606 bytes
 docs/phase1_1/LM358/pages/page-0032.png            |  Bin 0 -> 183044 bytes
 docs/phase1_1/LM358/pages/page-0033-annotated.png  |  Bin 0 -> 316624 bytes
 docs/phase1_1/LM358/pages/page-0033.png            |  Bin 0 -> 266323 bytes
 docs/phase1_1/LM358/pages/page-0035-annotated.png  |  Bin 0 -> 533683 bytes
 docs/phase1_1/LM358/pages/page-0035.png            |  Bin 0 -> 441019 bytes
 docs/phase1_1/LM358/pages/page-0036-annotated.png  |  Bin 0 -> 466954 bytes
 docs/phase1_1/LM358/pages/page-0036.png            |  Bin 0 -> 385140 bytes
 docs/phase1_1/LM358/pages/page-0037-annotated.png  |  Bin 0 -> 471436 bytes
 docs/phase1_1/LM358/pages/page-0037.png            |  Bin 0 -> 391111 bytes
 docs/phase1_1/LM358/pages/page-0038-annotated.png  |  Bin 0 -> 517447 bytes
 docs/phase1_1/LM358/pages/page-0038.png            |  Bin 0 -> 428187 bytes
 docs/phase1_1/LM358/pages/page-0043-annotated.png  |  Bin 0 -> 372842 bytes
 docs/phase1_1/LM358/pages/page-0043.png            |  Bin 0 -> 311330 bytes
 docs/phase1_1/LM358/pages/page-0044-annotated.png  |  Bin 0 -> 242416 bytes
 docs/phase1_1/LM358/pages/page-0044.png            |  Bin 0 -> 202243 bytes
 docs/phase1_1/LM358/pages/page-0047-annotated.png  |  Bin 0 -> 155140 bytes
 docs/phase1_1/LM358/pages/page-0047.png            |  Bin 0 -> 130290 bytes
 docs/phase1_1/LM358/table_stats.csv                |  413 ++
 docs/reviews/phase14_s1/003311f_s1.patch           | 5666 +++++++++++++++
 docs/reviews/phase14_s1/3fc4519_followup.patch     |  811 +++
 docs/reviews/phase14_s1/GIT_STATUS.txt             |   39 +
 docs/reviews/phase14_s1/REVIEW_RESPONSE.md         |  230 +
 .../phase14_s1/ds10cp152_p13_components.json       |  460 ++
 .../ds10cp152_p13_components_vs_region.png         |  Bin 0 -> 245657 bytes
 docs/reviews/phase14_s1/ds10cp152_p13_grid.json    |  201 +
 .../phase14_s1/ds10cp152_p13_grid_cells.png        |  Bin 0 -> 49444 bytes
 docs/reviews/phase14_s1/gold_v2_per_item_diff.json |  728 ++
 .../phase14_s1/micrf103_p03_components.json        |  208 +
 .../micrf103_p03_components_vs_region.png          |  Bin 0 -> 253991 bytes
 docs/reviews/phase14_s1/micrf103_p03_grid.json     | 1612 +++++
 docs/reviews/phase14_s1/micrf103_p03_grid_rows.png |  Bin 0 -> 276369 bytes
 docs/reviews/phase14_s1/phase12_per_item_diff.json | 1553 +++++
 gold/README.md                                     |  171 +
 gold/after_report.json                             | 6374 +++++++++++++++++
 gold/after_report.md                               |  198 +
 gold/after_tables.csv                              |   47 +
 gold/baseline_report.json                          | 7202 ++++++++++++++++++++
 gold/baseline_report.md                            |  600 ++
 gold/baseline_tables.csv                           |   47 +
 gold/comparison.md                                 |   93 +
 gold/generalization/PARAMS_FROZEN.json             |   52 +
 gold/generalization/gold_table_set.jsonl           |   29 +
 gold/generalization/independent_review.json        |  210 +
 gold/generalization/manifest.json                  |  116 +
 .../generalization/overlays/CY29FCT520-N01-P01.png |  Bin 0 -> 17677 bytes
 .../generalization/overlays/CY29FCT520-N02-P02.png |  Bin 0 -> 19146 bytes
 .../generalization/overlays/CY29FCT520-N03-P10.png |  Bin 0 -> 59001 bytes
 .../generalization/overlays/CY29FCT520-P04-T01.png |  Bin 0 -> 35410 bytes
 .../generalization/overlays/CY29FCT520-P04-T02.png |  Bin 0 -> 86693 bytes
 .../generalization/overlays/CY29FCT520-P05-T01.png |  Bin 0 -> 82751 bytes
 .../generalization/overlays/CY29FCT520-P06-T01.png |  Bin 0 -> 21657 bytes
 .../generalization/overlays/CY29FCT520-P08-T01.png |  Bin 0 -> 55019 bytes
 .../generalization/overlays/CY29FCT520-P10-T01.png |  Bin 0 -> 11383 bytes
 gold/generalization/overlays/DS10CP152-N01-P01.png |  Bin 0 -> 104563 bytes
 gold/generalization/overlays/DS10CP152-N02-P06.png |  Bin 0 -> 15879 bytes
 gold/generalization/overlays/DS10CP152-N03-P13.png |  Bin 0 -> 15215 bytes
 gold/generalization/overlays/DS10CP152-P02-T01.png |  Bin 0 -> 33620 bytes
 gold/generalization/overlays/DS10CP152-P03-T01.png |  Bin 0 -> 55674 bytes
 gold/generalization/overlays/DS10CP152-P03-T02.png |  Bin 0 -> 17925 bytes
 gold/generalization/overlays/DS10CP152-P04-T01.png |  Bin 0 -> 109848 bytes
 gold/generalization/overlays/DS10CP152-P05-T01.png |  Bin 0 -> 91057 bytes
 gold/generalization/overlays/DS10CP152-P07-T01.png |  Bin 0 -> 10941 bytes
 gold/generalization/overlays/DS10CP152-P07-T02.png |  Bin 0 -> 14844 bytes
 gold/generalization/overlays/DS10CP152-P11-T01.png |  Bin 0 -> 56106 bytes
 gold/generalization/overlays/DS10CP152-P13-T01.png |  Bin 0 -> 18576 bytes
 gold/generalization/overlays/DS10CP152-P13-T02.png |  Bin 0 -> 11287 bytes
 gold/generalization/overlays/DS10CP152-P14-T01.png |  Bin 0 -> 13326 bytes
 gold/generalization/overlays/DS10CP152-P15-T01.png |  Bin 0 -> 17873 bytes
 gold/generalization/overlays/MICRF103-N01-P01.png  |  Bin 0 -> 25229 bytes
 gold/generalization/overlays/MICRF103-N02-P04.png  |  Bin 0 -> 14134 bytes
 gold/generalization/overlays/MICRF103-P01-T01.png  |  Bin 0 -> 10338 bytes
 gold/generalization/overlays/MICRF103-P02-T01.png  |  Bin 0 -> 72283 bytes
 gold/generalization/overlays/MICRF103-P03-T01.png  |  Bin 0 -> 126194 bytes
 gold/generalization/review.html                    |   17 +
 .../review_crops/indep_CY29FCT520-N01-P01.png      |  Bin 0 -> 36959 bytes
 .../review_crops/indep_CY29FCT520-N02-P02.png      |  Bin 0 -> 34051 bytes
 .../review_crops/indep_CY29FCT520-N03-P10.png      |  Bin 0 -> 130615 bytes
 .../review_crops/indep_CY29FCT520-P04-T01.png      |  Bin 0 -> 68471 bytes
 .../review_crops/indep_CY29FCT520-P04-T02.png      |  Bin 0 -> 178662 bytes
 .../review_crops/indep_CY29FCT520-P05-T01.png      |  Bin 0 -> 173192 bytes
 .../review_crops/indep_CY29FCT520-P06-T01.png      |  Bin 0 -> 56488 bytes
 .../review_crops/indep_CY29FCT520-P08-T01.png      |  Bin 0 -> 111834 bytes
 .../review_crops/indep_CY29FCT520-P10-T01.png      |  Bin 0 -> 30705 bytes
 .../review_crops/indep_DS10CP152-N01-P01.png       |  Bin 0 -> 183482 bytes
 .../review_crops/indep_DS10CP152-N02-P06.png       |  Bin 0 -> 25880 bytes
 .../review_crops/indep_DS10CP152-N03-P13.png       |  Bin 0 -> 33605 bytes
 .../review_crops/indep_DS10CP152-P02-T01.png       |  Bin 0 -> 64617 bytes
 .../review_crops/indep_DS10CP152-P03-T01.png       |  Bin 0 -> 130228 bytes
 .../review_crops/indep_DS10CP152-P03-T02.png       |  Bin 0 -> 31898 bytes
 .../review_crops/indep_DS10CP152-P04-T01.png       |  Bin 0 -> 237445 bytes
 .../review_crops/indep_DS10CP152-P05-T01.png       |  Bin 0 -> 203237 bytes
 .../review_crops/indep_DS10CP152-P07-T01.png       |  Bin 0 -> 23476 bytes
 .../review_crops/indep_DS10CP152-P07-T02.png       |  Bin 0 -> 28251 bytes
 .../review_crops/indep_DS10CP152-P11-T01.png       |  Bin 0 -> 116560 bytes
 .../review_crops/indep_DS10CP152-P13-T01.png       |  Bin 0 -> 35019 bytes
 .../review_crops/indep_DS10CP152-P13-T02.png       |  Bin 0 -> 32703 bytes
 .../review_crops/indep_DS10CP152-P14-T01.png       |  Bin 0 -> 25216 bytes
 .../review_crops/indep_DS10CP152-P15-T01.png       |  Bin 0 -> 32887 bytes
 .../review_crops/indep_MICRF103-N01-P01.png        |  Bin 0 -> 51817 bytes
 .../review_crops/indep_MICRF103-N02-P04.png        |  Bin 0 -> 23324 bytes
 .../review_crops/indep_MICRF103-P01-T01.png        |  Bin 0 -> 19797 bytes
 .../review_crops/indep_MICRF103-P02-T01.png        |  Bin 0 -> 136824 bytes
 .../review_crops/indep_MICRF103-P03-T01.png        |  Bin 0 -> 247033 bytes
 gold/generalization/review_record.md               |  128 +
 gold/generalization/spec.yaml                      |  369 +
 .../versions/gen-2026-11-06.1/PARAMS_FROZEN.json   |   52 +
 .../versions/gen-2026-11-06.1/VERSION.json         |   13 +
 .../versions/gen-2026-11-06.1/gold_table_set.jsonl |   27 +
 .../versions/gen-2026-11-06.1/manifest.json        |   84 +
 .../versions/gen-2026-11-06.1/spec.yaml            |  259 +
 .../versions/gen-2026-11-06.2/PARAMS_FROZEN.json   |   52 +
 .../versions/gen-2026-11-06.2/VERSION.json         |   15 +
 .../versions/gen-2026-11-06.2/gold_table_set.jsonl |   29 +
 .../gen-2026-11-06.2/independent_review.json       |  210 +
 .../versions/gen-2026-11-06.2/manifest.json        |  116 +
 .../versions/gen-2026-11-06.2/review_record.md     |  128 +
 .../versions/gen-2026-11-06.2/spec.yaml            |  369 +
 gold/gold_table_set.jsonl                          |   65 +
 gold/independent_review.json                       |  399 ++
 gold/manifest.json                                 |   97 +
 gold/overlays/ADC12DJ5200-N01-P01-FEATURES.png     |  Bin 0 -> 105170 bytes
 gold/overlays/ADC12DJ5200-N02-P02-TOC.png          |  Bin 0 -> 97116 bytes
 gold/overlays/ADC12DJ5200-N03-P03-PINS.png         |  Bin 0 -> 141264 bytes
 gold/overlays/ADC12DJ5200-N04-P29-CHART.png        |  Bin 0 -> 157161 bytes
 gold/overlays/ADC12DJ5200-N05-P102-BITFIELD.png    |  Bin 0 -> 14338 bytes
 gold/overlays/ADC12DJ5200-N06-P180-NOTICE.png      |  Bin 0 -> 95549 bytes
 gold/overlays/ADC12DJ5200-N07-P102-BITFIELD.png    |  Bin 0 -> 13780 bytes
 gold/overlays/ADC12DJ5200-P01-T01.png              |  Bin 0 -> 10020 bytes
 gold/overlays/ADC12DJ5200-P100-T01.png             |  Bin 0 -> 207682 bytes
 gold/overlays/ADC12DJ5200-P102-T01.png             |  Bin 0 -> 45186 bytes
 gold/overlays/ADC12DJ5200-P102-T02.png             |  Bin 0 -> 21501 bytes
 gold/overlays/ADC12DJ5200-P102-T03.png             |  Bin 0 -> 16627 bytes
 gold/overlays/ADC12DJ5200-P39-T01.png              |  Bin 0 -> 82654 bytes
 gold/overlays/ADC12DJ5200-P41-T01.png              |  Bin 0 -> 29244 bytes
 gold/overlays/ADC12DJ5200-P43-T01.png              |  Bin 0 -> 16244 bytes
 gold/overlays/ADC12DJ5200-P46-T01.png              |  Bin 0 -> 27587 bytes
 gold/overlays/ADC12DJ5200-P47-T01.png              |  Bin 0 -> 16406 bytes
 gold/overlays/ADC12DJ5200-P54-T01.png              |  Bin 0 -> 16580 bytes
 gold/overlays/ADC12DJ5200-P61-T01.png              |  Bin 0 -> 59207 bytes
 gold/overlays/ADC12DJ5200-P61-T02.png              |  Bin 0 -> 75599 bytes
 gold/overlays/ADC12DJ5200-P72-T01.png              |  Bin 0 -> 79272 bytes
 gold/overlays/ADC12DJ5200-P78-T01.png              |  Bin 0 -> 48677 bytes
 gold/overlays/ADC12DJ5200-P78-T02.png              |  Bin 0 -> 36008 bytes
 gold/overlays/ADC12DJ5200-P78-T03.png              |  Bin 0 -> 49867 bytes
 gold/overlays/ADC12DJ5200-P78-T04.png              |  Bin 0 -> 22895 bytes
 gold/overlays/ADC12DJ5200-P79-T01.png              |  Bin 0 -> 19886 bytes
 gold/overlays/ADC12DJ5200-P98-T01.png              |  Bin 0 -> 189966 bytes
 gold/overlays/ADS1299-N01-P01-PROSE.png            |  Bin 0 -> 106582 bytes
 gold/overlays/ADS1299-N02-P02-TOC.png              |  Bin 0 -> 158148 bytes
 gold/overlays/ADS1299-N03-P16-PROSE.png            |  Bin 0 -> 132779 bytes
 gold/overlays/ADS1299-N04-P19-PINS.png             |  Bin 0 -> 117522 bytes
 gold/overlays/ADS1299-N05-P26-CHART.png            |  Bin 0 -> 164048 bytes
 gold/overlays/ADS1299-N06-P70-TIMING.png           |  Bin 0 -> 22248 bytes
 gold/overlays/ADS1299-N07-P84-NOTICE.png           |  Bin 0 -> 95208 bytes
 gold/overlays/ADS1299-P17-T01.png                  |  Bin 0 -> 34798 bytes
 gold/overlays/ADS1299-P17-T02.png                  |  Bin 0 -> 35261 bytes
 gold/overlays/ADS1299-P17-T03.png                  |  Bin 0 -> 30730 bytes
 gold/overlays/ADS1299-P23-T01.png                  |  Bin 0 -> 13074 bytes
 gold/overlays/ADS1299-P27-T01.png                  |  Bin 0 -> 19190 bytes
 gold/overlays/ADS1299-P35-T01.png                  |  Bin 0 -> 17750 bytes
 gold/overlays/ADS1299-P37-T01.png                  |  Bin 0 -> 16938 bytes
 gold/overlays/ADS1299-P40-T01.png                  |  Bin 0 -> 58044 bytes
 gold/overlays/ADS1299-P44-T01.png                  |  Bin 0 -> 93576 bytes
 gold/overlays/ADS1299-P45-T01.png                  |  Bin 0 -> 38515 bytes
 gold/overlays/ADS1299-P52-T01.png                  |  Bin 0 -> 75606 bytes
 gold/overlays/ADS1299-P67-T01.png                  |  Bin 0 -> 16599 bytes
 gold/overlays/ADS1299-P70-T01.png                  |  Bin 0 -> 12567 bytes
 gold/overlays/ADS1299-P74-T01.png                  |  Bin 0 -> 21607 bytes
 gold/overlays/ADS1299-P76-T01.png                  |  Bin 0 -> 147132 bytes
 gold/overlays/LM358-N01-P01-PROSE.png              |  Bin 0 -> 112555 bytes
 gold/overlays/LM358-N02-P02-TOC.png                |  Bin 0 -> 104864 bytes
 gold/overlays/LM358-N03-P03-PINS.png               |  Bin 0 -> 44016 bytes
 gold/overlays/LM358-N04-P15-CHART.png              |  Bin 0 -> 36775 bytes
 gold/overlays/LM358-N05-P31-REVHIST.png            |  Bin 0 -> 251527 bytes
 gold/overlays/LM358-P04-T01.png                    |  Bin 0 -> 74516 bytes
 gold/overlays/LM358-P04-T02.png                    |  Bin 0 -> 33716 bytes
 gold/overlays/LM358-P05-T01.png                    |  Bin 0 -> 37987 bytes
 gold/overlays/LM358-P05-T02.png                    |  Bin 0 -> 52381 bytes
 gold/overlays/LM358-P06-T01.png                    |  Bin 0 -> 118973 bytes
 gold/overlays/LM358-P08-T01.png                    |  Bin 0 -> 120439 bytes
 gold/overlays/LM358-P10-T01.png                    |  Bin 0 -> 106668 bytes
 gold/overlays/LM358-P11-T01.png                    |  Bin 0 -> 107410 bytes
 gold/overlays/LM358-P12-T01.png                    |  Bin 0 -> 100852 bytes
 gold/overlays/LM358-P14-T01.png                    |  Bin 0 -> 107783 bytes
 gold/overlays/LM358-P33-T01.png                    |  Bin 0 -> 160522 bytes
 gold/review.html                                   |   17 +
 gold/review_crops/ADC-N01-P01-FEATURES.png         |  Bin 0 -> 283519 bytes
 gold/review_crops/ADC-N02-P02-TOC.png              |  Bin 0 -> 109845 bytes
 gold/review_crops/ADC-P100-T01.png                 |  Bin 0 -> 246964 bytes
 gold/review_crops/ADC-P102-T01.png                 |  Bin 0 -> 48730 bytes
 gold/review_crops/ADC-P43-T01.png                  |  Bin 0 -> 13657 bytes
 gold/review_crops/ADC-P47-T01.png                  |  Bin 0 -> 14690 bytes
 gold/review_crops/ADC-P61-T02.png                  |  Bin 0 -> 84019 bytes
 gold/review_crops/ADC-P78-T02.png                  |  Bin 0 -> 32745 bytes
 gold/review_crops/ADC-P78-T03.png                  |  Bin 0 -> 47590 bytes
 gold/review_crops/ADC-P78-T04.png                  |  Bin 0 -> 17719 bytes
 gold/review_crops/ADC-P79-T01.png                  |  Bin 0 -> 14281 bytes
 gold/review_crops/ADC-P98-T01.png                  |  Bin 0 -> 221353 bytes
 gold/review_crops/ADS-P17-T01.png                  |  Bin 0 -> 31908 bytes
 gold/review_crops/ADS-P23-T01.png                  |  Bin 0 -> 9943 bytes
 gold/review_crops/ADS-P44-T01.png                  |  Bin 0 -> 99657 bytes
 gold/review_crops/ADS-P70-T01.png                  |  Bin 0 -> 8171 bytes
 gold/review_crops/ADS-P74-T01.png                  |  Bin 0 -> 21406 bytes
 gold/review_crops/ADS-P76-T01.png                  |  Bin 0 -> 168452 bytes
 gold/review_crops/LM-N02-P02-TOC.png               |  Bin 0 -> 120454 bytes
 gold/review_crops/LM-P04-T01.png                   |  Bin 0 -> 79962 bytes
 gold/review_crops/LM-P06-T01.png                   |  Bin 0 -> 134370 bytes
 gold/review_crops/LM-P08-T01.png                   |  Bin 0 -> 136473 bytes
 gold/review_crops/LM-P10-T01.png                   |  Bin 0 -> 118962 bytes
 gold/review_crops/LM-P11-T01.png                   |  Bin 0 -> 119484 bytes
 gold/review_crops/LM-P33-T01.png                   |  Bin 0 -> 171896 bytes
 .../indep_ADC12DJ5200-N01-P01-FEATURES.png         |  Bin 0 -> 157320 bytes
 .../review_crops/indep_ADC12DJ5200-N02-P02-TOC.png |  Bin 0 -> 127464 bytes
 .../indep_ADC12DJ5200-N03-P03-PINS.png             |  Bin 0 -> 188164 bytes
 .../indep_ADC12DJ5200-N04-P29-CHART.png            |  Bin 0 -> 234208 bytes
 .../indep_ADC12DJ5200-N05-P102-BITFIELD.png        |  Bin 0 -> 14811 bytes
 .../indep_ADC12DJ5200-N06-P180-NOTICE.png          |  Bin 0 -> 130377 bytes
 .../indep_ADC12DJ5200-N07-P102-BITFIELD.png        |  Bin 0 -> 13852 bytes
 gold/review_crops/indep_ADC12DJ5200-P01-T01.png    |  Bin 0 -> 10932 bytes
 gold/review_crops/indep_ADC12DJ5200-P46-T01.png    |  Bin 0 -> 34772 bytes
 gold/review_crops/indep_ADS1299-N01-P01-PROSE.png  |  Bin 0 -> 156621 bytes
 gold/review_crops/indep_ADS1299-N02-P02-TOC.png    |  Bin 0 -> 212656 bytes
 gold/review_crops/indep_ADS1299-N03-P16-PROSE.png  |  Bin 0 -> 172753 bytes
 gold/review_crops/indep_ADS1299-N04-P19-PINS.png   |  Bin 0 -> 157280 bytes
 gold/review_crops/indep_ADS1299-N05-P26-CHART.png  |  Bin 0 -> 221101 bytes
 gold/review_crops/indep_ADS1299-N06-P70-TIMING.png |  Bin 0 -> 25754 bytes
 gold/review_crops/indep_ADS1299-N07-P84-NOTICE.png |  Bin 0 -> 130377 bytes
 gold/review_crops/indep_ADS1299-P37-T01.png        |  Bin 0 -> 21724 bytes
 gold/review_crops/indep_ADS1299-P70-T01.png        |  Bin 0 -> 14714 bytes
 gold/review_crops/indep_LM358-N01-P01-PROSE.png    |  Bin 0 -> 152552 bytes
 gold/review_crops/indep_LM358-N02-P02-TOC.png      |  Bin 0 -> 136068 bytes
 gold/review_crops/indep_LM358-N03-P03-PINS.png     |  Bin 0 -> 54459 bytes
 gold/review_crops/indep_LM358-N04-P15-CHART.png    |  Bin 0 -> 45847 bytes
 gold/review_crops/indep_LM358-N05-P31-REVHIST.png  |  Bin 0 -> 337526 bytes
 gold/review_crops/indep_LM358-P04-T02.png          |  Bin 0 -> 46159 bytes
 gold/review_record.md                              |  192 +
 gold/spec.yaml                                     |  500 ++
 gold/versions/gold-2026-11-06.1/VERSION.json       |   11 +
 .../gold-2026-11-06.1/gold_table_set.jsonl         |   65 +
 gold/versions/gold-2026-11-06.1/manifest.json      |   97 +
 gold/versions/gold-2026-11-06.1/spec.yaml          |  500 ++
 pyproject.toml                                     |    1 +
 src/icpdf/classification/.gitattributes            |    2 +
 src/icpdf/classification/__init__.py               |   72 +
 src/icpdf/classification/classifier.py             | 1084 +++
 src/icpdf/classification/cli.py                    |  283 +
 src/icpdf/classification/evidence.py               |  192 +
 src/icpdf/classification/models.py                 |  549 ++
 src/icpdf/classification/report.py                 |  916 +++
 src/icpdf/classification/rules.py                  |  569 ++
 src/icpdf/cli.py                                   |    5 +-
 src/icpdf/domain/__init__.py                       |    2 +
 src/icpdf/domain/candidate.py                      |    5 +
 src/icpdf/domain/table.py                          |   86 +
 src/icpdf/domain/visual.py                         |   58 +
 src/icpdf/eval/__init__.py                         |    1 +
 src/icpdf/eval/jsonio.py                           |  114 +
 src/icpdf/eval/manifests.py                        |  327 +
 src/icpdf/parser/candidate_registry.py             |   40 +-
 src/icpdf/parser/config.py                         |  249 +
 src/icpdf/parser/coords.py                         |   28 +
 src/icpdf/parser/header_semantics.py               |  654 ++
 src/icpdf/parser/header_sides.py                   |  489 ++
 src/icpdf/parser/layout.py                         |   97 +
 src/icpdf/parser/logical_assembly.py               | 1604 +++++
 src/icpdf/parser/logical_attribution.py            |  201 +
 src/icpdf/parser/logical_boundary.py               |  954 +++
 src/icpdf/parser/logical_candidates.py             |  131 +
 src/icpdf/parser/logical_canopy.py                 |  286 +
 src/icpdf/parser/logical_decision.py               |  895 +++
 src/icpdf/parser/logical_evidence.py               | 1371 ++++
 src/icpdf/parser/logical_identity.py               |  419 ++
 src/icpdf/parser/logical_projection.py             |  399 ++
 src/icpdf/parser/pipeline.py                       |  107 +-
 src/icpdf/parser/pipeline_sandbox.py               |  302 +
 src/icpdf/parser/rule_primitives.py                |  279 +
 src/icpdf/parser/structure.py                      |  696 ++
 src/icpdf/parser/table_detector.py                 |  424 +-
 src/icpdf/parser/table_rebuilder.py                |   34 +-
 src/icpdf/parser/table_regions.py                  |  314 +
 src/icpdf/parser/text_blocks.py                    |    3 +-
 src/icpdf/parser/visual_structure.py               |  199 +
 src/icpdf/storage/artifact_store.py                |   63 +-
 src/icpdf/storage/run_store.py                     |   14 +-
 tests/fixtures/a3_e1.py                            |  225 +
 tests/fixtures/synthetic.py                        |   77 +
 tests/integration/test_a2_table_decision.py        | 1019 +++
 tests/integration/test_a3_e1_chain.py              |  304 +
 .../integration/test_a3_w1_d4_manifest_failure.py  |   98 +
 tests/integration/test_a3_w1_pipeline_wiring.py    |  323 +
 tests/integration/test_assembly_chain.py           |  176 +
 tests/integration/test_coordinate_chain.py         |   93 +
 .../test_header_candidate_production.py            |  256 +
 tests/integration/test_phase14_primitive_audit.py  |  436 ++
 tests/integration/test_phase14_s1.py               |  114 +
 tests/integration/test_phase14_s2.py               |  202 +
 tests/integration/test_s2b_chain.py                |  360 +
 tests/integration/test_s2b_identity.py             |  431 ++
 tests/integration/test_s2b_sandbox.py              |  620 ++
 tests/unit/test_a2_decision_dto.py                 |  255 +
 tests/unit/test_a3_e1_evidence.py                  |  517 ++
 tests/unit/test_a3_w1_c0b_failure_boundary.py      |   63 +
 tests/unit/test_a3_w1_c1_write_bytes.py            |  184 +
 tests/unit/test_a3_w1_d4_fsync.py                  |  102 +
 tests/unit/test_assembly.py                        | 1313 ++++
 tests/unit/test_eval_jsonio.py                     |   81 +
 tests/unit/test_eval_manifests.py                  |  309 +
 tests/unit/test_evidence_validation.py             |  488 ++
 tests/unit/test_header_sides.py                    |  680 ++
 tests/unit/test_label_grid.py                      |   84 +
 tests/unit/test_logical_candidates.py              |  210 +
 tests/unit/test_rule_primitives.py                 |  108 +
 tests/unit/test_s2b_attribution.py                 |  372 +
 tests/unit/test_s2b_boundary.py                    |  833 +++
 tests/unit/test_s2b_canopy_evidence.py             |  828 +++
 tests/unit/test_s2b_d4_word_extent.py              |   82 +
 tests/unit/test_s2b_d5_word_capture.py             |  145 +
 tests/unit/test_s2b_d6_row_lattice.py              |  127 +
 tests/unit/test_s2b_decision.py                    |  815 +++
 tests/unit/test_s2b_header_canopy.py               |  525 ++
 tests/unit/test_s2b_identity_registry.py           |  201 +
 tests/unit/test_s2b_projection.py                  |  922 +++
 tests/unit/test_s2b_row_projection.py              |  347 +
 tests/unit/test_s2b_word_row_invariants.py         |  232 +
 tests/unit/test_table_params_snapshot.py           |  176 +
 tests/unit/test_table_regions.py                   |  172 +
 tests/unit/test_visual_structure.py                |  254 +
 tools/a3_e1_parity_report.py                       |  436 ++
 tools/audit_visual_primitives.py                   |  662 ++
 tools/export_review_evidence.py                    |  188 +
 tools/goldset/__init__.py                          |    1 +
 tools/goldset/annotate.py                          |  500 ++
 tools/goldset/compare.py                           |  174 +
 tools/goldset/evaluate.py                          | 1098 +++
 tools/goldset/freeze_version.py                    |   96 +
 tools/goldset/inspect_components.py                |   34 +
 tools/goldset/render_review_crops.py               |   65 +
 tools/goldset/rules.py                             |  391 ++
 tools/head_parity_compare.py                       |  236 +
 tools/head_parity_probe.py                         |  116 +
 tools/phase11_audit.py                             |  235 +
 tools/render_detection_crops.py                    |   69 +
 tools/render_region_evidence.py                    |  155 +
 tools/validate_evidence.py                         |  639 ++
 tools/validate_manifests.py                        |   77 +
 .../CLASSIFIER_REVISION_PLAN.md                    |  343 +
 .../_classifier_revision/R1_PRIME_SUPPLEMENT.md    |  497 ++
 workbench/_classifier_revision/README.md           |   59 +
 workbench/_classifier_revision/SHA256SUMS.txt      |    3 +
 475 files changed, 90610 insertions(+), 229 deletions(-)
[EXIT=0]

### [8] 领先提交的逐文件状态
$ git diff --name-status origin/main..main
M	HANDOFF.md
M	configs/parser.yaml
A	docs/GOLD_SPEC.md
A	docs/PHASE1_1_DIAGNOSIS.md
A	docs/PHASE1_2_ARCHITECTURE.md
A	docs/PHASE1_3_EVIDENCE.md
A	docs/PHASE1_3_GENERALIZATION.md
A	docs/PHASE1_4_S1.md
A	docs/PHASE1_4_S2.md
A	docs/PHASE1_4_S2A.md
A	docs/PHASE1_4_S2B_A2_EVIDENCE.md
A	docs/PHASE1_4_S2B_A3_E1_EVIDENCE.md
A	docs/PHASE1_4_S2B_A3_E1_HEAD_PARITY.md
A	docs/PHASE1_4_S2B_A3_E1_R2_PARITY.md
A	docs/PHASE1_4_S2B_A3_W1_DESIGN.md
A	docs/PHASE1_4_S2B_A3_W1_EVIDENCE.md
A	docs/PHASE1_4_S2B_DESIGN.md
A	docs/PHASE1_4_S2B_DESIGN_r21.md
A	docs/PHASE1_4_S2B_DESIGN_r22.md
A	docs/PHASE1_4_STRUCTURE_MODEL.md
A	docs/S2A_FREEZE.md
A	docs/SLICE6_INTEGRATION_PLAN.md
A	docs/evidence/phase14_s1/ds10cp152_p13_detected.png
A	docs/evidence/phase14_s1/micrf103_p03_detected.png
A	docs/phase1_1/ADC12DJ5200/audit_candidates.csv
A	docs/phase1_1/ADC12DJ5200/contact_sheet.png
A	docs/phase1_1/ADC12DJ5200/page_stats.csv
A	docs/phase1_1/ADC12DJ5200/pages/page-0001-annotated.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0001.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0002-annotated.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0002.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0004-annotated.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0004.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0016-annotated.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0016.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0029-annotated.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0029.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0030-annotated.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0030.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0059-annotated.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0059.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0065-annotated.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0065.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0066-annotated.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0066.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0074-annotated.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0074.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0075-annotated.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0075.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0081-annotated.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0081.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0085-annotated.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0085.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0100-annotated.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0100.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0111-annotated.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0111.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0113-annotated.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0113.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0120-annotated.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0120.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0131-annotated.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0131.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0143-annotated.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0143.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0155-annotated.png
A	docs/phase1_1/ADC12DJ5200/pages/page-0155.png
A	docs/phase1_1/ADC12DJ5200/table_stats.csv
A	docs/phase1_1/ADS1299/audit_candidates.csv
A	docs/phase1_1/ADS1299/contact_sheet.png
A	docs/phase1_1/ADS1299/page_stats.csv
A	docs/phase1_1/ADS1299/pages/page-0001-annotated.png
A	docs/phase1_1/ADS1299/pages/page-0001.png
A	docs/phase1_1/ADS1299/pages/page-0006-annotated.png
A	docs/phase1_1/ADS1299/pages/page-0006.png
A	docs/phase1_1/ADS1299/pages/page-0010-annotated.png
A	docs/phase1_1/ADS1299/pages/page-0010.png
A	docs/phase1_1/ADS1299/pages/page-0013-annotated.png
A	docs/phase1_1/ADS1299/pages/page-0013.png
A	docs/phase1_1/ADS1299/pages/page-0016-annotated.png
A	docs/phase1_1/ADS1299/pages/page-0016.png
A	docs/phase1_1/ADS1299/pages/page-0017-annotated.png
A	docs/phase1_1/ADS1299/pages/page-0017.png
A	docs/phase1_1/ADS1299/pages/page-0026-annotated.png
A	docs/phase1_1/ADS1299/pages/page-0026.png
A	docs/phase1_1/ADS1299/pages/page-0040-annotated.png
A	docs/phase1_1/ADS1299/pages/page-0040.png
A	docs/phase1_1/ADS1299/pages/page-0044-annotated.png
A	docs/phase1_1/ADS1299/pages/page-0044.png
A	docs/phase1_1/ADS1299/pages/page-0046-annotated.png
A	docs/phase1_1/ADS1299/pages/page-0046.png
A	docs/phase1_1/ADS1299/pages/page-0048-annotated.png
A	docs/phase1_1/ADS1299/pages/page-0048.png
A	docs/phase1_1/ADS1299/pages/page-0053-annotated.png
A	docs/phase1_1/ADS1299/pages/page-0053.png
A	docs/phase1_1/ADS1299/pages/page-0056-annotated.png
A	docs/phase1_1/ADS1299/pages/page-0056.png
A	docs/phase1_1/ADS1299/pages/page-0066-annotated.png
A	docs/phase1_1/ADS1299/pages/page-0066.png
A	docs/phase1_1/ADS1299/pages/page-0074-annotated.png
A	docs/phase1_1/ADS1299/pages/page-0074.png
A	docs/phase1_1/ADS1299/table_stats.csv
A	docs/phase1_1/LM358/audit_candidates.csv
A	docs/phase1_1/LM358/contact_sheet.png
A	docs/phase1_1/LM358/page_stats.csv
A	docs/phase1_1/LM358/pages/page-0001-annotated.png
A	docs/phase1_1/LM358/pages/page-0001.png
A	docs/phase1_1/LM358/pages/page-0005-annotated.png
A	docs/phase1_1/LM358/pages/page-0005.png
A	docs/phase1_1/LM358/pages/page-0006-annotated.png
A	docs/phase1_1/LM358/pages/page-0006.png
A	docs/phase1_1/LM358/pages/page-0011-annotated.png
A	docs/phase1_1/LM358/pages/page-0011.png
A	docs/phase1_1/LM358/pages/page-0014-annotated.png
A	docs/phase1_1/LM358/pages/page-0014.png
A	docs/phase1_1/LM358/pages/page-0015-annotated.png
A	docs/phase1_1/LM358/pages/page-0015.png
A	docs/phase1_1/LM358/pages/page-0017-annotated.png
A	docs/phase1_1/LM358/pages/page-0017.png
A	docs/phase1_1/LM358/pages/page-0020-annotated.png
A	docs/phase1_1/LM358/pages/page-0020.png
A	docs/phase1_1/LM358/pages/page-0022-annotated.png
A	docs/phase1_1/LM358/pages/page-0022.png
A	docs/phase1_1/LM358/pages/page-0031-annotated.png
A	docs/phase1_1/LM358/pages/page-0031.png
A	docs/phase1_1/LM358/pages/page-0032-annotated.png
A	docs/phase1_1/LM358/pages/page-0032.png
A	docs/phase1_1/LM358/pages/page-0033-annotated.png
A	docs/phase1_1/LM358/pages/page-0033.png
A	docs/phase1_1/LM358/pages/page-0035-annotated.png
A	docs/phase1_1/LM358/pages/page-0035.png
A	docs/phase1_1/LM358/pages/page-0036-annotated.png
A	docs/phase1_1/LM358/pages/page-0036.png
A	docs/phase1_1/LM358/pages/page-0037-annotated.png
A	docs/phase1_1/LM358/pages/page-0037.png
A	docs/phase1_1/LM358/pages/page-0038-annotated.png
A	docs/phase1_1/LM358/pages/page-0038.png
A	docs/phase1_1/LM358/pages/page-0043-annotated.png
A	docs/phase1_1/LM358/pages/page-0043.png
A	docs/phase1_1/LM358/pages/page-0044-annotated.png
A	docs/phase1_1/LM358/pages/page-0044.png
A	docs/phase1_1/LM358/pages/page-0047-annotated.png
A	docs/phase1_1/LM358/pages/page-0047.png
A	docs/phase1_1/LM358/table_stats.csv
A	docs/reviews/phase14_s1/003311f_s1.patch
A	docs/reviews/phase14_s1/3fc4519_followup.patch
A	docs/reviews/phase14_s1/GIT_STATUS.txt
A	docs/reviews/phase14_s1/REVIEW_RESPONSE.md
A	docs/reviews/phase14_s1/ds10cp152_p13_components.json
A	docs/reviews/phase14_s1/ds10cp152_p13_components_vs_region.png
A	docs/reviews/phase14_s1/ds10cp152_p13_grid.json
A	docs/reviews/phase14_s1/ds10cp152_p13_grid_cells.png
A	docs/reviews/phase14_s1/gold_v2_per_item_diff.json
A	docs/reviews/phase14_s1/micrf103_p03_components.json
A	docs/reviews/phase14_s1/micrf103_p03_components_vs_region.png
A	docs/reviews/phase14_s1/micrf103_p03_grid.json
A	docs/reviews/phase14_s1/micrf103_p03_grid_rows.png
A	docs/reviews/phase14_s1/phase12_per_item_diff.json
A	gold/README.md
A	gold/after_report.json
A	gold/after_report.md
A	gold/after_tables.csv
A	gold/baseline_report.json
A	gold/baseline_report.md
A	gold/baseline_tables.csv
A	gold/comparison.md
A	gold/generalization/PARAMS_FROZEN.json
A	gold/generalization/gold_table_set.jsonl
A	gold/generalization/independent_review.json
A	gold/generalization/manifest.json
A	gold/generalization/overlays/CY29FCT520-N01-P01.png
A	gold/generalization/overlays/CY29FCT520-N02-P02.png
A	gold/generalization/overlays/CY29FCT520-N03-P10.png
A	gold/generalization/overlays/CY29FCT520-P04-T01.png
A	gold/generalization/overlays/CY29FCT520-P04-T02.png
A	gold/generalization/overlays/CY29FCT520-P05-T01.png
A	gold/generalization/overlays/CY29FCT520-P06-T01.png
A	gold/generalization/overlays/CY29FCT520-P08-T01.png
A	gold/generalization/overlays/CY29FCT520-P10-T01.png
A	gold/generalization/overlays/DS10CP152-N01-P01.png
A	gold/generalization/overlays/DS10CP152-N02-P06.png
A	gold/generalization/overlays/DS10CP152-N03-P13.png
A	gold/generalization/overlays/DS10CP152-P02-T01.png
A	gold/generalization/overlays/DS10CP152-P03-T01.png
A	gold/generalization/overlays/DS10CP152-P03-T02.png
A	gold/generalization/overlays/DS10CP152-P04-T01.png
A	gold/generalization/overlays/DS10CP152-P05-T01.png
A	gold/generalization/overlays/DS10CP152-P07-T01.png
A	gold/generalization/overlays/DS10CP152-P07-T02.png
A	gold/generalization/overlays/DS10CP152-P11-T01.png
A	gold/generalization/overlays/DS10CP152-P13-T01.png
A	gold/generalization/overlays/DS10CP152-P13-T02.png
A	gold/generalization/overlays/DS10CP152-P14-T01.png
A	gold/generalization/overlays/DS10CP152-P15-T01.png
A	gold/generalization/overlays/MICRF103-N01-P01.png
A	gold/generalization/overlays/MICRF103-N02-P04.png
A	gold/generalization/overlays/MICRF103-P01-T01.png
A	gold/generalization/overlays/MICRF103-P02-T01.png
A	gold/generalization/overlays/MICRF103-P03-T01.png
A	gold/generalization/review.html
A	gold/generalization/review_crops/indep_CY29FCT520-N01-P01.png
A	gold/generalization/review_crops/indep_CY29FCT520-N02-P02.png
A	gold/generalization/review_crops/indep_CY29FCT520-N03-P10.png
A	gold/generalization/review_crops/indep_CY29FCT520-P04-T01.png
A	gold/generalization/review_crops/indep_CY29FCT520-P04-T02.png
A	gold/generalization/review_crops/indep_CY29FCT520-P05-T01.png
A	gold/generalization/review_crops/indep_CY29FCT520-P06-T01.png
A	gold/generalization/review_crops/indep_CY29FCT520-P08-T01.png
A	gold/generalization/review_crops/indep_CY29FCT520-P10-T01.png
A	gold/generalization/review_crops/indep_DS10CP152-N01-P01.png
A	gold/generalization/review_crops/indep_DS10CP152-N02-P06.png
A	gold/generalization/review_crops/indep_DS10CP152-N03-P13.png
A	gold/generalization/review_crops/indep_DS10CP152-P02-T01.png
A	gold/generalization/review_crops/indep_DS10CP152-P03-T01.png
A	gold/generalization/review_crops/indep_DS10CP152-P03-T02.png
A	gold/generalization/review_crops/indep_DS10CP152-P04-T01.png
A	gold/generalization/review_crops/indep_DS10CP152-P05-T01.png
A	gold/generalization/review_crops/indep_DS10CP152-P07-T01.png
A	gold/generalization/review_crops/indep_DS10CP152-P07-T02.png
A	gold/generalization/review_crops/indep_DS10CP152-P11-T01.png
A	gold/generalization/review_crops/indep_DS10CP152-P13-T01.png
A	gold/generalization/review_crops/indep_DS10CP152-P13-T02.png
A	gold/generalization/review_crops/indep_DS10CP152-P14-T01.png
A	gold/generalization/review_crops/indep_DS10CP152-P15-T01.png
A	gold/generalization/review_crops/indep_MICRF103-N01-P01.png
A	gold/generalization/review_crops/indep_MICRF103-N02-P04.png
A	gold/generalization/review_crops/indep_MICRF103-P01-T01.png
A	gold/generalization/review_crops/indep_MICRF103-P02-T01.png
A	gold/generalization/review_crops/indep_MICRF103-P03-T01.png
A	gold/generalization/review_record.md
A	gold/generalization/spec.yaml
A	gold/generalization/versions/gen-2026-11-06.1/PARAMS_FROZEN.json
A	gold/generalization/versions/gen-2026-11-06.1/VERSION.json
A	gold/generalization/versions/gen-2026-11-06.1/gold_table_set.jsonl
A	gold/generalization/versions/gen-2026-11-06.1/manifest.json
A	gold/generalization/versions/gen-2026-11-06.1/spec.yaml
A	gold/generalization/versions/gen-2026-11-06.2/PARAMS_FROZEN.json
A	gold/generalization/versions/gen-2026-11-06.2/VERSION.json
A	gold/generalization/versions/gen-2026-11-06.2/gold_table_set.jsonl
A	gold/generalization/versions/gen-2026-11-06.2/independent_review.json
A	gold/generalization/versions/gen-2026-11-06.2/manifest.json
A	gold/generalization/versions/gen-2026-11-06.2/review_record.md
A	gold/generalization/versions/gen-2026-11-06.2/spec.yaml
A	gold/gold_table_set.jsonl
A	gold/independent_review.json
A	gold/manifest.json
A	gold/overlays/ADC12DJ5200-N01-P01-FEATURES.png
A	gold/overlays/ADC12DJ5200-N02-P02-TOC.png
A	gold/overlays/ADC12DJ5200-N03-P03-PINS.png
A	gold/overlays/ADC12DJ5200-N04-P29-CHART.png
A	gold/overlays/ADC12DJ5200-N05-P102-BITFIELD.png
A	gold/overlays/ADC12DJ5200-N06-P180-NOTICE.png
A	gold/overlays/ADC12DJ5200-N07-P102-BITFIELD.png
A	gold/overlays/ADC12DJ5200-P01-T01.png
A	gold/overlays/ADC12DJ5200-P100-T01.png
A	gold/overlays/ADC12DJ5200-P102-T01.png
A	gold/overlays/ADC12DJ5200-P102-T02.png
A	gold/overlays/ADC12DJ5200-P102-T03.png
A	gold/overlays/ADC12DJ5200-P39-T01.png
A	gold/overlays/ADC12DJ5200-P41-T01.png
A	gold/overlays/ADC12DJ5200-P43-T01.png
A	gold/overlays/ADC12DJ5200-P46-T01.png
A	gold/overlays/ADC12DJ5200-P47-T01.png
A	gold/overlays/ADC12DJ5200-P54-T01.png
A	gold/overlays/ADC12DJ5200-P61-T01.png
A	gold/overlays/ADC12DJ5200-P61-T02.png
A	gold/overlays/ADC12DJ5200-P72-T01.png
A	gold/overlays/ADC12DJ5200-P78-T01.png
A	gold/overlays/ADC12DJ5200-P78-T02.png
A	gold/overlays/ADC12DJ5200-P78-T03.png
A	gold/overlays/ADC12DJ5200-P78-T04.png
A	gold/overlays/ADC12DJ5200-P79-T01.png
A	gold/overlays/ADC12DJ5200-P98-T01.png
A	gold/overlays/ADS1299-N01-P01-PROSE.png
A	gold/overlays/ADS1299-N02-P02-TOC.png
A	gold/overlays/ADS1299-N03-P16-PROSE.png
A	gold/overlays/ADS1299-N04-P19-PINS.png
A	gold/overlays/ADS1299-N05-P26-CHART.png
A	gold/overlays/ADS1299-N06-P70-TIMING.png
A	gold/overlays/ADS1299-N07-P84-NOTICE.png
A	gold/overlays/ADS1299-P17-T01.png
A	gold/overlays/ADS1299-P17-T02.png
A	gold/overlays/ADS1299-P17-T03.png
A	gold/overlays/ADS1299-P23-T01.png
A	gold/overlays/ADS1299-P27-T01.png
A	gold/overlays/ADS1299-P35-T01.png
A	gold/overlays/ADS1299-P37-T01.png
A	gold/overlays/ADS1299-P40-T01.png
A	gold/overlays/ADS1299-P44-T01.png
A	gold/overlays/ADS1299-P45-T01.png
A	gold/overlays/ADS1299-P52-T01.png
A	gold/overlays/ADS1299-P67-T01.png
A	gold/overlays/ADS1299-P70-T01.png
A	gold/overlays/ADS1299-P74-T01.png
A	gold/overlays/ADS1299-P76-T01.png
A	gold/overlays/LM358-N01-P01-PROSE.png
A	gold/overlays/LM358-N02-P02-TOC.png
A	gold/overlays/LM358-N03-P03-PINS.png
A	gold/overlays/LM358-N04-P15-CHART.png
A	gold/overlays/LM358-N05-P31-REVHIST.png
A	gold/overlays/LM358-P04-T01.png
A	gold/overlays/LM358-P04-T02.png
A	gold/overlays/LM358-P05-T01.png
A	gold/overlays/LM358-P05-T02.png
A	gold/overlays/LM358-P06-T01.png
A	gold/overlays/LM358-P08-T01.png
A	gold/overlays/LM358-P10-T01.png
A	gold/overlays/LM358-P11-T01.png
A	gold/overlays/LM358-P12-T01.png
A	gold/overlays/LM358-P14-T01.png
A	gold/overlays/LM358-P33-T01.png
A	gold/review.html
A	gold/review_crops/ADC-N01-P01-FEATURES.png
A	gold/review_crops/ADC-N02-P02-TOC.png
A	gold/review_crops/ADC-P100-T01.png
A	gold/review_crops/ADC-P102-T01.png
A	gold/review_crops/ADC-P43-T01.png
A	gold/review_crops/ADC-P47-T01.png
A	gold/review_crops/ADC-P61-T02.png
A	gold/review_crops/ADC-P78-T02.png
A	gold/review_crops/ADC-P78-T03.png
A	gold/review_crops/ADC-P78-T04.png
A	gold/review_crops/ADC-P79-T01.png
A	gold/review_crops/ADC-P98-T01.png
A	gold/review_crops/ADS-P17-T01.png
A	gold/review_crops/ADS-P23-T01.png
A	gold/review_crops/ADS-P44-T01.png
A	gold/review_crops/ADS-P70-T01.png
A	gold/review_crops/ADS-P74-T01.png
A	gold/review_crops/ADS-P76-T01.png
A	gold/review_crops/LM-N02-P02-TOC.png
A	gold/review_crops/LM-P04-T01.png
A	gold/review_crops/LM-P06-T01.png
A	gold/review_crops/LM-P08-T01.png
A	gold/review_crops/LM-P10-T01.png
A	gold/review_crops/LM-P11-T01.png
A	gold/review_crops/LM-P33-T01.png
A	gold/review_crops/indep_ADC12DJ5200-N01-P01-FEATURES.png
A	gold/review_crops/indep_ADC12DJ5200-N02-P02-TOC.png
A	gold/review_crops/indep_ADC12DJ5200-N03-P03-PINS.png
A	gold/review_crops/indep_ADC12DJ5200-N04-P29-CHART.png
A	gold/review_crops/indep_ADC12DJ5200-N05-P102-BITFIELD.png
A	gold/review_crops/indep_ADC12DJ5200-N06-P180-NOTICE.png
A	gold/review_crops/indep_ADC12DJ5200-N07-P102-BITFIELD.png
A	gold/review_crops/indep_ADC12DJ5200-P01-T01.png
A	gold/review_crops/indep_ADC12DJ5200-P46-T01.png
A	gold/review_crops/indep_ADS1299-N01-P01-PROSE.png
A	gold/review_crops/indep_ADS1299-N02-P02-TOC.png
A	gold/review_crops/indep_ADS1299-N03-P16-PROSE.png
A	gold/review_crops/indep_ADS1299-N04-P19-PINS.png
A	gold/review_crops/indep_ADS1299-N05-P26-CHART.png
A	gold/review_crops/indep_ADS1299-N06-P70-TIMING.png
A	gold/review_crops/indep_ADS1299-N07-P84-NOTICE.png
A	gold/review_crops/indep_ADS1299-P37-T01.png
A	gold/review_crops/indep_ADS1299-P70-T01.png
A	gold/review_crops/indep_LM358-N01-P01-PROSE.png
A	gold/review_crops/indep_LM358-N02-P02-TOC.png
A	gold/review_crops/indep_LM358-N03-P03-PINS.png
A	gold/review_crops/indep_LM358-N04-P15-CHART.png
A	gold/review_crops/indep_LM358-N05-P31-REVHIST.png
A	gold/review_crops/indep_LM358-P04-T02.png
A	gold/review_record.md
A	gold/spec.yaml
A	gold/versions/gold-2026-11-06.1/VERSION.json
A	gold/versions/gold-2026-11-06.1/gold_table_set.jsonl
A	gold/versions/gold-2026-11-06.1/manifest.json
A	gold/versions/gold-2026-11-06.1/spec.yaml
M	pyproject.toml
A	src/icpdf/classification/.gitattributes
A	src/icpdf/classification/__init__.py
A	src/icpdf/classification/classifier.py
A	src/icpdf/classification/cli.py
A	src/icpdf/classification/evidence.py
A	src/icpdf/classification/models.py
A	src/icpdf/classification/report.py
A	src/icpdf/classification/rules.py
M	src/icpdf/cli.py
M	src/icpdf/domain/__init__.py
M	src/icpdf/domain/candidate.py
M	src/icpdf/domain/table.py
A	src/icpdf/domain/visual.py
A	src/icpdf/eval/__init__.py
A	src/icpdf/eval/jsonio.py
A	src/icpdf/eval/manifests.py
M	src/icpdf/parser/candidate_registry.py
A	src/icpdf/parser/config.py
M	src/icpdf/parser/coords.py
A	src/icpdf/parser/header_semantics.py
A	src/icpdf/parser/header_sides.py
A	src/icpdf/parser/layout.py
A	src/icpdf/parser/logical_assembly.py
A	src/icpdf/parser/logical_attribution.py
A	src/icpdf/parser/logical_boundary.py
A	src/icpdf/parser/logical_candidates.py
A	src/icpdf/parser/logical_canopy.py
A	src/icpdf/parser/logical_decision.py
A	src/icpdf/parser/logical_evidence.py
A	src/icpdf/parser/logical_identity.py
A	src/icpdf/parser/logical_projection.py
M	src/icpdf/parser/pipeline.py
A	src/icpdf/parser/pipeline_sandbox.py
A	src/icpdf/parser/rule_primitives.py
A	src/icpdf/parser/structure.py
M	src/icpdf/parser/table_detector.py
M	src/icpdf/parser/table_rebuilder.py
A	src/icpdf/parser/table_regions.py
M	src/icpdf/parser/text_blocks.py
A	src/icpdf/parser/visual_structure.py
M	src/icpdf/storage/artifact_store.py
M	src/icpdf/storage/run_store.py
A	tests/fixtures/a3_e1.py
M	tests/fixtures/synthetic.py
A	tests/integration/test_a2_table_decision.py
A	tests/integration/test_a3_e1_chain.py
A	tests/integration/test_a3_w1_d4_manifest_failure.py
A	tests/integration/test_a3_w1_pipeline_wiring.py
A	tests/integration/test_assembly_chain.py
A	tests/integration/test_coordinate_chain.py
A	tests/integration/test_header_candidate_production.py
A	tests/integration/test_phase14_primitive_audit.py
A	tests/integration/test_phase14_s1.py
A	tests/integration/test_phase14_s2.py
A	tests/integration/test_s2b_chain.py
A	tests/integration/test_s2b_identity.py
A	tests/integration/test_s2b_sandbox.py
A	tests/unit/test_a2_decision_dto.py
A	tests/unit/test_a3_e1_evidence.py
A	tests/unit/test_a3_w1_c0b_failure_boundary.py
A	tests/unit/test_a3_w1_c1_write_bytes.py
A	tests/unit/test_a3_w1_d4_fsync.py
A	tests/unit/test_assembly.py
A	tests/unit/test_eval_jsonio.py
A	tests/unit/test_eval_manifests.py
A	tests/unit/test_evidence_validation.py
A	tests/unit/test_header_sides.py
A	tests/unit/test_label_grid.py
A	tests/unit/test_logical_candidates.py
A	tests/unit/test_rule_primitives.py
A	tests/unit/test_s2b_attribution.py
A	tests/unit/test_s2b_boundary.py
A	tests/unit/test_s2b_canopy_evidence.py
A	tests/unit/test_s2b_d4_word_extent.py
A	tests/unit/test_s2b_d5_word_capture.py
A	tests/unit/test_s2b_d6_row_lattice.py
A	tests/unit/test_s2b_decision.py
A	tests/unit/test_s2b_header_canopy.py
A	tests/unit/test_s2b_identity_registry.py
A	tests/unit/test_s2b_projection.py
A	tests/unit/test_s2b_row_projection.py
A	tests/unit/test_s2b_word_row_invariants.py
A	tests/unit/test_table_params_snapshot.py
A	tests/unit/test_table_regions.py
A	tests/unit/test_visual_structure.py
A	tools/a3_e1_parity_report.py
A	tools/audit_visual_primitives.py
A	tools/export_review_evidence.py
A	tools/goldset/__init__.py
A	tools/goldset/annotate.py
A	tools/goldset/compare.py
A	tools/goldset/evaluate.py
A	tools/goldset/freeze_version.py
A	tools/goldset/inspect_components.py
A	tools/goldset/render_review_crops.py
A	tools/goldset/rules.py
A	tools/head_parity_compare.py
A	tools/head_parity_probe.py
A	tools/phase11_audit.py
A	tools/render_detection_crops.py
A	tools/render_region_evidence.py
A	tools/validate_evidence.py
A	tools/validate_manifests.py
A	workbench/_classifier_revision/CLASSIFIER_REVISION_PLAN.md
A	workbench/_classifier_revision/R1_PRIME_SUPPLEMENT.md
A	workbench/_classifier_revision/README.md
A	workbench/_classifier_revision/SHA256SUMS.txt
[EXIT=0]

### [9] 工作区状态
$ git status --porcelain=v1
 M src/icpdf/cli.py
 M workbench/_classifier_revision/R1_PRIME_SUPPLEMENT.md
?? .workbuddy-ai/
?? .workbuddy/
?? _premerge_backup/
?? backstage/
?? docs/Document_Classifier_V2_Design.md
?? docs/archive/
?? docs/v2_2_1_review/
?? "docs/\346\226\271\346\241\210\350\256\250\350\256\272.txt"
?? "docs/\346\243\200\346\237\245\351\224\231\350\257\257\346\270\205\345\215\225.txt"
?? icpdf_c6_verify.bundle
?? "review \346\211\247\350\241\214\346\270\205\345\215\225.md"
?? tests/unit/test_classification_processpool_sim.py
?? tests/unit/test_classification_v2.py
?? tests/unit/test_env_redact.py
?? tools/stage_a/
?? tools/stage_b/
?? workbench.html
?? workbench/LOCALHOST_SMOKE_REPORT.md
?? workbench/PARSER_CALL_CHAIN.md
?? workbench/SHA256SUMS.txt
?? workbench/WORKBENCH_CODE_CHANGES.md
?? workbench/WORKBENCH_P1P2_FIX.diff
?? workbench/WORKBENCH_P1P2_FIX_REPORT.md
?? workbench/_classifier_revision/CALIBER_AND_FINDINGS.md
?? workbench/_classifier_revision/CALLSITE_AUDIT.md
?? workbench/_classifier_revision/COMPARISON_REPORT.md
?? workbench/_classifier_revision/R1_PRIME_OVERTURN.md
?? workbench/_classifier_revision/R1_prime_harm_76.csv
?? workbench/_classifier_revision/VARIANT_changes.csv
?? workbench/_classifier_revision/_ads1299_pack.py
?? workbench/_classifier_revision/_build_csv.py
?? workbench/_classifier_revision/_d_prime/
?? workbench/_classifier_revision/_d_prime_check.py
?? workbench/_classifier_revision/_git_ancestry_verify/
?? workbench/_classifier_revision/_http_probe_v1_v4/
?? workbench/_classifier_revision/_impact_demote/
?? workbench/_classifier_revision/_impact_full/
?? workbench/_classifier_revision/_impact_guard/
?? workbench/_classifier_revision/_impact_guardonly/
?? workbench/_classifier_revision/_impact_matrix/
?? workbench/_classifier_revision/_logs/
?? workbench/_classifier_revision/_scan_demote.py
?? workbench/_classifier_revision/_scan_dprime.py
?? workbench/_classifier_revision/_scan_guard.py
?? workbench/_classifier_revision/_scan_guardonly.py
?? workbench/_classifier_revision/_scan_impact.py
?? workbench/_classifier_revision/_scan_matrix.py
?? workbench/_classifier_revision/_trace_case.py
?? workbench/_classifier_revision/ads1299/
?? workbench/_classifier_revision/affected_samples.csv
?? workbench/_classifier_revision/caliber_stats.json
?? workbench/_deps/
?? workbench/_diff/
?? workbench/_doc_verify/
?? workbench/_gate6a_prep/
?? workbench/_guard/
?? workbench/_probe_evm/
?? workbench/_probe_v002_v022/
?? workbench/_probe_v002_v022_slim/
?? workbench/_smoke/
?? workbench/_smoke_frozen_r2/
?? workbench/_verify_p1p2_static.py
?? workbench/classify_worker.py
?? workbench/index.html
?? workbench/parse_worker.py
?? workbench/serve_parser.py
?? workbench/uploads/
[EXIT=0]

------------------------------------------------------------------------------
### 补充核验（用于判断 origin/main 是否过期，不改任何 ref）

### [S1] 远端真实指向（纯查询，不写 ref），用于校验 origin/main 是否过期
$ git ls-remote origin main
853a80dd664c79ef90baaac53eefb9bbc2155dde	refs/heads/main
[EXIT=0]

### [S2] origin/main 的提交哈希/时间/标题
$ git log -1 --format=%H%n%ci%n%s origin/main
853a80dd664c79ef90baaac53eefb9bbc2155dde
2026-11-05 20:30:55 +0800
feat: initialize icpdf-extractor with Phase 0 contract and Phase 1 deterministic parser
[EXIT=0]

### [S3] 领先提交数
$ git rev-list --count origin/main..main
45
[EXIT=0]

### [S4] 落后提交数（应为 0）
$ git rev-list --count main..origin/main
0
[EXIT=0]
```

