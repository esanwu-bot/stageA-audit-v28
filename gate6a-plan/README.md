# gate6a-plan —— Gate 6A 标注准备包

本目录是 Gate 6A **标注阶段**的交付物，**没有任何解析结果**。
Parser 一次也没有被调用，Gold Set 一份也没有被创建（只给了模板）。

## 先看哪个

| 顺序 | 文件 | 看什么 |
| --- | --- | --- |
| 1 | `G7B_MERGE_REPORT.md` | D' 是否真的进了 `main`，`classifier.py` 字节有没有变 |
| 2 | `IMAGE_ONLY_SCAN_REPORT.md` | 扫描件缺失问题解决了没有、3 件补充样本怎么选的 |
| 3 | `Gold_Set_Template.README.md` | 标注人怎么填、哪些列不许动 |
| 4 | `Gold_Set_Template.csv` | 33 行待填样本（29 正式 + 1 诊断 + 3 补充） |

## 一句话结论

1. **G7b 已合入 `main`。** `main` 从 `6f3e58d5…` 快进到 `60a503cc…`，
   沿 17 个提交，无 merge commit。`classifier.py` 的 SHA-256 合入前后都是
   `28b9f0bf…`，**合入未改变任何字节**。
2. **扫描件缺口已解决。** 在 11,355 份真实池中扫出 79 份无文本层 PDF，
   去重后 62 份，按确定性规则选出 3 件补充样本，全 70 页逐页核验
   「0 字符 + 图像覆盖 100%」。PAIN-08 不再是假覆盖。
3. **V022 已隔离。** `diagnostic_only = TRUE`，不进任何分子分母，
   正式评测清单为 **29 件**。
4. **模板已就绪，标注可以开始。** 但 3 件补充样本需 Reviewer 先批准突破
   「从 350 池抽样」的约束。

## 文件清单

### 报告

| 文件 | 说明 |
| --- | --- |
| `G7B_MERGE_REPORT.md` | 合入报告，含合入前后 SHA、四条核验命令、stash 障碍与返工全过程 |
| `g7b_merge_raw.log` | 合并后现场逐条执行的终端日志，`[EXIT=n]` 为真实退出码 |
| `IMAGE_ONLY_SCAN_REPORT.md` | 无文本层 PDF 定位报告，含方法、结果、选样规则、返工记录 |

### 清单与模板

| 文件 | 行数 | 说明 |
| --- | --- | --- |
| `Gold_Set_Template.csv` | 33 | 人工标注主表，一行一个样本；前段预填只读，后段待填 |
| `Gold_Set_Template.candidates.csv` | 0 | `expected_candidates` 明细，一行一个期望参数 |
| `Gold_Set_Template.column_roles.csv` | 0 | 逐单元格 `gold_column_role`，Column Alignment 的唯一真值来源 |
| `Gold_Set_Template.README.md` | — | 三张表的填写说明、禁区、示例 |
| `GATE6A_SAMPLE_CANDIDATES_30.csv` | 30 | 30 件候选清单正式版，新增 `diagnostic_only` / `d_prime_change_hit` 两列 |
| `IMAGE_ONLY_CANDIDATES.csv` | 62 | 全部去重后的无文本层候选，供 Reviewer 复核或换样 |

### 证据

| 文件 | 说明 |
| --- | --- |
| `scan_summary.json` | 全量扫描汇总（11,355 件，79 命中，耗时 817 秒） |
| `scan_all.jsonl` | 逐件扫描原始记录（11,355 行） |
| `candidates.jsonl` | 79 件命中件的原始记录（含 SHA-256） |
| `selected_supplementary.json` | 3 件选定样本 + 选样规则 + 约束突破声明 |
| `full_page_textlayer_verify.json` | 3 件逐页核验明细（70 页逐页 chars / 图像对象 / 覆盖比） |
| `selfcheck.json` | 四项机器自检，`overall = PASS` |

### 脚本（可复现）

| 文件 | 作用 |
| --- | --- |
| `_capture_merge.py` | 采集合并终端证据，生成 `g7b_merge_raw.log` |
| `_build_merge_report.py` | 把原始日志逐字嵌入生成合并报告 |
| `_scan_image_only.py` | 全量扫描无文本层 PDF（8 进程，约 14 分钟） |
| `_select_supplementary.py` | 去重 + 分档选样，产出候选清单与选定样本 |
| `_verify_fullpage.py` | 3 件逐页全量文本层核验 |
| `_selfcheck.py` | 四项机器自检 |
| `_build_gold_template.py` | 生成三张模板表与 30 件候选清单 |

## 四项机器自检结果

| 检查 | 结论 |
| --- | --- |
| 30 件与 D' 193 条变化集交集 | **0 命中**，样本不因 D' 失效 |
| 350 池 `has_text_layer` 分布 | **350/350 = TRUE**，池内无真扫描件 |
| 3 件补充样本排除性 | 均在池外、均在 D' 变化集外、抽样页字符为 0 |
| 模板行数自洽 | 33 = 29 正式 + 1 诊断 + 3 补充 |

## 等待 Reviewer 裁定的事项

1. **是否批准 3 件补充样本计入分母。** 不批准则 PAIN-08 仍标 `NOT_COVERED`，
   这 3 件保留为 `DRAFT` 不进任何指标。
2. **"扫描型或复杂版面"层是否改名。** 该层原 3 件（V130/V290/V347）不是扫描件，
   建议改名「短文档（9–10 页）」，把扫描型职责交给 SUPPLEMENTARY。
3. **`main` 是否推送远端。** 当前 `main` 领先 `origin/main` 45 个提交，
   本次合并**只动了本地引用**，远端 `origin/main` 上还没有 D'。

## 边界声明

- 未调用 Parser；未调用大模型；未创建任何 Gold 标注。
- 未做 OCR，因此 3 件补充样本在 Parser 里的实际表现本轮未知。
- 未推送远端 Git；`main` 的变更仅存在于本地权威仓库。
- 扫描只读 PDF，未修改、未移动、未删除语料池中任何文件。
