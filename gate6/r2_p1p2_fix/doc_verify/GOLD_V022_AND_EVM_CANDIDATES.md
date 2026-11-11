# GOLD_V022_AND_EVM_CANDIDATES

- 生成时间：2026-11-11 08:03（GMT+8）
- 性质：**只读文档核验 + 数据集搜索**。未启动服务、未调用 `parse_pdf()`、未调用 `classify_one()`、未写任何 Run 产物。
- 工具：`workbench/_doc_verify/inspect_pdf_doc.py`（PyMuPDF 只读，仅取元数据与文本层）
- 结论一句话：**V022 是 CC2500 芯片 Datasheet，分类器判 DS_STRONG 是正确的；错的是我们给它贴的"EVM 伪装件"预期标签。** 真正的 EVM 负样本另有所在，已找到 2 份主候选 + 2 份备选。

---

## 任务一：V022 文档级核验

### 1.1 哈希与体量

| 项 | 值 |
| --- | --- |
| 文件 | `E:\workspace\IcPdfParser\data\pdfs\CC2500EMK__cc2500.pdf` |
| SHA-256 | `27364e9593879ec0c098944c46b90e7243a44e5b34e77b6d9ec3a3610ea25ae4` |
| 与探针时对照 | **一致**（探针响应 `validation.sha256` 同值） |
| 大小 | 2,509,323 B（2.39 MiB） |
| 页数 | 99 |
| 文本层字符数 | 203,258（有完整文本层，非扫描件） |

### 1.2 PDF 元数据

| 字段 | 值 |
| --- | --- |
| **Title** | **`Low-Cost Low-Power 2.4 GHz RF Transceiver datasheet (Rev. C)`** |
| **Subject** | **`Data Sheet`** |
| Author | `Texas Instruments, Incorporated [SWRS040,C]` |
| Creator | `SPDF` |
| Producer | `iText 2.1.7 by 1T3XT` |
| CreationDate / ModDate | `D:20260811004229-05'00'` |
| Format | PDF 1.6 |

> 元数据在 Title 和 Subject 两个字段上**同时**声明这是 datasheet，且 Author 里带 TI 文档号 `SWRS040`（CC2500 的 datasheet 号，SWRS 前缀 = 数据手册；用户指南是 SLAU/SLVU/SNLU/DLPU/SPRU 前缀）。

### 1.3 页级结构（99 页的真实构成）

| 页段 | 内容 | 判据 |
| --- | --- | --- |
| p1–p89 | **CC2500 芯片 Datasheet 正文** | 每页页脚 `CC2500 / SWRS040C / Page N of 89` |
| p90–p91 | Package Option Addendum（封装/订购信息） | 页首 `PACKAGE OPTION ADDENDUM` |
| p92–p98 | Package Materials Information（卷带/包装） | 页首 `PACKAGE MATERIALS INFORMATION` |
| p99 | Important Notice and Disclaimer（法务声明） | 页首 `IMPORTANT NOTICE AND DISCLAIMER` |

**关键点**：99 页里 **没有任何一页是 EVM 用户指南**。多出来的 10 页是 TI 所有 datasheet 都会附的标准 addendum，与评估板无关。

### 1.4 首页 / 第 2 页 / 目录页 / 末页文本

**p1（首屏原文节选）**

```
CC2500
SWRS040C
Page 1 of 89
CC2500
Low-Cost Low-Power 2.4 GHz RF Transceiver
Applications
2400-2483.5 MHz ISM/SRD band systems
Consumer electronics
Wireless game controllers
Wireless audio
Wireless keyboard and mouse
RF enabled remote controls
Product Description
The CC2500 is a low-cost 2.4 GHz transceiver designed for very low-power
wireless applications. ...
```

**p2（原文节选）**

```
CC2500
SWRS040C
Page 2 of 89
Programmable Preamble Quality Indicator (PQI) ...
Low-Power Features
400 nA SLEEP mode current consumption
Fast startup time: 240 us from SLEEP to RX or TX mode (measured on EM design)
...
General
Few external components: Complete on-chip frequency synthesizer, no external
filters or RF switch needed
Green package: RoHS compliant and no antimony or bromine
Small size (QLP 4x4 mm package, 20 pins)
```

**p4（Table of Contents，原文节选）**

