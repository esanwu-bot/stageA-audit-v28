# SHA-256 清单说明 · V1–V4 受控 HTTP 探针

校验入口：`sha256sum -c SHA256SUMS.txt`（25 个文件，本文件与 `SHA256SUMS.txt`
自身不入清单）。

---

## 1. 代码版本（最关键的三项）

| 项 | SHA-256 | 说明 |
|---|---|---|
| `classifier.py` 探针前 | `28b9f0bfc1b23f27f6b170b00c4651a0ba5a9baad35c375d2434e9fd07ee7d5b` | 与 D' 交付件 `_d_prime/classifier_dprime.py` 相同 |
| `classifier.py` 探针后 | `28b9f0bfc1b23f27f6b170b00c4651a0ba5a9baad35c375d2434e9fd07ee7d5b` | 前后一致，运行期无代码漂移 |
| 仓库 HEAD | `60a503cc8015ef9bfb27ddef1685e41593f3a75f` | `G7b: D' —— 板级证据足以裁决时抑制 DS_PRODUCT_MODEL_TITLE` |

运行时模块（`C.__file__` 指向的文件）哈希与上表一致，已由独立预检脚本验证，
见 `HTTP_PROBE_V1_V4_REPORT.md` 第 2.1 节。

`classifier.py` 与 `rules.py` 未列入本包的 `SHA256SUMS.txt`——本包只哈希包内文件，
避免把包外路径写进清单造成校验混淆。上表两项为**引用值**，取自
`repo_state_pre.json` 与 `probe_record.json → code_state`。

---

## 2. 四份原始响应体

| 样本 | `raw/V*.response.body.json` SHA-256 | 字节 |
|---|---|---|
| V1 | `5d4368dfba3bbc1768aeab4021bf329a01a75bf0b6832272582c17b348682edf` | 10544 |
| V2 | `b4810d13436efc2a8ed00537973ccef6e419ca4d463cf86fdad5516a25317bc5` | 11327 |
| V3 | `0a6c7a0b18e23ded426b15d3f8cd2967b52c5659a997c3b10cdb002d31bb6669` | 10639 |
| V4 | `c9b30bbfe30eab35eb84c48292860d677e68b759f58eaf8097f06d576c1cc334` | 9299 |

完整原始响应（含状态行与响应头）：`raw/V*.response.raw`，对应哈希见 `SHA256SUMS.txt`。
两类文件均为**未经重写**的字节：`.raw` 是 socket 上读到的全部内容，
`.body.json` 是从中切出的响应体，未做格式化。

---

## 3. 目录差异的哈希级证据

| 文件 | SHA-256 |
|---|---|
| `snapshots/runs_before.json` | `7f6a195e938e4520d3b3fafe11c9ffcf0ed5e2949934dc733b1a08550745633e` |
| `snapshots/runs_after.json` | `7f6a195e938e4520d3b3fafe11c9ffcf0ed5e2949934dc733b1a08550745633e` |

**两个哈希完全相同**，即 `workbench/runs` 在探针前后的全量文件清单（路径 / 大小 / mtime）
逐字节一致，零新增零删除。这比「新增数量为 0」更强的表述：
不是统计漏算，而是清单本身没变。

`uploads` 侧：`51ef2e04a0e397b7…` → `b84cbaa15fafb2cc4e40fce82752466133dfadc54e1d1f4f86b89eef7940191b`
（新增 4 个请求目录、4 份 PDF，与 4 次上传一一对应）。

---

## 4. 需要知悉的两处不一致（如实标注）

### 4.1 `_env_redact.py`：脱敏是事后补上的

`env/process_env.json` 的**初版**（提交 `e14f544`，blob `24ac7b0d…`）未脱敏，
把承载探针那台宿主机的全部 229 个环境变量原样写入，其中含 5 个真实凭据。
详见 `SEC_INCIDENT_01.md`。

现版本：

| 项 | 值 |
|---|---|
| `env/process_env.json` | `fbb866ad970d077daeae14c04fabf10ec53fa5bba6dff52e9d30fd60eede494a`（229 → 4 键脱敏版，2984 B） |
| `harness/_env_redact.py` | `66920efdffdc65b45388d8c74a7b58c5c1c8469eaae7c64e1643c247d5c73890` |
| `harness/_regenerate_env.py` | `af88b696dd8631696d112ccf17226724b511a21962b0ed3bdb4a4aa3fe632f69` |

脱敏版是从**同一份已捕获数据**就地重算的，指向的仍是 PID 63240 那个进程实例，
没有另起进程重新采集，因此证据同源性不变。

### 4.2 `_probe_v1_v4.py`：包内版本不是实际执行的那一版

`harness/_probe_v1_v4.py` 当前哈希
`dee94e7a015e816d3831fbc2e2ab224a33d4c552fe15662701fffd350318453f`，
它经过**两次**事后修改，都不是实际执行那一版的字节：

1. `netstat_8765()` 原用 `subprocess.run(text=True)` 解码中文 Windows 的 GBK 输出，
   首轮执行时在 `finally` 里崩溃（详见报告第 8 节）；已改为按字节捕获 + `cp936` 解码。
2. 环境采集原为 `json.dump(psutil...environ())` 全量落盘，造成 SEC-INCIDENT-01；
   已改为走 `redact_env()` 白名单 + 兜底闸。

因此：

- 包内脚本 = **已修复版**，可直接重跑；
- 实际产生 `raw/`、`startup.log` 的是**初版**（无脱敏、有 netstat 缺陷）；
- 除上述两处外，`http_post` / 采样逻辑 / 快照逻辑完全未变；
- 证据本身（原始响应字节、启动日志）不受这两次修改影响，因为崩溃与脱敏
  都发生在 4 次请求**全部完成之后**。

`_assemble_record.py` 与 `_build_matrix.py` 自写成一版后未再修改。

---

## 5. 未纳入本包的内容

以下内容**刻意不打包**，以避免证据边界含混：

- `workbench/uploads/WB-20261111-1052*/` 下 4 份 PDF 副本（合计约 3.5 MB）：
  其 sha256 已在报告第 5 节列出，且与源 PDF 逐字节一致，无需重复搬运二进制
- `src/icpdf/cli.py`、`workbench/_classifier_revision/R1_PRIME_SUPPLEMENT.md`
  的未提交改动：属探针之前既有的历史修改，与本轮无关，本轮未触碰
  （哈希前后未变，见报告第 6 节）
- `classifier.py` 源码本体：已在 `_d_prime/classifier_dprime.py` 中提供同哈希副本
