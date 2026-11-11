# 分类器修订方案全量对比：A / B(R1') / D / E / F

- 语料：`E:\workspace\IcPdfParser\data\pdfs`，**11,355 份 PDF**，打开失败 **0**
- 方法：每份读取前 3 页（`DEFAULT_FIRST_PAGES`，与生产一致）+ 元数据，调用**生产同一函数** `_decide_matrix`
- 脚本：`_scan_matrix.py`（单趟抽取、8 进程并行，2026-11-11 09:53–10:07，13 分 26 秒）
- 产物：`_impact_matrix/matrix.jsonl`（3,453 行）、`summary.json`、`VARIANT_changes.csv`（1,057 行）、`R1_prime_harm_76.csv`（76 行）、`affected_samples.csv`（3,243 行）
- 纪律：**未调用** `parse_pdf()` / `classify_one()`，未启动解析服务，未写 `runs/` 或 `uploads/`，未改任何产品代码

---

## 0. 结论摘要

| 方案 | 定义 | 修复 | EVM 误伤 | 送进 Parser | 真 DS 降级 | 裁定 |
| --- | --- | --- | --- | --- | --- | --- |
| **B（R1'）** | 更换型号参数来源 | 144 | **75** | **1** | 18 | **推翻，严禁合入** |
| **D** | 保留原参数 + 板级标题存在时抑制该规则 | **260** | **0** | **0** | **0** | **当前最优** |
| **E** | 保留原参数 + 无条件移除该规则 | 261 | 0 | 0 | 18 | 次优（有 DS 降级代价） |
| **F** | 更换来源 + 板级标题存在时抑制 | 261 | 0 | **1** | 18 | 不采纳（仍有致命漏放） |

一句话：**D 在全部三项危害指标上为零，且修复量最大（260 > 144）。**

---

## 1. 五个方案的精确定义（对应生产代码位置）

| 代号 | `classify_worker` 传给 `scan_pages` 的第 4 实参 | 规则处置 |
| --- | --- | --- |
| A（现状） | `provenance.document_subject_mpn or mpn`（≈`classifier.py:507`） | 不处置 |
| B（R1'） | `provenance.source_product_mpn or ""` | 不处置 |
| D | 同 A | 若 `page_hits` 含 `EVM_BOARD_TITLE`，丢弃 `DS_PRODUCT_MODEL_TITLE` |
| E | 同 A | 无条件丢弃 `DS_PRODUCT_MODEL_TITLE`（= 降级出 `DS_STRONG_RULES`） |
| F | 同 B | 同 D 的抑制条件 |

---

## 2. 全量结果（doc_type 或 route 发生变化的样本）

| 方案 | 变化文件数 | 去重文档数（SHA-256） | 迁移构成 |
| --- | --- | --- | --- |
| B | 238 | 138 | `UNKNOWN→EVM` 144；`EVM→UNKNOWN` 75；`DS_STRONG→DS_WEAK` 18；`EVM→DS_STRONG` 1 |
| D | 260 | 166 | `UNKNOWN→EVM` 260（**单一方向**） |
| E | 279 | 173 | `UNKNOWN→EVM` 261；`DS_STRONG→DS_WEAK` 18 |
| F | 280 | 174 | `UNKNOWN→EVM` 261；`DS_STRONG→DS_WEAK` 18；`EVM→DS_STRONG` 1 |

### 2.1 交叉校验（证明本次脚本与上一轮一致）

上一轮独立脚本 `_scan_impact.py` 给出的 B 结果为「238 文件 / 138 文档」，本次 `_scan_matrix.py` 复现 **238 / 138**，四项迁移计数逐项相同（144 / 75 / 18 / 1）。两套独立实现互证。

---

## 3. 关键样本逐方案判定

| 样本 | 性质 | A（现状） | B | D | E | F |
| --- | --- | --- | --- | --- | --- | --- |
| `ADC08060EVM__slau715a.pdf` | 真 EVM（缺陷复现样本） | `UNKNOWN/REVIEW` | `EVM/QUARANTINE` | `EVM/QUARANTINE` | `EVM/QUARANTINE` | `EVM/QUARANTINE` |
| `ADS1299EEGFE-PDK__slau443b.pdf` | 真 EVM（同型泛化） | `UNKNOWN/REVIEW` | `EVM/QUARANTINE` | `EVM/QUARANTINE` | `EVM/QUARANTINE` | `EVM/QUARANTINE` |
| `BQ25570EVM-206__sluuaa7a.pdf` | 真 EVM（对照，已有 SCHEMATIC） | `EVM/QUARANTINE` | 不变 | 不变 | 不变 | 不变 |
| `CC2500EMK__cc2500.pdf` | 真 Datasheet（防误伤） | `DS_STRONG/IC_PARSE` | 不变 | 不变 | 不变 | 不变 |
| `DRV2700EVM__slyu023.pdf` | 真 EVM（快速入门指南） | `EVM/QUARANTINE` | **`DS_STRONG/IC_PARSE`** | `EVM/QUARANTINE` | `EVM/QUARANTINE` | **`DS_STRONG/IC_PARSE`** |

