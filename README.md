# Stage A SRS 审计交付 · v2.8 r2

本仓库仅用于向 Reviewer 传递一个最小核验包，作为聊天附件的替代通道。
不含 Stage A 数据文件，不含任何凭据，提交方主项目仓库未被改动。

## 唯一有效附件

| 项 | 值 |
| --- | --- |
| 文件 | `audit_minimal_v28_r2.zip` |
| 字节 | 47,810 |
| SHA-256 | `ceea9a9e0a34dca87addb69ba0b04d9ac4478f5446f9f12476929d9c5c6e8873` |
| ZIP 条目 | 8 个 |

同名 `audit_minimal_v28.zip` 曾被覆盖两次，已作废，请勿使用。
三版（A / B / C）的辨识方法见包内 `VERSION_MAP.txt`。

## 下载与校验

```sh
BASE=https://raw.githubusercontent.com/esanwu-bot/stageA-audit-v28/main
curl -fL -O "$BASE/audit_minimal_v28_r2.zip"
curl -fL -O "$BASE/CHECKSUM.txt"
sha256sum -c CHECKSUM.txt

unzip -l audit_minimal_v28_r2.zip                 # 应为 8 个条目
unzip -o audit_minimal_v28_r2.zip -d r2
cd r2
sha256sum -c SHA256SUMS.txt                      # 4 行 OK
wc -l test_verify_reviewer.py                   # 743（旧版 720）
grep -n 'skip("T7a"' test_verify_reviewer.py    # 命中第 425 行
grep -n 'check("T7a", "无法创建' test_verify_reviewer.py   # 必须无输出
grep -n 'with io.open' test_verify_reviewer.py  # 306 / 310 / 652 / 656
```

## 复跑（需自备已核验的 Stage A 数据目录）

```sh
cd r2
python verify_reviewer.py --dir <DATA>
python -W error test_verify_reviewer.py --data <DATA> --verifier verify_reviewer.py
```

预期结果：

- 主验证器：`PASS=10 FAIL=0 SKIP=0`、`OVERALL_PASS=true`、退出码 0。
- 定向回归（junction 可用）：`共 81 项，PASS=81 SKIP=0 FAIL=0`、退出码 0。
- 定向回归（junction 不可用）：`共 81 项，PASS=79 SKIP=2 FAIL=0`、退出码 0，
  `SKIP 明细：T7a, T7b`。
- `PYTHON_REPRODUCIBILITY = UNVERIFIED (config 无 generation_python 记录)`。

## 口径边界

- `T11b` 会改动 `sampling_config.json`，使 V10 哈希比对必然 FAIL，因此它
  **不能**作为整套 `OVERALL_PASS=true` 的证据，只证明独立状态行未被削弱。
- 跨 Python 版本复现性保持 `UNVERIFIED`，未补 `generation_python`，
  不声明跨版本 VERIFIED。
- 数据侧 8 个哈希保持冻结；未做真实分类，未做 git 提交。
- 本仓库只是文件传输通道，不代表审计结论。当前裁定仍为
  `SCRIPT_AUDIT_PARTIAL_PASS`，以 Reviewer 的独立执行结果为准。

## r3（v2.8_r3，本轮交付）

r2 包仍保留在根目录，仅作为 C 版历史基线；本轮核验对象是 `r3/` 目录。

| 项 | 值 |
| --- | --- |
| 最小实物包 | `r3/audit_minimal_v28_r3.zip` |
| 字节 | 34,049 |
| SHA-256 | `866cc36f6dc263e3efa89869a251957a77b2fd30f72ce916aa0b3df8faf65f9e` |
| ZIP 条目 | 6 个（要求的 5 个文件 + 外层验证脚本，因 SHA256SUMS.txt 第 3 行列了它） |

```sh
BASE=https://raw.githubusercontent.com/esanwu-bot/stageA-audit-v28/main/r3
curl -fL -O "$BASE/audit_minimal_v28_r3.zip"
curl -fL -O "$BASE/CHECKSUM_r3.txt"      # 包体校验清单在 r3/ 目录内
sha256sum -c CHECKSUM_r3.txt
unzip -o audit_minimal_v28_r3.zip -d r3 && cd r3
sha256sum -c SHA256SUMS.txt               # 5 行 OK
```

