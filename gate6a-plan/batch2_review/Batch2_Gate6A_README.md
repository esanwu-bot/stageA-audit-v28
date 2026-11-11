# Gate 6A · Batch 2 Gold Set（v1.5）

## 这批是什么

6 件样本、**24 行**电气参数，全部经人工逐行比对 PDF 页面后签名
（`row_status=CONFIRMED`，`reviewer=wuxiaoxian`）。
PDF 原件另有 SHA-256 与页数留痕，见 `Batch2_PDF_PROVENANCE.csv`。

v1.4 把"数据自己说的身份"和"PDF 原件"绑死了；v1.5 修的是另一类问题：
**该报错的地方没报错**。四处 Fail-Open——溯源表读不到只提示一句、空字段直接跳过互校、
`--pdf-dir` 指不到就悄悄换数据源、哈希不符还接着核页内文字——全部改成硬失败。
数据一行没动，24 行结论仍是 OK=24。

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
同时作为 `sha256` / `page_count` / `size_bytes` 三个字段存进 `page_text.json`。

留痕的意义：别人拿到同一批语料，`sha256sum` 一比就知道是不是同一份手册；
换了一份修订版，哈希变了，Gold 行也就该重核。v1.4 起这不是"留个记录"，
而是**机检的前置门禁**——哈希不符，这一行连页内文字都不核，直接 ERROR。

## 三、V162 的 96 mA：一个被抓住的真实错配

`Current into any output in the low state` 这行原来填 `max_value=96`，单位 mA。
96 mA 是 **SN54LVTH182504A**（军温档）的值；本批样本是 **SN74**LVTH182504A（商用档），
手册同一张表的 SN74 列写的是 128 mA（A 端口 / TDO），B 端口另印 30 mA。

| 字段 | 旧 | 新 |
| --- | --- | --- |
| `max_value` | `96` | `128` |
| `condition` | （空） | `SN74LVTH182504A, A port or TDO` |
| `notes` | — | 记录"96 mA 属 SN54 系列；B 端口另印 30 mA，本行不单列" |

把温度档/端口条件写进 `condition` 之后，这行才叫"核对过"，而不是"抄了个像的值"。
这也说明一件事：数值在页面上出现，不等于它是**这一行**的值——同一个数字可能属于邻列、邻档、
邻型号。机检能验"存在"，验不了"归属"，所以 `condition` 必须写清。

## 四、机检脚本 v1.5：把"只查了一半"和"查错了对象"都堵上

| 检查 | 旧行为 | 现在（v1.5） |
| --- | --- | --- |
| **溯源一致性** | 无 | CSV ↔ sidecar 比 `file_name`/`device_model`；sidecar ↔ provenance 比 `file_name`/`device_model`/`sha256`/`page_count`。**任一侧为空或两侧不等都算 ERROR** |
| **PDF 实算哈希** | 无 | PDF 模式从原件重算 SHA-256，与 sidecar 不符 → **ERROR**，且该样本**不再读页内文字** |
| 参数名 | 不验 | 必须在本页原文出现；整串→去空白→逐词三级，**带字母边界**（`Input volta` 是 `...input voltage...` 的子串，只用 `in` 会放过去） |
| 数值类型 | 只认第一个数 | 先分类：NUMBER / ±PM / RANGE / FORMULA / WITH_UNIT / TEXT，公式与文字直接 ERROR |
| **±PM** | `±2.5` 只验 `2.5` 出现过；页面上只有 `-2.5` 也能过 | **正负号都要真出现**：要么页面印 `±2.5`，要么 `+2.5` 与 `-2.5` 都在。用带符号的正则，不再复用不限符号的 `num_pattern`（它会把 `-2.5` 里的 `2.5` 当成正数） |
| **RANGE** | 只验两个端点各自在页面上 | 必须匹配 `A to B` / `A ~ B` / `A ... B` / `A - B` 的**完整结构**（允许端点后带单位，真实页面印的是 `-0.5V to 7V`）。两端点分列在两列不算区间 |
| 路径 | 写死绝对路径 `E:\workspace\...` | 零硬编码：CSV 走 `--csv`，PDF 目录按 `--pdf-dir`→`ICPDF_PDF_DIR`→`./pdfs` 三级回退，sidecar/provenance 也都能 `--page-text` / `--provenance` 指定。干净解压包直接能跑 |
| 其他 | — | 型号在第 1 页核对、单位需独立出现（`µA` 里的 A 不算）、整行重复、`CONFIRMED` 必须有签名、页码不得超过 PDF 页数 |

