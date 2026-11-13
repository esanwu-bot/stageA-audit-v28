# 证据 2：准备上线的两段配置（完整原文）

> 状态：**尚未下发**，等 Reviewer 批准后执行。
> 参数取 `2r/s + burst 10 + limit_conn 4`（理由见 `04_param_matrix.txt`）。

---

## 第一段：http 级（限流区定义）

### 1.1 新建文件 `/www/server/panel/vhost/nginx/dsb/dsb-limit-req.conf`

```nginx
# ============================================================
# dsb.0668xgwl.com 限流区定义（http 上下文）
# 被 nginx.conf 显式 include，位置在 include vhost glob 之前
#
# 分桶键用 $binary_remote_addr：
#   1. 服务器没套 CDN，$remote_addr 就是 TCP 对端真实 IP；
#   2. 全站无 real_ip_header，客户端无法影响它（已实测，见 01 号证据）；
#   3. $binary_remote_addr 是 4 字节二进制，比字符串省内存。
# ============================================================

# 请求速率：2 次/秒/IP，突发 10（瞬时容量 = burst + 1 = 11 个）
limit_req_zone $binary_remote_addr zone=dsb_parse:10m rate=2r/s;

# 并发连接：4 条/IP
# 为什么还要 conn：rate 只管"每秒几个请求"，不管"同时在传几个 50MB"。
# 即使 2r/s，2 × 50MB = 100MB/s 入站，持续 10 秒就是 1GB。
# 注：HTTP/2 下 nginx 按并发请求计数（1.19.7+），多路复用绕不过去。
limit_conn_zone $binary_remote_addr zone=dsb_conn:10m;
```

### 1.2 在 `/www/server/nginx/conf/nginx.conf` 第 109–110 行加 include

**位置必须在 `include .../vhost/nginx/*.conf;` 之前**，否则报
`zero size shared memory zone "dsb_parse"`。

```nginx
# dsb.0668xgwl.com 的限流区（必须位于 http 直下、vhost include 之前）
include /www/server/panel/vhost/nginx/dsb/dsb-limit-req.conf;

include /www/server/panel/vhost/nginx/*.conf;
```

> 这 2 行是**本次唯一触碰 `nginx.conf` 的地方**，纯增量：
> 只定义一个 zone，不引用、不改变任何站点行为。
> 若不接受改 `nginx.conf`，走方案 B：把 zone 文件移到
> `vhost/nginx/` 根目录，靠现有 glob 自动进 http 级，然后删掉这 2 行
> （与 `site-a.example.conf` 定义 `yx_perip` 的做法一致）。

---

## 第二段：server 级（`/www/server/panel/vhost/nginx/dsb.0668xgwl.com.conf`）

替换现有第 104–132 行的两个 location 块：

```nginx
    # ---- 解析入口：严格限流 ----
    location = /api/parse {
        limit_req  zone=dsb_parse burst=10 nodelay;
        limit_req_status 429;
        limit_conn dsb_conn 4;
        limit_conn_status 429;

        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        # ↓ 覆盖而非追加：不让客户端自带的 XFF 传进应用层
        proxy_set_header X-Forwarded-For   $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection        "";
        proxy_read_timeout 200s;
        proxy_send_timeout 200s;
        proxy_buffering off;
    }

    location = /api/process {
        limit_req  zone=dsb_parse burst=10 nodelay;
        limit_req_status 429;
        limit_conn dsb_conn 4;
        limit_conn_status 429;

        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection        "";
        proxy_read_timeout 200s;
        proxy_send_timeout 200s;
        proxy_buffering off;
    }
```

### 顺带建议：把 `location /` 里的 XFF 也改成覆盖

现有第 98 行：

```nginx
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
```

建议改为：

```nginx
        proxy_set_header X-Forwarded-For   $remote_addr;
```

理由：`$proxy_add_x_forwarded_for` 会把客户端传来的 XFF 原样拼在前面带进上游，
`$remote_addr` 是覆盖语义。虽然应用层现在完全不读 XFF，但**不留伪造入口**比
"依赖下游不读"更可靠。

---

## 备选参数（若 Reviewer 认为 120 次/分钟偏紧）

只改 `dsb-limit-req.conf` 一行 + 两个 location 的 burst：

```nginx
limit_req_zone $binary_remote_addr zone=dsb_parse:10m rate=5r/s;
```
```nginx
        limit_req  zone=dsb_parse burst=10 nodelay;
```

效果：瞬时 11 个、持续 300 次/分钟、15 连发第 13 次被挡（实测 C 组）。

---

## 为什么不是 10r/s

上一版草案写的是 `10r/s + burst 20`，Reviewer 暂缓是对的，**我收回这个值**：

| | 瞬时容量 | 持续速率 | 判断 |
|---|---|---|---|
| `10r/s + burst 20` | 21 个 | 600 次/分钟 | 闸门形同虚设 |
| `2r/s + burst 10` | 11 个 | 120 次/分钟 | 推荐 |
| `10r/m + burst 2` | 3 个 | 10 次/分钟 | 实测误伤正常用户 |

一个单次耗时 13 秒、单文件 2.6MB 的重接口，600 次/分钟的上限没有防护意义。

---

## 上线步骤

```bash
# 1. 备份（两个文件都要）
TS=$(date +%Y%m%d-%H%M%S)
cp /www/server/panel/vhost/nginx/dsb.0668xgwl.com.conf{,.bak-$TS}
cp /www/server/panel/vhost/nginx/dsb/dsb-limit-req.conf{,.bak-$TS}
cp /www/server/nginx/conf/nginx.conf{,.bak-$TS}

# 2. 写文件（见上两段）

# 3. 语法检查 —— 必须先过再 reload
nginx -t

# 4. 生效（reload 不中断连接）
nginx -s reload

# 5. 复验
curl -s -o /dev/null -w "%{http_code}\n" -k -H "Host: dsb.0668xgwl.com" https://127.0.0.1/
curl -s -o /dev/null -w "%{http_code}\n" -k -H "Host: dsb.0668xgwl.com" https://127.0.0.1/api/health
```

## 回滚

```bash
# 只放宽速率，不动结构
sed -i 's#rate=2r/s#rate=5r/s#' /www/server/panel/vhost/nginx/dsb/dsb-limit-req.conf
nginx -t && nginx -s reload

# 整体还原
cp /www/server/panel/vhost/nginx/dsb.0668xgwl.com.conf.bak-$TS \
   /www/server/panel/vhost/nginx/dsb.0668xgwl.com.conf
nginx -t && nginx -s reload
```

> 出事故第一动作不是回滚 nginx，是 `deploy/dsb/rollback.sh freeze`
> （改一个文件，下一个请求即生效，无需 reload）。
> 限流配错顶多是可用性问题，解析跑起来才是真事故。

---

## 关于 error_log 级别的建议（新增）

dsb vhost 第 86 行现在是：

```nginx
    error_log  /www/wwwlogs/dsb.0668xgwl.com.error.log;
```

没写级别 = 默认 `error`。而 `limit_req_log_level` 在 http 级被设成了 `warn`
（`site-a.example.conf` 第 36 行），所以 **`limiting requests` 日志被过滤掉，看不见**。

本次取证时临时改成 `warn` 才抓到日志，取证后已还原。

建议正式上线时一并改成：

```nginx
    error_log  /www/wwwlogs/dsb.0668xgwl.com.error.log warn;
```

代价：多记 warn 级日志。收益：被限流的请求有据可查，出问题能复盘。
