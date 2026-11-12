#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DuckDB 联合查询 Demo：一条 SQL 从 eval 追到 parse 再追到 raw。

三个查询，回答三个不同的问题：

  Q1  eval → parse → raw 的完整链路（含当时用的 Parser 指纹与配置哈希）
  Q2  同一组可复现条件下，是否保留了多次执行（证明 run_id 才是身份）
  Q3  某次 run 的候选在原文里的分布（证明 Parquet 侧可独立聚合）

用法：py -3.13 lake/_query_demo.py [--run-id XXXX]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

LAKE = Path(__file__).resolve().parent
DB = LAKE / "catalog.duckdb"


def show(con, title: str, sql: str, params=None) -> None:
    print(f"\n--- {title} ---")
    print(sql.strip())
    rel = con.execute(sql, params or [])
    cols = [d[0] for d in rel.description]
    rows = rel.fetchall()
    if not rows:
        print("(无结果)")
        return
    widths = [max(len(str(c)), *(len(str(r[i])) for r in rows)) for i, c in enumerate(cols)]
    print(" | ".join(str(c).ljust(w) for c, w in zip(cols, widths)))
    print("-+-".join("-" * w for w in widths))
    for r in rows:
        print(" | ".join(str(v).ljust(w) for v, w in zip(r, widths)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args()
    if not DB.is_file():
        print(f"缺少 {DB}，先跑 lake/_build_lake.py", file=sys.stderr)
        return 1

    con = duckdb.connect(str(DB), read_only=True)
    run_id = args.run_id or con.execute(
        "SELECT run_id FROM parse_runs ORDER BY created_at DESC LIMIT 1").fetchone()[0]

    # Q1：跨三层
    show(con, "Q1  eval → parse → raw（给定 run_id 一条 SQL 追到底）", f"""
SELECT  e.run_id,
        e.source_sha256,
        p.parser_fingerprint,
        p.parser_commit,
        p.config_hash,
        r.file        AS raw_file,
        r.bytes       AS raw_bytes,
        e.gold_version,
        e.semantic_hit_rate
FROM    eval_results e
JOIN    parse_runs  p USING (run_id)
JOIN    raw_docs    r ON r.source_sha256 = p.source_sha256
WHERE   e.run_id = '{run_id}'
""")

    # Q2：run_id 独立性
    show(con, "Q2  同一组可复现条件下保留了多次执行（run_id 才是执行身份）", """
SELECT  reproducibility_key,
        count(*)              AS runs_with_same_conditions,
        count(DISTINCT run_id) AS distinct_run_ids,
        min(created_at)       AS first_run,
        max(created_at)       AS last_run
FROM    parse_runs
GROUP BY reproducibility_key
ORDER BY runs_with_same_conditions DESC
""")

    # Q3：Parquet 侧聚合
    show(con, "Q3  candidates 按 run 聚合（Parquet 直读，不经 JSON）", f"""
SELECT  run_id,
        count(*)                                             AS candidates,
        count(DISTINCT page_number)                          AS pages_with_candidates,
        count(DISTINCT table_id)                             AS tables,
        sum(CASE WHEN column_role = 'value' THEN 1 ELSE 0 END) AS value_cells
FROM    candidates
WHERE   run_id = '{run_id}'
GROUP BY run_id
""")

    # Q4：硬约束自证——run_id 是主键，三元组不是
    show(con, "Q4  约束自证：三元组无唯一约束，run_id 有", """
SELECT  (SELECT count(*) FROM duckdb_constraints()
         WHERE table_name = 'parse_runs' AND constraint_type = 'PRIMARY KEY') AS pk_count,
        (SELECT count(*) FROM duckdb_constraints()
         WHERE table_name = 'parse_runs' AND constraint_type = 'UNIQUE')      AS unique_count
""")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