### v1.5 修的 4 处 Fail-Open

Fail-Open 是"本该报错却没报错"，比"漏查一项"更危险：报告还是绿的，人却以为查过了。

| # | 漏洞 | v1.4 的表现 | v1.5 的做法 |
| --- | --- | --- | --- |
| F1 | 溯源表读不到 | `notes.append` 一句"跳过三处互校"就继续，等于第三方参照丢了还照常出 OK=24 | 抛 `FatalInput` → `[ERROR]` + **退出码 2**，拒绝出报告 |
| F2 | 空字段跳过互校 | `if a and b and a != b`：任一侧为空就整条跳过，"缺"被当成"无所谓" | 统一成 `if not a or not b or a != b → ERROR`，并写死字段对应关系 |
| F3 | PDF 缺失静默降级 | `--pdf-dir` 不存在 / 文件不在 / 打不开，都掉头去读 sidecar，只多一行提示 | 显式给了 `--pdf-dir`（或 `ICPDF_PDF_DIR`）却不可用 → 退出码 2；目录在但文件缺/打不开/算不了哈希 → 该样本 ERROR。**任何情况下不再自动换源** |
| F4 | 哈希不符仍读文本 | 哈希不符混进 `prov_issues` 后，行循环照样调 `page_text()` | 发现不符即入 `hash_bad`，该样本所有行 ERROR 并 `continue`，**在 `page_text()` 之前短路** |

F4 的自证方式值得单独说：自测最后一例把 `Pages.page_text` 换成计数器，在同一进程里跑
`main()`，断言调用次数为 **0**。否则"哈希不符就不读页文本"只是一句承诺，没人能验。

另外，字段对应关系在报告里直接印出来，不用读者猜：

```
字段对应：CSV↔sidecar 比 file_name/device_model；
          sidecar↔provenance 比 file_name/device_model/sha256/page_count
判据：任一侧为空 或 两侧不等 → ERROR（空字段不再当作“跳过”）
```

**自测 30 例，30/30 通过**（`_selftest_validator_v2.py`）：16 例跑真实 Gold 行与真实页文本，
5 例跑**合成页文本**（样本 V900）专造"页面只印了一半"的反例，1 例篡改 PDF 验哈希门禁，
8 例是 v1.5 新增的 Fail-Open 负面用例。

| 用例 | 标注 | 期望 | 实测 |
| --- | --- | --- | --- |
| 合成页只有 `-2.5` | `±2.5` | **ERROR** | ERROR |
| 合成页写 `±2.5` | `±2.5` | OK | OK |
| 合成页 `+2.5` 与 `-2.5` 分列 | `±2.5` | OK | OK |
| 合成页 `-0.5` `7` 分列、无 `to` | `-0.5 to 7` | **ERROR** | ERROR |
| 合成页写 `-0.5 to 7` | `-0.5 to 7` | OK | OK |
| 真 PDF 尾部追加字节 | 原来 OK 的行 | **ERROR（提示哈希不符）** | ERROR |

第 6 例是关键：它证明溯源检查是**门禁**而不是注释——PDF 被动过一个字节，整批行立刻落 ERROR，
哪怕页内文字一个都没变。

8 个 Fail-Open 负面用例（`N1`–`N8`），每一例都断言"报错"，而且还要断言输出里没有那句自我安慰：

