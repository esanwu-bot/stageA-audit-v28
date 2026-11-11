# Batch 2 复审包 v1.4 · 入口

Gate 6A Batch 2 Gold Set 第五次送审。24 行数据已获认可，本轮两件事：
**修正 V162 的 96 mA 错配**，以及**把"数据自称的身份"和 PDF 原件用哈希绑死**。

- 代码仓：`[REDACTED-INTERNAL-REPO]`
- 送审分支：`feat/gate6a-annotation`
  - `2725f90` 数据（v1.2） → `2c7881b` 证据子提交
  - `5f5cc29` 数据（v1.3） → `db785b7` 证据子提交
  - `9097ed6` 本轮数据（v1.4）→ `a87ba4a` 本轮证据子提交（**分支 tip**）
- `main` 未动，仍为 `853a80d`

## 先看这五个

| 顺序 | 文件 | 看什么 |
| --- | --- | --- |
| 1 | `Batch2_Gate6A_README.md` | 身份、溯源、V162 修正、机检 v1.4、局限 |
| 2 | `selftest_report.txt` | **22 例自测，22/22**，含 4 个反例 |
| 3 | `validation_report.txt` | PDF 模式 + 离线模式**双跑**，都是 **OK=24 / SUSPECT=0 / ERROR=0** |
| 4 | `Batch2_PDF_PROVENANCE.csv` | 6 件 PDF 的 SHA-256 与页数，是机检的前置门禁 |
| 5 | `git_evidence_commit_chain.txt` | 三轮「数据 → 证据」成对提交的父子关系 |

## 1. V162 的 96 mA：错在哪

`Current into any output in the low state, IO` 原来填 `96 mA`。翻开 V162 手册
（`74LVTH182504APMG4__sn74lvth18504a.pdf` 第 25 页，Absolute Maximum Ratings）会看到：

| 手册列 | A port or TDO | B port |
| --- | --- | --- |
| **SN54**LVTH182504A | ±96 mA | ±30 mA |
| **SN74**LVTH182504A | ±128 mA | ±30 mA |

本批样本是 **SN74**（商用档），96 mA 属 SN54（军温档）那一行。改法（方案 A）：

| 字段 | 旧 | 新 |
| --- | --- | --- |
| `max_value` | `96` | `128` |
| `condition` | （空） | `SN74LVTH182504A, A port or TDO` |
| `notes` | 通用说明 | 追加"原 96 mA 是 SN54LVTH182504A(A port/TDO) 的值；本行器件为 SN74，改取 128 mA；B 端口另印 30 mA，未单列" |

**这一处暴露的不是抄错数字，而是"数值归属"没被记录**。同一个表里，同一串数字可能属于
邻列、邻档、邻型号；机检只能验"页面上有这个数"，验不了"这个数是不是这一行的"。
所以 `condition` 必须把温度档和端口写清——这不是修饰，是数据的一部分。

影响面：仅此 1 行。其余 23 行未动，`git diff` 只有这一行。

## 2. 溯源一致性：从"留个记录"变成"前置门禁"

v1.3 已经算了 6 件 PDF 的 SHA-256，但那只是文档里的一行字，机检并不看它。
v1.4 把它接进了判定链，新增两项检查：

**A. 三处互校**（离线模式也跑）——`file_name`、`device_model`、`sha256`、`page_count`
必须在三个地方逐字相同，缺条目即 ERROR：

| 处 | 文件 | 谁写的 |
| --- | --- | --- |
| ① | `Batch2_GOLD_v1.csv` | 人工填 |
| ② | `page_text.json`（sidecar） | `_build_page_text.py` 抽页时写入 |
| ③ | `Batch2_PDF_PROVENANCE.csv` | `_build_provenance.py` 从 ② 摊平 |

三方独立生成、互相比对，任一处被单独改过都会露馅。

**B. PDF 实算哈希**（PDF 模式）——从原件重算 SHA-256 与 sidecar 比对，
**不符直接 ERROR，不再继续核页内文字**。哈希在这一步是门禁，不是注释。

自测里专门有一例：复制真 PDF、尾部追加 20 字节（PDF 仍能正常解析、页内文字一个没变），
要求验证器落 ERROR 且输出含"哈希不符"。实测通过。这一例说明，只要语料被动过，
整批行立刻失效。

## 3. 去硬编码路径

上一版脚本里写着 `E:\workspace\IcPdfParser\data\pdfs`，解压到别的机器就跑不了。
v1.4 全部改为运行时传入，`grep -rn "E:\\\\workspace" --include=*.py .` 已无残留：

| 输入 | 传法 |
| --- | --- |
| Gold CSV | `--csv`（默认同目录 `Batch2_GOLD_v1.csv`） |
| PDF 目录 | `--pdf-dir` → `ICPDF_PDF_DIR` → `./pdfs` 三级回退 |
| sidecar | `--page-text`（默认同目录 `page_text.json`） |
| 溯源表 | `--provenance`（默认同目录 `Batch2_PDF_PROVENANCE.csv`） |

