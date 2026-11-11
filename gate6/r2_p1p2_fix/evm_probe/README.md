# evm_probe — 两份真实 EVM 样本的只分类探针

**判定：`PROBE_PASS`**（安全全绿；分类侧 B 完美，A 为 fail-closed 的 `AMBIGUOUS`）

模式：`ICEX_WORKBENCH_ALLOW_PARSE=1` + `ICEX_CLASSIFY_ONLY=1`，仅 `127.0.0.1:8765`，串行 2 次 `POST /api/process`。

## 先读哪个

| 目的 | 文件 |
| --- | --- |
| 看结论与归因分析 | `PROBE_REPORT.md` |
| 直接看安全字段对照 | `60_safety_matrix.md` |
| 看原始响应 | `10_A_response.json` / `20_B_response.json` |
| 看 `runs/` 是否零新增 | `01_snapshot_before.json` vs `30_snapshot_after.json` |
| 复现证据生成 | `_snapshot_dirs.py` / `_extract_safety.py` |

## 三行结论

1. 两份样本 **都没有进入 Parser**：`parse_pdf_calls=0`、`parser.stages_seen=[]`、`runs/` 97→97 且 rollup 指纹未变。
2. **B（BQ25570EVM-206）** 判为 `NON_DATASHEET` / `doc_type=EVM` / `route=QUARANTINE` —— 5 条 DS 证据被 `overridden_by_board_evidence` 显式否决，路径完全符合预期。
3. **A（ADC08060EVM）** 判为 `AMBIGUOUS` / `UNKNOWN` / `REVIEW` —— 元数据标题 `ADC08xx0 Evaluation Module User's Guide` 让 `DS_PRODUCT_MODEL_TITLE` 在**标题字符串**里匹配到型号，与 EVM 证据形成强对强冲突。fail-closed 拦住，但多一次人工复核。

## 两个容易误读的点

- **`safety_blocked` 为 `null` 不代表哨兵失效**。哨兵的 L1 在 `decision == DATASHEET` 之后才生效；两份都在分类阶段就被判非 DATASHEET，哨兵没轮到出手——这是更强结果，不是更弱。
- **「服务日志无 `[WORKER]` 行」不能作为证据**。worker stdout 走管道、不继承到服务 stdout；上一轮确实解析过的 V002 日志同样 0 条 `[WORKER]`。权威判据是响应里的 `parser.stages_seen`（两份均为 `[]`）。

## 复跑

```bash
ICEX_WORKBENCH_ALLOW_PARSE=1 ICEX_CLASSIFY_ONLY=1 \
  py -3.13 workbench/serve_parser.py --host 127.0.0.1 --port 8765
```

校验完整性：`sha256sum -c SHA256SUMS.txt`