---

## 4. 三个必须说清的事实

### 4.1 R1' 为什么被推翻（B）

238 份变化里，**只有 144 份是收益**；另外 76 份是反向：

- **75 份 EVM 被误伤**：`EVM/QUARANTINE → UNKNOWN/REVIEW`。机制是「修复把假证据从文件名右半段搬到了左半段」——新候选是板名（如 `ADC128S102EVM`），剥离后缀即芯片型号，而评估板手册标题**本来就写芯片型号**，三条件再次成立。
- **1 份致命漏放**：`DRV2700EVM__slyu023.pdf → DS_STRONG/IC_PARSE`。该文件无 `EVM_BOARD_TITLE`（`Quick Start Guide` 不在 `BOARD_TITLE_GROUPS`），`board_strong` 为空，直接落档 3/4。`assert_route_invariant` 不会报警，因为 `DS_STRONG ⟺ IC_PARSE` 这条不变量**被满足了**。

逐条明细见 `R1_prime_harm_76.csv`（19 列 + 危害类别，致命案例排首行）。

### 4.2 D 的三个零及其代价

D 的 260 份变化**全部是 `UNKNOWN → EVM`**：没有一份 EVM 掉出隔离区，没有一份非 DS 进入 `IC_PARSE`，也没有一份 `DS_STRONG` 被降级。

代价（相对 E/F）只有 1 份：`DS10CP154TSQX_NOPB__DS10CP154.pdf`。它的板级证据是 `EVM_BOARD_SCHEMATIC`（不是 `EVM_BOARD_TITLE`），而 D 的抑制条件只认 `EVM_BOARD_TITLE`，所以这份没被修好，仍是 `UNKNOWN/REVIEW`。

> 这是 D 的**已知边界**，不是缺陷：把抑制条件从「有 `EVM_BOARD_TITLE`」放宽为「有任一板级强证据」可以覆盖它，但那是一个**新变体（记 D'）**，本轮**未实测**，不得据此下结论。

### 4.3 E / F 的 18 份降级是真 Datasheet，不是隐藏收益

这 18 份的共同点是 `其他强证据 = (none)`：它们**只**依赖 `DS_PRODUCT_MODEL_TITLE` 这一条强证据，规则一移除就掉到 `DS_WEAK/REVIEW`。

我抽查了 5 份的元数据与首页（只读）：

| 文件 | 元数据 Title | 判定 |
| --- | --- | --- |
| `AM1806BZCE3__AM1806.pdf` | `AM1806 ARM Microprocessor (Rev. F)`，Subject `Data Manual on Single Products` | 真 Datasheet |
| `ADC12D2000RFIUT__ADC12D2000RF.pdf` | `ADC12D2000RF 12-Bit, Single 4.0 GSPS RF Sampling ADC` | 真 Datasheet |
| `COP8-EMFLASH-00__COP8CFE9.pdf` | `COP8CFE9 8-Bit CMOS Flash Microcontroller…` | 真 Datasheet |
| `DLP-7970ABP__TRF7970A.pdf` | `TRF7970A Multiprotocol… Transceiver IC (Rev. L)` | 真 Datasheet |
| `EVM430-F6779__MSP430F677x.pdf` | `MSP430F6779 poly-phase energy meter IC system on chip` | 真 Datasheet（文件名带 EVM 但内容是 IC 手册） |

所以这 18 份是**真实的解析能力损失**（方向安全：进 REVIEW 而非 Parser），不是「隐藏的 EVM 修复」。剩余 13 份未逐份抽查，见 §6 局限。

---

## 5. 建议

1. **D 作为最小修订候选**：它是唯一在「修复量、误伤、漏放、DS 降级」四项上无短板的方案，且改动面最小（只在 `scan_pages` 之后过滤一条规则，不动参数传递）。
2. **D 不消除根因**：`document_subject_mpn` 仍被当作型号根传给 `scan_pages`（DEFECT-001 的真实触发链），D 只是让这条规则的假证据在板级文档上失效。参数类型混淆应作为**独立议题**另行评审，不要塞进本次最小修订。
3. **E / F 不推荐**：E 以 18 份真 DS 降级换 1 份额外修复；F 继承了 R1' 的致命漏放（`DRV2700EVM`），本质仍是「换来源」，不可合入。
4. **合入前必须做端到端探针**：本轮全部是纯函数级模拟，不是 HTTP 链路验证。

---

## 6. 口径与局限（不要超出本文能支撑的范围）

