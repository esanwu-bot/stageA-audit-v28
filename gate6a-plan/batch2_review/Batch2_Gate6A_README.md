# Gate 6A · Batch 2 Gold Set（v1.2）

## 这批是什么

6 件样本、**24 行**电气参数，全部经人工逐行比对 PDF 页面后签名
（`row_status=CONFIRMED`，`reviewer=wuxiaoxian`）。

## 一、样本身份：以 PDF 封面为准，不看文件名

Reviewer 指出型号对不上。逐个翻开封面核对后，确认 README 早期版本 **4 处写错**，已全部改正：

| 样本 | 文件名（语料里的订购码） | 封面原文型号 | 本批 `device_model` | 行数 | 旧 README |
| --- | --- | --- | --- | --- | --- |
| V101 | `CD74HCT574EE4__schs183c.pdf` | CD54/74HC374 … **CD54/74HCT574** | `CD74HCT574` | 9 | CD74HCT574 ✓ |
| V097 | `DEM-OPA-MSOP-2A__opa2830.pdf` | **OPA2830** Dual, Low-Power, Wideband Op Amp | `OPA2830` | 3 | ~~DEM-OPA~~ ✗ |
| V162 | `74LVTH182504APMG4__sn74lvth18504a.pdf` | SN54LVTH18504A…**SN74LVTH182504A** | `SN74LVTH182504A` | 3 | ~~SN74LVTH18504A~~ ✗ |
| V349 | `ADC3544IRSBT__adc3544.pdf` | **ADC3544** 14-bit, 125-MSPS ADC | `ADC3544` | 3 | ~~ADC3541~~ ✗ |
| V145 | `DAC8775IRWFR__dac8775.pdf` | **DAC8775** Quad-Channel, 16-Bit DAC | `DAC8775` | 3 | ~~DAC7750~~ ✗ |
| V111 | `DS90C189TWRTDTQ1__ds90c189-q1.pdf` | **DS90C189-Q1** RGB-to-Open LDI Bridge | `DS90C189-Q1` | 3 | ~~DS90C~~ ✗ |

三条容易踩的坑，一并记下来：

1. **文件名前缀是订购码，不是芯片型号**。`DEM-OPA-MSOP-2A` 是评估板编号，手册讲的是 OPA2830；
   `74LVTH182504APMG4` 是 182504A 的订购码，手册把 18504A 和 182504A 印在同一份里。
2. **旧 CSV 的文件名还被截断过**：`DAC8775IRWFR.pdf`、`DS90C189TWRTDTQ1.pdf` 都丢了
   `__<手册名>.pdf` 后缀，照着找文件必然找不到。现按磁盘真实文件名改正，脚本会断言文件存在。
3. **`ADC3541` 确实出现在 ADC3544 手册第 1 页**——在 "Device Comparison" 表里作为同族型号列出。
   所以"封面上有这串字"不足以证明身份，型号判定以**标题行**为准，证据见 `screenshots/`。

封面与关键页截图（红框标出型号原文，说明条在图片下方）：

- `screenshots/V349_cover_ADC3544.png`、`V145_cover_DAC8775.png` —— Reviewer 指定
- `screenshots/V097_cover_OPA2830.png`、`V162_cover_SN74LVTH182504A.png`、
  `V111_cover_DS90C189-Q1.png`、`V101_cover_CD74HCT574E.png`
- `screenshots/V101_p3_full_5.9.png`、`V101_p3_VOH_zoom.png` —— 5.9 的位置

## 二、V101 按 VCC 拆行（上一轮意见，已落地）

第 3 页 `TEST CONDITIONS` 列里的 `2` / `4.5` / `6` 是**三个行条件**，不是三个列头，
所以 MIN/MAX 要按行读，不能按列取。三个参数各拆 3 行，共 9 行，`condition` 填 `HC, VCC=xV`：

| 参数 | VCC=2V | VCC=4.5V | VCC=6V | 取值列 |
| --- | --- | --- | --- | --- |
| VIH（MIN） | 1.5 | 3.15 | 4.2 | MIN |
| VIL（MAX） | 0.5 | 1.35 | 1.8 | MAX |
| VOH（MIN） | 1.9 | 4.4 | **5.9** | MIN |

顺带修正：v1 把 VOH 第三组误写成 4.4（与 4.5V 行重复），实测页面是 **5.9**。

## 三、机检脚本 v2：补上三种漏判

v1 的三个洞，v2 逐个堵：

| 漏洞 | v1 行为 | v2 做法 |
| --- | --- | --- |
| 不验参数名 | 只验 `symbol`，`Input volta`、`VPOS_IN_x` 都能过 | 名字必须在该页原文出现，三级比对（整串 / 去空白 / 逐词），缺词要报出缺哪个 |
| 数值只认第一个数 | `±2.5` 只验 `2.5`；`-0.5 to 7` 只验左端点；`VCC-0.2` 抠出 `-0.2` | 先分类再验：NUMBER / ±PM / RANGE / FORMULA / WITH_UNIT / TEXT；公式、文字、带单位一律 ERROR |
| 路径写死 | 依赖 `Gold_Set_v1.1_WORKING.csv` 里的绝对路径 | 只认 CSV 的 `file_name`；PDF 目录按 `--pdf-dir` → `ICPDF_PDF_DIR` → 同目录 `pdfs/` 找，都找不到就退到随包的 `page_text.json`，此时**不需要 PyMuPDF** |

