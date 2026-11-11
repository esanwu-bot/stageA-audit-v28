# Git 祖先关系核验 · 权威仓库 `E:\workspace\icpdf-extractor`

- 执行时间：2026-11-11 12:03（UTC+8）
- 执行方式：**只读**。仅 `remote / status / branch / rev-parse / merge-base / diff / log / ls-tree`，
  未写工作区、未改索引、未提交、未 push。
- 原始终端输出：`git_verify_raw.log`（227 行，逐字节，含所有 stdout/stderr 与退出码）
- 空白成因证据：`whitespace_check.json`

---

## 1. 七条命令的逐条结论

| # | 命令 | 退出码 | 结论 |
|---|---|---|---|
| 1 | `git remote -v` | 0 | `origin` 指向阿里云 CodeUp `icpdf-extractor.git`；**权威仓库不在 GitHub** |
| 2 | `git status --short` | 0 | 仅 2 个**已跟踪**文件修改（见 §2），其余均为未跟踪 |
| 3 | `git branch --show-current` | 0 | `feat/s2b-schema-d4-d6` |
| 4 | `git rev-parse HEAD` | 0 | `60a503cc8015ef9bfb27ddef1685e41593f3a75f` |
| 5 | `git rev-parse main` | 0 | `6f3e58d51e6e4278e623171251f055474de8ae0a` |
| 6 | `git merge-base --is-ancestor main 60a503c` | **0** | **PASS：`main` 是 `60a503c` 的祖先** |
| 7 | `git diff --check 60a503c^ 60a503c` | **2** | **假阳性**，成因见 §3；真实尾随空白为 **0** |

## 2. `git status --short` 里唯一需要解释的两项

只有两个**已跟踪**文件处于修改态，且都**不是** G7b 引入、本轮也未触碰：

| 文件 | 内容 | 归属 |
|---|---|---|
| `src/icpdf/cli.py` | +38 行，新增 `classify` / `qc-report` 两个 typer 子命令 | G7b 之前既有，未提交 |
| `workbench/_classifier_revision/R1_PRIME_SUPPLEMENT.md` | +40 行补充说明 | 同上 |

`src/icpdf/classification/classifier.py` 在 `git status` 中**不出现**，
说明 D' 的改动已全部随 `60a503c` 入库，工作区与该提交一致。

其余 `??` 项均为本轮及此前生成的分析脚本与证据目录（`_d_prime/`、
`_http_probe_v1_v4/`、`_git_ancestry_verify/` 等），均为未跟踪，不入库、不影响祖先关系。

## 3. 第 7 条：`EXIT=2` 的成因（关键，勿误判）

命令输出了 **42 条** `trailing whitespace` 告警，退出码 2。
若不加辨别，会误判为「G7b 提交带入了尾随空白」。**实际不是。**

成因链：

1. `src/icpdf/classification/.gitattributes` 设了 `* -text`
   （`git ls-tree` 可见，blob `29b8eabe1a8c94bbc00083631ee89cd81b1eee96`），
   因此 blob **按原样存为 CRLF**——实测该文件 CR=1084、LF=1084，即每行都是 CRLF。
2. `git diff --check` 的判定规则把行尾的 `\r` 当作尾随空白，
   于是**每一条** CRLF 新增行都被点名一次。
3. 42 条告警 = 42 条新增行，一一对应，**没有一条是真正的空格/制表符**。

两个独立判据（`whitespace_check.json`）：

| 判据 | 结果 |
|---|---|
| diff 新增行总数 | 42 |
| 其中以 `\r` 结尾 | **42**（全部） |
| 剥掉行尾 `\r` 后仍以空格或 `\t` 结尾的新增行 | **0** |
| 剥掉 `\r` 后整份 blob 中真实尾随空白行 | **0** |

复现方式：

```bash
# 1. 看到 EXIT=2 与 42 条提示
git diff --check 60a503c^ 60a503c

# 2. 确认 blob 是 CRLF：输出 1084
git cat-file -p 60a503c:src/icpdf/classification/classifier.py | tr -dc '\r' | wc -c

# 3. 剥 CR 后逐行判定真实尾随空白：输出 0
py -3.13 workbench/_classifier_revision/_git_ancestry_verify/_check_whitespace.py
```

**结论：第 7 条不构成缺陷。** 这是「字节保真」与「git 空白检查」两个目标天然冲突的
副产物——为了让 `classifier.py` 的 sha256 在提交前后完全一致（D' 证据链依赖这一点），
必须保留 CRLF，而 `git diff --check` 不理解这个意图。

## 4. 补充佐证

