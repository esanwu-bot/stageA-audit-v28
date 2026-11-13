# dsb.0668xgwl.com 限流落地证据包

> 对应 Reviewer 要求的 7 项证据
> 采集时间：2026-11-13 01:03–01:09 UTC（09:03–09:09 北京时间）
> 服务器：`159.89.190.225`　nginx/1.26.3　aaPanel　16 个站点
> 采集方式：全部为对生产机的只读采集 + 临时改参数实测，**取证后已完整还原并复验**

---

## 文件索引

| 文件 | 对应证据 |
|---|---|
| `01_xff_forgery_test.log` | 证据 1、2：6 次伪造 XFF 完整响应码 + nginx `limiting requests` 日志 |
| `02_nginx_T_dsb_server_block.conf` | 证据 4：`nginx -T` 展开后的 dsb server 块（183 行，仅本站点） |
| `03_app_side_effects.txt` | 证据 5、6：应用层副作用穷举排查 + `proxy_headers=False` 代码段 |
| `04_param_matrix.txt` | 证据 7：参数对照矩阵、误伤量化、推荐值推导 |
| `05_deploy_patch.md` | 证据 3：准备上线的两段配置完整原文 + 上线/回滚步骤 |

---

## 脱敏说明（重要）

**本包不公开完整的 `nginx -T` 输出。** 该输出为整台服务器全部站点的展开配置，
含其他租户的域名、上游端口与路径信息，不适合进入公开仓库。

作为替代，证据 4 提供：

1. **dsb 自己的 server 块完整原文**（`02_nginx_T_dsb_server_block.conf`，183 行）——
   Reviewer 可据此核对本站点的每一条指令；
2. **不含域名的 `grep` 统计结果**（见证据 4）——
   用计数与 block 归属证明「`dsb_parse` 只被 dsb 引用，其他站点零引用」。

两者合起来足以独立核验隔离性，且不泄露任何他站信息。

文中出现的 `site-a.example` / `site-b.example` … / `harness.example.com` 均为占位符，
分别代指同一台服务器上的其他站点（原域名已脱敏）。完整 `nginx -T` 原文保留在
内部审计目录，不随公开包分发，需要时可单独提供。


---

## 证据 1：伪造 XFF 的 6 次完整响应码

参数组 `10r/m + burst 2`（当时线上值），每次换一个伪造的 `X-Forwarded-For` 和 `X-Real-IP`：

```
203.0.113.1 -> 200
203.0.113.2 -> 200
203.0.113.3 -> 200
203.0.113.4 -> 429
203.0.113.5 -> 429
203.0.113.6 -> 429
```

若按 XFF 分桶，换 IP 应当每次都能过。第 4 次即被挡 → **分桶键是 `$binary_remote_addr`（TCP 对端），伪造头无效。**

同组实验还做了 15 连发（每次换 IP），截断点严格等于 `burst + 2`，四组参数全部复现 → 结论不是偶然。

## 证据 2：对应的 nginx 限流日志

```
2026/11/13 01:04:14 [warn] 1498806#0: *42747844 limiting requests, excess: 2.991 by zone "dsb_parse",
  client: 127.0.0.1, server: dsb.0668xgwl.com, request: "POST /api/parse HTTP/2.0"
...（共 7 条，完整原文见 01 号文件）
```

**7 条日志与响应码逐条对得上**：P1 的 3 次 429 + P2 的 2 次 429 + P3 的 2 次 429。

⚠️ **一个必须报备的坑**：dsb vhost 第 86 行的 `error_log` **没写级别（默认 `error`）**，
而 `limit_req_log_level` 在 http 级被设成了 `warn`，所以 `limiting requests` 平时**被日志级别过滤掉、根本看不见**。
本次取证时临时改成 `warn` 才抓到，**取证后已还原**。建议正式上线时把这一行定为 `warn`。

`client: 127.0.0.1` 是因为本次从服务器本机打本机（curl 走 127.0.0.1），不是 XFF 生效。

## 证据 3：准备上线的两段配置

见 `05_deploy_patch.md`，含 http 级 zone 定义 + nginx.conf 的 2 行 include + server 级两个 location 块完整原文。

## 证据 4：`nginx -T` 证明只影响 dsb

> 为保护其他租户的隐私，**不公开完整的 `nginx -T` 输出**，
> 仅提供 dsb 的隔离块（`02` 号文件）及以下 `grep` 统计结果证明未影响其他站点。

### 4.1 计数（不含任何他站域名）

```
$ nginx -T | grep -c "dsb_parse"
3

$ nginx -T | grep -c "limit_req zone=dsb_parse"
2

$ nginx -T | grep -c "limit_req_zone"
5

$ nginx -T | grep -c "limit_req zone="
9
```

| 指标 | 数值 | 含义 |
|---|---|---|
| `dsb_parse` 出现总次数 | **3** | 1 处定义 + 2 处引用 |
| `dsb_parse` 被引用次数 | **2** | 分别对应 `/api/parse` 与 `/api/process` |
| 全站 `limit_req_zone` 定义总数 | 5 | 4 个既有 + 1 个本次新增 |
| 全站 `limit_req` 引用总数 | 9 | 既有 7 处 + 本次新增 2 处 |

### 4.2 归属：引用 `dsb_parse` 的 server 块只有一个

对展开后的配置按 `server {}` 分块，统计哪一块引用了 `dsb_parse`：

```
  block#5  server_name=dsb.0668xgwl.com
```

