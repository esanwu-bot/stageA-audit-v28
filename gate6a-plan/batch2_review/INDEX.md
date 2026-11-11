# Batch 2 复审包 v1.3 · 入口

Gate 6A Batch 2 Gold Set 第四次送审。24 行数据已获认可，本轮只收尾五项工程细节：
**验证器逻辑、PDF 溯源、SUSPECT 裁定、提交说明、重新打包**。

- 代码仓：`[REDACTED-INTERNAL-REPO]`
- 送审分支：`feat/gate6a-annotation`
  - `2725f90` 数据（v1.2）
  - `2c7881b` 证据子提交
  - `5f5cc29` 本轮修正（v1.3）
  - `db785b7` 本轮证据子提交（分支 tip）
- `main` 未动，仍为 `853a80d`

## 先看这五个

| 顺序 | 文件 | 看什么 |
| --- | --- | --- |
| 1 | `Batch2_Gate6A_README.md` | 身份、溯源、机检、裁定、局限 |
| 2 | `selftest_report.txt` | **21 例自测，21/21**，含两个反例 |
| 3 | `validation_report.txt` | Gold 24 行：**OK=24 / SUSPECT=0 / ERROR=0** |
| 4 | `Batch2_PDF_PROVENANCE.csv` | 6 件 PDF 的 SHA-256 与页数 |
| 5 | `git_evidence_commit_chain.txt` | 为什么有两个 SHA |

## 1. 验证器逻辑：PM 与 RANGE 的两处漏判

### PM（± 值）

旧实现复用不限符号的正则，`±2.5` 只要求页面上出现过 `2.5`。问题在于 `-2.5` 里也含 `2.5`，
于是**页面只有负值时也会放行**。现在改为带符号的两条路径：

- 页面印 `±2.5` → OK
- 页面分列 `+2.5` 与 `-2.5` → 两边都必须在；缺哪边就报"缺正号 / 缺负号"

### RANGE（区间）

旧实现只验两个端点各自在页面上出现过。表格里 `-0.5` 和 `7` 分处两列同样满足，
但那不是一个区间。现在要求**完整结构**：`A to B` / `A ~ B` / `A ... B` / `A - B`，
并允许端点后带单位（真实页面印的是 `-0.5V to 7V`，正是这个细节让第一版结构匹配漏掉了）。

### 反例测试（审稿人指定）

自测从 14 例扩到 21 例，其中 5 例用**合成页文本**（样本 V900）专造反例：

| 合成页上写的是 | 标注 | 判定 |
| --- | --- | --- |
| 只有 `-2.5` | `±2.5` | **ERROR**（缺正号） |
| `±2.5` | `±2.5` | OK |
| `+2.5` 与 `-2.5` 分列 | `±2.5` | OK |
| `-0.5` `7` 分列、无分隔符 | `-0.5 to 7` | **ERROR**（无区间结构） |
| `-0.5 to 7` | `-0.5 to 7` | OK |

另外补了两例裁定相关：空符号但没填裁定码 → SUSPECT；裁定码写成 `BOGUS` → ERROR。

## 2. PDF 溯源

| 样本 | 型号 | 页数 | 大小 | SHA-256（前 16 位） |
| --- | --- | --- | --- | --- |
| V097 | OPA2830 | 52 | 2.07 MB | `0165370d5ffbabba` |
| V101 | CD74HCT574 | 21 | 1.17 MB | `059d448c5a34a4b1` |
| V111 | DS90C189-Q1 | 39 | 2.25 MB | `0c31c316536a2156` |
| V145 | DAC8775 | 80 | 7.51 MB | `099d8e430da67530` |
| V162 | SN74LVTH182504A | 43 | 0.86 MB | `025966b873cd942a` |
| V349 | ADC3544 | 75 | 3.42 MB | `095874fb14061c23` |

完整 64 位在 `Batch2_PDF_PROVENANCE.csv`，同一份数据也进了 XLSX 的 `pdf_provenance` 页。
`page_text.json` 每个样本节点新增 `sha256` / `page_count` / `size_bytes` 三个字段，
机检用 `page_count` 挡"页码越界"这类错。

## 3. SUSPECT 的人工裁定

三条空符号（`Slew rate`、`Settling time to 0.1%`、`Current Flowing into VSENSEP`）
在手册上确实只印名字，不印符号。CSV 新增 `human_adjudication` 列，三行填：

```
ACCEPTED_SOURCE_HAS_NO_SYMBOL
```

机检见此码放行，并在报告里单列"人工裁定"一节。报告现在 **OK=24 / SUSPECT=0 / ERROR=0**。
反向也留了门：空符号却没填裁定码 → SUSPECT；裁定码拼错 → ERROR。
这样"没查"和"查过、源头确实没有"永远能分开。

## 4. 为什么是两个 SHA

| SHA | 是什么 | 新增内容 |
| --- | --- | --- |
| `2725f90` | 数据提交 | Gold 24 行、机检 v2、截图、全部脚本 |
| `2c7881b` | 它的**子提交** | 只加 `git_evidence_gate6a.txt` 一个文件 |

原因是 4 条指定命令里有一条 `git status --porcelain=v1`。若把证据文件写进工作区再采集，
status 会显示 `?? git_evidence_gate6a.txt`——等于自己把自己忽略掉。所以先在 `2725f90` 上
清空工作区、把证据写到 worktree 之外，采到真正的空 status，再单独提交证据文件。

`git_evidence_commit_chain.txt` 用三条互相印证的原始输出固定这个关系：
`git cat-file -p 2c7881b` 的 `parent` 行、`git rev-parse 2c7881b^`、
`git merge-base --is-ancestor 2725f90 2c7881b`。`git diff --stat 2725f90 2c7881b` 显示只差一个文件。

v1.3 沿用同一做法：`5f5cc29` 数据、`db785b7` 证据，`git_evidence_v13.txt` 里有完整记录。

## 5. 复核命令

```bash
python validate_annotation.py --csv Batch2_GOLD_v1.csv     # OK=24 SUSPECT=0 ERROR=0
python _selftest_validator_v2.py                           # 21/21
python _freeze_gold.py                                     # CSV/XLSX 逐格比对：全部一致
sha256sum -c SHA256SUMS.txt
```

## 已知局限（未变）

1. 型号核对只判"封面上有没有这串字"，拦不住近亲型号（ADC3541 就印在 ADC3544 手册里）。
2. 单位核对是"出现在页面上"级别，`A` 这种单字母单位正文里随便一个 "a" 就能命中。
3. 参数名语义判不了：`VNEG_IN_x` 只能提示"全大写带下划线、疑似引脚名"。
4. `confidence_score` 是纯 det 分，未校准，不能当准确率上界。
5. 本批 24 行不得外推到 28 件全集。
