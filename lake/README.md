# Stage B · 单件血缘 Demo（V101）

一条 PDF 从原始字节走到评估结论，中间每一层都能独立校验。这不是架构图，
是能跑的东西：三个脚本、一个 DuckDB 库、两份 run。

## 三层各管一件事

```
raw_layer/<sha256>/          原始 PDF，目录名就是内容哈希，文件权限 0o444
  RAW.json                   哈希、字节数、只读策略、来源路径
parse_layer/
  _blobs/<sha256>/<name>     解析产物按内容寻址（两次 run 相同则只存一份）
  <run_id>/run_manifest.json 四个绑定 + 产物清单 + 依赖锁哈希
  <run_id>/config_snapshot.json
  <run_id>/candidates.parquet
eval_layer/
  gold/gold_v1.0.0/          Gold 定稿 + GOLD_MANIFEST.json（逐文件 sha256）
  <run_id>/eval.json         指标 + Gold 版本 + 评估器指纹
  <run_id>/attribution.csv   逐行归因
catalog.duckdb               三张表 + v_lineage 视图
```

## 四个绑定，两重身份

| 字段 | 值（V101） | 作用 |
| --- | --- | --- |
| `source_sha256` | `059d448c5a34a4b1…` | 输入内容身份 |
| `parser_fingerprint` | `7e70c1f801004c54…` | 27 个 `.py` 合并哈希（v2 postfix） |
| `config_hash` | `ab9f12527767c7df…` | `configs/parser.yaml` 快照 |
| `run_id` | `V101-20261112T231416Z-ff12` | **执行身份** |

前三个合起来是**可复现条件**，`reproducibility_key = sha256(三者拼接)`。
`run_id` 是**执行身份**——同样的条件跑两次，得到两个 `run_id`，两条记录都留着。

为什么 `parser_fingerprint` 不用 commit SHA：v2 那次复跑跑在「修复已写好但
未提交」的工作树上（`dirty_files` 199 项）。commit SHA 描述不了那份字节，
27 文件合并哈希可以。

## 三个脚本

```bash
py -3.13 lake/_build_lake.py --runs 2 --reset   # 建湖（默认 2 个 run，为了证明身份独立）
py -3.13 lake/_verify_lineage.py                # 跨层校验：eval → parse → raw
py -3.13 lake/_query_demo.py                    # DuckDB 四条 SQL
py -3.13 lake/_negative_tests.py                # 三个反例
py -3.13 lake/_s3_connectivity_test.py --local  # 同一段聚合 SQL 的本地模式
```

`_verify_lineage.py` 校验的不是「文件存在」，而是引用自洽：

- `eval.run_id == parse.run_id`（跨层主键）
- `parse.source_sha256 == raw 目录名 == raw 文件实算哈希`（内容寻址未被篡改）
- `eval.gold_version` 对应目录存在，且 Gold 文件哈希与清单一致
- `eval.evaluator_fingerprint == 当前 _evaluate.py 的 sha256`

## DuckDB：一条 SQL 追到底

```sql
SELECT e.run_id, e.source_sha256, p.parser_fingerprint,
       p.parser_commit, p.config_hash, r.file, r.bytes,
       e.gold_version, e.semantic_hit_rate
FROM   eval_results e
JOIN   parse_runs  p USING (run_id)
JOIN   raw_docs    r ON r.source_sha256 = p.source_sha256
WHERE  e.run_id = 'V101-20261112T231416Z-ff12';
```

实测输出（`_query_demo.py` Q1）：

```
run_id                     | parser_fingerprint   | parser_commit | config_hash  | raw_file   | gold_version | semantic
V101-20261112T231416Z-ff12 | 7e70c1f801004c54…    | bede1f581945… | ab9f125277…  | source.pdf | gold_v1.0.0  | 0.0
```

Q2 用 `GROUP BY reproducibility_key` 直接给出「同条件 2 次执行、2 个 run_id」；
Q4 查 `duckdb_constraints()` 证明 `parse_runs` 只有 1 个 PRIMARY KEY、0 个 UNIQUE
——三元组**刻意不加唯一约束**，否则重复执行会被数据库拒绝，历史就丢了。

## 三个反例

| 反例 | 期望 | 实测 |
| --- | --- | --- |
| raw 改 1 个 bit | 哈希失配，raw_layer 中无对应目录 | PASS |
| 发布新 Gold | `gold_v1.0.0` 字节不变，新旧目录并存 | PASS |
| 只有 eval、没有 manifest | 抛 `ManifestMissing`，不做尽力而为 | PASS |

## 关于 S3 / OSS

`_s3_connectivity_test.py` 用 DuckDB `httpfs` 直读 Parquet，同一段聚合 SQL
可切 `--local` / `--s3`。**本机没有任何 S3/OSS 凭据**，所以 S3 分支只验证了
「缺凭据时明确拒绝（退出码 2）」，没有跑过真实桶。

部署前必须先定一件事：**计算与存储同区**。DuckDB 直读对象存储时，每次 scan
都是 HTTP range 请求；跨区（例如 DO NYC 读国内 OSS）的 RTT 会把查询拖成几十倍，
这时不要直读，先把 Parquet 物化到本地 NVMe。同区（DO Spaces 同 region，或
国内 OSS + 国内计算节点）才有讨论直读的意义。

## 这个 Demo 没做的事

- 只有 1 个样本（V101），没有批量，没有并发。
- `lake/` 里的 PDF、`_blobs/`、`catalog.duckdb` 未入库（可重建），
  所以 clone 后 `_verify_lineage.py` 会因缺 raw 文件失败——这是预期，
  先跑 `_build_lake.py` 再验证。
- V101 的 `semantic_hit_rate` 是 **0.00%**（9 行语义命中全为 0）。逐行原因在
  `eval.json.reason_counts`：**6 行 `symbol_not_on_row`、3 行
  `condition_not_on_row:grouped_subheader`**。这是真实结果，不是 bug：
  V101 正是当初用来暴露「符号不在命中行」的样本。
  全库口径 58/105 = 55.24%，见 `eval.json` 的 `global_reference`。