```
CC2500
SWRS040C
Page 4 of 89
Table of Contents
APPLICATIONS ......................................1
PRODUCT DESCRIPTION .............................1
KEY FEATURES .....................................1
RF PERFORMANCE ...................................1
ANALOG FEATURES .................................1
DIGITAL FEATURES .................................1
LOW-POWER FEATURES ..............................2
GENERAL ..........................................2
1  ABSOLUTE MAXIMUM RATINGS ......................6
...
5  PIN CONFIGURATION ............................15
```

**p99（末页）**

```
IMPORTANT NOTICE AND DISCLAIMER
TI PROVIDES TECHNICAL AND RELIABILITY DATA (INCLUDING DATASHEETS), ...
```

### 1.5 芯片参数特征命中（全文逐页扫描，附页码与上下文）

| 特征词 | 命中页 | 上下文（首处） | 性质 |
| --- | --- | --- | --- |
| `ABSOLUTE MAXIMUM RATINGS` | 4（目录）、6（正文） | `1 ABSOLUTE MAXIMUM RATINGS` | ✅ 典型 datasheet 章节 |
| `PIN CONFIGURATION` | 4（目录）、15、25、58、61 | `5 PIN CONFIGURATION` | ✅ 典型 datasheet 章节 |
| `Electrical Characteristics` | **0 处** | — | ⚠️ 该 datasheet 用 `RF PERFORMANCE` / `ANALOG FEATURES` / `DC CHARACTERISTICS` 表述，不含此串 |
| `Evaluation Module` | 86 | `Orderable Evaluation Module Description ... CC2500-CC2550DK / CC2500EMK` | ⚠️ 出现在**订购信息表**里，是"可订购的评估模块"一行，不是文档身份 |
| `Bill of Materials` | 19 | `Table 15: Bill Of Materials for the Application Circuit` | ⚠️ 是 datasheet 的**参考应用电路** BOM，不是 EVM BOM |
| `Schematic` | 51、56 | `The schematic, BOM and layout Gerber files are all available from the TI website` | ⚠️ 是**参考布局**章节的引用语 |

**这张表本身就是一条重要结论**：如果将来给分类器加"命中 BOM / Schematic / Evaluation Module 就判 EVM"的规则，**这份纯 datasheet 会被误伤** —— 它在 p19 有 BOM、p51 有 Schematic、p86 有 Evaluation Module。关键词规则在这个数据集上双向都不可靠。

### 1.6 双维度判定（严格区分）

| 维度 | 判定 | 依据 |
| --- | --- | --- |
| **`document_type`（文档本体类型）** | **芯片 Datasheet** | Title/Subject 双声明 `datasheet` / `Data Sheet`；文档号 `SWRS040`；89 页正文含 Applications / Product Description / Key Features / Absolute Maximum Ratings / Pin Configuration / RF Performance；附标准 addendum |
| **`source_context`（采集来源上下文）** | **EVM 产品页 / 评估套件页面** | 文件名 `CC2500EMK__cc2500.pdf` 的前缀 `CC2500EMK` 是 TI 的评估模块型号（CC2500 Evaluation Module Kit）；该 PDF 是从 EMK 产品页的"Datasheet"链接下载的，文件名被采集脚本拼成 `<来源型号>__<文档词干>.pdf` |
| 是否混合型 | **否** | 99 页中 EVM 内容为 0 页；`Evaluation Module` 仅作为订购表的一行出现 |

**结论：`document_type = 芯片 Datasheet`，`source_context = EVM 套件页面`。两者不冲突——"从 EVM 页面下载到的芯片手册"仍然是芯片手册。**

### 1.7 对 V022 预期标签的修正建议

- 现有预期：`NON_DATASHEET`（EVM 伪装件）→ **错误**。
- 建议修正为：`DATASHEET`（`doc_type = DS_STRONG`），并在 Gold 里记录 `source_context = EVM kit page`、`selection_basis` 改为"来源上下文为 EVM 页面但文档本体为 datasheet，用于验证分类器不被文件名前缀误导"。
- 也就是说：V022 不是"负样本"，而是一个**正样本 + 干扰文件名**的对抗性用例。它的价值从"检验门禁能否拦截 EVM"变成"检验分类器能否抵抗 `EMK` 文件名噪声" —— 而分类器**通过了**这个测试。

---

## 任务二：真正的 EVM 负样本候选

### 2.1 搜索方法（刻意不用文件名判定）

