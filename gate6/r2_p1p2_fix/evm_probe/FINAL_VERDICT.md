# 最终裁定 — 两份真实 EVM 样本只分类探针

**裁定方**：Reviewer
**裁定日期**：2026-11-11
**适用对象**：`evm_probe/` 全部证据（服务 PID 28040，`ALLOW_PARSE=1` + `CLASSIFY_ONLY=1`，仅 `127.0.0.1:8765`）

> 本文件是**最终裁定**，优先级高于本目录内任何自评文字。
> 特别地，它覆盖 `PROBE_REPORT.md` §0 中我方的自评「`PROBE_PASS`」——那个自评只回答了「有没有进 Parser」这一个问题；
> Reviewer 的裁定把它拆成**执行 / 安全 / 分类**三个独立维度分别定级，更严谨，故以本文件为准。

---

## 1. 裁定状态（机器可读）

```ini
PROBE_EXECUTION_STATUS     = PASS
PARSER_SAFETY_STATUS       = PASS
EVM_CLASSIFICATION_STATUS  = PARTIAL_PASS
SAMPLE_A                   = AMBIGUOUS_REVIEW_REQUIRED
SAMPLE_B                   = EVM_CLASSIFICATION_PASS
```

---

## 2. 三个维度分别是什么

| 维度 | 状态 | 含义 | 依据 |
| --- | --- | --- | --- |
| **探针执行** | `PASS` | 两次 `POST /api/process` 均按计划串行完成，响应完整、可复现，证据链闭环（含哈希链、运行前后快照、停服与冻结态恢复） | `10_A_*` / `20_B_*` / `01_`+`30_` 快照 / `40_stop.txt` / `50_`+`51_` |
| **解析器安全** | `PASS` | `parse_pdf()` 调用 0 次；`runs/` 零新增（97→97，rollup 指纹一致）；无 LLM 调用 | `60_safety_matrix.md` |
| **EVM 分类** | `PARTIAL_PASS` | 两份样本都被挡在 Parser 之外（安全目标达成），但**只有 B 被精准识别为 EVM**；A 落入人工审核池 | 见 §3 |

**关键区分**：「安全」与「分类纯净度」是两件事。本轮安全目标 100% 达成；分类纯净度 1/2 达成。把两者混为一个「PASS」会掩盖真实缺陷，这正是拆成三维度的意义。

---

## 3. 样本级结论

### SAMPLE_A = `AMBIGUOUS_REVIEW_REQUIRED`

| 项 | 值 |
| --- | --- |
| 文件 | `ADC08060EVM__slau715a.pdf` |
| SHA-256 | `09fabc2407fc5834f77c40b6f8a2b5bfb012caa983ac2724c950f9224a4c02ca` |
| 分类结果 | `AMBIGUOUS` / `doc_type=UNKNOWN` / `route=REVIEW` / `confidence=low` |
| `evidence_conflict` | `true` |
| 安全字段 | 全绿（`parse_pdf_calls=0`、`parser.stages_seen=[]`） |
| 结论 | 未误放行，但**未被识别为 EVM**，需人工复核。根因见 `DEFECT-001` |

### SAMPLE_B = `EVM_CLASSIFICATION_PASS`

| 项 | 值 |
| --- | --- |
| 文件 | `BQ25570EVM-206__sluuaa7a.pdf` |
| SHA-256 | `60aac1d0cad5e571feac7949f882b25a8eaaad814b190cbec333e7c0b5bb8d2e` |
| 分类结果 | `NON_DATASHEET` / `doc_type=EVM` / `route=QUARANTINE` / `confidence=high` |
| `evidence_conflict` | `false` |
| 安全字段 | 全绿（`parse_pdf_calls=0`、`parser.stages_seen=[]`） |
| 结论 | 精准识别为 EVM 并自动隔离。5 条 `DS_ELECTRICAL_SECTIONS` 被 `overridden_by_board_evidence` 显式否决，方向性裁决生效 |

---

## 4. DEFECT-001 — `DS_PRODUCT_MODEL_TITLE` 在元数据标题路径上误记强 DS 证据

| 字段 | 值 |
| --- | --- |
| **ID** | `DEFECT-001` |
| **严重级别** | 中（分类纯净度缺陷，**不构成安全越权**） |
| **状态** | `OPEN` — 本轮冻结代码，未修复 |
| **发现于** | 本轮 EVM 探针 · 样本 A |
| **组件** | `src/icpdf/classification/rules.py` · 规则 `DS_PRODUCT_MODEL_TITLE`（classifier `docclassifier-2.2.1` / `doc-classifier-v2`） |
| **影响样本** | `ADC08060EVM__slau715a.pdf` |

### 4.1 现象

样本 A 的 PDF 元数据 `Title` 为：

```
ADC08xx0 Evaluation Module User's Guide (Rev. A)
```

这一个字符串里**同时**包含两类信息：

- 板载 IC 型号：`ADC08xx0`
- 文档类型：`Evaluation Module User's Guide`

规则 `DS_PRODUCT_MODEL_TITLE` **仅在字符串中匹配到了型号**，就记了一票 `strength=strong` 的 DS 证据：

```json
{
  "rule_id": "DS_PRODUCT_MODEL_TITLE",
  "matched_text": "ADC08xx0 Evaluation Module User's Guide (Rev. A) User's Guide 1 SLAU715A–February 2017–Revised July 2017 Submit Documentation Feedback Copyright © 2017, Texas I",
  "source": "metadata",
  "confidence": "high",
  "strength": "strong"
}
```

