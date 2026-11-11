# gate6a-plan —— Gate 6A 标注准备包

本目录是 Gate 6A **标注阶段**的交付物，**没有任何解析结果**。
Parser 一次也没有被调用，Gold Set 一份也没有被创建（只给了模板与 SOP）。

## 先看哪个

| 顺序 | 文件 | 看什么 |
| --- | --- | --- |
| 1 | `PUSH_REVIEW_45_COMMITS.md` | 推送前 45 个提交改了什么，能不能快进 |
| 2 | `G7B_MERGE_REPORT.md` | D' 是否真的进了 `main`，`classifier.py` 字节有没有变 |
| 3 | `SCAN_SELECTION_EVIDENCE.md` | S01–S03 凭什么入池：11,355 → 79 → 62 → 3 全链条 |
| 4 | `ANNOTATION_SOP.md` | 标注员怎么填、页码/数值/单位怎么记、冲突怎么标 unresolved |
| 5 | `Gold_Set_Template.csv` | 33 行待填样本（29 池内 + 3 池外扫描件 + 1 诊断） |
| 6 | `IMAGE_ONLY_SCAN_REPORT.md` | 无文本层 PDF 定位的方法与结果 |

## 一句话结论

1. **G7b 已合入本地 `main`，未推远端。** `main` 从 `6f3e58d5…` 快进到 `60a503cc…`，
   沿 17 个提交，无 merge commit。`classifier.py` 的 SHA-256 合入前后都是
   `28b9f0bf…`，**合入未改变任何字节**。远端 `origin/main` 仍是 `853a80dd…`。
2. **扫描件缺口已解决。** 11,355 份真实池中扫出 79 份无文本层 PDF，去重后 62 份，
   按确定性规则选出 3 件，共 70 页逐页核验「0 字符 + 图像覆盖 100%」。
3. **层定义已修正。** 原「扫描型或复杂版面」改名「短文档（9–10 页）」；
   新增「扫描件（无文本层）」层 3 件（池外）。
4. **V022 已隔离。** `diagnostic_only = TRUE`、`denominator_eligible = FALSE`，
   永不进分母。可计文件数上界 **32**（29 池内 + 3 池外），Gold Set 总件数 **33**。
5. **标注可以开始。** SOP 已就绪；但 3 件池外样本计入分母仍以 `CONFIRMED` 为前提。

## 文件清单

### 报告

| 文件 | 说明 |
| --- | --- |
| `PUSH_REVIEW_45_COMMITS.md` | 推送前审查：475 文件 / 459 新增 / 16 修改，含原始终端输出逐字嵌入 |
| `push_review_raw.log` | 九条只读命令 + 四条补充核验的原始日志（remote URL 已脱敏） |
| `G7B_MERGE_REPORT.md` | 合入报告，含合入前后 SHA、四条核验命令、stash 障碍与返工全过程 |
| `g7b_merge_raw.log` | 合并后现场逐条执行的终端日志，`[EXIT=n]` 为真实退出码 |
| `SCAN_SELECTION_EVIDENCE.md` | 79 → 62 → 3 证据链：去重规则、分档边界、各档首件、逐页明细 |
| `IMAGE_ONLY_SCAN_REPORT.md` | 无文本层 PDF 定位报告，含方法、结果、选样规则、口径返工记录 |

### 标注载体与 SOP

| 文件 | 行数 | 说明 |
| --- | --- | --- |
| `Gold_Set_Template.csv` | 33 | 人工标注主表；前段预填只读，后段待填 |
| `Gold_Set_Template.candidates.csv` | 0 | `expected_candidates` 明细 |
| `Gold_Set_Template.column_roles.csv` | 0 | 逐单元格 `gold_column_role` |
| `Gold_Set_Template.README.md` | — | 三张表的列含义、禁区、示例、折叠校验 |
| `ANNOTATION_SOP.md` | — | 标注操作规程：`gold_json_path`、页码、数值单位、`unresolved`、扫描件特例 |

### 清单

| 文件 | 行数 | 说明 |
| --- | --- | --- |
| `GATE6A_SAMPLE_CANDIDATES.csv` | 33 | 候选清单正式版（原 `_30.csv` 已废弃），含 `denominator_eligible` / `in_350_pool` |
| `IMAGE_ONLY_CANDIDATES.csv` | 62 | 全部去重后的无文本层候选，含别名，供 Reviewer 复核或换样 |
| `S01_S03_PAGE_DETAIL.csv` | 70 | S01–S03 逐页机读明细 |

### 证据（JSON / JSONL）

| 文件 | 说明 |
| --- | --- |
| `scan_summary.json` | 全量扫描汇总（11,355 件，79 命中，817 秒） |
| `scan_all.jsonl` | 逐件扫描原始记录（11,355 行） |
| `candidates.jsonl` | 79 件命中件的原始记录（含 SHA-256） |
| `selected_supplementary.json` | 3 件选定样本 + 选样规则 + 批准记录 |
| `full_page_textlayer_verify.json` | 3 件逐页核验明细（70 页 chars / 图像对象 / 覆盖比） |
| `selfcheck.json` | 四项机器自检 |

### 脚本（可复现）

| 文件 | 作用 |
| --- | --- |
| `_capture_push_review.py` | 采集九条推送前核验命令，URL 凭据脱敏 |
| `_capture_merge.py` | 采集合并终端证据，生成 `g7b_merge_raw.log` |
| `_build_merge_report.py` | 把原始日志逐字嵌入生成合并报告 |
| `_build_evidence_v11.py` | 生成推送审查报告、选样证据链、逐页明细 CSV |
| `_scan_image_only.py` | 全量扫描无文本层 PDF（8 进程，约 14 分钟） |
| `_select_supplementary.py` | 去重 + 分档选样 |
| `_verify_fullpage.py` | 3 件逐页全量文本层核验 |
| `_selfcheck.py` | 四项机器自检 |
| `_build_gold_template.py` | 生成三张模板表 + 33 件候选清单 |

## 四项机器自检结果

| 检查 | 结论 |
| --- | --- |
| 30 件池内样本与 D' 193 条变化集交集 | **0 命中**，样本不因 D' 失效 |
| 350 池 `has_text_layer` 分布 | **350/350 = TRUE**，池内无真扫描件 |
| 3 件池外样本排除性 | 均在池外、均在 D' 变化集外、逐页 0 字符 |
| 模板行数自洽 | 33 = 29 池内 + 3 池外 + 1 诊断 |

## 等待 Reviewer 裁定的事项

1. **§3.1.2 措辞**：池外 3 件是否允许以「32 件中 3 件为池外补充」一句话合并表述，
   还是必须完全分行、连汇总行都不合并。
2. **`baseline_5` 是否强制双人复核。**
3. **`unresolved` 单列不进分母**是否认可。
4. **禁止外推总体准确率**是否认可。
5. **是否批准进入「建 Gold Set」阶段**（SOP 已就绪）。
6. **本地 `main`（45 个提交）是否推送远端**（审查材料见 `PUSH_REVIEW_45_COMMITS.md`）。

## 边界声明

- 未调用 Parser；未调用大模型；未创建任何 Gold 标注；未做 OCR。
- 3 件池外样本在 Parser 里的实际表现本轮**未知**，
  不得从「无文本层」推断「Parser 会失败」。
- **未推送任何远端**：既未推送 `E:\workspace\icpdf-extractor` 的 `main`，
  也未改动该仓库的任何 ref。
- 扫描只读 PDF，未修改、未移动、未删除语料池中任何文件。
