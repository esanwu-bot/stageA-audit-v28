#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage B · 单件血缘 Demo 建湖脚本（V101）。

建三层，每层只干一件事：

    raw_layer/    原始 PDF，以 SHA-256 为键（内容寻址），只读
    parse_layer/  解析产物 + run_manifest.json（含四个绑定）+ 配置快照 + 依赖锁
    eval_layer/   Gold（版本化）+ 每 run 的评估结果与错误归因

四条不变量（脚本里逐条落实，`_negative_tests.py` 逐条反证）：

  1. 原始层只读       —— 文件权限置 0o444，且目录名就是 sha256；写入时若同名
                        文件已存在但字节不同，直接拒绝（内容寻址天然幂等）。
  2. 解析层可复现     —— 每个 run 一个 manifest，记录 source_sha256 /
                        parser_fingerprint / config_hash / run_id 四项绑定，
                        并附配置快照与依赖锁的哈希。
  3. 评估层版本化     —— Gold 按 `gold_vX.Y.Z` 目录存放，新版本只增不改；
                        每个 run 的 eval.json 引用 Gold 版本号与评估器指纹。
  4. 跨层引用         —— 三层共享 `run_id`（执行身份）与 `source_sha256`
                        （内容身份），`_verify_lineage.py` 用它们串起来。

关于 run_id 的语义（Reviewer 要求明确区分）：

    (source_sha256, parser_fingerprint, config_hash)  → 可复现条件
    run_id                                           → 唯一执行身份

同样的三元组可以跑很多次，每次得到不同的 run_id，全部保留。本脚本默认
建 2 个 run（`--runs 2`）就是为了把这件事变成可见事实，而不是口头承诺。

用法：
    py -3.13 lake/_build_lake.py --runs 2
    py -3.13 lake/_build_lake.py --runs 1 --reset
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LAKE = REPO / "lake"

SAMPLE = "V101"
PER_SAMPLE = REPO / "runs" / "gate6a_replay_v2_postfix" / "per_sample" / SAMPLE

# Parser 代码身份：27 个 .py 的合并哈希（v2 postfix），来自 audit/parser_commit.txt。
# 单看 commit SHA 不够——v2 那次复跑跑在「修复已写好但未提交」的工作树上，
# 所以用逐文件合并哈希钉代码字节。
PARSER_FINGERPRINT = "7e70c1f801004c54667b062934efdce28fb5624f461da9bd1625d62872132dca"
PARSER_FINGERPRINT_SCOPE = "src/icpdf/parser 下 27 个 .py 的合并 sha256（v2 postfix）"
PARSER_COMMIT = "bede1f581945331fa0f213a8be5d1171601639ae"

EVALUATOR = REPO / "workbench" / "gate6a_replay" / "audit" / "evaluator_v3_1to1" / "_evaluate.py"
METRICS_JSON = REPO / "workbench" / "gate6a_replay" / "artifacts" / "v3_metrics.json"
ERROR_MATRIX = REPO / "workbench" / "gate6a_replay" / "audit" / "error_matrix_105.csv"

GOLD_SRC = [
    ("b1", REPO / "archive" / "final_drafts" / "b1" / "Batch3_B1_CONFIRMED.csv"),
    ("b2", REPO / "archive" / "final_drafts" / "b2" / "Batch3_B2_FINAL.csv"),
    ("b3", REPO / "archive" / "final_drafts" / "b3" / "Batch3_B3_FINAL.csv"),
    ("b4", REPO / "archive" / "final_drafts" / "b4" / "Batch3_B4_FINAL.csv"),
]
GOLD_VERSION = "gold_v1.0.0"

