# Ds Bit 工作台 · 本地端到端截图

**这些截图来自本机 `http://127.0.0.1:8000`，不是 DO 服务器。** 没有公网地址、
没有 TLS、没有鉴权。把它们当作「前后端在单机上真的通了」的证据，
不要当作线上验收。

启动方式：

```bash
ICEX_WORKBENCH_ALLOW_PARSE=1 ICEX_WORKBENCH_PORT=8000 py -3.13 workbench/serve_parser.py
```

浏览器打开 `http://127.0.0.1:8000`，上传样例 PDF（V101 / CD74HCT574，21 页）。

## 五张图分别证明什么

| 文件 | 证明的事 |
| --- | --- |
| `dsbit_landing.png` | 落地页可用，状态栏显示「后端已连接」，可以上传 |
| `dsbit_e2e_result.png` | JSON 页签里是 `POST /api/parse` 的**真实响应**，`run_id`、`document_sha256`、`parser.version 0.1.0`、`tables 14` 全部来自实际解析 |
| `dsbit_e2e_full.png` | 左右分栏：左边完整 JSON，右边页面图 + 红框，底部「红框 54 处」 |
| `dsbit_redbox_closeup.png` | 红框特写：54 个框精准落在 Ordering Information 表格的每个单元格上 |
| `dsbit_invalid_file.png` | 上传 `.txt` 时的报错：红色状态条 `[INVALID_FILE] 不是 PDF 文件`，**不是白屏** |

## 红框是怎么画上去的

不依赖 `evidence` 字段，也不依赖前端自己算像素：

1. 后端返回 `parser_output.candidates[]`，每项带 `page_number` 和 `bbox`
   （PDF 点坐标，1 pt = 1/72 inch）；
2. 页面图是 Parser 渲染的 PNG，后端同时给出该页的 `rect`（页面盒子，单位 pt）；
3. 前端把 `bbox` 直接写成 SVG `<rect>`，`viewBox` 用页面 `rect`，
   `preserveAspectRatio="none"`，浏览器负责缩放。

所以红框能证明「**这个候选在原文哪一页的哪个位置**」，
但**不能**证明它被判定为某个参数——那是 Eval 层的事，见 `lake/`。

## 与三层湖的关系

这两条路径是**分开**的，不要混：

- `workbench/` 是**交互式单件观察台**，产物落在 `workbench/runs/<run_id>/`，
  给人看红框、看 diagnostics；
- `lake/` 是**批量血缘 Demo**，产物落在 `lake/parse_layer/<run_id>/`，
  给机器校验、给 DuckDB 查询。

两者的 `run_id` 前缀不同（`G6A-…` vs `V101-…`），不要拿一边的 `run_id`
去查另一边的表。
