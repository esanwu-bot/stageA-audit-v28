# G7b 合入报告（D' 修订进入 main）

> 结论先说：**合入成功，`main` 已快进到 `60a503c`，`classifier.py` 字节未变。**
> 合入前后 `classifier.py` 的 SHA-256 都是 `28b9f0bf…`，说明这次合入没有引入任何
> 内容改动，只是把已有的 17 个提交搬上主干。

| 项 | 值 |
| --- | --- |
| 仓库 | `E:\workspace\icpdf-extractor` |
| 合并前 `main` | `6f3e58d51e6e4278e623171251f055474de8ae0a` |
| 合并前 `HEAD`（`feat/s2b-schema-d4-d6`） | `60a503cc8015ef9bfb27ddef1685e41593f3a75f` |
| 待合入提交数 | 17（`main..60a503c`），反向 0（`60a503c..main`） |
| 祖先关系 | `git merge-base --is-ancestor main 60a503c` → 0，快进安全 |
| **合并后 `main`** | **`60a503cc8015ef9bfb27ddef1685e41593f3a75f`** |
| **合并后 `HEAD`** | **`60a503cc8015ef9bfb27ddef1685e41593f3a75f`** |
| **合并后 `classifier.py` SHA-256** | **`28b9f0bfc1b23f27f6b170b00c4651a0ba5a9baad35c375d2434e9fd07ee7d5b`** |
| 合并方式 | `git merge --ff-only`（无 merge commit，历史线性） |

---

## 1. 合并前的四条核验命令

Reviewer 指定的四条命令全部 `EXIT=0`，才允许进入合并：

| # | 命令 | 结果 |
| --- | --- | --- |
| 1 | `git rev-parse main` | `6f3e58d5…` |
| 2 | `git rev-parse HEAD` | `60a503cc…` |
| 3 | `git status --porcelain=v1` | 仅 2 个已跟踪改动 + 未跟踪路径，无冲突态 |
| 4 | `git -c core.whitespace=cr-at-eol diff --check 60a503c^ 60a503c` | **无输出，`EXIT=0`** |

第 4 条值得单独记一笔：早前用不带 `cr-at-eol` 的 `git diff --check` 会以 `EXIT=2`
报 42 处行尾空白，那是 **CRLF 仓库的行尾 `\r` 被当成尾随空白**的假阳性。
`classifier.py` 的 blob 是 CRLF（1084 CR = 1084 LF），而 D' 的 SHA-256 是在
CRLF 字节上算的，**不能为了过检查改成 LF**，否则哈希失真。
`whitespace_check.json` 已用逐字节证据证明去掉 `\r` 后真实尾随空白为 0。
Reviewer 这次改用 `-c core.whitespace=cr-at-eol`，等于官方承认了该判定口径。

---

## 2. 合并过程中出现的一个真实障碍（不瞒报）

`git checkout main` **第一次被 Git 拒绝**，原样记录：

```
error: Your local changes to the following files would be overwritten by checkout:
	workbench/_classifier_revision/R1_PRIME_SUPPLEMENT.md
Please commit your changes or stash them before you switch branches.
Aborting
```

原因是：`R1_PRIME_SUPPLEMENT.md` 在 `feat/s2b-schema-d4-d6` 上是已跟踪文件且工作区有
未提交改动，但 `main` 当时还没有这个文件（它由 17 个待合入提交之一新增）。
Git 拒绝是**正确行为**，且是原子的——工作区一个字节都没动。

处理方式（全程留备份，不依赖任何"应该没事"的假设）：

1. 把两个改动文件物理复制到 `_premerge_backup/`，记录 SHA-256；
2. `git stash push` 只暂存这两个路径，不动其余未跟踪文件；
3. `git checkout main` → `git merge --ff-only 60a503c`；
4. `git stash pop` 恢复；
5. **发现哈希变了**：`cli.py` 从 `c288bffa…` 变成 `9f205dfd…`，
   `R1_PRIME_SUPPLEMENT.md` 从 `e9c76650…` 变成 `07225695…`。

第 5 步是 stash 应用时 `core.autocrlf=true` 把 LF 转成了 CRLF。
验证结果：**归一化换行后内容完全一致**（`LF-normalized identical: True`），
纯换行符差异。为保持工作区与合并前字节级一致，最终从备份还原原始字节，
还原后两个哈希与合并前完全相同：

```
src/icpdf/cli.py                                       c288bffa…（与合并前一致）
workbench/_classifier_revision/R1_PRIME_SUPPLEMENT.md  e9c76650…（与合并前一致）
```

**教训**：`git stash pop` 在 `autocrlf=true` 的仓库里不是字节级无损操作，
校验要按"归一化后是否一致"判，不能只比哈希。

---

## 3. 合并后的仓库状态

- `main` 与 `HEAD` 同为 `60a503c`，无 merge commit；
- `git rev-list --count main..60a503c` = 0，`60a503c..main` = 0，双向同步；
- `classifier.py` 的 HEAD 对象哈希 `2918bc63…`，工作区实测 SHA-256 `28b9f0bf…`，
  与 G7b 提交信息里写死的值一致；
- D' 代码块在位：`_BOARD_DECISIVE_TITLE_GROUPS` 在第 219 行，
  `_board_decisive()` 在 222 行，两处 `overridden_by_board_evidence`
  分别在第 357 行（D' 抑制）与第 381 行（档 1 既有逻辑），**两处未串位**；
