# DEFECT-001（修订版）— `DS_PRODUCT_MODEL_TITLE` 把文档号当作器件型号

> ## ⚠️ 此版本推翻原版归因
>
> 本文件**取代** `FINAL_VERDICT.md` §4 中 `DEFECT-001` 的「现象」与「根因」两节。
> 原版把触发源判定为"元数据标题里的 `ADC08xx0`"——**该判定是错的**。
> 真实触发源是**文件名后缀的文档号 `slau715a`**，经 `mpn_root()` 变成 `SLAU715A`，
> 出现在**首页页眉**（不是元数据）并逐字命中标题块。
>
> 原版的「影响」「严重级别」「状态」三节**仍然有效**，本文件不改动它们。
>
> **为什么必须公开更正**：原版归因直接推导出的修法是"给 metadata 降权"。
> 而真实触发串根本不在 metadata 里（见 §3 实测：`metadata 里是否含 SLAU715A = False`），
> 按原版去改**不会修好任何东西**，还会误伤型号只写在 metadata 里的真 Datasheet。

| 项 | 值 |
| --- | --- |
| ID | `DEFECT-001`（修订版 v2） |
| 原版位置 | `FINAL_VERDICT.md` §4 |
| 修订日期 | 2026-11-11 |
| 修订依据 | `61_defect001_repro.log`（只读复现日志） |
| 状态 | `OPEN` — 本轮冻结代码，未修复 |
| 严重级别 | 中（分类纯净度缺陷，**不构成安全越权**）— 与原版一致，未变 |

---

## 1. 原版 vs 真实：逐项对照

| 维度 | 原版（**误诊**） | 真实根因（已实测） |
| --- | --- | --- |
| **匹配到的"型号"是什么** | `ADC08xx0`（板载 IC 型号） | **`SLAU715A`（文档编号）** |
| **该串来自哪个平面** | 元数据 `Title` 字段 | **首页第 2 行页眉**（`SLAU715A–February 2017–…`），不在元数据里 |
| **谁提供了这个串** | 出版方填写的 metadata | `parse_provenance(文件名)` 取 `__` 后半段 → `document_subject_mpn = "slau715a"` |
| **它如何变成"型号根"** | 未涉及 | `_classify_worker` 把 `subject` 当作 `mpn` 传给 `scan_pages`；`mpn_root("slau715a")` 无 EVM 家族后缀可剥，**原样返回** `SLAU715A` |
| **`DEVICE_WORD_RE` 的作用** | 未识别出这一环 | **决定性一环**：它命中 `ADC`（`ADC08xx0` 的**子串**），才让规则成立 |
| **`ADC08xx0` 的真实作用** | 被当成"被匹配的型号" | 只是**凑条件**：提供 `DEVICE_WORD_RE` 需要的 `ADC` 子串 |
| **B 为什么没触发** | 未解释 | B 的 `SLUUAA7A` **同样**在标题块，但 `DEVICE_WORD_RE` **无命中**（`battery`/`charger` 不在器件词表） |
| **正确修法** | "元数据路径降权" | **文档号不得作为型号根**（`mpn_root` 对 `SLAU`/`SBAU`/`SBAA`/`SWRA` 前缀应返回空） |
| **原修法是否有效** | — | **无效**。`SLAU715A` 在正文页眉，降权 metadata 打不到它 |

---

## 2. 真实触发链（五步，每步可复现）

| 步 | 位置 | 发生什么 |
| --- | --- | --- |
| 1 | `classifier.py:507` | `subject = provenance.document_subject_mpn or mpn` → 取到 `slau715a` |
| 2 | `classifier.py:518` | `scan_pages(pages, meta_title, meta_subject, subject, page_statuses)` → **把文档号当 `mpn` 传入** |
| 3 | `rules.py:221` `mpn_root()` | 该函数只剥 `EVM/EVK/EMK/EVAL/PDK/BOOST/DEMO/DK` 后缀；`slau715a` 无此后缀 → **原样返回 `SLAU715A`** |
| 4 | `rules.py:392` `title_block()` | 标题块 = metadata Title + metadata Subject + 首页前 6 个非空行。`SLAU715A` 来自**首页第 2 行** |
| 5 | `rules.py:452-459` | 三条件全满足 → 产出 `DS_PRODUCT_MODEL_TITLE`，强度 `STRONG`，来源标 `METADATA` |

规则三条件（`rules.py:454-455`）：

| # | 条件 | A 的取值 | B 的取值 |
| --- | --- | --- | --- |
| 1 | 根非空且长度 ≥ 4 | `SLAU715A` ✓ | `SLUUAA7A` ✓ |
| 2 | 根逐字出现在标题块（忽略大小写） | ✓ | ✓ |
| 3 | `DEVICE_WORD_RE` 命中 | `ADC` ✓ | **无 ✗** |
| 结论 | — | **触发**（假证据） | **不触发** |

**A 与 B 的唯一分叉点就是条件 3。** 两个"弱条件"（文档号必在页眉 + 任意器件词子串）相乘，产出了一个 `STRONG` 结论。

---

## 3. 实测证据（`61_defect001_repro.log`）

样本 A 的标题块构成：

```
metadata Title      : "ADC08xx0 Evaluation Module User's Guide (Rev. A)"
metadata Subject    : "User's Guide"
首页前 6 个非空行:
  1| 1
  2| SLAU715A–February 2017–Revised July 2017        ← 文档号在这里
  3| Submit Documentation Feedback
  4| Copyright © 2017, Texas Instruments Incorporated
  5| ADC08xx0 Evaluation Module
  6| User's Guide

metadata 里是否含 SLAU715A : False    ← 关键：不在 metadata
首页前 6 行是否含 SLAU715A : True     ← 在正文页眉
metadata 里是否含 ADC08060 : False
首页前 6 行是否含 ADC08060 : False
```

