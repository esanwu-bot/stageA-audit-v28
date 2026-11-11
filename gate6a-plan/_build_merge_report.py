# -*- coding: utf-8 -*-
"""组装 G7B_MERGE_REPORT.md：把 g7b_merge_raw.log 逐字嵌入，避免手抄失真。"""
from __future__ import print_function

import sys
from pathlib import Path

PREP = Path(__file__).resolve().parent
RAW = PREP / "g7b_merge_raw.log"

PROSE_HEAD = """# G7b 合入报告（D' 修订进入 main）

> 结论先说：**合入成功，`main` 已快进到 `60a503c`，`classifier.py` 字节未变。**
> 合入前后 `classifier.py` 的 SHA-256 都是 `28b9f0bf…`，说明这次合入没有引入任何
> 内容改动，只是把已有的 17 个提交搬上主干。

| 项 | 值 |
| --- | --- |
| 仓库 | `E:\\workspace\\icpdf-extractor` |
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
报 42 处行尾空白，那是 **CRLF 仓库的行尾 `\\r` 被当成尾随空白**的假阳性。
`classifier.py` 的 blob 是 CRLF（1084 CR = 1084 LF），而 D' 的 SHA-256 是在
CRLF 字节上算的，**不能为了过检查改成 LF**，否则哈希失真。
`whitespace_check.json` 已用逐字节证据证明去掉 `\\r` 后真实尾随空白为 0。
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
"""


def main():
    raw = RAW.read_text(encoding="utf-8").rstrip("\n")
    body = PROSE_HEAD + "\n```text\n" + raw + "\n```\n"
    out = PREP / "G7B_MERGE_REPORT.md"
    out.write_text(body, encoding="utf-8", newline="\n")
    print("written %s (%d bytes, %d lines)"
          % (out, len(body.encode("utf-8")), body.count("\n") + 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
