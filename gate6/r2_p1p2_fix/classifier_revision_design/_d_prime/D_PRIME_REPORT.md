# D' 方案：本地实现 + 全量离线回归报告

- 分支：`feat/s2b-schema-d4-d6`
- 提交：`35cd8a1`（基线入库）→ `60a503c`（D' 修订，HEAD）
- 语料：`E:\workspace\IcPdfParser\data\pdfs`，**11,355 份**
- 纪律：未调用 `parse_pdf()` / `classify_one()`，未启动服务，未发起 HTTP，未写 `runs/` 或 `uploads/`

---

## 1. 两项前置修复

### 1.1 统计优先级 Bug（`_scan_matrix.py`）

原实现先判 `evm_lost`、后判 `leak_to_parser`，导致 `EVM→DS_STRONG` 这类**同时**满足两条件的事件被吞进误伤计数：

```
EVM/QUARANTINE -> DS_STRONG/IC_PARSE
  原：a.doc_type == "EVM" and b.doc_type != "EVM"  → evm_lost（错，76 = 75 + 1）
  修：先判 b.route == "IC_PARSE"                    → leak_to_parser（1）
```

修正后 `evm_lost` 对 B 方案为 **75**、`leak_to_parser` 为 **1**，两者互斥。
本次 D' 回归脚本 `_scan_dprime.py` 从一开始就按修正后的优先级实现。

### 1.2 修正效果的实测确认

上一轮 B（R1'）汇总的 `evm_lost=76` 是错的；按新口径是 `75 + 1`。这不是数字变化，是**分类口径变化**：把致命漏放从误伤里拆出来单独计。

---

## 2. D' 的最小 diff

`git show 60a503c` → **1 file changed, 42 insertions(+), 0 deletions(-)**，纯插入，无一行改动或删除。

### 2.1 抑制前提

```python
_BOARD_DECISIVE_TITLE_GROUPS = frozenset({"EVAL_MODULE", "EVAL_BOARD", "DEV_KIT"})

def _board_decisive(board_strong: list[Hit]) -> bool:
    for h in board_strong:
        if h.rule_id == "EVM_BOARD_SCHEMATIC":
            return True
        if (h.rule_id == "EVM_BOARD_TITLE"
                and (h.group or "").upper() in _BOARD_DECISIVE_TITLE_GROUPS):
            return True
    return False
```

对照你给的清单：

| 要求 | 实现 | 结果 |
| --- | --- | --- |
| `EVM_BOARD_SCHEMATIC` 计入 | 第一条分支直接返回 True | ✅ |
| `EVAL_MODULE` / `BOARD` / `DEV_KIT` 计入 | 集合 `{EVAL_MODULE, EVAL_BOARD, DEV_KIT}` | ✅（代码里 `BOARD` 组名实为 `EVAL_BOARD`） |
| `USER_GUIDE`(MEDIUM) 排除 | 不在集合内 | ✅ |
| `DOCNUMBER_UG` 排除 | 不是 `EVM_BOARD_TITLE`，也不可能等于 SCHEMATIC | ✅ |
| `EVM_BOARD_TERMS`(MEDIUM) 排除 | 不在 `EVM_STRONG_RULES`，不进 `board_strong` | ✅ |
| `EVM_BODY_MENTION`(WEAK) 排除 | 同上 | ✅ |

### 2.2 抑制动作与留痕

```python
if ds_title and _board_decisive(board_strong) and all(
        h.rule_id == "DS_PRODUCT_MODEL_TITLE" for h in ds_title):
    for h in ds_title:
        rejected.append((h.rule_id, h.matched_text,
                         "overridden by board evidence (%s); 评估板标题里的芯片型号不代表本文档是 Datasheet"
                         % _board_description(hits),
                         "overridden_by_board_evidence"))
    hits = [h for h in hits if h.rule_id != "DS_PRODUCT_MODEL_TITLE"]
    ds_title = []
    ds_title_strong = False
    ds_strong = ds_combo
```

- 留痕：被抑制的每一条命中都进 `rejected_rules`，第 4 元组位（reason code）为 `overridden_by_board_evidence`，与既有板级裁决使用同一 code。
- 范围：**仅当 `ds_title` 全部由 `DS_PRODUCT_MODEL_TITLE` 构成**时才抑制。`DS_DOCUMENT_TITLE` 在场时不动 → 仍走档 5 冲突 → `UNKNOWN`（保守）。
- 位置：在档 5（冲突）判断之前、档 1（板级裁决）之前插入，因此抑制后自然落到档 1 → `EVM/HIGH`。

