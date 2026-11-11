# doc_verify — V022 文档级核验与 EVM 负样本搜索（只读）

- 时间：2026-11-11 08:03（GMT+8）
- 性质：**纯只读**。未启动服务、未 POST 请求、未调用 `parse_pdf()`、**未调用 `classify_one()`**。
- 主报告：`GOLD_V022_AND_EVM_CANDIDATES.md`

## 1. 结论摘要

| 项 | 结论 |
| --- | --- |
| V022 `CC2500EMK__cc2500.pdf` 的 `document_type` | **芯片 Datasheet**（不是 EVM 手册） |
| V022 的 `source_context` | EVM 评估套件页面（文件名前缀 `CC2500EMK` 是采集来源） |
| 分类器判 `DS_STRONG / IC_PARSE` | **正确**；错的是我们贴的「EVM 伪装件」预期标签 |
| 99 页构成 | p1–89 datasheet（页脚 `Page N of 89`）+ p90–91 Package Option Addendum + p92–98 Package Materials + p99 Important Notice，**EVM 内容 0 页** |
| 元数据 | Title `Low-Cost Low-Power 2.4 GHz RF Transceiver datasheet (Rev. C)`、Subject `Data Sheet`、Author 含 `SWRS040` |

**数据集命名约定**：`<采集来源型号>__<文档词干>.pdf`，前缀是下载来源、不是文档类型。
350 清单里 3 个 EVM 命名文件（V022 / V164 / V255）的元数据 `Subject` **全是 `Data Sheet`**。

**关键词规则双向不可靠**（主报告 §1.5 有页码定位）：这份纯 datasheet 里
`Bill of Materials`(p19，应用电路 BOM)、`Schematic`(p51)、`Evaluation Module`(p86，订购表)
都出现了，但**没有** `Electrical Characteristics`（该手册用 `RF PERFORMANCE` / `DC CHARACTERISTICS`）。

## 2. 真正的 EVM 负样本候选（已按元数据+正文核验，未分类）

| | 路径 | SHA-256 | 页 | Title |
| --- | --- | --- | --- | --- |
| A | `E:\workspace\IcPdfParser\data\pdfs\ADC08060EVM__slau715a.pdf` | `09fabc2407fc5834f77c40b6f8a2b5bfb012caa983ac2724c950f9224a4c02ca` | 20 | `ADC08xx0 Evaluation Module User's Guide (Rev. A)` |
| B | `E:\workspace\IcPdfParser\data\pdfs\BQ25570EVM-206__sluuaa7a.pdf` | `60aac1d0cad5e571feac7949f882b25a8eaaad814b190cbec333e7c0b5bb8d2e` | 24 | `User's Guide for bq25570 Battery Charger Evaluation Module …` |
| 备选 | `ADS1299EEGFE-PDK__slau443b.pdf` | `6fd26141fe2d0f740c82a4de860d9c14e893a3297ce8c9860b55a044f4a666fa` | 64 | `ADS1299EEG-FE EEG Front-End Performance Demonstration Kit (Rev. B)` |
| 备选 | `DLPDLCR230NPEVM__dlpu103a.pdf` | `8fdeb5f64f9fe8dbcb751a851912276a2112818ffcb9f0d622ab02415af8a93f` | 22 | `DLP® LightCrafter™ Display 230NP EVM User's Guide (Rev. B)` |

A 的 datasheet 特征命中 **0 个**；B 仅 1 处 `Recommended Operating Conditions`（板级表）。

## 3. 文件索引

| 文件 | 内容 |
| --- | --- |
| `GOLD_V022_AND_EVM_CANDIDATES.md` | 主报告（含首页/第 2 页/目录页/末页原文、页码级特征定位、双维度判定） |
| `inspect_pdf_doc.py` | 只读核验脚本（PyMuPDF，仅读元数据与文本层；不 import parser/classifier） |
| `v022_raw.json` | V022 完整核验结果（元数据、各页文本、全文特征命中、字符数） |
| `candidates_raw.json` | 350 清单里 3 个「EVM 命名」文件的核验结果（证明它们都是 datasheet） |
| `evm_candidates_raw.json` | 4 份 EVM 候选的核验结果 |
| `meta_scan.json` | 11,355 份 PDF 中 623 份 TI 用户指南文档号的元数据扫描（623 条） |
| `SHA256SUMS.txt` | 本目录全部文件哈希 |

## 4. 复现

```bash
cd gate6/r2_p1p2_fix/doc_verify
sha256sum -c SHA256SUMS.txt

py -3.13 inspect_pdf_doc.py "E:/workspace/IcPdfParser/data/pdfs/CC2500EMK__cc2500.pdf"
py -3.13 inspect_pdf_doc.py "E:/workspace/IcPdfParser/data/pdfs/ADC08060EVM__slau715a.pdf" \
                            "E:/workspace/IcPdfParser/data/pdfs/BQ25570EVM-206__sluuaa7a.pdf"
```

脚本只做 `pymupdf.open()` + `get_text()` + `metadata`，不写任何文件到 `runs/` 或 `uploads/`。

## 5. 未做与待授权

- **未对任何候选调用 `classify_one()`**，因此**不知道分类器会把 A/B 判成什么**。
  按冻结边界保留，等 Reviewer 批准后再做「只分类、不解析」探针。
  这一步是判断「EVM 是否真的会被门禁放过」的唯一直接证据。
- 未把候选写入任何样本清单或 Gold 文件。
- 未修改任何代码、阈值、路由矩阵。

## 6. 零写入证明

`workbench/uploads/` 仍为 2 个文件、`workbench/runs/` 仍为 2 个目录 / 97 个文件，
最新 mtime 均为 07:47（上一轮探针遗留）；`find uploads runs -newermt "2026-11-11 07:55"` 返回空；
8765 端口无监听。
