# Gate 6A · Batch 2 Gold Set（v1.3）

## 这批是什么

6 件样本、**24 行**电气参数，全部经人工逐行比对 PDF 页面后签名
（`row_status=CONFIRMED`，`reviewer=wuxiaoxian`）。
PDF 原件另有 SHA-256 与页数留痕，见 `Batch2_PDF_PROVENANCE.csv`。

## 一、样本身份：以 PDF 封面为准，不看文件名

| 样本 | 文件名（语料里的订购码） | 封面原文型号 | 本批 `device_model` | 行数 |
| --- | --- | --- | --- | --- |
| V101 | `CD74HCT574EE4__schs183c.pdf` | CD54/74HC374 … **CD54/74HCT574** | `CD74HCT574` | 9 |
| V097 | `DEM-OPA-MSOP-2A__opa2830.pdf` | **OPA2830** Dual, Low-Power, Wideband Op Amp | `OPA2830` | 3 |
| V162 | `74LVTH182504APMG4__sn74lvth18504a.pdf` | SN54LVTH18504A…**SN74LVTH182504A** | `SN74LVTH182504A` | 3 |
| V349 | `ADC3544IRSBT__adc3544.pdf` | **ADC3544** 14-bit, 125-MSPS ADC | `ADC3544` | 3 |
| V145 | `DAC8775IRWFR__dac8775.pdf` | **DAC8775** Quad-Channel, 16-Bit DAC | `DAC8775` | 3 |
| V111 | `DS90C189TWRTDTQ1__ds90c189-q1.pdf` | **DS90C189-Q1** RGB-to-Open LDI Bridge | `DS90C189-Q1` | 3 |

三条容易踩的坑：

1. **文件名前缀是订购码，不是芯片型号**。`DEM-OPA-MSOP-2A` 是评估板编号，手册讲 OPA2830；
   `74LVTH182504APMG4` 是 182504A 的订购码，手册把 18504A / 182504A 印在同一份里。
2. **旧 CSV 的文件名被截断过**：`DAC8775IRWFR.pdf`、`DS90C189TWRTDTQ1.pdf` 都丢了
   `__<手册名>.pdf` 后缀。现按磁盘真实名改正，脚本会断言文件存在。
3. **`ADC3541` 确实印在 ADC3544 手册第 1 页**——在 Device Comparison 表里作为同族型号。
   所以"封面上有这串字"证明不了身份，型号判定以**标题行**为准，截图全部框标题。

## 二、PDF 溯源：6 件原件逐一留痕

| 样本 | 型号 | 文件 | 页数 | 大小 | SHA-256（前 16 位） |
| --- | --- | --- | --- | --- | --- |
| V097 | OPA2830 | `DEM-OPA-MSOP-2A__opa2830.pdf` | 52 | 2.07 MB | `0165370d5ffbabba` |
| V101 | CD74HCT574 | `CD74HCT574EE4__schs183c.pdf` | 21 | 1.17 MB | `059d448c5a34a4b1` |
| V111 | DS90C189-Q1 | `DS90C189TWRTDTQ1__ds90c189-q1.pdf` | 39 | 2.25 MB | `0c31c316536a2156` |
| V145 | DAC8775 | `DAC8775IRWFR__dac8775.pdf` | 80 | 7.51 MB | `099d8e430da67530` |
| V162 | SN74LVTH182504A | `74LVTH182504APMG4__sn74lvth18504a.pdf` | 43 | 0.86 MB | `025966b873cd942a` |
| V349 | ADC3544 | `ADC3544IRSBT__adc3544.pdf` | 75 | 3.42 MB | `095874fb14061c23` |

完整 64 位哈希在 `Batch2_PDF_PROVENANCE.csv`（也写进了 XLSX 的 `pdf_provenance` 页），
同时作为 `sha256` / `page_count` / `size_bytes` 三个字段存进 `page_text.json`，
机检会用它挡掉"页码超出该 PDF 页数"这种错。

留痕的意义：别人拿到同一批语料，`sha256sum` 一比就知道是不是同一份手册；
换了一份修订版，哈希变了，Gold 行也就该重核。

## 三、机检脚本 v2.1：把"只查了一半"也堵上

| 检查 | 旧行为 | 现在 |
| --- | --- | --- |
| 参数名 | 不验 | 必须在本页原文出现；整串→去空白→逐词三级，**带字母边界**（`Input volta` 是 `...input voltage...` 的子串，只用 `in` 会放过去） |
| 数值类型 | 只认第一个数 | 先分类：NUMBER / ±PM / RANGE / FORMULA / WITH_UNIT / TEXT，公式与文字直接 ERROR |
| **±PM** | `±2.5` 只验 `2.5` 出现过；页面上只有 `-2.5` 也能过 | **正负号都要真出现**：要么页面印 `±2.5`，要么 `+2.5` 与 `-2.5` 都在。用带符号的正则，不再复用不限符号的 `num_pattern`（它会把 `-2.5` 里的 `2.5` 当成正数） |
| **RANGE** | 只验两个端点各自在页面上 | 必须匹配 `A to B` / `A ~ B` / `A ... B` / `A - B` 的**完整结构**（允许端点后带单位，真实页面印的是 `-0.5V to 7V`）。两端点分列在两列不算区间 |
| 路径 | 写死 WORKING.csv | 只认 CSV 的 `file_name`；PDF 目录按 `--pdf-dir`→`ICPDF_PDF_DIR`→`./pdfs` 找，都没有就退到 `page_text.json`，**不需要 PyMuPDF** |
| 其他 | — | 型号在第 1 页核对、单位需独立出现（`µA` 里的 A 不算）、整行重复、`CONFIRMED` 必须有签名、页码不得超过 PDF 页数 |