**有且仅有 1 个 server 块引用 `dsb_parse`，就是 dsb 自己。**
其余 server 块对 `dsb_parse` 的引用数为 **0**，配置零变化。

### 4.3 定义位置（http 级，只有一处）

```
limit_req_zone $binary_remote_addr zone=dsb_parse:10m rate=10r/m;   ← 定义（http 级，仅 1 处）
        limit_req zone=dsb_parse burst=2 nodelay;                   ← /api/parse
        limit_req zone=dsb_parse burst=2 nodelay;                   ← /api/process
```

### 4.4 交叉核对方式（Reviewer 可自行复现）

```bash
# 在服务器上执行，不需要下载任何他站配置
nginx -T 2>/dev/null | grep -c "dsb_parse"                    # 期望 3
nginx -T 2>/dev/null | grep -c "limit_req zone=dsb_parse"     # 期望 2
nginx -T 2>/dev/null | grep -c "limit_req zone="              # 期望 9（含既有 7）
```


## 证据 5：应用层副作用排查 —— 零依赖

穷举 grep `workbench/serve_parser.py`（1477 行）全文件：

| 检查项 | 结果 |
|---|---|
| `request.url` / `request.url.scheme` | **无** |
| `request.base_url` | **无** |
| `request.client.host` | **无** |
| `url_for` | **无**（且无模板引擎，`index.html` 是 FileResponse 直出） |
| 生成绝对 URL（`http://` 拼接） | **无** |
| `RedirectResponse` / 30x | **无**（HTTPS 跳转全在 nginx 的 `HTTP_TO_HTTPS_START` 块） |
| 读过的 header（穷举 3 处） | `x-filename` / `x-requested-mpn` / `content-length` —— 与 IP、scheme 全无关 |
| 前端 URL 写法 | 三处全是相对路径（`/api/health`、`/api/parse`、`/api/page?...`） |

**结论：`proxy_headers=False` 在本项目是纯安全项，不是功能项，加它不会打破任何东西。**

## 证据 6：`proxy_headers=False` 代码段

```python
uvicorn.run(
    app,
    host=bind_host,
    port=bind_port,
    # 显式关闭代理头解析。
    # uvicorn 默认 proxy_headers=True、forwarded_allow_ips 回落到 "127.0.0.1"；
    # 而容器内看到的 nginx 来源是 docker 网桥网关（实测 172.23.0.1），
    # 不等于 127.0.0.1，所以现在"碰巧"没生效。
    # 但这是巧合不是设计——一旦有人设了 FORWARDED_ALLOW_IPS=*，
    # 客户端自带的 X-Forwarded-For 就会立刻变成可伪造的判据。
    proxy_headers=False,
)
```

配套 nginx 侧：`X-Forwarded-For $proxy_add_x_forwarded_for` → `$remote_addr`（追加改覆盖）。

## 证据 7：参数微调 —— 误伤量化 + 推荐中间值

15 连发实测（每发换伪造 IP）：

| 参数组 | rate | burst | 首个 429 | 持续速率 |
|---|---|---|---|---|
| A 当前线上 | `10r/m` | 2 | 第 4 次 | 10 次/分钟 |
| B 中间值偏低 | `2r/s` | 5 | 第 7 次 | 120 次/分钟 |
| C 中间值偏高 | `5r/s` | 10 | 第 13 次 | 300 次/分钟 |
| **D 推荐** | **`2r/s`** | **10** | **第 12 次** | **120 次/分钟** |

规律：瞬时容量 = `burst + 1`，首个 429 在第 `burst + 2` 次（rate 高时补桶会略微后移）。

**A 组的误伤是硬证据**（人手 2 秒间隔连点 3 次）：

```
第 1 次 -> 429
第 2 次 -> 429
第 3 次 -> 200
```

一个正常用户选错文件、重选再传，前两次就被 429。之前外网浏览器测试报的 `Failed to fetch`，根因就是这个。

**同时我收回上一版 `10r/s` 的草案**：瞬时 21 个、持续 600 次/分钟，对一个单次 13 秒、单文件 2.6MB 的重接口来说闸门形同虚设。Reviewer 暂缓的判断是对的。

**推荐 `2r/s + burst 10`**：瞬时 11 个（人手重试不误伤）、持续 120 次/分钟（脚本刷立刻撞墙）。

配套 `limit_conn 4` 不可省 —— `rate` 只管"每秒几个请求"，不管"同时在传几个 50MB"：
2r/s × 50MB = 100MB/s 入站，10 秒就是 1GB。`limit_conn` 把单 IP 在途请求钉死在 4 个。
（HTTP/2 下 nginx 1.19.7+ 按并发请求计数，多路复用绕不过去，本站 1.26.3 符合。）

---

## 取证过程的可复现性

脚本：`deploy/dsb/_ratelimit_evidence.sh`（幂等，跑完自动还原）
临时备份归档：服务器 `/root/dsb-ratelimit-bak/`（4 个文件）
还原后确认：`nginx -t` 通过，`error_log` 无 `warn`，`rate=10r/m`，`burst=2`，四站存活复验正常。

## 仍未做的事

- **限流配置尚未下发**（等 Reviewer 批准 `2r/s + burst 10` 还是 `5r/s + burst 10`）
- **`proxy_headers=False` 尚未改代码**（需重建镜像 + 重启容器，约 15 秒中断，建议单独窗口）
- `error_log` 级别是否定为 `warn`，等 Reviewer 一并决定
