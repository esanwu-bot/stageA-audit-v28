# classify_only_guard — 只分类哨兵（`ICEX_CLASSIFY_ONLY`）

**本目录是增量包**：父目录 `gate6/r2_p1p2_fix/` 的冻结快照与其 `SHA256SUMS.txt` **保持不变**，本目录只描述「物理切断 Parser 调用路径」这一处改动。

## 先读哪个

| 目的 | 文件 |
| --- | --- |
| 看结论与三层拦截的代码证明 | `GUARD_REPORT.md` |
| 只看代码改了什么 | `CLASSIFY_ONLY_GUARD.diff`（168 行 / 2 文件 / 9 补丁点） |
| 复现「强注 DATASHEET 也调不到 `parse_pdf`」 | `test_classify_only_guard.py` + `_pytest_guard.log` |
| 复跑静态验收（61 项） | `_verify_p1p2_static.py` + `_p1p2_static_verify_guard.log` |
| 自己验证 diff 可应用且逐字节还原 | `pre_guard/` + `serve_parser.py` / `parse_worker.py` |

## 核心命题

`ICEX_CLASSIFY_ONLY=1` 时，`parse_pdf()` 调用次数**恒为 0**。

三层拦截，任一层生效即可：

| 层 | 位置 | 行为 |
| --- | --- | --- |
| L1 | `api_parse` / `api_process` | 返回 `status=SAFETY_BLOCKED`，不调度 worker、不建 Run 目录 |
| L2 | `_execute_parse()` 第一行 | 抛 `SafetyBlocked`，连 `run_id` 都不创建 |
| L3 | `parse_worker.py` | 进程内自查，在 `import parser` **之前**退出（exit 3） |

## 开关矩阵

| `ALLOW_PARSE` | `CLASSIFY_ONLY` | 行为 |
| --- | --- | --- |
| `0` | 任意 | 全 `FROZEN`，连请求体都不读 |
| `1` | `0` | 正常：分类 → 仅 `DATASHEET` 才解析 |
| `1` | `1` | **只分类**：分类结果照常返回，Parser 被切断 |

## 复现

```bash
# 单测（5 passed）
py -3.13 -m pytest test_classify_only_guard.py -v

# 静态验收（61/61 PASS）
py -3.13 _verify_p1p2_static.py

# diff 可应用 + 逐字节还原（注意必须关掉 autocrlf）
mkdir -p /tmp/v/workbench && cp pre_guard/*.py /tmp/v/workbench/
cd /tmp/v && git -c core.autocrlf=false apply -p1 <path>/CLASSIFY_ONLY_GUARD.diff
cmp /tmp/v/workbench/serve_parser.py <path>/serve_parser.py   # 应无输出
```

校验完整性：`sha256sum -c SHA256SUMS.txt`