| # | 构造的坏输入 | 期望 | 实测 |
| --- | --- | --- | --- |
| N1 | `--provenance` 指向不存在的文件 | 退出码 2 + `[ERROR]`，且**不含**"跳过三处互校" | 达标 |
| N2 | sidecar 的 `file_name` 置空 | ERROR（空字段不再跳过） | ERROR |
| N3 | CSV 的 `device_model` 置空 | ERROR | ERROR |
| N4 | provenance 的 `page_count` 置空 | ERROR | ERROR |
| N5 | `--pdf-dir` 指向不存在的目录 | 退出码 2 + `[ERROR]`，且**不含**"使用随包的 page_text.json" | 达标 |
| N6 | PDF 模式 + 目录里没有该样本的 PDF | ERROR（不是 `CANNOT_VERIFY`） | ERROR |
| N7 | 同名路径是目录，哈希算不出来 | ERROR（"无法计算哈希"） | ERROR |
| N8 | 篡改 PDF 触发哈希不符 | 该样本全行 ERROR，且 `page_text()` 调用 **0 次** | 0 次 |

N1、N5 特意加了"不含某句话"的断言——只验"有 ERROR"不够，还要证明它没有再悄悄绕过去。
N8 是唯一跑在同一进程里的用例（换成计数器才能数调用次数），其余都走子进程，看的是真实退出码。

## 五、人工裁定：3 条空 symbol 已定性，不再是 SUSPECT

`Slew rate`、`Settling time to 0.1%`、`Current Flowing into VSENSEP` 三个参数，
手册上只印名字、不印符号。CSV 有 `human_adjudication` 列，这三行填：

```
human_adjudication = ACCEPTED_SOURCE_HAS_NO_SYMBOL
```

机检见到这个裁定码就放行并单独列一节，**OK=24、SUSPECT=0、ERROR=0**；
裁定码写错（比如 `BOGUS`）或空符号却没填裁定，仍会报错——"没查"和"查过、源头确实没有"必须能区分。

## 六、CSV 与 XLSX 的关系

**CSV 是输入真源，脚本据此生成 XLSX 并逐格比对。**

`_freeze_gold.py` 只读 `Batch2_GOLD_v1.csv`，不反向写回；生成 XLSX 后回读**逐格比对**，
不一致就非零退出。XLSX 三个页签：`Gold`（数据）、`meta`（源 CSV 的 SHA-256 与行数）、
`pdf_provenance`（6 件 PDF 的溯源）。这样"表改坏了"和"脚本改坏了"能分开定位：
改数据只动 CSV，改格式只动脚本。

## 七、提交链：为什么是两个 SHA

每轮都是成对提交：

- **数据提交** —— Gold 行、机检脚本、报告、截图、全部脚本
- 它的**子提交** —— 只新增 Git 证据文件一个（`git diff --stat` 可验）

拆两个的原因：指定命令里有一条是 `git status --porcelain=v1`。若把证据文件写进工作区再采集，
status 会显示 `?? git_evidence_*.txt`，等于自己把自己忽略掉。所以先在数据提交上清空工作区、
把证据写到 worktree 之外，采到真正的空 status，再单独提交证据文件。

每轮的父子关系见 `git_evidence_commit_chain.txt`：`git cat-file -p <子提交>` 的 `parent` 行、
`git rev-parse <子提交>^`、`git merge-base --is-ancestor` 三条互为印证。已留证的：

| 轮次 | 数据提交 | 证据子提交 |
| --- | --- | --- |
| v1.2 | `2725f90` | `2c7881b` |
| v1.3 | `5f5cc29` | `db785b7` |
| v1.4 | `9097ed6` | `a87ba4a` |
| v1.5 | 见 `git_evidence_commit_chain.txt` | 见 `git_evidence_commit_chain.txt` |

v1.5 这一对不在这里写死：数据提交的 SHA 要在提交之后才知道，而证据子提交的 SHA
又要等它提交之后才知道——写进同一份文档就会指向一个不存在的对象。
所以改由 `git_evidence_commit_chain.txt`（提交时用 `parent` 行自证）与
审计仓 `INDEX.md`（提交后在仓外补登）分别留证。

## 八、跑一遍