同一份文档里，EVM 侧同样有 `strength=strong` 的证据（`EVM_BOARD_TITLE`「Evaluation Module」，2 条）。两个强信号指向相反方向，冲突无法裁决，最终：

```
evidence_conflict = true  →  doc_type = UNKNOWN  →  route = REVIEW  →  decision = AMBIGUOUS
```

对照样本 B：B 同样命中 5 条 `DS_ELECTRICAL_SECTIONS`，但它具备 `EVM_BOARD_SCHEMATIC`，触发了 `overridden_by_board_evidence` 覆盖规则，把 DS 侧证据显式否决，因此得到干净的 `doc_type=EVM`。

A 的 `matched_rules` 中**没有** `EVM_BOARD_SCHEMATIC`（也没有 BOM / TEST_POINTS），覆盖规则未激活，`DS_PRODUCT_MODEL_TITLE` 无人压制 —— 这是 A 与 B 结果分叉的直接机制。

### 4.2 影响

- 非 Datasheet 文档**未被精准识别为 EVM**，而是落入人工审核池（`AMBIGUOUS` / `REVIEW` / `review_status=pending`）。
- **不构成安全越权**：A 依然被挡在 Parser 之外（`parser.called=false`、`parse_pdf_calls=0`、`runs/` 零新增）。fail-closed 设计生效。
- 但影响**分类纯净度**与运维成本：每份此类文档都要人工看一遍；若人工池长期积压，实际上会削弱门禁的自动化价值。
- 泛化风险：凡「元数据标题里带板载 IC 型号」的 EVM/UG 文档都可能复现。TI 的 EVM 用户指南普遍采用「<板载IC型号> Evaluation Module User's Guide」这一命名格式，**这不是孤例，而是一个文档族的系统性特征**。

### 4.3 根因

`DS_PRODUCT_MODEL_TITLE` 在 `source=metadata` 路径上，只做了「字符串是否包含型号模式」的判定，**没有判断该型号在语义上是文档主语还是板载器件**。

元数据 `Title` 是出版方填写的自由文本，常把「板名 + 板载 IC 型号 + 文档类型」揉在一个字符串里。在这个位置命中型号，**不能证明文档本体是 Datasheet**。

### 4.4 修复建议

1. **元数据路径降权**：`source=metadata` 的 `DS_PRODUCT_MODEL_TITLE` 一律降为 `medium`（或不计入 strong 集），使其无法单独与 EVM 强证据形成「强对强」僵局。
2. **组合判定**：要求同一型号在**正文**（非元数据）也出现，才允许记为 DS 证据；元数据命中仅作辅助。
3. **语义排除**：若命中位置附近存在 `Evaluation Module` / `User's Guide` / `EVM` 等文档类型词，则该次型号命中作废或降权。
4. **（可选，治本）放宽板级覆盖条件**：当前覆盖规则实质要求 `EVM_BOARD_SCHEMATIC` 存在。A 已具备 `EVM_BOARD_TITLE`(2，含 1 条 strong) + `EVM_BOARD_TERMS`(3) + `DOCNUMBER_UG`，证据量并不弱于 B。建议把触发条件从「必须含 SCHEMATIC」改为「板级 strong 证据 ≥ N 条」，或把 `DOCNUMBER_UG`（`slau7`/`slau4` 这类 TI 用户指南文档号）计入板级强证据。

> 以上 4 条仅为建议，**本轮未做任何代码修改**。修复应走独立变更单，并配套回归：样本 A 必须从 `AMBIGUOUS` 转为 `NON_DATASHEET`/`EVM`，同时样本 B 与 V022 的结论不得回退。

### 4.5 复现路径

```bash
# 只读：直接查已归档的原始响应，无需启动服务
py -3.13 -c "
import json
c = json.load(open('10_A_response.json', encoding='utf-8'))['classification']
print(c['evidence_conflict'], c['doc_type'], c['route'])
for r in c['matched_rules']:
    if r['rule_id'].startswith('DS_') or r['rule_id'] == 'EVM_BOARD_TITLE':
        print(r['rule_id'], r['source'], r['strength'], r['matched_text'][:60])
"
```

预期输出：`True UNKNOWN REVIEW`，并可见 `DS_PRODUCT_MODEL_TITLE`（`source=metadata`，`strength=strong`）与 `EVM_BOARD_TITLE`（`strength=strong`）并存。

---

## 5. 本轮未做的事（冻结声明）

- **未修改任何代码**：`workbench/serve_parser.py`、`workbench/parse_worker.py`、`src/icpdf/parser/pipeline.py`、`src/icpdf/classification/` 均未触碰；`DEFECT-001` 仅登记，未修复。
- **未改动任何原始证据**：`evm_probe/` 下既有的 26 个文件逐字节不变，哈希见 `SHA256SUMS.txt`（本次仅新增本文件，并为它追加一行校验和）。
- **未改动上传副本与日志**：`workbench/uploads/` 两份副本、`02_server_stdout.log`、`40_stop.txt`、`50_restore_frozen.log` 原样保留。
- 未重新启动服务、未重新跑探针。

---

## 6. 本目录阅读顺序

| 顺序 | 文件 | 作用 |
| --- | --- | --- |
| 1 | **`FINAL_VERDICT.md`（本文件）** | 最终裁定 + 缺陷登记 |
| 2 | `60_safety_matrix.md` | 安全字段与哈希链核对表 |
| 3 | `PROBE_REPORT.md` | 执行过程与归因分析（§0 自评已被本文件覆盖） |
| 4 | `10_A_response.json` / `20_B_response.json` | 完整原始响应 |
| 5 | `01_snapshot_before.json` / `30_snapshot_after.json` | `uploads/`+`runs/` 前后快照 |