| 补充命令 | 输出 | 含义 |
|---|---|---|
| `git merge-base main 60a503c` | `6f3e58d5…` **= `main` 自身** | `main` 就是分叉点，HEAD 在其下游 |
| `git rev-list --count main..60a503c` | **17** | HEAD 领先 `main` 17 个提交，无「脱离主线」 |
| `git log --format="%H %P %s" -1 60a503c` | 父 = `35cd8a10…` | G7b 的父提交正是 G7a |
| `git log --oneline -3 60a503c` | `60a503c G7b` / `35cd8a1 G7a` / `55da906 G6` | 提交链连续，G7a→G7b 无跳步 |
| `git config --get core.autocrlf` | `true` | 但 `-text` 属性覆盖它，故 blob 保持 CRLF |
| `git ls-tree HEAD …/.gitattributes` | `100644 blob 29b8eabe…` | 该属性文件已入库，不是本地未跟踪设置 |

## 5. 总结论

1. **祖先关系成立**：`main` 是 `60a503c` 的祖先，退出码 0，`merge-base` 等于 `main` 自身，
   HEAD 领先 `main` 17 个提交。G7b 未被孤立、未被 rebase 到别处。
2. **工作区未污染**：`classifier.py` 干净；仅两个与 D' 无关的既有修改（`cli.py`、
   `R1_PRIME_SUPPLEMENT.md`）处于未提交态，需由 Reviewer 决定去留。
3. **第 7 条告警为假阳性**，真实尾随空白为 0，两个独立判据一致。
4. 权威仓库远端为阿里云 CodeUp，**不是** GitHub；GitHub 上的 `stageA-audit-v28`
   仅为文件传输用途，不构成基线。

---

## 附：终端完整输出（原样，逐字节复制自 `git_verify_raw.log`）