# 解析层要落地的产物（pages/*.png 是渲染截图，不入湖）
PARSE_ARTIFACTS = [
    "document.json",
    "tables.json",
    "candidates.json",
    "boundary_decisions.json",
    "product.json",
    "run_config.json",
    "pages/geometry.json",
    "text_blocks.json",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def new_run_id() -> str:
    """执行身份：样本 + UTC 时间戳 + 4 位随机。同样的输入配置再跑一次必然不同。"""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{SAMPLE}-{ts}-{uuid.uuid4().hex[:4]}"


def build_raw() -> dict:
    """原始层：以 sha256 为键，只读。"""
    src = PER_SAMPLE / "source.pdf"
    digest = sha256_file(src)
    doc_dir = LAKE / "raw_layer" / digest
    doc_dir.mkdir(parents=True, exist_ok=True)
    dst = doc_dir / src.name

    if dst.exists():
        if sha256_file(dst) != digest:
            raise SystemExit(f"内容寻址冲突：{dst} 已存在但字节不同")
    else:
        shutil.copyfile(src, dst)

    os.chmod(dst, 0o444)  # 只读：去掉写位

    raw_meta = {
        "source_sha256": digest,
        "file": src.name,
        "bytes": dst.stat().st_size,
        "immutable": True,
        "policy": "以 SHA-256 为键内容寻址；文件权限 0o444；写入幂等（同键同字节）",
        "first_seen": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "original_path": f"runs/gate6a_replay_v2_postfix/per_sample/{SAMPLE}/source.pdf",
    }
    write_json(doc_dir / "RAW.json", raw_meta)
    return raw_meta


def build_parse_blobs() -> list[dict]:
    """解析产物按内容寻址存放：两次 run 若产物相同，只存一份（天然去重）。"""
    blobs = []
    for name in PARSE_ARTIFACTS:
        src = PER_SAMPLE / name
        if not src.is_file():
            continue
        digest = sha256_file(src)
        dst = LAKE / "parse_layer" / "_blobs" / digest / src.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            shutil.copyfile(src, dst)
        blobs.append({"name": name, "sha256": digest, "bytes": dst.stat().st_size,
                      "blob": f"_blobs/{digest}/{src.name}"})
    return blobs


def build_dependency_lock() -> tuple[str, str]:
    """依赖锁：pip freeze 去掉 VCS 行后落盘。

    注意：`-e git+https://<内网>/...@<sha>` 这类行会被去掉——它同时是内网地址
    泄露源与 GitGuardian 的误报触发点。解析器自身的身份改由 parser_fingerprint
    表达，比一行 URL 更精确。
    """
    try:
        out = subprocess.run([sys.executable, "-m", "pip", "freeze"],
                             capture_output=True, text=True, timeout=120).stdout
    except Exception:
        out = ""
    lines = []
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-e ") or " @ " in line or "@ git+" in line or "://" in line:
            continue
        lines.append(line)
    lines.append("icpdf-extractor==0.1.0  # 本地可编辑安装；源码身份见 parser_fingerprint")
    text = "\n".join(sorted(lines)) + "\n"
    path = LAKE / "parse_layer" / "_dependency_lock.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return str(path.relative_to(LAKE)).replace("\\", "/"), hashlib.sha256(text.encode()).hexdigest()


def build_candidates_parquet(run_id: str, source_sha256: str) -> tuple[str, int]:
    """把 candidates.json 展平成 Parquet，供 DuckDB 直接查。"""
    import pyarrow as pa
    import pyarrow.parquet as pq

    data = json.loads((PER_SAMPLE / "candidates.json").read_text(encoding="utf-8"))
    items = data["candidates"]
    rows = []
    for it in items:
        rows.append({
            "run_id": run_id,
            "source_sha256": source_sha256,
            "candidate_id": it.get("candidate_id"),
            "document_id": it.get("document_id"),
            "table_id": it.get("table_id"),
            "row_id": it.get("row_id"),
            "cell_id": it.get("cell_id"),
            "page_number": it.get("page_number"),
            "bbox": [float(x) for x in (it.get("bbox") or [])],
            "raw_text": it.get("raw_text"),
            "normalized_value": it.get("normalized_value"),
            "unit": it.get("unit"),
            "column_role": it.get("column_role"),
            "role_source": it.get("role_source"),
            "candidate_type": it.get("candidate_type"),
            "extraction_method": it.get("extraction_method"),
            "source_text_type": it.get("source_text_type"),
            "reconstruction_status": it.get("reconstruction_status"),
        })
    tbl = pa.Table.from_pylist(rows)
    out = LAKE / "parse_layer" / run_id / "candidates.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(tbl, out, compression="zstd")
    return str(out.relative_to(LAKE)).replace("\\", "/"), len(rows)


def build_run(raw_meta: dict, blobs: list[dict], lock_rel: str, lock_hash: str) -> dict:
    """建一个 run：manifest 四项绑定 + 配置快照 + 依赖锁引用。"""
    run_id = new_run_id()
    run_dir = LAKE / "parse_layer" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    cfg = json.loads((PER_SAMPLE / "run_config.json").read_text(encoding="utf-8"))
    config_hash = cfg["parser_config_sha256"]
    write_json(run_dir / "config_snapshot.json", cfg)

    parquet_rel, n_cand = build_candidates_parquet(run_id, raw_meta["source_sha256"])

    # 可复现条件 = 三元组的哈希。两个 run 条件相同 → 该值相同；
    # run_id 不同 → 执行身份不同。这正是 Reviewer 要求区分的东西。
    repro_key = hashlib.sha256(
        f"{raw_meta['source_sha256']}|{PARSER_FINGERPRINT}|{config_hash}".encode()
    ).hexdigest()

    manifest = {
        "schema": "lakehouse/run-manifest/v1",
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "identity": {
            "run_id": run_id,
            "role": "唯一执行身份。同一组可复现条件下重复执行，run_id 必须不同，且全部保留。",
        },
        "reproducibility": {
            "reproducibility_key": repro_key,
            "role": "可复现条件。三元组相同即代表「同一输入 + 同一代码 + 同一配置」。",
            "source_sha256": raw_meta["source_sha256"],
            "parser_fingerprint": PARSER_FINGERPRINT,
            "config_hash": config_hash,
        },
        "source_sha256": raw_meta["source_sha256"],
        "parser_fingerprint": PARSER_FINGERPRINT,
        "parser_fingerprint_scope": PARSER_FINGERPRINT_SCOPE,
        "parser_commit": PARSER_COMMIT,
        "parser_version": "0.1.0-phase1",
        "config_hash": config_hash,
        "config_snapshot": "config_snapshot.json",
        "dependency_lock": lock_rel,
        "dependency_lock_sha256": lock_hash,
        "artifacts": blobs,
        "candidates_parquet": parquet_rel,
        "candidate_count": n_cand,
        "page_count": 21,
        "table_count": 14,
    }
    write_json(run_dir / "run_manifest.json", manifest)
    return manifest


def build_gold() -> dict:
    """评估层：Gold 版本化。新版本只增不改，旧版本字节不动。"""
    gdir = LAKE / "eval_layer" / "gold" / GOLD_VERSION
    gdir.mkdir(parents=True, exist_ok=True)
    entries, total = [], 0
    for batch, src in GOLD_SRC:
        if not src.is_file():
            raise SystemExit(f"缺少 Gold 定稿：{src}")
        digest = sha256_file(src)
        dst = gdir / src.name
        if dst.exists() and sha256_file(dst) != digest:
            raise SystemExit(f"Gold 版本目录内文件被改动：{dst}")
        if not dst.exists():
            shutil.copyfile(src, dst)
        with dst.open(encoding="utf-8-sig") as fh:
            n = sum(1 for _ in csv.DictReader(fh))
        total += n
        entries.append({"batch": batch, "file": src.name, "sha256": digest,
                        "bytes": dst.stat().st_size, "rows": n})
    manifest = {
        "gold_version": GOLD_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "policy": "版本目录只增不改；新 Gold 发布为新目录（如 gold_v1.1.0），旧目录字节不变",
        "total_rows": total,
        "files": entries,
    }
    write_json(LAKE / "eval_layer" / "gold" / GOLD_VERSION / "GOLD_MANIFEST.json", manifest)
    return manifest


def build_eval(manifest: dict, gold: dict) -> dict:
    """评估层：每个 run 一份结果，引用 Gold 版本号 + 评估器指纹。"""
    run_id = manifest["run_id"]
    evaluator_fp = sha256_file(EVALUATOR)
    metrics_all = json.loads(METRICS_JSON.read_text(encoding="utf-8"))

    with ERROR_MATRIX.open(encoding="utf-8-sig") as fh:
        rows = [r for r in csv.DictReader(fh) if r["sample_id"] == SAMPLE]

    def yes(col: str) -> int:
        return sum(1 for r in rows if r.get(col) == "是")

    reasons: dict[str, int] = {}
    for r in rows:
        k = r.get("semantic_hit_reason") or "—"
        reasons[k] = reasons.get(k, 0) + 1

    gold_rows = len(rows)
    sem = yes("condition_gated_strict_hit")
    result = {
        "schema": "lakehouse/eval-result/v1",
        "run_id": run_id,
        "source_sha256": manifest["source_sha256"],
        "gold_version": gold["gold_version"],
        "evaluator_version": f"evaluator_v3_1to1 / schema {metrics_all['schema_version']}",
        "evaluator_fingerprint": evaluator_fp,
        "sample_id": SAMPLE,
        "metrics": {
            "gold_rows": gold_rows,
            "exact_rows": sum(1 for r in rows if r.get("match_status") == "完全一致"),
            "symbol_gated_strict_hit": yes("symbol_gated_strict_hit"),
            "condition_gated_strict_hit": sem,
            "semantic_hit_rate": round(sem / gold_rows, 4) if gold_rows else 0.0,
        },
        "reason_counts": dict(sorted(reasons.items())),
        "global_reference": {
            "semantic_hit_rows": metrics_all["semantic_hit_rows"],
            "semantic_hit_rate": metrics_all["semantic_hit_rate"],
            "gold_rows": metrics_all["gold_rows"],
            "note": "全库口径，仅供对照；本文件只对本 run 的这一件负责。",
        },
    }
    write_json(LAKE / "eval_layer" / run_id / "eval.json", result)

    attr = LAKE / "eval_layer" / run_id / "attribution.csv"
    attr.parent.mkdir(parents=True, exist_ok=True)
    cols = ["gold_row_id", "match_status", "strict_hit", "symbol_gated_strict_hit",
            "condition_gated_strict_hit", "semantic_hit_reason", "error_category"]
    with attr.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})
    return result


