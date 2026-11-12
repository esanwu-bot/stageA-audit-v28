#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S3 / OSS 连通性测试：用 DuckDB httpfs 直接读 Parquet 并跑聚合。

设计要点
--------
1. **同一段 SQL 跑两种后端**：`--local` 走本地 Parquet，`--s3` 走对象存储。
   SQL 一字不改，所以「本地通了但 S3 不通」一定是网络/凭据问题，不是 SQL 问题。
2. **凭据只从环境变量读**，不落盘、不打印。缺失就退出码 2 并说明缺哪个，
   绝不假装成功。
3. **推荐同区部署**：DuckDB 直接读对象存储时，每次 scan 都是一次 HTTP range
   请求。计算与存储跨区（例如 DO NYC 读国内 OSS）会因 RTT 把查询拖成几十倍。
   同区时按 §「实测」给出的吞吐判断是否可接受；跨区时不要这么做，
   改为先把 Parquet 物化到本地 NVMe 再查。

环境变量（--s3 模式）
--------------------
    S3_ENDPOINT     例如 https://nyc3.digitaloceanspaces.com（DO Spaces）
                    或 https://oss-cn-hangzhou.aliyuncs.com（阿里云 OSS）
    S3_BUCKET       桶名
    S3_PREFIX       桶内前缀，例如 lake/parse_layer
    S3_KEY / S3_SECRET
    S3_REGION       DO Spaces 用桶所在 region（nyc3/sgp1…）；OSS 用 oss-cn-xxx
    S3_URL_STYLE    path（默认，OSS 用）或 vhost（Spaces 用）

用法
----
    py -3.13 lake/_s3_connectivity_test.py --local
    py -3.13 lake/_s3_connectivity_test.py --s3 --prefix lake/parse_layer
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

LAKE = Path(__file__).resolve().parent

AGG_SQL = """
SELECT  count(*)                                    AS rows,
        count(DISTINCT run_id)                      AS runs,
        count(DISTINCT table_id)                    AS tables,
        count(DISTINCT page_number)                 AS pages,
        sum(CASE WHEN column_role = 'value'
                 THEN 1 ELSE 0 END)                 AS value_cells
FROM    read_parquet('{src}')
"""

REQUIRED = ["S3_ENDPOINT", "S3_BUCKET", "S3_KEY", "S3_SECRET"]


def configure(con) -> None:
    """把 S3 配置注入 DuckDB；不打印任何密钥。"""
    con.execute("INSTALL httpfs")
    con.execute("LOAD httpfs")
    endpoint = os.environ["S3_ENDPOINT"].replace("https://", "").replace("http://", "")
    style = os.getenv("S3_URL_STYLE", "path")
    region = os.getenv("S3_REGION", "")
    con.execute(f"SET s3_endpoint='{endpoint}'")
    con.execute(f"SET s3_access_key_id='{os.environ['S3_KEY']}'")
    con.execute(f"SET s3_secret_access_key='{os.environ['S3_SECRET']}'")
    con.execute(f"SET s3_url_style='{style}'")
    con.execute("SET s3_use_ssl=true")
    if region:
        con.execute(f"SET s3_region='{region}'")


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--local", action="store_true", help="读本地 Parquet（无需凭据）")
    g.add_argument("--s3", action="store_true", help="读对象存储（需环境变量）")
    ap.add_argument("--prefix", default="lake/parse_layer",
                    help="S3 模式下的桶内前缀")
    args = ap.parse_args()

    import duckdb

    con = duckdb.connect()
    if args.local:
        src = (LAKE / "parse_layer" / "*" / "candidates.parquet").as_posix()
        mode = "local"
    else:
        missing = [k for k in REQUIRED if not os.getenv(k)]
        if missing:
            print("缺少环境变量：" + ", ".join(missing), file=sys.stderr)
            print("未配置凭据时不会发起任何请求，也不会伪造成功结果。", file=sys.stderr)
            return 2
        configure(con)
        bucket = os.environ["S3_BUCKET"]
        src = f"s3://{bucket}/{args.prefix.rstrip('/')}/*/candidates.parquet"
        mode = f"s3://{bucket}/{args.prefix}"

    sql = AGG_SQL.format(src=src)
    print(f"模式      : {mode}")
    print(f"数据源    : {src}")
    t0 = time.time()
    try:
        cols = [d[0] for d in con.execute(sql).description]
        row = con.execute(sql).fetchone()
    except Exception as e:  # noqa: BLE001
        print(f"查询失败（{type(e).__name__}）：{e}", file=sys.stderr)
        return 1
    dt = time.time() - t0

    print(f"耗时      : {dt*1000:.0f} ms")
    print("结果      :")
    for c, v in zip(cols, row):
        print(f"  {c:12s} = {v}")
    if row[0] == 0:
        print("警告：0 行。本地模式请先跑 _build_lake.py；S3 模式请检查前缀与分区。",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
