# Batch 2 复审包 v1.2 · 入口

Gate 6A Batch 2 Gold Set 第三次送审。上一轮（v1.1）只改了 V101 的拆行，本轮处理 Reviewer
新指出的**身份、脚本、同源、提交**四类问题，并把证据做全。

- 代码仓：`[REDACTED-INTERNAL-REPO]`
- 送审分支：`feat/gate6a-annotation`，tip `2c7881b`
- 数据提交：`2725f90`（Git 证据就是对着这个提交跑的）
- `main` 未动，仍为 `853a80d`

## 先看这五个

| 顺序 | 文件 | 看什么 |
| --- | --- | --- |
| 1 | `Batch2_Gate6A_README.md` | 身份纠正、机检改造、局限 |
| 2 | `screenshots/` | 6 张封面 + V101 第 3 页 5.9 圈选 |
| 3 | `Batch2_GOLD_v1.csv` | 24 行交付数据（UTF-8 BOM） |
| 4 | `git_evidence_gate6a.txt` | 你指定 4 条命令的原文与空 status |
| 5 | `selftest_report.txt` | 机检脚本 14 例自测，14/14 |

## 意见 1：V349 / V145 身份 —— 已按封面纠正

翻开 PDF 第 1 页核过，README 里 **4 处型号写错**：

| 样本 | 旧写法 | 封面实际 | 证据图 |
| --- | --- | --- | --- |
| V349 | ADC3541 | **ADC3544** 14-bit, 125-MSPS | `V349_cover_ADC3544.png` |
| V145 | DAC7750 | **DAC8775** Quad-Channel, 16-Bit | `V145_cover_DAC8775.png` |
| V097 | DEM-OPA | **OPA2830**（DEM-OPA-MSOP-2A 是评估板号） | `V097_cover_OPA2830.png` |
| V162 | SN74LVTH18504A | **SN74LVTH182504A**（订购码 74LVTH182504APMG4） | `V162_cover_SN74LVTH182504A.png` |

另两件只是写法不统一，已规范：V111 → `DS90C189-Q1`，V101 → `CD74HCT574`。

顺带修掉两个**被截断的文件名**（照原名根本找不到文件）：
`DAC8775IRWFR.pdf` → `DAC8775IRWFR__dac8775.pdf`、
`DS90C189TWRTDTQ1.pdf` → `DS90C189TWRTDTQ1__ds90c189-q1.pdf`。

需要提请注意的一点：**`ADC3541` 确实印在 ADC3544 手册第 1 页**——在 Device Comparison
表里作为同族型号列出。所以"封面上有这串字"证明不了身份，判定一律以**标题行**为准，
这也是全部截图都框在标题上的原因。

## 意见 2：validate_annotation.py 重构 —— 三处漏判已堵

| 漏洞 | v1 | v2 |
| --- | --- | --- |
| 不验参数名 | 只验 symbol | `parameter_name` 必须在本页原文出现；整串→去空白→逐词三级，带字母边界（`Input volta` 是 `...input voltage...` 的子串，只用 in 判断会放过去） |
| 数值只认第一个数 | `±2.5` 只验 `2.5`；`-0.5 to 7` 只验左端；`VCC-0.2` 抠出 `-0.2` | 先分类：NUMBER / ±PM / RANGE / FORMULA / WITH_UNIT / TEXT。`±` 要求正负号写法、范围要求两端点、公式与文字直接 ERROR |
| 路径写死 | 依赖 `Gold_Set_v1.1_WORKING.csv` 的绝对路径 | 只认 CSV 的 `file_name`；PDF 目录按 `--pdf-dir`→`ICPDF_PDF_DIR`→`./pdfs` 找，都没有就退到随包 `page_text.json`，**不需要 PyMuPDF** |

新增检查：型号在第 1 页核对（能还原 `CD54/74HCT574` 这类族名写法）、单位必须独立出现
（`µA` 里的 A 不算）、整行完全重复、`CONFIRMED` 必须有签名。

复核命令（在本目录直接可跑，无需 PDF、无需改路径）：

```bash
python validate_annotation.py --csv Batch2_GOLD_v1.csv     # 离线：OK=21 SUSPECT=3 ERROR=0
python _selftest_validator_v2.py                           # 自测：14/14 通过
sha256sum -c SHA256SUMS.txt
```

## 意见 3：24 行版本固化 —— CSV 与 XLSX 同源

`_freeze_gold.py` 是唯一真源：一个 rows 同时写 CSV 和 XLSX，写完立刻回读**逐格比对**，
不等就非零退出。XLSX 的 `meta` 页记录源 CSV 的 SHA-256 和行数，改表不改脚本会被对账发现。

```
CSV 行数 24，样本 6 件
CSV/XLSX 逐格比对：全部一致
```

## 意见 4：重新提交 —— 只动分支，工作区干净

`2725f90` 把准备目录里所有未跟踪（Batch1/Batch2 的表格、脚本、文档、截图）和已修改
（Gold、README、机检脚本）的文件整理入库，共 75 个文件；`2c7881b` 只补 Git 证据。
`.gitignore` 排除了可重跑的全量扫描快照（3.3 MB）、`__pycache__`、上传目录与历史备份。

`git status --porcelain=v1` 在证据里是**真空**——证据文件当时写在 worktree 之外，
不是把自己忽略了。`git merge-base origin/main 2725f90` = `853a80d`，与 main tip 一致。

## 意见 5：截图与打包

`screenshots/` 8 张，全部由 `_shots_batch2.py` 用 PDF 词坐标定位后画框，说明文字接在图片下方
（不往页面上叠字，避免盖住被证明的对象）：

- `V101_p3_full_5.9.png` —— 第 3 页整页，红框 5.9、蓝框 VCC=6 行
- `V101_p3_VOH_zoom.png` —— VOH 三行放大：2V→1.9 / 4.5V→4.4 / 6V→5.9
- 其余 6 张为封面型号

`Batch2_Gate6A_review.zip` 是本目录全部交付物的打包副本，`SHA256SUMS.txt` 给出校验和。

## 机检为什么还有 3 条 SUSPECT

`Slew rate`、`Settling time to 0.1%`、`Current Flowing into VSENSEP` 三个参数手册只印名字、
不印符号，`symbol` 列只能留空。不是错，是否需要补符号请 Reviewer 定。

## 已知局限（v1.2 新增两条）

1. 型号核对只判"封面上有没有这串字"，拦不住近亲型号（ADC3541 就在 ADC3544 手册里）。
2. 单位核对是"出现在页面上"级别：`A` 这种单字母单位，正文里任意一个 "a" 就能命中。
3. 参数名的语义判断不了：`VNEG_IN_x` 这类引脚名机检只能提示"全大写带下划线、疑似引脚名"。
4. `confidence_score` 是纯 det 分，未校准，不能当准确率上界。
5. 本批 24 行不得外推到 28 件全集。