```text
Git 祖先关系核验 · 权威仓库 E:\workspace\icpdf-extractor
执行时间：2026-11-11T12:03:20+08:00
执行方式：只读查询，未写工作区 / 未改索引 / 未提交 / 未 push
说明：git status 会刷新索引 stat 缓存，属 git 自身行为
==============================================================================

## 一、Reviewer 指定的 7 条命令（顺序原样）

$ git remote -v
origin	[REDACTED-INTERNAL-REPO] (fetch)
origin	[REDACTED-INTERNAL-REPO] (push)
[EXIT=0]

$ git status --short
 M src/icpdf/cli.py
 M workbench/_classifier_revision/R1_PRIME_SUPPLEMENT.md
?? .workbuddy-ai/
?? .workbuddy/
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

$ git branch --show-current
feat/s2b-schema-d4-d6
[EXIT=0]

$ git rev-parse HEAD
60a503cc8015ef9bfb27ddef1685e41593f3a75f
[EXIT=0]

$ git rev-parse main
6f3e58d51e6e4278e623171251f055474de8ae0a
[EXIT=0]

$ git merge-base --is-ancestor main 60a503c
(无输出)
[EXIT=0]

$ git diff --check 60a503c^ 60a503c
src/icpdf/classification/classifier.py:210: trailing whitespace.
+#: D' 的抑制前提：板级证据必须**独立足以裁决**。
src/icpdf/classification/classifier.py:211: trailing whitespace.
+#:
src/icpdf/classification/classifier.py:212: trailing whitespace.
+#: 只认两类：
src/icpdf/classification/classifier.py:213: trailing whitespace.
+#:   * ``EVM_BOARD_SCHEMATIC`` —— 板级原理图/布局，天然只出现在评估板文档；
src/icpdf/classification/classifier.py:214: trailing whitespace.
+#:   * ``EVM_BOARD_TITLE`` 的 ``EVAL_MODULE`` / ``EVAL_BOARD`` / ``DEV_KIT`` 三组。
src/icpdf/classification/classifier.py:215: trailing whitespace.
+#:
src/icpdf/classification/classifier.py:216: trailing whitespace.
+#: 明确排除：``EVM_BOARD_TITLE`` 的 ``USER_GUIDE`` 组（MEDIUM，Datasheet 也可能自带
src/icpdf/classification/classifier.py:217: trailing whitespace.
+#: 用户指南字样）、``DOCNUMBER_UG``、``EVM_BOARD_TERMS``（MEDIUM）、
src/icpdf/classification/classifier.py:218: trailing whitespace.
+#: ``EVM_BODY_MENTION``（WEAK）。这些都不构成「板级足以裁决」。
src/icpdf/classification/classifier.py:219: trailing whitespace.
+_BOARD_DECISIVE_TITLE_GROUPS = frozenset({"EVAL_MODULE", "EVAL_BOARD", "DEV_KIT"})
src/icpdf/classification/classifier.py:220: trailing whitespace.
+
src/icpdf/classification/classifier.py:221: trailing whitespace.
+
src/icpdf/classification/classifier.py:222: trailing whitespace.
+def _board_decisive(board_strong: list[Hit]) -> bool:
src/icpdf/classification/classifier.py:223: trailing whitespace.
+    """板级证据是否足以独立裁出 EVM（D' 抑制 ``DS_PRODUCT_MODEL_TITLE`` 的前提）。"""
src/icpdf/classification/classifier.py:224: trailing whitespace.
+    for h in board_strong:
src/icpdf/classification/classifier.py:225: trailing whitespace.
+        if h.rule_id == "EVM_BOARD_SCHEMATIC":
src/icpdf/classification/classifier.py:226: trailing whitespace.
+            return True
src/icpdf/classification/classifier.py:227: trailing whitespace.
+        if (h.rule_id == "EVM_BOARD_TITLE"
src/icpdf/classification/classifier.py:228: trailing whitespace.
+                and (h.group or "").upper() in _BOARD_DECISIVE_TITLE_GROUPS):
src/icpdf/classification/classifier.py:229: trailing whitespace.
+            return True
src/icpdf/classification/classifier.py:230: trailing whitespace.
+    return False
src/icpdf/classification/classifier.py:231: trailing whitespace.
+
src/icpdf/classification/classifier.py:343: trailing whitespace.
+
src/icpdf/classification/classifier.py:344: trailing whitespace.
+    # ---- D'（A3-W2）：板级裁决足以成立时，抑制「标题里的型号」这一条 DS 证据
src/icpdf/classification/classifier.py:345: trailing whitespace.
+    #      ``DS_PRODUCT_MODEL_TITLE`` 只证明「标题块里出现了本芯片型号」，但评估板
src/icpdf/classification/classifier.py:346: trailing whitespace.
+    #      手册的标题**本来就**写被测芯片型号（板以芯片命名），因此在板级证据已经
src/icpdf/classification/classifier.py:347: trailing whitespace.
+    #      足以裁出 EVM 时，这条规则不参与冲突计数，而是记为被板级证据推翻。
src/icpdf/classification/classifier.py:348: trailing whitespace.
+    #      抑制范围严格限定：只动这一条规则；``DS_DOCUMENT_TITLE``、``DS_ELECTRICAL_SECTIONS``
src/icpdf/classification/classifier.py:349: trailing whitespace.
+    #      等其它 DS 证据不受影响，它们在场时仍走档 5 冲突。
src/icpdf/classification/classifier.py:350: trailing whitespace.
+    if ds_title and _board_decisive(board_strong) and all(
src/icpdf/classification/classifier.py:351: trailing whitespace.
+            h.rule_id == "DS_PRODUCT_MODEL_TITLE" for h in ds_title):
src/icpdf/classification/classifier.py:352: trailing whitespace.
+        for h in ds_title:
src/icpdf/classification/classifier.py:353: trailing whitespace.
+            rejected.append((
src/icpdf/classification/classifier.py:354: trailing whitespace.
+                h.rule_id, h.matched_text,
src/icpdf/classification/classifier.py:355: trailing whitespace.
+                "overridden by board evidence (%s); 评估板标题里的芯片型号不代表本文档是 Datasheet"
src/icpdf/classification/classifier.py:356: trailing whitespace.
+                % _board_description(hits),
src/icpdf/classification/classifier.py:357: trailing whitespace.
+                "overridden_by_board_evidence"))
src/icpdf/classification/classifier.py:358: trailing whitespace.
+        hits = [h for h in hits if h.rule_id != "DS_PRODUCT_MODEL_TITLE"]
src/icpdf/classification/classifier.py:359: trailing whitespace.
+        ds_title = []
src/icpdf/classification/classifier.py:360: trailing whitespace.
+        ds_title_strong = False
src/icpdf/classification/classifier.py:361: trailing whitespace.
+        ds_strong = ds_combo
src/icpdf/classification/classifier.py:362: trailing whitespace.
+
[EXIT=2]

==============================================================================

## 二、补充佐证命令（用于解释第 7 条告警，非 Reviewer 要求）

$ git merge-base main 60a503c
6f3e58d51e6e4278e623171251f055474de8ae0a
[EXIT=0]

$ git log --format=%H %P %s -1 60a503c
60a503cc8015ef9bfb27ddef1685e41593f3a75f 35cd8a10983323fb9ea80af5edd6ffedbffeaaa4 G7b: D' —— 板级证据足以裁决时抑制 DS_PRODUCT_MODEL_TITLE
[EXIT=0]

$ git rev-list --count main..60a503c
17
[EXIT=0]

$ git log --oneline -3 60a503c
60a503c G7b: D' —— 板级证据足以裁决时抑制 DS_PRODUCT_MODEL_TITLE
35cd8a1 G7a: 纳入 classification 包基线（D' 之前的原始状态）
55da906 G6: replace R1 blacklist with parameter-source fix (R1' supplement)
[EXIT=0]

$ git config --get core.autocrlf
true
[EXIT=0]

$ git ls-tree HEAD src/icpdf/classification/.gitattributes
100644 blob 29b8eabe1a8c94bbc00083631ee89cd81b1eee96	src/icpdf/classification/.gitattributes
[EXIT=0]

==============================================================================

## 三、退出码汇总

git remote -v                                              EXIT=0
git status --short                                         EXIT=0
git branch --show-current                                  EXIT=0
git rev-parse HEAD                                         EXIT=0
git rev-parse main                                         EXIT=0
git merge-base --is-ancestor main 60a503c                  EXIT=0
git diff --check 60a503c^ 60a503c                          EXIT=2
```