另外新增：型号在第 1 页核对（含 `CD54/74HCT574` 这类族名还原）、整行完全重复检测、
`CONFIRMED` 必须有 `reviewer` 签名、单位必须是"独立出现"而非 `mA` 里的一截。

自测 14 例（`_selftest_validator_v2.py`），每例埋一个已知的错，**14/14 判定正确**：

```
用例 14，通过 14，失败 0
```

## 四、跑一遍

```bash
# 离线（包里没有 PDF 也能跑，靠 page_text.json）
python validate_annotation.py --csv Batch2_GOLD_v1.csv

# 有 PDF 原件时（能做"这个值到底在哪一页"的建议）
python validate_annotation.py --csv Batch2_GOLD_v1.csv --pdf-dir /path/to/pdfs

# 自测机检本身有没有失效
python _selftest_validator_v2.py
```

本批结果：**OK=21，SUSPECT=3，ERROR=0**。三条 SUSPECT 都是 `symbol` 为空
（Slew rate / Settling time / Current Flowing into VSENSEP 三个参数手册上只给名字、没给符号），
不是错误，已标注待 Reviewer 裁定是否补符号。

原始输出见 `validation_report.txt`（机检）、`selftest_report.txt`（自测）。

## 五、CSV 与 XLSX 同源

两者都由 `_freeze_gold.py` 从同一份 rows 生成，写完立刻回读逐格比对：

```
CSV 行数 24，样本 6 件，SHA-256 6f62d79c…（完整值见 meta 页）
CSV/XLSX 逐格比对：全部一致
```

XLSX 的 `meta` 页记录了源 CSV 的 SHA-256 与行数，改表不改脚本会被对账发现。

## 六、保留下来的四条硬规则

1. 参数名必须能在该页原文里原样搜到，不是模型转述、不是条件、不是残词；
2. `min/typ/max` 只放纯数字（允许 `±` 与 `A to B`），单位一律进 `unit` 列；
3. 单位必须出现在该页；
4. 同一参数若按条件（VCC/温度/负载）分组，按条件拆行、条件写进 `condition`。

初稿 82 行剔除 64 行的理由：残词断句（`Input volta`、`Short-Circuit Durati`）、
把条件当参数名（`VNEG_IN_x`）、数值列塞英文（`Continuous`、`See Thermal Information Table`）、
表达式而非数值（`MIN(2.1, AVDD+0.3)`、`VCC-0.2`）、同参数重复（V349 SNR 5 行、V145 Input voltage 8 行）。

## 七、已知局限

1. **型号核对只判"封面上有没有这串字"**。ADC3541 就印在 ADC3544 手册第 1 页的
   Device Comparison 表里，机检拦不住近亲型号，必须看图。
2. **单位核对是"出现在页面上"级别**。`A` 这种单字母单位，页面正文里随便一个 "a" 就能命中，
   机检不判错；真正要确认单位对不对，看 `unit` 列语境。
3. **参数名的语义判断不了**。`VNEG_IN_x` 这种"引脚名当参数名"，机检只能提示
   "全大写带下划线、疑似引脚名"，是否为条件需人读表。
4. `confidence_score` 是纯 det 分（VLM 自报恒为 1.00，掺进去只会抹平区分度），
   **未经校准**，不能当准确率上界。
5. 分母口径未变：准确率 = Gold `CONFIRMED` 行；漏提取分母 = Gold 应有总数；
   错提取分母 = Parser 输出候选总数。本批不得外推到 28 件全集。

## 八、文件

| 文件 | 说明 |
| --- | --- |
| `Batch2_GOLD_v1.csv` | 交付 Gold，24 行，UTF-8 带 BOM |
| `Batch2_GOLD_v1.xlsx` | 同源 Excel，含 `meta` 对账页 |
| `page_text.json` | 6 件样本第 1 页 + 证据页原文，供离线机检 |
| `validate_annotation.py` | 机检 v2 |
| `_selftest_validator_v2.py` | 机检自测 14 例 |
| `_freeze_gold.py` | CSV/XLSX 同源生成 + 逐格比对 |
| `_build_page_text.py` | 抽取证据页原文 |
| `_shots_batch2.py` | 证据截图（封面 + V101 5.9） |
| `screenshots/*.png` | 8 张证据图 |
| `git_evidence_gate6a.txt` | Reviewer 指定的 4 条 Git 命令原始输出 |
| `validation_report.txt` / `selftest_report.txt` | 机检与自测的终端原始输出 |
| `Batch2_DRAFT_FIXED.csv` | 82 行机器草稿，Gold 的筛选来源 |
| `_build_batch2_interactive.py` / `_b2_app.js` | 圈选台生成器与前端 |
| `_draft_extract.py` / `_vl_extract.py` | 草稿提取 / VLM 预标注 |
| `_build_batch2_viewer.py` | 早期实现，留作对照 |