1. **文件数 ≠ 文档数**：语料存在同一 PDF 多命名副本（最多 27 份共用同一 SHA-256）。B 的 238 是文件数，去重后 138。两者不可混用。
2. **纯函数级模拟**：直接调用生产 `_decide_matrix`，绕过了 `_classify_worker` 的进程边界、超时与上传链路，**不等于**端到端探针。
3. **18 份降级只抽查 5 份**，其余 13 份的真实文档类型未逐份核验。
4. **A 基线未做独立复核**：A 使用生产代码的实参表达式，其判定即当前生产判定，但本次未与线上历史结论逐条对齐。
5. **未观察到的风险不能声称不存在**：本次只覆盖 `doc_type` / `route` 的变化，`confidence`、`evidence_conflict` 的变化未逐条统计（`matrix.jsonl` 中有原始字段可供复核）。

---

## 7. 服务启动失败原因（本轮实测）

三次启动观察，均为本机 127.0.0.1:8765：

| # | 时间 | 方式 | 结果 |
| --- | --- | --- | --- |
| 1 | 08:34（前一轮，已归档） | 命令末尾加 `&` | 端口短暂 LISTENING 后进程随 shell 退出被杀（PID 27940），`psutil` 报 `NoSuchProcess` |
| 2 | 09:53（本轮） | 后台任务托管、`> 日志`，**未加 `-u`**，同时 8 进程全量扫描占满 CPU | 进程存在，但 40 秒内端口未监听、日志 0 字节 |
| 3 | 10:08（本轮） | 后台任务托管、`py -3.13 -u`，CPU 空闲 | **6 秒内 `Application startup complete`**，`/api/health` 返回 `frozen=true / allow_parse=false` |

**结论**：

- **不是端口冲突**：8765 在三次尝试之间均为空闲（`Get-NetTCPConnection` 计数 0）。
- **不是环境变量错误**：第 3 次 `frozen=true`、`allow_parse=false`，`ICEX_WORKBENCH_ALLOW_PARSE=0` 正确生效。
- **不是代码报错**：无 traceback，`/api/health` 完整返回，`git_head=55da906`。
- 第 1 次是**启动方式错误**（`&` 脱离任务管理）；第 2 次失败的根因**无法从现有证据唯一确定**——CPU 竞争导致启动迟滞、与 `stdout` 块缓冲导致「日志为空」的可观测性缺失，两者都能解释该现象，本轮没有做对照实验，不作断言。
- 工程建议：启动一律使用**后台任务托管 + `-u`**，并在启动后以 `/api/health` 判定，不要以「日志有无输出」判定。

---

## 8. 产物与哈希

| 文件 | 说明 |
| --- | --- |
| `COMPARISON_REPORT.md` | 本文件 |
| `R1_PRIME_OVERTURN.md` | R1' 推翻声明（可直接引用的结论段） |
| `R1_prime_harm_76.csv` | 75 误伤 + 1 漏放，76 行 × 20 列 |
| `VARIANT_changes.csv` | B/D/E/F 四方案全部 `doc_type`/`route` 变化，1,057 行 |
| `affected_samples.csv` | R1' 全量受影响样本，3,243 行 × 19 列 |
| `summary.json` | 机器可读汇总（计数、迁移分布、关注事件示例） |
| `_scan_matrix.py` | 本次扫描脚本（可复现） |
| `trace_DRV2700EVM__slyu023.json` | 致命案例（1 份漏放）的五方案完整判定轨迹 |
| `trace_ADC08060EVM__slau715a.json` | 缺陷复现样本（A）的五方案完整判定轨迹 |
| `_trace_case.py` | 轨迹导出脚本 |

**轨迹文件的性质**：由 `_decide_matrix` 纯函数直接生成，**不是** `/api/parse` 或 `/api/process` 的响应体（未经过 `_classify_worker` 进程、上传链路与超时控制）。文件内 `evidence_kind` 字段已显式标注。致命案例在 B 方案下的证据链可直接复核：唯一 STRONG 证据是 `DS_PRODUCT_MODEL_TITLE`（`source=metadata`，`matched_text` 为整个标题块），板级证据仅 `EVM_FILENAME_SUFFIX`(medium) + `EVM_BOARD_TERMS`×3(medium) + `EVM_BODY_MENTION`×2(weak)，`EVM_BOARD_TITLE` 缺失 → `DS_STRONG/IC_PARSE/high`，且 `conflict=false`、`rejected_rules=[]`。

校验：见同目录 `SHA256SUMS.txt`（`sha256sum -c` 可直接校验）。所有 CSV 为 UTF-8 with BOM（Excel 直接打开不乱码）。

**未推送**：`_impact_matrix/matrix.jsonl`（4.5 MB，3,453 行原始逐样本五方案判定）。它在本地保留，可用 `py -3.13 workbench/_classifier_revision/_scan_matrix.py` 重新生成（13 分 26 秒，只读）。如果需要逐样本的 `confidence` / `evidence_conflict` 级复核，请另行索取。