```bash
python validate_annotation.py --csv Batch2_GOLD_v1.csv          # 离线：OK=24，退出码 0
python validate_annotation.py --csv Batch2_GOLD_v1.csv --pdf-dir /path/to/pdfs
python _selftest_validator_v2.py                                # 自测：30/30
ICPDF_PDF_DIR=/path/to/pdfs python _selftest_validator_v2.py    # 含篡改 PDF 与 N8 计数断言
python _freeze_gold.py                                          # CSV → XLSX 并逐格比对
```

`--pdf-dir` 只影响"页文本从哪来"和"哈希能不能实算"，不影响 CSV 读取；
不带 PDF 也能把 24 行全部核完（用随包 `page_text.json`）。

但有一条不一样了：**给了 `--pdf-dir` 就必须能用**。路径不存在、文件不在、打不开、
哈希算不了，一律报错退出，不会再悄悄换成 `page_text.json` 把结论凑绿。
退出码：`0` 无 ERROR，`1` 有 ERROR 行，`2` 判据/环境不可用（拒绝出报告）。

## 九、已知局限

1. **型号核对只判"封面上有没有这串字"**。ADC3541 就印在 ADC3544 手册里，拦不住近亲型号，
   必须看图（`screenshots/` 六张封面）。溯源一致性只保证"三处写的是同一个型号"，
   不保证"这个型号是对的"。
2. **单位核对是"出现在页面上"级别**。`A` 这种单字母单位，正文里随便一个 "a" 就能命中。
3. **参数名的语义判断不了**。`VNEG_IN_x` 这类引脚名，机检只能提示"全大写带下划线、疑似引脚名"。
4. **数值归属判断不了**。V162 的 96 mA 就是靠人眼看表头才发现的；机检只认"页面上有 128"。
5. `confidence_score` 是纯 det 分（VLM 自报恒为 1.00），未校准，不能当准确率上界。
6. 分母口径未变：准确率 = Gold `CONFIRMED` 行；漏提取分母 = Gold 应有总数；
   错提取分母 = Parser 输出候选总数。本批不得外推到 28 件全集。
7. **"关掉 Fail-Open"不等于"全覆盖"**。v1.5 关门的是我们**想到**的四条路径，
   自测只能证明这四条被关上；没被想到的 fail-open 仍然存在。真正的判据是
   每次新增检查时都问一句"它失败的时候，报告会不会还是绿的"。

## 十、文件

| 文件 | 说明 |
| --- | --- |
| `Batch2_GOLD_v1.csv` | 交付 Gold，24 行，UTF-8 带 BOM，含 `device_model` / `human_adjudication` |
| `Batch2_GOLD_v1.xlsx` | 由 CSV 派生：`Gold` + `meta` + `pdf_provenance` 三页 |
| `Batch2_PDF_PROVENANCE.csv` | 6 件 PDF 的 SHA-256 / 页数 / 大小 |
| `page_text.json` | 第 1 页 + 证据页原文 + 溯源字段，供离线机检 |
| `validate_annotation.py` | 机检 v1.5（含溯源三方互校、PDF 实算哈希、4 处 Fail-Open 收紧） |
| `_selftest_validator_v2.py` | 自测 30 例（16 真实 + 5 合成反例 + 1 篡改 PDF + 8 Fail-Open 负面） |
| `_freeze_gold.py` | 读 CSV → 生成 XLSX → 逐格比对 |
| `_build_page_text.py` / `_build_provenance.py` | 抽页原文 / 生成溯源表 |
| `_shots_batch2.py` + `screenshots/` | 8 张证据图（6 封面 + V101 5.9） |
| `git_evidence_*.txt` | 指定命令的原始输出、两轮提交的父子关系证明 |
| `validation_report.txt` / `selftest_report.txt` | 机检（PDF + 离线双模式）与自测的终端原始输出 |
| `Batch2_DRAFT_FIXED.csv` | 82 行机器草稿，Gold 的筛选来源 |
| `_build_batch2_interactive.py` / `_b2_app.js` | 圈选台生成器与前端 |
| `_draft_extract.py` / `_vl_extract.py` | 草稿提取 / VLM 预标注 |
| `_build_batch2_viewer.py` | 早期实现，留作对照 |