**自测 21 例，21/21 通过**（`_selftest_validator_v2.py`）。其中 5 例跑的是**合成页文本**
（样本 V900），专造"页面只印了一半"的反例：

| 合成页内容 | 标注 | 期望 |
| --- | --- | --- |
| 只有 `-2.5` | `±2.5` | **ERROR** ← 审稿人要求的反例 |
| `±2.5` | `±2.5` | OK |
| `+2.5` 与 `-2.5` 分列 | `±2.5` | OK |
| `-0.5` `7` 分列、无 `to` | `-0.5 to 7` | **ERROR** ← 第二个反例 |
| `-0.5 to 7` | `-0.5 to 7` | OK |

## 四、人工裁定：3 条空 symbol 已定性，不再是 SUSPECT

`Slew rate`、`Settling time to 0.1%`、`Current Flowing into VSENSEP` 三个参数，
手册上只印名字、不印符号。CSV 新增 `human_adjudication` 列，这三行填：

```
human_adjudication = ACCEPTED_SOURCE_HAS_NO_SYMBOL
```

机检见到这个裁定码就放行并单独列一节，**OK=24、SUSPECT=0、ERROR=0**；
裁定码写错（比如 `BOGUS`）或空符号却没填裁定，仍会报错——"没查"和"查过、源头确实没有"必须能区分。

## 五、CSV 与 XLSX 同源

`_freeze_gold.py` 是唯一真源：一个 rows 同时写 CSV 和 XLSX，写完回读**逐格比对**，
不等就非零退出。XLSX 三个页签：`Gold`（数据）、`meta`（源 CSV 的 SHA-256 与行数）、
`pdf_provenance`（6 件 PDF 的溯源）。改动请改脚本，直接改表会被对账发现。

## 六、提交链：为什么是两个 SHA

- `2725f90` —— **数据提交**：Gold 24 行、机检 v2、截图、全部脚本
- `2c7881b` —— 它的**子提交**，只新增 `git_evidence_gate6a.txt` 一个文件（`git diff --stat` 可验）

拆两个的原因：4 条指定命令里有一条是 `git status --porcelain=v1`。若把证据文件写进工作区再采集，
status 会显示 `?? git_evidence_gate6a.txt`，等于自己把自己忽略掉。所以先在 `2725f90` 上清空工作区、
把证据写到 worktree 之外，采到真正的空 status，再单独提交证据文件。

原始输出见 `git_evidence_commit_chain.txt`：`git cat-file -p 2c7881b` 的 `parent` 行、
`git rev-parse 2c7881b^`、`git merge-base --is-ancestor` 三条互为印证。

## 七、跑一遍

```bash
python validate_annotation.py --csv Batch2_GOLD_v1.csv          # 离线：OK=24
python validate_annotation.py --csv Batch2_GOLD_v1.csv --pdf-dir /path/to/pdfs
python _selftest_validator_v2.py                                # 自测：21/21
python _freeze_gold.py                                          # 重新生成 CSV/XLSX 并逐格比对
```

## 八、已知局限

1. **型号核对只判"封面上有没有这串字"**。ADC3541 就印在 ADC3544 手册里，拦不住近亲型号，
   必须看图（`screenshots/` 六张封面）。
2. **单位核对是"出现在页面上"级别**。`A` 这种单字母单位，正文里随便一个 "a" 就能命中。
3. **参数名的语义判断不了**。`VNEG_IN_x` 这类引脚名，机检只能提示"全大写带下划线、疑似引脚名"。
4. `confidence_score` 是纯 det 分（VLM 自报恒为 1.00），未校准，不能当准确率上界。
5. 分母口径未变：准确率 = Gold `CONFIRMED` 行；漏提取分母 = Gold 应有总数；
   错提取分母 = Parser 输出候选总数。本批不得外推到 28 件全集。

## 九、文件

| 文件 | 说明 |
| --- | --- |
| `Batch2_GOLD_v1.csv` | 交付 Gold，24 行，UTF-8 带 BOM，含 `device_model` / `human_adjudication` |
| `Batch2_GOLD_v1.xlsx` | 同源 Excel：`Gold` + `meta` + `pdf_provenance` 三页 |
| `Batch2_PDF_PROVENANCE.csv` | 6 件 PDF 的 SHA-256 / 页数 / 大小 |
| `page_text.json` | 第 1 页 + 证据页原文 + 溯源字段，供离线机检 |
| `validate_annotation.py` | 机检 v2.1 |
| `_selftest_validator_v2.py` | 自测 21 例（含 5 例合成反例） |
| `_freeze_gold.py` | CSV/XLSX 同源生成 + 逐格比对 |
| `_build_page_text.py` / `_build_provenance.py` | 抽页原文 / 生成溯源表 |
| `_shots_batch2.py` + `screenshots/` | 8 张证据图（6 封面 + V101 5.9） |
| `git_evidence_gate6a.txt` | 4 条指定命令的原始输出 |
| `git_evidence_commit_chain.txt` | 2725f90 与 2c7881b 的父子关系 |
| `validation_report.txt` / `selftest_report.txt` | 机检与自测的终端原始输出 |
| `Batch2_DRAFT_FIXED.csv` | 82 行机器草稿，Gold 的筛选来源 |
| `_build_batch2_interactive.py` / `_b2_app.js` | 圈选台生成器与前端 |
| `_draft_extract.py` / `_vl_extract.py` | 草稿提取 / VLM 预标注 |
| `_build_batch2_viewer.py` | 早期实现，留作对照 |
