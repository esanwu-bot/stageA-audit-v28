# Git 基线冻结与未提交改动隔离清单

**冻结 = 只读写哈希清单，不是 Git 操作。** 本轮未执行 `git add` / `git commit` /
`git push` 到主项目；未回滚、未合并、未 stash 任何改动。GitHub 推送仅发生于独立
文件传输仓库 `esanwu-bot/stageA-audit-v28` 的 `gate6/r2/` 路径，该仓库只是取件通道，
**不是权威基线、不是审计依据**。

机器可读版：`GIT_BASELINE.json`（状态与统计）、`BASELINE_FREEZE.csv`（逐文件 SHA-256）。

---

## 一、权威基线

| 项 | 值 |
| --- | --- |
| 目录 | `E:\workspace\icpdf-extractor` |
| 分支 | `feat/s2b-schema-d4-d6` |
| HEAD | `3ed22a4a83564b36ca238792af4b2328fd966469` |
| remote origin | `[REDACTED-INTERNAL-REPO]` |
| 已跟踪文件 | 491 |
| `git status --short` 条目 | 17 |
| 忽略规则 | `.gitignore:18` `runs/`（`git check-ignore -v` 实测命中） |

`E:/workspace/github/icpdf-extractor` 是副本（分支 `main`、HEAD `020bcffd…`、
remote GitHub），按用户指令**不作为审计依据**。
对照旧项目 `E:\workspace\IcPdfParser` 分支 `main`、
HEAD `ce2a013c81b1442bd444ba6a0abda813fe00c65c`。

---

## 二、`git status --short` 原样输出（17 项）

```
 M src/icpdf/cli.py
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
?? src/icpdf/classification/
?? tests/unit/test_classification_processpool_sim.py
?? tests/unit/test_classification_v2.py
?? tools/stage_a/
?? tools/stage_b/
?? workbench.html
```

---

## 三、隔离分类（后续实施前必须保持）

| 类 | 含义 | 成员 | 处置规则 |
| --- | --- | --- | --- |
| **A** | HEAD 已跟踪且未修改（491 项中的其余） | 冻结基线主体 | 不得改动；任何变更须单独审批 |
| **B** | 已跟踪但工作区修改 | `src/icpdf/cli.py` | **必须隔离**，不得混入正式代码提交；CLI 修改需单独评审后单独提交 |
| **C** | 未跟踪、与实施相关的源码/工具（**46 个 git 可见文件**） | `src/icpdf/classification/`（7）、`tools/stage_a/`（36）、`tools/stage_b/`（1）、`tests/unit/test_classification_processpool_sim.py`、`tests/unit/test_classification_v2.py`（2） | 待单独评审后**单独提交**；不得与 B 类或报告一起打包 |
| **D** | 未跟踪的文档/报告/工作台/日志（**25 个文件**） | `backstage/`、`docs/*`、`workbench.html`、`icpdf_c6_verify.bundle`、`review 审查清单.md`、`.workbuddy*` | 审计材料，**不得进代码提交** |
| **E** | gitignored 运行时产物 | `runs/` 全部（含 `stage_a_350/gate6/`、`gate6_r2/`、`gate2a/`） | 不进 Git；仅通过独立传输通道交付 |

### B 类关键证据

`src/icpdf/cli.py` 工作区与 HEAD 是**两个不同字节**，不可混同：

| 版本 | SHA-256 |
| --- | --- |
| 工作区 `src/icpdf/cli.py` | `c288bffa1d0ac87d31624b3b9727dc23f5f3c51f7d8905625cb68d77c7f3a2a4` |
| `HEAD:src/icpdf/cli.py` | `f0347d3802b4bc5f71e5f7cafd216863af3eb9b6d9bb453423783d91409ca5bc` |

`git diff --stat`：`1 file changed, 38 insertions(+)`；差异内容为新增
`classify()` 与 `qc-report()` 两个命令，转调 `icpdf.classification.cli.main()`。
**HEAD 中的 `cli.py` 不含这两个命令**；Gate 6 审计里引用的 `cli.py:95-130`
是工作区版本，必须注明。

---

## 四、冻结清单内容

`BASELINE_FREEZE.csv` 每行：`category, path, bytes, sha256, note`。

- 覆盖 B 类全部已修改文件 + `HEAD:src/icpdf/cli.py` 基线哈希；
- 覆盖 C/D 类全部 **71 个** git 可见未跟踪文件（由
  `git -c core.quotePath=false ls-files --others --exclude-standard` 枚举，
  逐文件计算 SHA-256，含 44 MB 的 `icpdf_c6_verify.bundle`）；
  计数口径为 git 可见文件，不含被 `.gitignore` 忽略的 `__pycache__` 等缓存
  （例如 `tools/stage_a/` 磁盘 39 个文件、git 可见 36 个）；
- E 类不逐文件列举（`runs/` 逾万文件），只记录忽略规则与文件总数，
  避免把运行时产物写进基线清单。

复核方式（只读）：

```sh
cd E:/workspace/icpdf-extractor
git rev-parse HEAD                      # 应为 3ed22a4a...
git status --short                      # 应为上述 17 项
sha256sum src/icpdf/cli.py              # 应等于工作区哈希
git show HEAD:src/icpdf/cli.py | sha256sum   # 应等于 HEAD 哈希
```

---

## 五、对 Reviewer「实施前冻结基线」的落实

1. 本轮**没有**把 CLI 修改、临时报告或运行产物混入任何提交：主项目 Git 零提交。
2. Gate 6 第一轮 `gate6/` 交付件字节不变（其 `SHA256SUMS.txt` 9 OK）；
   第二轮材料另放 `gate6_r2/`，物理隔离。
3. `runs/stage_a_350/gate2a/` 保持 `LEGACY_PIPELINE_TRIAL` 标记，
   不因本轮清理、覆盖或改名。
4. 后续实施前建议（**待批准**）：由 Reviewer 指定一次**仅含获批源码**的独立提交，
   提交前用 `BASELINE_FREEZE.csv` 复核工作区；B/C/D/E 四类分别处理，
   禁止 `git add -A` 或批量提交。本轮不执行该动作。

---

## 六、证据边界

`ROUND2_VERIFY.json` 的 PASS 与 `SHA256SUMS.txt` 的 OK 只证明
「交付件内部一致 + 文件字节完整」，**不证明**审计结论已获独立复核、
字段映射正确、方案获批或基线已被正式冻结为 Git 提交。
