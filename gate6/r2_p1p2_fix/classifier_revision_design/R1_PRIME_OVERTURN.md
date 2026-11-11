# R1' 方案已推翻 —— 全量实测证据

- 状态：**REJECTED / 严禁合入**
- 结论日期：2026-11-11
- 依据：全量 11,355 份 PDF 只读扫描（`_scan_impact.py`，2026-11-11 09:12–09:32，`open_err=0`）
- 复现：`py -3.13 workbench/_classifier_revision/_scan_impact.py` → `_impact_full/affected.jsonl`（3,243 行）

---

## 1. 推翻声明（可直接引用）

> **R1' 方案（`classify_worker` 第 507 行的 `subject = provenance.document_subject_mpn or mpn` 改为 `source_product_mpn or ""`，即「更换型号参数来源」）因全量实测发现会导致 1 份 EVM 被误判为 Datasheet 并送进 Parser、75 份 EVM 从隔离区退回人工复核队列，已被正式推翻，严禁合入。**
>
> 该方案同时修复了 144 份 EVM（`UNKNOWN → EVM`）并让 18 份真 Datasheet 从 `DS_STRONG` 降级为 `DS_WEAK`。修复收益真实，但不足以抵偿 1 份致命漏放。

---

## 2. 全量实测口径

| 项 | 值 |
| --- | --- |
| 语料 | `E:\workspace\IcPdfParser\data\pdfs` |
| 文件总数 | 11,355 |
| 打开失败 | 0 |
| 每份读取页数 | `DEFAULT_FIRST_PAGES = 3`（与生产一致） |
| 对比 | 当前生产代码 vs R1' 修正 |
| 判定函数 | `_decide_matrix`（生产同一函数） |
| 规则命中变化 | 3,243 文件 / 1,344 去重文档 |
| **`doc_type` 或 `route` 变化** | **238 文件 / 138 去重文档** |

### 2.1 238 份的构成

| 变化 | 文件数 | 性质 |
| --- | --- | --- |
| `UNKNOWN → EVM`（`REVIEW → QUARANTINE`） | 144 | 缺陷被修复（收益） |
| `EVM → UNKNOWN`（`QUARANTINE → REVIEW`） | **75** | **回退：EVM 被误伤** |
| `DS_STRONG → DS_WEAK`（`IC_PARSE → REVIEW`） | 18 | 副作用：真 Datasheet 降级（安全侧） |
| `EVM → DS_STRONG`（`QUARANTINE → IC_PARSE`） | **1** | **致命：EVM 被送进 Parser** |
| 合计 | 238 | — |

---

## 3. 致命案例（1 份）

| 字段 | 值 |
| --- | --- |
| 文件名 | `DRV2700EVM__slyu023.pdf` |
| PDF SHA-256 | `5affb226c8921348842fc2883a71c5addd2dd30f56dfce9ae019c07cb4e25c45` |
| 原 doc_type / route | `EVM` / `QUARANTINE` |
| 新 doc_type / route | `DS_STRONG` / `IC_PARSE` |
| 原候选（传参） | `slyu023`（文档号） |
| 新候选（传参） | `DRV2700EVM`（板名） |
| 其他强证据 | `(none)` |

机制：`mpn_root('DRV2700EVM')` = `DRV2700`，逐字出现在标题块 `DRV2700EVM Quick Start Guide` 中，`DEVICE_WORD_RE` 又命中 `Reference`（来自 `Reference Guide`，不是器件词），三条件同时成立 → 假 `DS_PRODUCT_MODEL_TITLE`（strong）。该文件没有任何 `EVM_BOARD_TITLE`（`Quick Start Guide` 不在 `BOARD_TITLE_GROUPS`），`board_strong` 为空 → 直接落档 3/4 → `DS_STRONG` → `IC_PARSE`。

**门禁为何没拦住**：`assert_route_invariant` 要求 `DS_STRONG ⟺ IC_PARSE`，此处该不变量**被满足**。不变量只能保证"判成 DS 才进解析"，不能保证"判成 DS 是对的"。

---

## 4. 误伤案例（75 份）

`EVM → UNKNOWN`，全部从 `QUARANTINE` 退回 `REVIEW`。按 `其他强证据` 分布：

| 其他强证据 | 份数 |
| --- | --- |
| `EVM_BOARD_TITLE/EVAL_MODULE` | 28 |
| `EVM_BOARD_SCHEMATIC/SCHEMATIC;EVM_BOARD_TITLE/EVAL_MODULE` | 13 |
| `EVM_BOARD_SCHEMATIC/SCHEMATIC;EVM_BOARD_TITLE/EVAL_BOARD;EVM_BOARD_TITLE/EVAL_MODULE` | 6 |
| `(none)` | 6 |
| `EVM_BOARD_TITLE/EVAL_BOARD;EVM_BOARD_TITLE/EVAL_MODULE` | 3 |
| 其余组合 | 19 |

机制：新候选全部以 `EVM` 结尾，剥离后就是被测芯片型号（`ADC128S102`、`ADC12DL2500`…）。评估板手册的标题**本来就写被测芯片型号**（板以芯片命名）→ 三个条件再次同时成立 → 假 DS 证据与真实 `EVM_BOARD_TITLE` 在档 5 相撞 → `UNKNOWN`。**修复把假证据从文件名右半段搬到了左半段。**

逐条明细：`R1_prime_harm_76.csv`（76 行，19 列 + 危害类别，致命案例排首行）。

---

## 5. R1' 仍然成立的收益（不因推翻而抹去）

- A 样本 `ADC08060EVM__slau715a.pdf`：`UNKNOWN/low/REVIEW/conflict=True` → `EVM/high/QUARANTINE/conflict=False`（在 144 份修复内）
- 同型样本 `ADS1299EEGFE-PDK__slau443b.pdf`：同样被修复（在 144 份修复内）
- `BQ25570EVM-206__sluuaa7a.pdf`、`CC2500EMK__cc2500.pdf` 等对照样本结论未变

这证明「参数来源」确实是 A 样本的**触发路径**；但全量数据表明它不是规则的**结构性缺陷**——换任何一半文件名都治不了 EVM 误伤。

---

## 6. 复现命令与产物

```bash
py -3.13 workbench/_classifier_revision/_scan_impact.py     # 约 19 分钟，只读
py -3.13 workbench/_classifier_revision/_build_csv.py       # 生成 CSV + 口径统计
```

| 产物 | 说明 |
| --- | --- |
| `_impact_full/affected.jsonl` | 3,243 行原始差异 |
| `affected_samples.csv` | 3,243 份逐样本明细（19 列） |
| `caliber_stats.json` | 口径统计（含 Clopper-Pearson 区间） |
| `R1_prime_harm_76.csv` | 75 误伤 + 1 漏放，共 76 行 |

**口径提醒**：238 是**文件数**，去重后是 138 个文档；语料存在同一 PDF 多命名副本（最多 27 份共用同一 SHA）。
