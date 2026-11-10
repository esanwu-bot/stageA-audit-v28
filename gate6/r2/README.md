# Gate 6 第二轮交付索引（供 Reviewer 复核）

提交时间：2026-11-10。提交方式：推送到独立文件传输仓库
`esanwu-bot/stageA-audit-v28` 的 `gate6/r2/`，主项目 CodeUp 仓库零提交。
该传输仓库**不是权威基线、不是审计依据**；权威基线仍为
`E:\workspace\icpdf-extractor`（HEAD `3ed22a4a83564b36ca238792af4b2328fd966469`）。

---

## 0. 路线调整（本轮两次追加指令已并入）

Reviewer 调整了优先级：**不应因为 LLM 能力缺失就直接把重心转到 LLM 接入，
应先证明 `icpdf-extractor` 能可靠读懂 PDF，再让 LLM 理解它读出来的内容。**

| 阶段 | 状态 |
| --- | --- |
| Gate 6 原始审计 | 已提交，待证据复核 |
| **Gate 6A Parser-only 质量测试** | **待方案批准（本轮首要交付）** |
| Gate 6B Parser 缺陷修复与回归 | 待 6A 结果 |
| Gate 6C LLM 抽取能力建设 | **暂缓** |
| Gate 6D 端到端 30 件正式试跑 | 未批准 |
| 320 件批次 | 未批准 |

因此本轮材料中，上一轮要求的 6 项里与 Gate 6C/6D 相关的部分
（12 条验收、P1-002 修复、调用链、PG 草案、字段映射）**全部标注为暂缓草案**；
`G6-P1-001`（Parser 崩溃保护）归入 Gate 6A/6B，优先级上升。

`ICPDF_EXTRACTOR_LLM_READY = false` 不变，但当前主要阻塞项改为
**「Parser 质量未经基线验证」**。

---

## 1. 七项交付清单

| # | Reviewer 要求 | 文件 | 状态 |
| --- | --- | --- | --- |
| 1 | FIELD_MAPPING.csv 完整 46 行内容 | `FIELD_MAPPING_FULL.md`、`FIELD_MAPPING_REVIEW.csv` | 设计稿，Gate 6C 暂缓 |
| 2 | 12 条机器验收条件的逐条定义/输入/预期/测试实现 | `ACCEPTANCE_12.md` | 规格草案，Gate 6D 未批准 |
| 3 | G6-P1-001 / G6-P1-002 修复设计 | `P1_FIX_DESIGN.md` | P1-001 归 6A/6B；P1-002 暂缓 |
| 4 | Provider/Prompt/Schema/Evidence/Domain/Storage 目标调用链图 | `TARGET_CALL_CHAIN.md` | 目标态，Gate 6C 暂缓 |
| 5 | PostgreSQL 数据模型草案（暂不执行建库） | `POSTGRES_MODEL_DRAFT.md` | 逻辑契约，DDL 0 条 |
| 6 | 当前 Git 基线与未提交改动隔离清单 | `GIT_BASELINE_ISOLATION.md`、`GIT_BASELINE.json`、`BASELINE_FREEZE.csv` | 只读冻结清单 |
| **7** | **Gate 6A Parser-only Benchmark 方案**（新增，含 `ic-ex` 架构核查） | `GATE6A_PARSER_BENCHMARK.md`、`GATE6A_SAMPLE_PROPOSAL.csv`、`GATE6A_SAMPLE_STATS.json` | **待批准，未执行** |

辅助：`ROUND2_VERIFY.json`（交付件内部一致性）、`SHA256SUMS.txt`、
两个生成脚本 `_build_r2.py` / `_build_gate6a_samples.py`（只读，不含解析逻辑）。

### Gate 6A 方案新增的三个要点

1. **`ic-ex` 架构核查**：按已确认身份 `ic-ex = icpdf-extractor`，它**自带**
   `pipeline.parse_pdf()` 确定性解析；`backstage/` 工作台只读 JSON、不解析 PDF；
   权威仓库内**没有**读取旧项目 `IcPdfParser` JSON 的 importer。
   期望 JSON 字段来自 `backstage/…修订版.md:245-259` §5「Extraction Package 数据契约」
   （7 个产物）与 `docs/DATA_CONTRACT.md` + `src/icpdf/domain/`。
   由此如实指出「5 件跑 ic-ex 自带解析看能否超越」在身份确认后是自己比自己，
   给出 C1/C2/C3 三种条件化口径请 Reviewer 指定。