### 2.3 未触碰的边界（逐项声明）

| 边界 | 是否改动 | 证据 |
| --- | --- | --- |
| 参数传递（`document_subject_mpn or mpn`） | 未动 | diff 只含 `_decide_matrix` 内部与新增 helper |
| Parser / `parse_pdf` | 未动 | 本次零调用 |
| 8 项白名单 / `assert_route_invariant` | 未动 | diff 无相关 hunk |
| `rules.py` / `evidence.py` / `models.py` | 未动 | 两个提交只改 `classifier.py`（+ 基线提交本身） |
| `DS_STRONG_RULES` | 未动 | 规则仍是 strong，只是在本场景不参与裁决 |

---

## 3. 定向验收：8/8 PASS

判定链与生产一致（`scan_filename` + `scan_pages` + `_decide_matrix`），A 基线用「把 `_board_decisive` 打成恒 False」复现，差异只可能来自 D' 本身。

| # | 样本 | A 基线 | D' | 期望 | 结果 |
| --- | --- | --- | --- | --- | --- |
| V1 | `ADC08060EVM__slau715a.pdf` | `UNKNOWN/REVIEW` | `EVM/QUARANTINE` | EVM | ✅ 靠 `EVAL_MODULE` 抑制 |
| V2 | `BQ25570EVM-206__sluuaa7a.pdf` | `EVM/QUARANTINE` | `EVM/QUARANTINE` | 不变 | ✅ |
| V3 | `DS10CP154TSQX_NOPB__DS10CP154.pdf` | `UNKNOWN/REVIEW` | `EVM/QUARANTINE` | EVM | ✅ **靠 `EVM_BOARD_SCHEMATIC` 抑制** |
| V4 | `DRV2700EVM__slyu023.pdf` | `EVM/QUARANTINE` | `EVM/QUARANTINE` | 不变 | ✅ 致命反例未受影响 |
| V5 | `CC2500EMK__cc2500.pdf` | `DS_STRONG/IC_PARSE` | 同 | 不变 | ✅ |
| V6 | `DRV8262VEVM__drv8262.pdf` | `DS_STRONG/IC_PARSE` | 同 | 不变 | ✅ |
| V7 | `CC31XXEMUBOOST__cc3100.pdf` | `DS_STRONG/IC_PARSE` | 同 | 不变 | ✅ |
| V8 | `CD4098BE-NG__cd4098b.pdf` | `DS_STRONG/IC_PARSE` | 同 | 不变 | ✅ |

V1 的 `rejected_rules` 实际内容（`_d_prime/check.json`）：2 条 `DS_PRODUCT_MODEL_TITLE`（metadata 页眉 + 首页标题块各一次命中）+ 1 条 `DS_ELECTRICAL_SECTIONS`，code 均为 `overridden_by_board_evidence`。

分类器既有单测：`test_classification_v2.py` + `test_rule_primitives.py` + `test_classification_processpool_sim.py` → **98 passed**。

---

## 4. 全量离线回归（11,355 份）

| 项 | 值 |
| --- | --- |
| 语料 | 11,355 |
| 打开失败 | **0** |
| 变化文件数 | **193** |
| 变化类型 | `UNKNOWN/REVIEW → EVM/QUARANTINE` ×193（单一方向） |
| EVM 退出隔离区 | **0** |
| 非 DS 进入 Parser | **0** |
| 真 DS 降级 | **0** |
| 触发抑制的文件 | 193（全部 `rejected_codes = {overridden_by_board_evidence}`） |
| 耗时 | 14 分 29 秒，8 进程 |

**用词限定：本次 11,355 份语料未观察到危害。**

### 4.1 与上一轮 D 方案的差异（必须解释，否则数字对不上）

上一轮 D（抑制条件只认任意 `EVM_BOARD_TITLE`）修复 **260** 份；D' 修复 **193** 份。差额可完全分解：