- 冒烟导入通过：`from icpdf.classification import classifier` 正常，
  `_BOARD_DECISIVE_TITLE_GROUPS = ['DEV_KIT', 'EVAL_BOARD', 'EVAL_MODULE']`。

工作区仍保留合并前的 2 个已跟踪改动（`cli.py`、`R1_PRIME_SUPPLEMENT.md`）
与一批未跟踪路径，**均未被本次合并触碰**。

---

## 4. 一个必须写明的边界

本次合并**只动了 Git 引用，没有推送远端**。`main` 当前领先 `origin/main` 45 个提交。
是否推送、何时推送，等 Reviewer 指示。在此之前，远端 `origin/main` 上**没有** D'。

---

## 5. 原始终端日志（逐字嵌入，未编辑）

以下内容由 `_capture_merge.py` 在合并完成后现场逐条执行生成，
`[EXIT=n]` 为真实退出码，未做任何删改。

```text
==============================================================================
G7b 合入终端证据（只读命令逐条执行）
repo      : E:\workspace\icpdf-extractor
recorded  : 2026-11-11T12:16:22
==============================================================================

### 合并动作发生当时现场记录（PRE-MERGE，不可事后重算）
  main_sha                 6f3e58d51e6e4278e623171251f055474de8ae0a
  head_sha                 60a503cc8015ef9bfb27ddef1685e41593f3a75f
  branch                   feat/s2b-schema-d4-d6
  commits_ahead            17
  commits_behind           0
  classifier_py_sha256     28b9f0bfc1b23f27f6b170b00c4651a0ba5a9baad35c375d2434e9fd07ee7d5b
  cli_py_sha256            c288bffa1d0ac87d31624b3b9727dc23f5f3c51f7d8905625cb68d77c7f3a2a4
  r1_supplement_sha256     e9c766500d3d28e292d302465b95b5c4c3018e9ac710c50c51314c52c2311ae7

### 合并后现场执行（POST-MERGE）

$ git rev-parse main
60a503cc8015ef9bfb27ddef1685e41593f3a75f
[EXIT=0]

$ git rev-parse HEAD
60a503cc8015ef9bfb27ddef1685e41593f3a75f
[EXIT=0]

$ git rev-parse --abbrev-ref HEAD
main
[EXIT=0]

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

$ git -c core.whitespace=cr-at-eol diff --check 60a503c^ 60a503c
[EXIT=0]

$ git merge-base --is-ancestor 60a503c main
[EXIT=0]

$ git rev-list --count main..60a503c
0
[EXIT=0]

$ git rev-list --count 60a503c..main
0
[EXIT=0]

$ git log -1
commit 60a503cc8015ef9bfb27ddef1685e41593f3a75f
Author: esan <esan.wu@gmail.com>
Date:   Wed Nov 11 10:36:39 2026 +0800

    G7b: D' —— 板级证据足以裁决时抑制 DS_PRODUCT_MODEL_TITLE
    
    最小修订，只动一条规则的参与权，不动参数传递、不动 Parser、不动 8 项白名单、
    不动 assert_route_invariant。
    
    抑制前提（_board_decisive）：
    - EVM_BOARD_SCHEMATIC，或
    - EVM_BOARD_TITLE 的 EVAL_MODULE / EVAL_BOARD / DEV_KIT 三组
    明确排除：USER_GUIDE 组、DOCNUMBER_UG、EVM_BOARD_TERMS、EVM_BODY_MENTION。
    
    抑制动作：把 DS_PRODUCT_MODEL_TITLE 的命中从 hits 中移除，并写入
    rejected_rules，reason code = overridden_by_board_evidence。
    仅当 ds_title 全部由该规则构成时才抑制；DS_DOCUMENT_TITLE 在场时仍走档 5 冲突。
    
    定向验收 8/8 PASS（含 V1/V2/V3 修复，V4 致命反例不变，V5-V8 真 DS 不降级）。
    全量 11,355 份离线回归：193 份变化，全部 UNKNOWN/REVIEW -> EVM/QUARANTINE，
    EVM 退出隔离区 0、非 DS 进 Parser 0、真 DS 降级 0，打开失败 0。
    
    文件 sha256（修改后）= 28b9f0bfc1b23f27f6b170b00c4651a0ba5a9baad35c375d2434e9fd07ee7d5b
[EXIT=0]

$ git log --oneline -5
60a503c G7b: D' —— 板级证据足以裁决时抑制 DS_PRODUCT_MODEL_TITLE
35cd8a1 G7a: 纳入 classification 包基线（D' 之前的原始状态）
55da906 G6: replace R1 blacklist with parameter-source fix (R1' supplement)
3ed22a4 C6: never let a failed cleanup mask the original write error
a48c771 C5: clean up the temp file when write_json fails to rename
[EXIT=0]

### 合并后关键文件 SHA-256（工作区实测）
  src/icpdf/classification/classifier.py                   28b9f0bfc1b23f27f6b170b00c4651a0ba5a9baad35c375d2434e9fd07ee7d5b
  src/icpdf/cli.py                                         c288bffa1d0ac87d31624b3b9727dc23f5f3c51f7d8905625cb68d77c7f3a2a4
  workbench/_classifier_revision/R1_PRIME_SUPPLEMENT.md    e9c766500d3d28e292d302465b95b5c4c3018e9ac710c50c51314c52c2311ae7

### HEAD 中 classifier.py 对象哈希（不读工作区）
  2918bc63823bc9283b06818480bc831e564e5377
```