1. 先在 350 清单里按路径筛 EVM/EMK/BOOST/PDK 等关键词，得到 3 条；
2. 逐份核验，**结果全部是 datasheet**（见 2.2）——证明文件名不可信；
3. 改用**元数据 + 正文**双证据扫描 `E:\workspace\IcPdfParser\data\pdfs`（11,355 份）：
   先按 TI 文档号前缀（`SLAU/SLVU/SNLU/DLPU/SPRU/SBAU/SLOU/SLYU`）收窄到 623 份，
   再读 PDF 元数据 `Title`/`Subject` 过滤，得到 **622 份**标题或主题明确含
   `User's Guide` / `Evaluation Module` / `Evaluation Board` 的文档；
4. 从这 622 份里按"正文特征必须成立"逐份抽检，最终选定 2 份主候选 + 2 份备选。

### 2.2 关键发现：350 清单里 3 个"EVM 命名"文件全是 Datasheet

| 样本号 | 文件 | 页数 | 元数据 Subject | 元数据 Title | 实际类型 |
| --- | --- | --- | --- | --- | --- |
| V022 | `CC2500EMK__cc2500.pdf` | 99 | `Data Sheet` | `... 2.4 GHz RF Transceiver datasheet (Rev. C)` | 芯片 Datasheet |
| V164 | `DRV8262VEVM__drv8262.pdf` | 65 | `Data Sheet` | `DRV8262 : 60V ... Motor Driver ... datasheet (Rev. C)` | 芯片 Datasheet |
| V255 | `CC31XXEMUBOOST__cc3100.pdf` | 45 | `Data Sheet` | `CC3100 ... datasheet (Rev. D)` | 芯片 Datasheet |

三份的 `Subject` 全是 `Data Sheet`，正文全含 `Absolute Maximum Ratings` / `Pin Configuration`。
**结论：本数据集的命名约定是 `<采集来源型号>__<文档词干>.pdf`，前缀是下载来源，不是文档类型。任何"文件名含 EVM 就当负样本"的做法都会错。**

### 2.3 主候选 A：ADC08060EVM（SLAU715A）

| 项 | 值 |
| --- | --- |
| 绝对路径 | `E:\workspace\IcPdfParser\data\pdfs\ADC08060EVM__slau715a.pdf` |
| SHA-256 | `09fabc2407fc5834f77c40b6f8a2b5bfb012caa983ac2724c950f9224a4c02ca` |
| 大小 / 页数 | 1,260,819 B / 20 |
| Title | `ADC08xx0 Evaluation Module User's Guide (Rev. A)` |
| Subject | `User's Guide` |

**首两页原文**

```
p1:
1
SLAU715A–February 2017–Revised July 2017
Submit Documentation Feedback
Copyright © 2017, Texas Instruments Incorporated
ADC08xx0 Evaluation Module
User's Guide
This user's guide describes the function and use of the ADC08xx0 evaluation module (EVM).
Included in this document are a quick-start guide, instructions for optimizing evaluation
results, jumper and connector descriptions, software description, and alternate hardware
configurations.
Contents
1 Overview ............ 3
1.1 Required Hardware ...

p2:
www.ti.com
2
SLAU715A–February 2017–Revised July 2017
ADC08xx0 Evaluation Module
Trademarks
Microsoft, Windows are registered trademarks of Microsoft Corporation.
```

**特征命中**：DS 特征 **0 个**；EVM 特征 `Evaluation Module ×19`、`Jumper ×16`、`Quick Start ×3`、`Hardware Setup ×3`、`Schematic ×1`。
**判定：纯 EVM 用户指南，无芯片参数章节 —— 首选负样本。**

### 2.4 主候选 B：BQ25570EVM-206（SLUUAA7A）

| 项 | 值 |
| --- | --- |
| 绝对路径 | `E:\workspace\IcPdfParser\data\pdfs\BQ25570EVM-206__sluuaa7a.pdf` |
| SHA-256 | `60aac1d0cad5e571feac7949f882b25a8eaaad814b190cbec333e7c0b5bb8d2e` |
| 大小 / 页数 | 1,139,868 B / 24 |
| Title | `User's Guide for bq25570 Battery Charger Evaluation Module for Energy Harvesting (Rev. A)` |
| Subject | `EVM User's guide` |

**首两页原文**

```
p1:
User's Guide
SLUUAA7A–July 2013–Revised August 2014
User's Guide for bq25570 Battery Charger Evaluation
Module for Energy Harvesting
This user's guide describes the bq25570 evaluation module (EVM), how to perform a
stand-alone evaluation and how to allow the EVM to interface with the system and host.
The boost charger output is configured to deliver up to 4.2-V maximum voltage to its
output, VSTOR, using external resistors. ...

p2:
Introduction
www.ti.com
1 Introduction
1.1 EVM Features
• Evaluation module for bq25570
• Ultra-low power boost charger and buck converter with battery management ...
• Test points for key signals available for testing purpose – easy probe hook-up.
• Jumpers available – easy to change settings
1.2 General Description
The bq25570 is an integrated energy harvesting Nano-Power management solution ...
```

