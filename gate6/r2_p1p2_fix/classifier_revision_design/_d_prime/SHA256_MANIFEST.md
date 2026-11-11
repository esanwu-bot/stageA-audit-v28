# D' 修订证据包 —— 哈希清单

- 证据包生成时间：2026-11-11
- 源仓库：`E:\workspace\icpdf-extractor`，分支 `feat/s2b-schema-d4-d6`
- 被修订对象：`src/icpdf/classification/classifier.py`

---

## 1. classifier.py 修改前后哈希

| 状态 | sha256 | 证据包内对应文件 |
| --- | --- | --- |
| **修改前**（D' 之前，A 基线） | `21445afd0f45c3d0c03a40ab5cbbe4f55eccb640e96e8f7df94f0020c82f0861` | `classifier_pre.py` |
| **修改后**（D'，当前 HEAD） | `28b9f0bfc1b23f27f6b170b00c4651a0ba5a9baad35c375d2434e9fd07ee7d5b` | `classifier_dprime.py` |

`classifier_pre.py` 与 `classifier_dprime.py` 是上述两个状态的本机快照，字节相同，因此可离线复核：

```bash
sha256sum classifier_pre.py classifier_dprime.py
# 应分别等于上表两个值
```

## 2. 补丁文件哈希

| 文件 | sha256 | 说明 |
| --- | --- | --- |
| `G7b_D_PRIME.patch` | `b6f9fc619312717c9f98ab7f2c1d2cfbf1a63e056c13178db9ff368a3a3d5e02` | 由 `git show 60a503c` 原样导出（含提交头），正文为 unified diff |

补丁规模：**1 file changed, 42 insertions(+), 0 deletions(-)**，纯插入，无删除行。

## 3. 提交链

| 提交 | SHA | 说明 |
| --- | --- | --- |
| G7a | `35cd8a10983323fb9ea80af5edd6ffedbffeaaa4` | classification 包基线入库（D' 之前的原始状态，8 文件 3,625 行，含 `* -text`） |
| G7b | `60a503cc8015ef9bfb27ddef1685e41593f3a75f` | D' 修订（parent = G7a） |
| 前序 | `55da90610cfb7760e4ef1ff79152dbf2865d2e1d` | R1' 补充（G7a 的 parent） |

`G7b` 的父提交即 `G7a`，`G7a` 的父提交即 `55da906`，单链无分叉。

## 4. 目录内其他文件

| 文件 | 内容 |
| --- | --- |
| `D_PRIME_REPORT.md` | 完整回归报告（定向 8/8、全量 11,355 份、数字分解、局限） |
| `dprime_changes.csv` | A 基线 vs D' 的逐文件差异，**193 行** |
| `regression.jsonl` | 193 份变化样本的完整判定字段（含 rejected codes） |
| `summary.json` | 回归汇总（population / open_errors / harm 三类计数） |
| `check.json` | 8 个定向样本在 A 与 D' 下的完整判定与 rejected 明细 |
| `SHA256SUMS.txt` | 本目录文件的校验和（`sha256sum -c` 直接可用） |

## 5. 复核步骤

```bash
git clone https://github.com/esanwu-bot/stageA-audit-v28.git
cd stageA-audit-v28/gate6/r2_p1p2_fix/classifier_revision_design/_d_prime

# 1) 全目录字节校验
sha256sum -c SHA256SUMS.txt

# 2) 两个源码快照的哈希
sha256sum classifier_pre.py classifier_dprime.py

# 3) 补丁哈希
sha256sum G7b_D_PRIME.patch

# 4) 补丁与两份快照是否自洽（补丁 → 必须逐字节还原出修改后的文件）
sed -n '/^diff --git/,$p' G7b_D_PRIME.patch > /tmp/g7b.diff
rm -rf /tmp/g7b_pre && mkdir -p /tmp/g7b_pre/src/icpdf/classification
cp classifier_pre.py /tmp/g7b_pre/src/icpdf/classification/classifier.py
cd /tmp/g7b_pre && git init -q . && git apply -p1 /tmp/g7b.diff
sha256sum src/icpdf/classification/classifier.py   # 应等于 28b9f0bf…（修改后哈希）
```

## 6. 边界声明

- 本证据包**不含** `src/icpdf/classification/` 的其他文件（`rules.py` / `evidence.py` / `models.py` / `report.py` / `cli.py` / `__init__.py`）：D' 未修改它们，G7b 的 diff 也只涉及 `classifier.py`。
- 本轮**未调用** `parse_pdf()` / `classify_one()`，未启动服务，未发起 HTTP，未写 `runs/` 或 `uploads/`。
- 全部判定为 `_decide_matrix` **纯函数级**结果，不是端到端探针。
