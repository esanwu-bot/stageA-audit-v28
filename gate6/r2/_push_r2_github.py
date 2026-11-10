#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 Gate 6 第二轮交付件推送到独立公开传输仓库（GitHub Contents API）。

该仓库只是文件传输通道，不是权威基线、不是审计依据。
凭据只在本进程内存中从 Git Credential Manager 读取，不落盘、不打印、
不写进任何交付文件。主项目 CodeUp 仓库不做任何 add / commit / push。
"""
from __future__ import annotations

import base64
import json
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

OWNER = "esanwu-bot"
REPO = "stageA-audit-v28"
BRANCH = "main"
API = "https://api.github.com/repos/%s/%s" % (OWNER, REPO)
REMOTE_DIR = "gate6/r2"
OUT = Path(__file__).resolve().parent


def get_token() -> str:
    proc = subprocess.run(
        ["git", "credential", "fill"],
        input=b"protocol=https\nhost=github.com\n\n",
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError("凭据读取失败")
    fields = {}
    for line in proc.stdout.decode("utf-8", "replace").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            fields[k] = v
    token = fields.get("password")
    if not token:
        raise RuntimeError("未取得 github.com 凭据")
    return token


def request(token: str, method: str, url: str, body=None):
    data = None
    headers = {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "User-Agent": "stageA-gate6-r2",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw.decode("utf-8")) if raw else {}
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode("utf-8", "replace")[:300]}


def content_url(path: str) -> str:
    return "%s/contents/%s" % (API, path)


def get_sha(token: str, path: str):
    status, obj = request(token, "GET", content_url(path) + "?ref=" + BRANCH)
    return obj.get("sha") if status == 200 else None


def upload(token: str, remote: str, data: bytes, message: str):
    body = {"message": message, "content": base64.b64encode(data).decode("ascii"),
            "branch": BRANCH}
    old = get_sha(token, remote)
    if old:
        body["sha"] = old
    status, obj = request(token, "PUT", content_url(remote), body)
    if status not in (200, 201):
        raise RuntimeError("上传失败 %s: HTTP %s %s" % (remote, status, obj))
    print("  OK  %-52s %8d B  %s" % (
        remote, len(data), obj.get("commit", {}).get("sha", "")[:7]))
    return obj


def update_root_readme(token: str, files: list[str]):
    status, obj = request(token, "GET", content_url("README.md") + "?ref=" + BRANCH)
    if status != 200:
        print("  WARN 根 README 读取失败，跳过: HTTP %s" % status)
        return
    old_text = base64.b64decode(obj["content"]).decode("utf-8")
    marker = "## Gate 6 第二轮"
    if marker in old_text:
        print("  SKIP 根 README 已含 Gate 6 第二轮节")
        return
    appendix = """
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
本仓库只是文件传输通道，权威基线仍为本地 `E:\\workspace\\icpdf-extractor`
（HEAD `3ed22a4a83564b36ca238792af4b2328fd966469`）。
"""
    body = {"message": "README 追加 Gate 6 第二轮取件节",
            "content": base64.b64encode(
                (old_text.rstrip() + "\n" + appendix).encode("utf-8")).decode("ascii"),
            "branch": BRANCH, "sha": obj["sha"]}
    status2, _ = request(token, "PUT", content_url("README.md"), body)
    print("  %s README.md HTTP %s" % ("OK  " if status2 in (200, 201) else "WARN", status2))


def main() -> int:
    token = get_token()
    status, repo = request(token, "GET", API)
    print("传输仓库状态: HTTP %s  %s" % (status, repo.get("full_name", repo.get("error", ""))))
    if status != 200:
        return 1

    files = sorted(p for p in OUT.iterdir() if p.is_file())
    print("待推送 %d 个文件 -> %s/" % (len(files), REMOTE_DIR))
    for p in files:
        upload(token, "%s/%s" % (REMOTE_DIR, p.name), p.read_bytes(),
               "Gate6 r2 交付: %s" % p.name)
    update_root_readme(token, [p.name for p in files])
    print("推送完成；主项目 CodeUp 仓库未做任何 add / commit / push")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
