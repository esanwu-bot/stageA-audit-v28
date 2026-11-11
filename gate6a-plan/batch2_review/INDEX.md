# Batch 2 复审包 · 入口

本目录是 Gate 6A Batch 2 Gold Set 的**第二次送审**。上一版（18 行）按 Reviewer 意见做了两处修正，
同时补齐 Git 证据、机检原始输出与生成器源码，全部可本地复现。

工作仓库：`[REDACTED-INTERNAL-REPO]`
送审分支：`feat/gate6a-annotation`（**未触碰 main**，main 仍停在 `853a80d`）

## 先看这三个

| 顺序 | 文件 | 看什么 |
| --- | --- | --- |
| 1 | `Batch2_Gate6A_README.md` | 保留标准、剔除清单、已知局限 |
| 2 | `Batch2_GOLD_v1.csv` | 24 行交付数据（UTF-8 BOM，Excel 直接开） |
| 3 | `git_evidence_gate6a.txt` | 你指定的 4 条命令的终端原始输出 |

`Batch2_Gold_v1.xlsx` 与 CSV 同内容；`Batch2_Gate6A_review.zip` 是以上全部文件的打包副本。

## 意见 1：V101 按 VCC 拆行 —— 已修正

v1 每组只留了 VCC=2V 一列。现按页面结构拆成 **3 参数 × 3 VCC = 9 行**，
`condition` 填 `HC, VCC=2V` / `HC, VCC=4.5V` / `HC, VCC=6V`。

| 参数 | VCC=2V | VCC=4.5V | VCC=6V |
| --- | --- | --- | --- |
| VIH（MIN） | 1.5 | 3.15 | 4.2 |
| VIL（MAX） | 0.5 | 1.35 | 1.8 |
| VOH（MIN） | 1.9 | 4.4 | **5.9** |

顺带修正一个 v1 的错值：VOH 第三组原写成 4.4（与 4.5V 行重复），实测页面第 3 页是 **5.9**。

判定依据：第 3 页 `TEST CONDITIONS` 列里的 `2` / `4.5` / `6` 是**三个行条件**，
不是三个列头——所以 MIN/MAX 列要按行读，不能按列取。

## 意见 2：Git 证据 —— 已采集

`git_evidence_gate6a.txt` 内含 4 条命令的命令原文、原始 stdout/stderr 与 exit code，
外加两条 `rev-parse` 用于证明 main 未被本次推送改动。摘录：

- `git merge-base origin/main <SHA>` → `853a80dd664c79ef90baaac53eefb9bbc2155dde`
  与 `origin/main` tip 完全一致，说明送审提交是从 main 线性长出来的，不是孤岛。
- `git diff-tree --no-commit-id --name-status -r <SHA>` → 9 个文件全部 `A`（新增）。

## 意见 3：打包 —— 已打包

`Batch2_Gate6A_review.zip`（54 KB，12 个文件），`SHA256SUMS.txt` 给出全部文件的 SHA-256。

## 复核方法（不需要 CodeUp 权限）

```bash
# 1. 数据自检：6 类检查，应输出 OK=24 / 0 ERROR
python validate_annotation.py --csv Batch2_GOLD_v1.csv

# 2. 校验文件未被篡改
sha256sum -c SHA256SUMS.txt
```

`validation_report.txt` 是我这边的机检原始输出（`OK=24`）。
`Batch2_DRAFT_FIXED.csv` 是 82 行机器草稿，Gold 就是从这份里做减法筛出来的，可逐行倒查。

## 目录里的脚本是干什么的

| 文件 | 作用 |
| --- | --- |
| `_build_batch2_interactive.py` | 圈选台生成器：预载草稿、减法操作、CSV 回导、禁止点出孤儿数字行 |
| `_b2_app.js` | 圈选台前端逻辑（含 `parseLine` 的 U+2212/负号合并/括号注跳过） |
| `_draft_extract.py` | 零 Parser 依赖的草稿提取器 |
| `_vl_extract.py` | Qwen3-VL 预标注，带磁盘缓存 |
| `_build_batch2_viewer.py` | 早期实现（标题定位 + 目录页过滤），保留供对照 |
| `validate_annotation.py` | 机检，含 15 行脏数据自测 |

脚本不是交付物，只为让 24 行数字可复算。若只想看结论，忽略本表以下全部内容。