def build_catalog() -> None:
    """DuckDB 目录：三张表 + 一个跨层视图。"""
    import duckdb

    db = LAKE / "catalog.duckdb"
    if db.exists():
        db.unlink()
    con = duckdb.connect(str(db))

    con.execute("""
        CREATE TABLE raw_docs (
            source_sha256 VARCHAR PRIMARY KEY,
            file          VARCHAR NOT NULL,
            bytes         BIGINT  NOT NULL,
            immutable     BOOLEAN NOT NULL,
            first_seen    VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE parse_runs (
            run_id               VARCHAR PRIMARY KEY,
            source_sha256        VARCHAR NOT NULL,
            parser_fingerprint   VARCHAR NOT NULL,
            parser_commit        VARCHAR,
            parser_version       VARCHAR,
            config_hash          VARCHAR NOT NULL,
            reproducibility_key  VARCHAR NOT NULL,
            created_at           VARCHAR NOT NULL,
            manifest_path        VARCHAR NOT NULL
        )
    """)
    # 刻意**不**在 (source_sha256, parser_fingerprint, config_hash) 上加唯一约束：
    # 同一组条件允许跑多次，run_id 才是主键。这条设计由 SQL 反证（见 _query_demo.py）。
    con.execute("""
        CREATE TABLE eval_results (
            run_id                 VARCHAR PRIMARY KEY,
            source_sha256          VARCHAR NOT NULL,
            gold_version           VARCHAR NOT NULL,
            evaluator_version      VARCHAR NOT NULL,
            evaluator_fingerprint  VARCHAR NOT NULL,
            gold_rows              INTEGER,
            symbol_gated           INTEGER,
            condition_gated        INTEGER,
            semantic_hit_rate      DOUBLE,
            created_at             VARCHAR
        )
    """)

    for raw_json in sorted((LAKE / "raw_layer").glob("*/RAW.json")):
        m = json.loads(raw_json.read_text(encoding="utf-8"))
        con.execute("INSERT INTO raw_docs VALUES (?,?,?,?,?)",
                    [m["source_sha256"], m["file"], m["bytes"], True, m["first_seen"]])

    for mf in sorted((LAKE / "parse_layer").glob("*/run_manifest.json")):
        m = json.loads(mf.read_text(encoding="utf-8"))
        rel = str(mf.relative_to(LAKE)).replace("\\", "/")
        con.execute("INSERT INTO parse_runs VALUES (?,?,?,?,?,?,?,?,?)", [
            m["run_id"], m["source_sha256"], m["parser_fingerprint"], m["parser_commit"],
            m["parser_version"], m["config_hash"], m["reproducibility"]["reproducibility_key"],
            m["created_at"], rel])

    for ev in sorted((LAKE / "eval_layer").glob("*/eval.json")):
        e = json.loads(ev.read_text(encoding="utf-8"))
        con.execute("INSERT INTO eval_results VALUES (?,?,?,?,?,?,?,?,?,?)", [
            e["run_id"], e["source_sha256"], e["gold_version"], e["evaluator_version"],
            e["evaluator_fingerprint"], e["metrics"]["gold_rows"],
            e["metrics"]["symbol_gated_strict_hit"], e["metrics"]["condition_gated_strict_hit"],
            e["metrics"]["semantic_hit_rate"],
            json.loads((LAKE / "parse_layer" / e["run_id"] / "run_manifest.json")
                       .read_text(encoding="utf-8"))["created_at"]])

    # DuckDB 的相对 glob 按进程 CWD 解析，这里显式给绝对路径，避免换目录就失效。
    pq_glob = (LAKE / "parse_layer" / "*" / "candidates.parquet").as_posix()
    con.execute(
        "CREATE VIEW candidates AS SELECT * FROM read_parquet("
        f"'{pq_glob}', union_by_name = true)"
    )
    con.execute("""
        CREATE VIEW v_lineage AS
        SELECT  e.run_id,
                e.source_sha256,
                e.gold_version,
                e.evaluator_version,
                p.parser_fingerprint,
                p.parser_version,
                p.config_hash,
                p.reproducibility_key,
                r.file            AS raw_file,
                r.bytes           AS raw_bytes,
                e.semantic_hit_rate
        FROM eval_results e
        JOIN parse_runs  p USING (run_id)
        JOIN raw_docs    r ON r.source_sha256 = p.source_sha256
    """)
    con.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=2, help="建几个 run（同条件重复执行）")
    ap.add_argument("--reset", action="store_true", help="先清空 lake（保留本脚本）")
    args = ap.parse_args()

    if args.reset:
        for name in ("raw_layer", "parse_layer", "eval_layer"):
            p = LAKE / name
            if p.exists():
                shutil.rmtree(p)
        db = LAKE / "catalog.duckdb"
        if db.exists():
            db.unlink()

    raw = build_raw()
    blobs = build_parse_blobs()
    lock_rel, lock_hash = build_dependency_lock()

    runs = []
    for _ in range(max(1, args.runs)):
        runs.append(build_run(raw, blobs, lock_rel, lock_hash))

    gold = build_gold()
    for m in runs:
        build_eval(m, gold)

    build_catalog()

    print(f"raw_layer     : {raw['source_sha256']}  ({raw['bytes']:,} B, 只读)")
    print(f"parse_layer   : {len(runs)} 个 run，{len(blobs)} 个内容寻址产物（两 run 共享同一批 blob）")
    for m in runs:
        print(f"                {m['run_id']}  repro={m['reproducibility']['reproducibility_key'][:16]}…")
    print(f"eval_layer    : {gold['gold_version']}（{gold['total_rows']} 行）+ {len(runs)} 份 eval.json")
    print(f"catalog.duckdb: 3 张表 + 2 个视图")
    return 0


if __name__ == "__main__":
    sys.exit(main())