| 项 | 份数 | 说明 |
| --- | --- | --- |
| D 的修复集 | 260 | — |
| 减去：只靠 `EVM_BOARD_TITLE/USER_GUIDE` 触发的 | **−68** | D' 按你的要求排除 `USER_GUIDE`，这 68 份保持 `UNKNOWN/REVIEW` |
| 加上：只靠 `EVM_BOARD_SCHEMATIC` 触发的 | **+1** | 即 V3 `DS10CP154TSQX_NOPB__DS10CP154.pdf`，D 漏、D' 修 |
| = D' 的修复集 | **193** | 与实测一致 |

也就是说：**D' 比 D 更保守**（少修 68 份），代价是那 68 份继续留在人工复核队列；收益是 V3 这类「只有原理图、没有标题字样」的评估板也能正确落 EVM。这 68 份是否值得放进来，取决于你如何权衡「`USER_GUIDE` 出现在 Datasheet 里的风险」——本轮按你的规则执行，未擅自放宽。

---

## 5. 交付件

| 文件 | 路径（本地） |
| --- | --- |
| 最小 diff（git 权威版） | `workbench/_classifier_revision/_d_prime/G7b_D_PRIME.patch` |
| 逐文件差异 CSV（193 行） | `workbench/_classifier_revision/_d_prime/dprime_changes.csv` |
| 回归汇总 | `workbench/_classifier_revision/_d_prime/summary.json` |
| 逐文件原始判定 | `workbench/_classifier_revision/_d_prime/regression.jsonl` |
| 定向验收明细 | `workbench/_classifier_revision/_d_prime/check.json` |
| 扫描脚本 | `workbench/_classifier_revision/_scan_dprime.py` |
| 定向验收脚本 | `workbench/_classifier_revision/_d_prime_check.py` |

### 5.1 文件 SHA-256

| 状态 | sha256 |
| --- | --- |
| 修改前 `classifier.py` | `21445afd0f45c3d0c03a40ab5cbbe4f55eccb640e96e8f7df94f0020c82f0861` |
| 修改后 `classifier.py` | `28b9f0bfc1b23f27f6b170b00c4651a0ba5a9baad35c375d2434e9fd07ee7d5b` |

### 5.2 提交

| 提交 | SHA | 内容 |
| --- | --- | --- |
| G7a | `35cd8a10983323fb9ea80af5edd6ffedbffeaaa4` | classification 包基线入库（8 文件 3,625 行，含 `* -text`） |
| G7b | `60a503cc8015ef9bfb27ddef1685e41593f3a75f` | D'（1 文件 +42 行） |

入库 blob 与工作区逐字节一致（8/8 sha256 相同），`src/icpdf/classification/.gitattributes` 写入 `* -text`，保证 `git clone` 后哈希可复核。

**需要知情**：`src/icpdf/classification/` 此前从未入库，因此「最小 diff」必须拆成两个提交——G7a 是不可避免的前像，G7b 才是本次修订。只审 G7b 即可。

---

## 6. 冻结与残留核查

| 检查项 | 结果 |
| --- | --- |
| 8765 端口 | 无监听 |
| `ICEX_WORKBENCH_ALLOW_PARSE` | 未设置（<unset>，默认冻结） |
| 残留 python 进程 | 仅 `IcPdfParser\algorithm_lab\daemon.py`（PID 5916，07:28 启动，与本任务无关，未动） |
| `runs/` 最新写入 | 2026-11-10 19:59（今日零新增） |
| `workbench/uploads/` 最新写入 | 2026-11-11 08:35（本轮零新增） |
| `parse_pdf()` / `classify_one()` 调用 | 0 |
| HTTP 请求 | 0 |
| LLM 调用 | 0 |

---

## 7. 局限（不要超出本报告能支撑的范围）

1. **纯函数级模拟**：直接调用生产 `_decide_matrix`，绕过 `_classify_worker` 进程边界、超时与上传链路，**不是端到端探针**。合入前应补一次真实 HTTP 串行探针。
2. **A 基线是"关掉抑制分支"复现的**，不是历史二进制；两者代码路径相同，但严格说是同版本内对照，不是跨版本对照。
3. **193 份只核了判定字段**（doc_type / route / confidence / conflict / rejected code），未逐份人工确认"这份确实是 EVM"。方向上是"更安全"（从复核队列回到隔离区），且 8 个定向样本已人工核过。
4. **68 份 USER_GUIDE-only 的样本仍在 REVIEW**，本方案不解决，是否要解由你定。
5. 语料存在同一 PDF 多命名副本，193 是**文件数**，未去重。