**特征命中**：DS 特征仅 `Recommended Operating Conditions ×1`（板级推荐工作条件表，非器件参数表）；EVM 特征 `Evaluation Module ×23`、`User's Guide ×25`、`Bill of Materials ×11`、`Schematic ×6`、`PCB Layout ×4`、`Header ×5`。
**判定：EVM 用户指南（含 BOM 与原理图），次选负样本；因为带 1 处 `Recommended Operating Conditions`，比候选 A 更适合检验"轻微混合型"的判定边界。**

### 2.5 备选候选

| 文件 | SHA-256 | 页 | Title | 特征 |
| --- | --- | --- | --- | --- |
| `ADS1299EEGFE-PDK__slau443b.pdf` | `6fd26141fe2d0f740c82a4de860d9c14e893a3297ce8c9860b55a044f4a666fa` | 64 | `ADS1299EEG-FE EEG Front-End Performance Demonstration Kit (Rev. B)` | DS 0；`Schematic ×22`、`Bill of Materials ×20`、`Jumper ×44` —— **板级原理图 + BOM 最典型** |
| `DLPDLCR230NPEVM__dlpu103a.pdf` | `8fdeb5f64f9fe8dbcb751a851912276a2112818ffcb9f0d622ab02415af8a93f` | 22 | `DLP® LightCrafter™ Display 230NP EVM User's Guide (Rev. B)` | DS 0；`Evaluation Module ×1`、`Hardware Setup ×1` |

### 2.6 本次**未做**的验证（需另行授权）

- **没有**对上述候选跑 `classify_one()`，因此**不知道分类器会把它们判成什么**。
  按本轮"只读核验、不跑解析/不跑分类"的边界，这一步留到 Reviewer 授权后再做。
  这也是下一步最该补的证据：如果分类器把 `ADC08060EVM` 判成 `DS_STRONG`，那才是真正的
  "EVM 未拦截"缺陷；如果判成 `EVM/UG` 且 `route≠IC_PARSE`，则说明门禁链路本身是通的，
  V022 只是一次被文件名误导的**假警报**。
- 未把候选写入任何样本清单 / Gold 文件（只读）。

---

## 三、对分类器的启示（供 Reviewer 参考，不预设结论）

1. **文件名前缀是采集噪声，不是文档属性**。`CC2500EMK__cc2500.pdf`、`DRV8262VEVM__drv8262.pdf`、
   `CC31XXEMUBOOST__cc3100.pdf` 三份的 `Subject` 全是 `Data Sheet`。若分类器给文件名证据
   过高权重，会系统性地把"从 EVM 页面下载的 datasheet"误判为 EVM。
2. **关键词规则双向不可靠**：V022 这份纯 datasheet 里 `Bill of Materials`（p19，应用电路 BOM）、
   `Schematic`（p51）、`Evaluation Module`（p86，订购表）都出现了；反过来它**没有**
   `Electrical Characteristics` 这个最常见的数据手册标志。所以"命中 BOM 就判 EVM"会误伤，
   "没命中 Electrical Characteristics 就不判 DS"会漏判。
3. **`document_type` 与 `source_context` 必须分栏存放**。V022 的正确答案是
   `document_type=DATASHEET` + `source_context=EVM kit page`，
   任何把两者压成一个标签的 schema 都会在类似样本上反复出错。

---

## 四、边界声明

- 全程只读：未启动服务、未 POST 任何请求、未调用 `parse_pdf()` / `classify_one()`、
  未写 `runs/` 或 `uploads/`、未修改任何样本清单或 Gold 文件。
- **零写入证明**：`workbench/uploads/` 仍为 2 个文件（最新 mtime 07:47）、
  `workbench/runs/` 仍为 2 个目录 / 97 个文件（最新 mtime 07:47），
  均为上一轮探针遗留；`find uploads runs -newermt "2026-11-11 07:55"` 返回空。
  8765 端口无监听。
- 唯一写入的是本报告与 `workbench/_doc_verify/` 下的核验脚本与原始 JSON（核验证据）。
- 本文所有"结论"均基于元数据 + 正文文本 + 页码定位，未使用文件名作为判定依据（2.1 已说明原因）。
- 未对候选样本的解析质量做任何评价 —— 本轮没有解析它们。