逐项直链：`$BASE/verify_reviewer.py`、`$BASE/test_verify_reviewer.py`、
`$BASE/verify_reviewer_v2.8_to_r3.diff`、
`$BASE/test_verify_reviewer_v2.8_to_r3.diff`、`$BASE/SHA256SUMS.txt`。

说明文件：`r3/REVIEWER_LETTER_v28_r3.txt`、`r3/R3_CHANGES.txt`、
`r3/test_three_state_v28r3.py`（外层三态定向验证）。

## v2.8 r4 最小核验包

BASE: `https://raw.githubusercontent.com/esanwu-bot/stageA-audit-v28/main/r4`

| 项 | 值 |
| --- | --- |
| 包体 | `audit_minimal_v28_r4.zip` |
| 字节 | 38,641 |
| SHA-256 | `bac3368991171941b7bf74fc62f0e006e0a063c78477b823438349cd6f01e0eb` |
| ZIP 条目 | 8 个（SHA256SUMS.txt 列出的 7 个文件 + 清单自身） |

r4 只收窄了 `test_verify_reviewer.py` 第 422 行 T7 的异常捕获，主程序
`verify_reviewer.py` 未改动，字节与 r3 一致。

```sh
BASE=https://raw.githubusercontent.com/esanwu-bot/stageA-audit-v28/main/r4
curl -fL -O "$BASE/audit_minimal_v28_r4.zip"
curl -fL -O "$BASE/CHECKSUM_r4.txt"
sha256sum -c CHECKSUM_r4.txt
unzip -o audit_minimal_v28_r4.zip -d r4
cd r4 && sha256sum -c SHA256SUMS.txt
```

变更说明见 `r4/R4_CHANGES.txt`，正式回信见
`r4/REVIEWER_LETTER_v28_r4.txt`。本仓库只是文件传输通道，不代表审计
结论；当前裁定仍为 `SCRIPT_AUDIT_PARTIAL_PASS`。

## Gate 6 第二轮交付（r2）

BASE: `https://raw.githubusercontent.com/esanwu-bot/stageA-audit-v28/main/gate6/r2`

本轮**只请求 Gate 6A Parser-only Benchmark 方案的审批**，不请求开始跑任何测试。
路线已按 Reviewer 裁定调整：先验证 Parser，再决定是否接 LLM。
Gate 6C（LLM 接入）暂缓、Gate 6D 与 320 件未批准。

- 首要：`GATE6A_PARSER_BENCHMARK.md`（含 `ic-ex` 架构核查、三方字段对齐、
  历史痛点放大）、`GATE6A_SAMPLE_PROPOSAL.csv`、`GATE6A_SAMPLE_STATS.json`
- 上一轮 6 项（暂缓草案）：`FIELD_MAPPING_FULL.md` / `FIELD_MAPPING_REVIEW.csv` /
  `FIELD_MAPPING_SOURCE.csv`、`ACCEPTANCE_12.md`、`P1_FIX_DESIGN.md`、
  `TARGET_CALL_CHAIN.md`、`POSTGRES_MODEL_DRAFT.md`、`GIT_BASELINE_ISOLATION.md`
- 完整性：`SHA256SUMS.txt`、`ROUND2_VERIFY.json`、`GIT_BASELINE.json`、
  `BASELINE_FREEZE.csv`、`README.md`

```sh
BASE=https://raw.githubusercontent.com/esanwu-bot/stageA-audit-v28/main/gate6/r2
curl -fL -O "$BASE/SHA256SUMS.txt"
# 下载下列文件后执行： sha256sum -c SHA256SUMS.txt
```

**证据边界**：`ROUND2_VERIFY.json` 的 9/9 PASS 与 `sha256sum` 的 17 OK
只证明交付件字节完整与内部一致，不证明审计结论、字段映射或方案已通过独立审核。
本仓库只是文件传输通道，权威基线仍为本地 `E:\workspace\icpdf-extractor`
（HEAD `3ed22a4a83564b36ca238792af4b2328fd966469`）。