干净解压包直接可跑：带 PDF 走 PDF 模式，不带 PDF 退到 sidecar，两种模式结论一致。

## 4. 自测：14 → 21 → 22 例

本轮在 v1.3 的 21 例基础上补了审稿人指定的两个负面用例，现在是
**16 例真实 Gold/真实页文本 + 5 例合成页文本（V900）+ 1 例篡改 PDF = 22 例，22/22 通过**。

| 用例 | 标注 | 期望 | 实测 |
| --- | --- | --- | --- |
| 合成页只有 `-2.5` | `±2.5` | **ERROR**（缺正号） | ERROR |
| 合成页写 `±2.5` | `±2.5` | OK | OK |
| 合成页 `+2.5` 与 `-2.5` 分列 | `±2.5` | OK | OK |
| 合成页 `-0.5` `7` 分列、无分隔符 | `-0.5 to 7` | **ERROR**（无区间结构） | ERROR |
| 合成页写 `-0.5 to 7` | `-0.5 to 7` | OK | OK |
| **真 PDF 尾部追加字节** | 原来 OK 的行 | **ERROR（提示哈希不符）** | ERROR |

另外几类仍在守：参数名被截断成残词 → SUSPECT、把条件当参数名 → SUSPECT、
数值写公式/纯文字 → ERROR、整行重复 → SUSPECT、`CONFIRMED` 没签名 → ERROR、
单位页面上没有 → ERROR、型号与溯源不一致 → ERROR、空符号未裁定 → SUSPECT、裁定码拼错 → ERROR。

## 5. `_freeze_gold.py` 的措辞纠正

上一版 README 写它是"唯一真源"，不准确——脚本实际是**读 CSV → 生成 XLSX**，
CSV 才是输入。现已改为：

> **CSV 是输入真源，脚本据此生成 XLSX 并逐格比对。**

脚本只读不写 CSV；生成后回读 XLSX 逐格比对，不一致即非零退出。
本轮实测：`输入 Batch2_GOLD_v1.csv：24 行 / 6 样本 / SHA-256 68d46f6d8fbad159…`
→ `输出 Batch2_GOLD_v1.xlsx，逐格比对：全部一致`。

## 6. 为什么每轮都是两个 SHA

| SHA | 是什么 | 新增内容 |
| --- | --- | --- |
| `9097ed6` | v1.4 数据提交 | 11 个文件：CSV/XLSX、机检 v1.4、5 个脚本、双模式报告、README |
| `a87ba4a` | 它的**子提交** | 只加 `git_evidence_v14.txt`(155 行) + 更新 `git_evidence_commit_chain.txt` |

原因是 4 条指定命令里有一条 `git status --porcelain=v1`。若把证据文件写进工作区再采集，
status 会显示未跟踪的 `git_evidence_*.txt`——等于自己把自己忽略掉。所以先在数据提交上
清空工作区、把证据写到 worktree 之外，采到真正的空 status，再单独提交证据文件。

`git_evidence_commit_chain.txt` 用三条互相印证的原始输出固定关系：
`git cat-file -p <子>` 的 `parent` 行、`git rev-parse <子>^`、`git merge-base --is-ancestor`；
再用 `git diff --stat` 证明子提交只差证据文件。v1.2、v1.3、v1.4 三轮都在同一份文件里。

## 7. 复核命令

```bash
python validate_annotation.py --csv Batch2_GOLD_v1.csv                  # 离线：OK=24
python validate_annotation.py --csv Batch2_GOLD_v1.csv --pdf-dir <PDF>  # PDF：OK=24 + 实算哈希已比对
python _selftest_validator_v2.py                                        # 22/22
ICPDF_PDF_DIR=<PDF> python _selftest_validator_v2.py                    # 含篡改 PDF 那一例
python _freeze_gold.py                                                  # CSV → XLSX 逐格比对：全部一致
sha256sum -c SHA256SUMS.txt
```

## 已知局限（未变，且本轮又添一条）

1. 型号核对只判"封面上有没有这串字"，拦不住近亲型号（ADC3541 就印在 ADC3544 手册里）。
   溯源一致性只保证"三处写的是同一个型号"，不保证"这个型号是对的"。
2. 单位核对是"出现在页面上"级别，`A` 这种单字母单位正文里随便一个 "a" 就能命中。
3. 参数名语义判不了：`VNEG_IN_x` 只能提示"全大写带下划线、疑似引脚名"。
4. **数值归属判不了**——V162 的 96 mA 是靠人眼看表头才发现的，机检只认"页面上有 128"。
   这条是本轮新增的自觉：哈希能保证"文件没换"，保证不了"读的是对的列"。
5. `confidence_score` 是纯 det 分，未校准，不能当准确率上界。
6. 本批 24 行不得外推到 28 件全集。