这四行布尔值是本次更正的**决定性证据**：原版说"元数据里有型号被匹配"，但实测元数据里既没有 `SLAU715A`、也没有 `ADC08060`。

样本 B 对照：

```
metadata Title      : "User's Guide for bq25570 Battery Charger Evaluation Module for Energy Harvesting (Rev. A)"
document_subject_mpn: sluuaa7a  →  mpn_root = SLUUAA7A  →  在标题块中 = True
DEVICE_WORD_RE 命中 : None      →  规则不触发
```

---

## 4. 为什么这条假证据能压掉真 EVM 证据

| 档 | 代码位置 | 条件 | 结论 |
| --- | --- | --- | --- |
| **档 5** | `classifier.py:322` | `board_strong and ds_title_strong` | `UNKNOWN` + `conflict=true` ← **A 停在这里** |
| 档 1 | `classifier.py:334` | `board_strong` | `EVM` / high（并把 DS 命中写进 `rejected_rules`） |

**档 5 在档 1 之前执行。** 只要 DS 侧出现**任一**标题级 STRONG，板级证据就失去裁决权——即使板级证据更充分。

A 的 `board_strong` 本来就是 `True`（`EVM_BOARD_TITLE` 的 `Evaluation Module` 组，STRONG）。所以：

> **只要去掉那条假 DS 证据，A 会直接落到档 1，判 `EVM` / high，全程不需要 `EVM_BOARD_SCHEMATIC`。**

这也一并推翻了我在 `evm_probe/PROBE_REPORT.md` §5 建议 2 中的说法（"板级覆盖条件不应只认 SCHEMATIC，应放宽"）。**该建议是误诊**：`board_strong` 一直包含 `EVM_BOARD_TITLE`，从未"只认 SCHEMATIC"。

---

## 5. 原版中仍然有效的部分

以下结论经复核无误，本修订不改动：

| 项 | 内容 | 复核结果 |
| --- | --- | --- |
| 影响 | 非 Datasheet 文档未被精准识别为 EVM，落入人工审核池 | 有效（A 实测 `UNKNOWN`/`REVIEW`/`review_status=pending`） |
| 安全边界 | 不构成安全越权，`parse_pdf()` 仍 0 次调用 | 有效（`parse_pdf_calls=0`、`runs/` 零新增） |
| 严重级别 | 中（分类纯净度缺陷） | 有效 |
| 泛化风险 | 凡"元数据标题带板载 IC 型号"的 EVM/UG 都可能复现 | **需下调**——真实条件是"文档号在标题块 + 任意器件词子串"，与"标题带型号"不是同一条件。泛化范围应以 `CLASSIFIER_REVISION_PLAN.md` §6 假设 H2/H4/H5 的验证结果为准 |

---

## 6. 一处顺带发现的内部不一致

| 项 | 声明 | 实际 |
| --- | --- | --- |
| `DS_PRODUCT_MODEL_TITLE` 的 `EvidenceSource` | `rules.py:187` 声明为 `FIRST_PAGE` | `rules.py:457` 实际产出 `METADATA` |

**任何"按 `source` 字段做降权或门控"的修法，都会踩到这个不一致。** 修之前必须先把它统一，否则改动行为不可预测。

---

## 7. 修正后的修复方向

完整设计见 `classifier_revision_design/CLASSIFIER_REVISION_PLAN.md`。核心判断只有一句：

> **只需修一条规则——文档号（`SLAU`/`SBAU`/`SBAA`/`SWRA` 前缀）不得作为型号根。**
> 不需要动板级证据的强弱体系，不需要放宽覆盖条件。

验证门槛（详见设计文档 §5）：

- **V1**：A 必须从 `AMBIGUOUS` 转为 `EVM` / high / `evidence_conflict=false`；
- **V2**：B 结论零回退（仍为 `EVM` / high，5 条 DS 证据仍被 `overridden_by_board_evidence` 否决）；
- **V3–V7**：真 Datasheet 召回不回退，含 V022/V164/V255 三份 EVM 式文件名的真 Datasheet。

**注意**：V1 的预期结果目前是【推论】——基于档 5→档 1 的代码路径推导，**尚未实测**（本轮冻结）。见设计文档假设 H1。

---

## 8. 本轮未做的事

- 未修改任何代码（`rules.py` / `classifier.py` 时间戳均早于本轮）。
- 未启动服务，`8765` 无监听，`ICEX_WORKBENCH_ALLOW_PARSE` 保持冻结。
- 未调用 `classify_one()`、未触碰 Parser。
- 未改动 `FINAL_VERDICT.md` 正文（保留原版归因原文，以便审计对照）。本文件是**叠加的修订层**，不覆写历史。

---

## 9. 证据索引

| 证据 | 位置 |
| --- | --- |
| 只读复现日志（本文全部数值来源） | `61_defect001_repro.log` |
| A 的原始响应（含 `matched_rules`） | `10_A_response.json` |
| B 的原始响应（含 `rejected_rules`） | `20_B_response.json` |
| 原版归因（保留，供对照） | `FINAL_VERDICT.md` §4 |
| 修正后的设计方案 | `../classifier_revision_design/CLASSIFIER_REVISION_PLAN.md` |
| 安全字段与哈希链 | `60_safety_matrix.md` |