2. **字段对齐三方对比**：旧方案 `IcPdfParser` / 新方案 Parser artifacts /
   `ic-ex` 期望结构与 Domain 模型，逐项列出 MIN/TYP/MAX/UNIT、bbox、页码、
   表格归属、文档 SHA 的对应关系与 3 个缺口（`evidence.json`、`qc_report.json`、
   `raw_extraction.json` 命名不一致）。
3. **历史痛点放大**：从 `docs/检查错误清单.txt`、`docs/方案讨论.txt`、
   `qc/deterministic_extract.py`、`SYSTEM_PROMPT` 等真实证据整理 PAIN-01..12，
   30 件中 17 件刻意落在痛点区（跨页、多层表头、多封装、特殊符号、
   单位错乱、EVM 混入、证据页 NONE）。

---

## 2. 证据边界（Reviewer 特别指出，已写入各文件）

- `GATE6_VERIFY.json` 的 **9/9 PASS** 与 `sha256sum` 的 **9 OK**，
  只证明所校验文件的**字节完整性**；不证明审计结论、字段映射正确性、
  方案获批或已通过独立审核。
- 本轮 `ROUND2_VERIFY.json` 的 PASS 同样只证明**交付件内部一致性与完整性**。
- `FIELD_MAPPING_FULL.md` 的 46 行全量与逐项审查矩阵是**提交方自审**，
  其中 10 组显式默认值全部标记 `needs_reviewer_approval=YES`，未声称零默认值。
- 30 件样本清单的所有 `proposed_stratum` 都是**建议占位**，
  `gold_status=PROPOSED_PENDING_GOLD_CONFIRMATION`；清单字段无法判定
  「扫描型/复杂版面」，须人工 Gold Set 确认。

---

## 3. 本轮实际边界

只读 `git` / CSV / 源码 / 文档检索，生成方案、清单与哈希。

```
PDF 打开 0 · Parser 调用 0 · LLM 调用 0 · Gold 标注 0
依赖安装 0 · 数据库连接 0 · DDL 0 · 代码改动 0
主项目 git add / commit / push 0
```

Gate 1 冻结件与 Gate 6 第一轮文件字节均未改动；
`runs/stage_a_350/gate2a/` 保持 `LEGACY_PIPELINE_TRIAL` 标记。

---

## 4. 取件与复核命令

```sh
BASE=https://raw.githubusercontent.com/esanwu-bot/stageA-audit-v28/main/gate6/r2
curl -fL -O "$BASE/SHA256SUMS.txt"
# 逐个下载下列文件后：
sha256sum -c SHA256SUMS.txt
```

建议复核顺序：`GATE6A_PARSER_BENCHMARK.md` → `GATE6A_SAMPLE_PROPOSAL.csv`
→ `FIELD_MAPPING_FULL.md` / `FIELD_MAPPING_REVIEW.csv`
→ `ACCEPTANCE_12.md` → `P1_FIX_DESIGN.md` → `TARGET_CALL_CHAIN.md`
→ `POSTGRES_MODEL_DRAFT.md` → `GIT_BASELINE_ISOLATION.md`。

---

## 5. 等待 Reviewer 确认（Gate 6A 关闭条件）

1. `ic-ex` 对比口径选 C1 / C2 / C3；若 C3 请给具体仓库路径与入口函数。
2. 30 件建议配额与具体编号，特别是「扫描型或复杂版面」3 件的人工确认方式。
3. Gold Set 字段草案与 `DRAFT → CONFIRMED` 流程。
4. 7 项指标口径与「匹配判定阈值待基线后确定」的安排（本轮不设总分阈值）。
5. `raw_extraction.json` 命名差异、多出的 3 个产物是否保留。
6. Gate 6A 独立目录、Run ID 前缀与审批令牌形式。
7. 上一轮 6 项材料是否按「暂缓草案」归档，或需按 Reviewer 口径改写。

任一未确认前，Gate 6A 保持 `NOT_STARTED`；Gate 6B/6C/6D 与 320 件均不启动。

**本轮只请求 Gate 6A 方案的审批**（样本清单、Gold Set 格式、评估指标、
与 `ic-ex` 的对比方法）。其余 6 项按上一轮要求附上供复核，但依最新路线
全部降级为暂缓草案，**不请求实施批准、不请求开始跑任何测试**。
