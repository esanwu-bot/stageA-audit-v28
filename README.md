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
