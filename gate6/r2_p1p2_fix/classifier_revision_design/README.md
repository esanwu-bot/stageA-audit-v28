# classifier_revision_design — 分类器最小修订方案（设计稿）

**状态**：设计草案，待 Reviewer 审批。**本轮冻结代码，未新增/修改任何实现。**

## 先读哪个

| 目的 | 文件 |
| --- | --- |
| 看完整方案 | `CLASSIFIER_REVISION_PLAN.md` |
| **先看更正声明** | 该文件 **§1** —— `DEFECT-001` 原先的"现象"描述有误，本文已更正 |
| 看验证矩阵 | 该文件 **§5** |
| 看待验证假设 | 该文件 **§6** |

## 一句话摘要

`DEFECT-001` 的真实根因不是"元数据标题里含型号"，而是**文件名后缀的文档号 `slau715a` 被 `mpn_root()` 当作器件型号**，恰好又命中标题块里的 `ADC` 子串，于是产出一条 STRONG 的 `DS_PRODUCT_MODEL_TITLE` 假证据，与真实的 EVM 强证据在**档 5（冲突）**相撞。

**因此：只需修一条规则（文档号不得作为型号根），不需要动板级证据强弱体系。**

## 四个问题的答案（各一句）

1. **证据语义**：问题不在"用了 metadata"，而在"用了却没校验语义"。文档号不是型号；标题块含文档类型词时型号命中应降权；严禁一刀切禁用 metadata（会误伤只在 metadata 里规范写型号的真 Datasheet）。
2. **板级优先级**：`EVM_BOARD_SCHEMATIC` 与 `EVM_BOARD_TITLE`（`EVAL_MODULE` 组）同为 STRONG 且都进 `board_strong`。A 命中的正是 `Evaluation Module`（STRONG）——**A 本来就不需要 SCHEMATIC**，只要去掉那条假 DS 证据就会落到档 1 判 `EVM`/high。
3. **运维分流**：`NON_DATASHEET` 可自动归档，不进复核队列；`AMBIGUOUS` 进人工复核。**人工复核只能"退回"或"重跑"，绝不能"放行"——放行的唯一路径是重新经过分类器并满足全部 8 项白名单。**
4. **验证矩阵**：V1 复现（A）、V2 对照（B，零回退）、V3–V7 真 Datasheet 防误伤（含 EVM 式文件名的 V022/V164/V255）、E1–E8 假 UG 与边界场景。

## 修订版已发布

`evm_probe/DEFECT-001_REVISED.md` 已发布，显式推翻原版归因，并附只读复现日志 `evm_probe/61_defect001_repro.log`。

`FINAL_VERDICT.md` 正文保留原版原文不动（供审计对照），修订以 `DEFECT-001_REVISED.md` 为准。本设计文档 §1 与其完全一致。

校验完整性：`sha256sum -c SHA256SUMS.txt`
