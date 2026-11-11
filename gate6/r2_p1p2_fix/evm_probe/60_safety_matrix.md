# 安全字段核对表（两份 EVM 样本，`ALLOW_PARSE=1` + `CLASSIFY_ONLY=1`）

判据来源：响应 JSON 内字段。**不采信「服务日志无 `[WORKER]` 行」**——
worker 的 stdout 走管道被父进程解析、不继承到服务 stdout，该条件恒真，无鉴别力
（已用上一轮确实解析过的 V002 日志反证：其日志同样 0 条 `[WORKER]`）。

| # | 安全字段 | 期望 | A (`ADC08060EVM__slau715a.pdf`) | B (`BQ25570EVM-206__sluuaa7a.pdf`) |
| --- | --- | --- | --- | --- |
| 1 | `parser.called` | `False` | `False` | `False` |
| 2 | `diagnostics.parse_pdf_calls` | `0` | `0` | `0` |
| 3 | `diagnostics.parse_worker_started` | `False` | `False` | `False` |
| 4 | `llm_called` | `False` | `False` | `False` |
| 5 | `parser.stages_seen（无 PARSER_CALL_* 标记）` | `[]` | `[]` | `[]` |

## 补充不变量

| 项 | 期望 | A | B |
| --- | --- | --- | --- |
| `parser.status` | `SKIPPED` | `SKIPPED` | `SKIPPED` |
| `parser.run_id` | `None` | `None` | `None` |
| `parser.run_dir` | `None` | `None` | `None` |
| `diagnostics.parser_call_count` | `0` | `0` | `0` |
| `parser_output` | `{}` | `{}` | `{}` |
| `classifier_llm_calls` | `0` | `0` | `0` |

## 哈希链

| 项 | A | B |
| --- | --- | --- |
| 源样本 SHA-256 | `09fabc2407fc5834f77c40b6f8a2b5bfb012caa983ac2724c950f9224a4c02ca` | `60aac1d0cad5e571feac7949f882b25a8eaaad814b190cbec333e7c0b5bb8d2e` |
| 与 Reviewer 给定值一致 | PASS | PASS |
| 上传副本 SHA-256 | `09fabc2407fc5834f77c40b6f8a2b5bfb012caa983ac2724c950f9224a4c02ca` | `60aac1d0cad5e571feac7949f882b25a8eaaad814b190cbec333e7c0b5bb8d2e` |
| 上传副本 == 源样本 | PASS | PASS |
| 响应 SHA-256 | `3ce79cf5b098224803abcf54eb20035e08f658e119d42eb316a249921148f773` | `a077c5cb12220779131611a1d6257acf15457ff1df2bac16ea540389bfb19743` |
| 响应字节数 | 9922 | 11327 |

## 分类结果

| 项 | A | B |
| --- | --- | --- |
| `status` | `AMBIGUOUS` | `NON_DATASHEET` |
| `classification.decision` | `AMBIGUOUS` | `NON_DATASHEET` |
| `classification.doc_type` | `UNKNOWN` | `EVM` |
| `classification.route` | `REVIEW` | `QUARANTINE` |
| `classification.classification_status` | `SUCCESS` | `SUCCESS` |
| `classification.read_status` | `OK` | `OK` |
| `classification.source_hash_status` | `success` | `success` |
| `classification.ic_datasheet_extraction` | `False` | `False` |
| `classification.evidence_conflict` | `True` | `False` |
| `classification.evidence_pages` | `[1, 2, 3]` | `[1, 2, 3]` |
| `classification.source_sha256` | `09fabc2407fc5834f77c40b6f8a2b5bfb012caa983ac2724c950f9224a4c02ca` | `60aac1d0cad5e571feac7949f882b25a8eaaad814b190cbec333e7c0b5bb8d2e` |
| `diagnostics.gate_decision` | `AMBIGUOUS` | `NON_DATASHEET` |
| `diagnostics.safety_blocked` | `None` | `None` |
| `diagnostics.safety_guard_layer` | `None` | `None` |
