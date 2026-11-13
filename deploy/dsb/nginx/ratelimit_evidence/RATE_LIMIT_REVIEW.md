# dsb.0668xgwl.com 网关限流审查报告

> 提交对象：Reviewer
> 服务器：`159.89.190.225`（DigitalOcean，Ubuntu，nginx/1.26.3，aaPanel 宝塔）
> 采集时间：2026-11-13 00:55–01:05 UTC
> 结论：**服务器没有套 Cloudflare，无任何 `real_ip` 指令，`$remote_addr` 就是 TCP 对端真实 IP，无法伪造。已实测验证。**

---

## 0. 一句话结论

| 项 | 现状 |
|---|---|
| 是否有现成 `limit_req_zone` 可供 dsb 复用 | **没有**。全局只有 `limit_conn_zone`，`limit_req_zone` 分散在各站点自己文件里 |
| `$remote_addr` 是否为真实客户端 IP | **是**。全 conf 树 0 条 `real_ip_header` / `set_real_ip_from` |
| 伪造 `X-Forwarded-For` 能否绕过限流 | **不能**。已实测：换 6 个伪造 XFF，第 4 个仍然 429 |
| 当前线上是否已有限流 | **有**，但过紧：`10r/m + burst 2`，连发 3 次即 429 |
| 本次需要改全局 `nginx.conf` 吗 | 需要 2 行（已有），见 §4 三选一 |

---

## 1. 配置原文 · harness.example.com.conf（62 行，历史参考）

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name harness.example.com;

    location ^~ /.well-known/acme-challenge/ {
        root /www/wwwroot/harness.example.com;
        try_files $uri =404;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name harness.example.com;

    ssl_certificate     /www/server/panel/vhost/cert/harness.example.com/fullchain.pem;
    ssl_certificate_key /www/server/panel/vhost/cert/harness.example.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;

    client_max_body_size 100m;

    access_log /www/wwwlogs/harness.example.com.log;
    error_log  /www/wwwlogs/harness.example.com.error.log;

    # 仅允许指定 IP 访问（新增 IP 追加一行 allow）
# [IP-WL-DISABLED 20261103]     allow 18.220.42.49;
# [IP-WL-DISABLED 20261103]     allow 13.192.162.69;
# [IP-WL-DISABLED 20261103]     allow 54.178.100.181;
# [IP-WL-DISABLED 20261103]     allow 2600:1f16:5b0:8300:a2f2:277d:b9fa:3fb9;
# [IP-WL-DISABLED 20261103]     allow 13.159.18.202;   # 2026-11-03 新增
# [IP-WL-DISABLED 20261103]     allow 13.230.119.224;   # 2026-11-03 出口漂移（代理节点，AWS 东京段）
# [IP-WL-DISABLED 20261103]     allow 57.180.42.240;   # 2026-11-03 实测直连出口
# [IP-WL-DISABLED 20261103]     allow 111.55.209.246;  # 2026-11-03 真实 ISP 出口（直连）
# [IP-WL-DISABLED 20261103]     deny  all;

    auth_basic "DeepSeek Harness";
    auth_basic_user_file /www/server/nginx/conf/dsh.htpasswd;

    location / {
        proxy_pass http://127.0.0.1:3082;
        proxy_http_version 1.1;
        proxy_set_header Host 127.0.0.1:3082;
        proxy_set_header Origin "";
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_buffering off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

**要点**：
- 全文件**没有任何 `limit_req`**。dsh 的防护靠 `auth_basic`（401），不靠限流。
- 白名单已全部注释并标记 `[IP-WL-DISABLED 20261103]`——dsh 同样取消了网关层白名单。
- `proxy_read_timeout 3600s` + `Upgrade`/`Connection "upgrade"`：WebSocket 长连接，**这个站点不能套用 dsb 的 30s 超时**。

---

## 2. 配置原文 · dsb.0668xgwl.com.conf（141 行）

```nginx
server
{
    listen 80;
    listen 443 ssl;
    listen 443 quic;
    http2 on;
    server_name dsb.0668xgwl.com;
    index index.php index.html index.htm default.php default.htm default.html;
    root /www/wwwroot/dsb.0668xgwl.com;
    #CERT-APPLY-CHECK--START
    # 用于SSL证书申请时的文件验证相关配置 -- 请勿删除
    include /www/server/panel/vhost/nginx/well-known/dsb.0668xgwl.com.conf;
    #CERT-APPLY-CHECK--END

    #SSL-START SSL相关配置，请勿删除或修改下一行带注释的404规则
    #error_page 404/404.html;
    #HTTP_TO_HTTPS_START
    set $isRedcert 1;
    if ($server_port != 443) {
        set $isRedcert 2;
    }
    if ( $uri ~ /\.well-known/ ) {
        set $isRedcert 1;
    }
    if ($isRedcert != 1) {
        rewrite ^(/.*)$ https://$host$1 permanent;
    }
    #HTTP_TO_HTTPS_END
    ssl_certificate    /www/server/panel/vhost/cert/dsb.0668xgwl.com/fullchain.pem;
    ssl_certificate_key    /www/server/panel/vhost/cert/dsb.0668xgwl.com/privkey.pem;
    ssl_protocols TLSv1.1 TLSv1.2 TLSv1.3;
    ssl_ciphers EECDH+CHACHA20:EECDH+CHACHA20-draft:EECDH+AES128:RSA+AES128:EECDH+AES256:RSA+AES256:EECDH+3DES:RSA+3DES:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_tickets on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    add_header Strict-Transport-Security "max-age=31536000";
    add_header Alt-Svc 'quic=":443"; h3=":443"; h3-29=":443"; h3-27=":443";h3-25=":443"; h3-T050=":443"; h3-Q050=":443";h3-Q049=":443";h3-Q048=":443"; h3-Q046=":443"; h3-Q043=":443"';
    error_page 497  https://$host$request_uri;

    #SSL-END

    #ERROR-PAGE-START  错误页配置，可以注释、删除或修改
    error_page 404 /404.html;
    #error_page 502 /502.html;
    #ERROR-PAGE-END

    #PHP-INFO-START  PHP引用配置，可以注释或修改
    include enable-php-00.conf;
    #PHP-INFO-END

    #REWRITE-START URL重写规则引用,修改后将导致面板设置的伪静态规则失效
    include /www/server/panel/vhost/rewrite/dsb.0668xgwl.com.conf;
    #REWRITE-END

    #禁止访问的文件或目录
    location ~ ^/(\.user.ini|\.htaccess|\.git|\.env|\.svn|\.project|LICENSE|README.md)
    {
        return 404;
    }

    #一键申请SSL证书验证目录相关设置
    location ~ \.well-known{
        allow all;
    }

    #禁止在证书验证目录放入敏感文件
    if ( $uri ~ "^/\.well-known/.*\.(php|jsp|py|js|css|lua|ts|go|zip|tar\.gz|rar|7z|sql|bak)$" ) {
        return 403;
    }

    location ~ .*\.(gif|jpg|jpeg|png|bmp|swf)$
    {
        expires      30d;
        error_log /dev/null;
        access_log /dev/null;
    }

    location ~ .*\.(js|css)?$
    {
        expires      12h;
        error_log /dev/null;
        access_log /dev/null;
    }
    access_log  /www/wwwlogs/dsb.0668xgwl.com.log;
    error_log  /www/wwwlogs/dsb.0668xgwl.com.error.log;

    # ===== Ds Bit 反代（PM 决策 2026-11-13：取消网关层 IP 白名单）=====
    # 安全边界全部压在应用层：ALLOW_PARSE=0 时 /api/parse 不读 body、不落盘、不起 worker。
    # 这里不加 allow/deny；只保留 limit_req，防止有人拿 FROZEN 端点刷请求。
    client_max_body_size 50m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection        "";
        proxy_read_timeout 30s;
    }

    location = /api/parse {
        limit_req zone=dsb_parse burst=2 nodelay;
        limit_req_status 429;
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection        "";
        proxy_read_timeout 200s;
        proxy_send_timeout 200s;
        proxy_buffering off;
    }

    location = /api/process {
        limit_req zone=dsb_parse burst=2 nodelay;
        limit_req_status 429;
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection        "";
        proxy_read_timeout 200s;
        proxy_send_timeout 200s;
        proxy_buffering off;
    }

    location = /api/health {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_read_timeout 10s;
    }

}
```

**注意**：第 1–87 行是宝塔面板生成的（`#SSL-START` / `#PHP-INFO-START` / `#REWRITE-START` 这些标记块），
**面板每次保存站点设置都会重写这一段**。第 88–139 行是我们手工追加的反代块，位于所有标记块之后，
宝塔重写时会保留（这一点在 2026-11-13 00:40 已被实测验证过一次）。

---

## 3. 全局审查结果

### 3.1 `nginx.conf` 里有没有现成 `limit_req_zone`？

**没有。** `/www/server/nginx/conf/nginx.conf` 全文只在第 63–64 行有两个 `limit_conn_zone`：

```nginx
limit_conn_zone $binary_remote_addr zone=perip:10m;
limit_conn_zone $server_name zone=perserver:10m;
```

`limit_req_zone` 全部散落在各站点自己的文件里：

| 文件 | 行 | 定义 | 速率 |
|---|---|---|---|
| `site-a.example.conf` | 33 | `zone=yx_perip` | 300r/m |
| `site-a.example.conf` | 34 | `zone=yx_rsc`（按 `$arg__rsc` 分桶） | 600r/m |
| `site-b.example.conf` | 23 | `zone=maison_perip` | 150r/m |
| `site-c.example.conf` | 17 | `zone=echo5_llm` | 1r/s |
| `dsb/dsb-limit-req.conf` | 5 | `zone=dsb_parse`（本次新增） | 10r/m |

**命名惯例**：`<站点前缀>_<用途>`。我们的 `dsb_parse` 与之一致，**不会撞名**。

### 3.2 关键发现：`vhost/nginx/*.conf` 是 **http 级** include

`nginx.conf` 第 112 行：

```nginx
include /www/server/panel/vhost/nginx/*.conf;
```

这是**非递归 glob，且位于 `http {}` 内**。所以：

- 放在 `vhost/nginx/` **根目录**的 `.conf` → 被当 **http 级**配置读入
- 放在 **子目录**（如 `vhost/nginx/dsb/`）→ **不会被 glob 命中**，必须显式 include

证据：`site-a.example.conf` 第 29–36 行在文件顶层（第一个 `server {` 在第 39 行之前）写了
`map`、`limit_req_zone`、`limit_req_status`、`limit_req_log_level`，这些都是 http 级指令，
正因为该文件被 http 级 include 才合法。**这是本服务器既有的、被 14 个站点验证过的做法。**

> ⚠️ **历史事故（必须写进规范）**：2026-11-13 00:14–00:18 UTC，我们曾把含 `deny all;` 的
> `dsb-allow-ips.conf` 放进 `vhost/nginx/` 根目录，`allow/deny` 是 http 级合法指令，
> 于是**全站 16 个站点对外全部 403**，持续约 4 分钟。
> 教训：**该目录根禁止放任何带访问控制语义的片段**。纯 `limit_req_zone` 定义无运行时副作用，可以放；
> 但为了不再踩坑，我们选择了子目录 + 显式 include（见 §4 方案 A）。

### 3.3 `limit_req_status` 已经是全局 429

`site-a.example.conf` 第 35–36 行（http 级）：

```nginx
limit_req_status 429;
limit_req_log_level warn;
```

也就是说**全服务器被限流时默认就返回 429，不是 503**。
dsb 的 location 里再写一次 `limit_req_status 429;` 是冗余但无害的防御（防止那个文件被人改掉）。

### 3.4 真实客户端 IP：确认无 `real_ip` 指令

```
grep -rniE "real_ip_header|set_real_ip_from|real_ip_recursive" \
     /www/server/nginx/conf/ /www/server/panel/vhost/nginx/
→ (无任何 real_ip 指令)
```

**结论**：nginx 的 `$remote_addr` 直接来自 TCP 三次对端地址，**没有任何一条路径能让客户端影响它**。
这与「服务器没套 Cloudflare、直接暴露 DO IP」的前提完全吻合，**不需要也绝不能配 `real_ip_header`**。

#### 实测证据：伪造 XFF 无法绕过限流

对 `https://dsb.0668xgwl.com/api/parse` 连发 6 次，每次换一个伪造的 `X-Forwarded-For` 和 `X-Real-IP`：

```
伪造 XFF=203.0.113.1 -> 200
伪造 XFF=203.0.113.2 -> 200
伪造 XFF=203.0.113.3 -> 200
伪造 XFF=203.0.113.4 -> 429      ← 第 4 个就被挡
伪造 XFF=203.0.113.5 -> 429
伪造 XFF=203.0.113.6 -> 429
```

如果限流桶是按 XFF 分桶的，换 IP 就应该每次都能过。**实测证明分桶键是 `$binary_remote_addr`，伪造头完全无效。**

---

## 4. `limit_req_zone` 放哪里：三个方案

> 先澄清一个前提：**宝塔（aaPanel）的 nginx 没有「全局扩展配置」这个 UI**（Apache 有，nginx 没有）。
> 在 nginx 上，这个诉求等价于「在 http 上下文 include 一次」，只有下面三条路。

### 方案 A（推荐，＝ 当前已上线状态）

`/www/server/panel/vhost/nginx/dsb/dsb-limit-req.conf` + `nginx.conf` 里加 2 行 include：

```nginx
# nginx.conf 第 109–110 行，位置必须在 include vhost glob（第 112 行）之前
# dsb.0668xgwl.com 的限流区（必须位于 http 直下、vhost include 之前）
include /www/server/panel/vhost/nginx/dsb/dsb-limit-req.conf;

include /www/server/panel/vhost/nginx/*.conf;
```

- ✅ 已在跑，`nginx -t` 通过
- ✅ dsb 的片段不落在共享 glob 目录（避开 §3.2 的事故现场）
- ⚠️ 动了 `nginx.conf` 2 行（纯增量，只定义一个 zone，不引用、不改变任何站点行为）
- 先例：该文件第 104–107 行的 `geo $yx_geo_country` 块也是别的项目为 http 级需求加的

### 方案 B（零 `nginx.conf` 改动）

把 `dsb-limit-req.conf` 直接放进 `/www/server/panel/vhost/nginx/` **根目录**，靠现有 glob 自动进 http 级，
然后删掉 `nginx.conf` 第 109–110 行。

- ✅ `nginx.conf` 回到原样
- ✅ 与 `site-a.example.conf` 的做法完全一致（该站就是这么定义 `yx_perip` 的）
- ⚠️ 宝塔「网站」列表可能多出一个没有 `server {}` 的条目（面板按文件名枚举站点）
- ⚠️ 就在事故目录根，后续任何人往里加 `allow/deny` 都会重演全站 403

### 方案 C（不推荐）

塞进 `/www/server/nginx/conf/proxy.conf`（`nginx.conf` 第 27 行 include）。
改的是宝塔自带文件，面板升级/修复会被覆盖，且所有站点共享这个文件，风险最高。

**建议**：维持方案 A。如果 Reviewer 坚持「`nginx.conf` 一行都不能动」，改走方案 B，我可以 5 分钟内切换并复验。

---

## 5. 限流草案（可直接贴，待批准后执行）

### 5.1 http 级：`/www/server/panel/vhost/nginx/dsb/dsb-limit-req.conf`

```nginx
# ============================================================
# dsb.0668xgwl.com 限流区定义（http 上下文）
# 被 nginx.conf 显式 include，位置在 include vhost glob 之前
#
# 分桶键用 $binary_remote_addr：
#   1. 服务器没套 CDN，$remote_addr 就是 TCP 对端真实 IP；
#   2. 全站无 real_ip_header，客户端无法影响它；
#   3. $binary_remote_addr 是 4 字节二进制，比字符串省内存。
# 已实测：伪造 X-Forwarded-For / X-Real-IP 无法换桶绕过。
# ============================================================

# 请求速率：10 次/秒/IP，突发 20
limit_req_zone $binary_remote_addr zone=dsb_parse:10m rate=10r/s;

# 并发连接：4 条/IP
# 为什么还要 conn：单 IP 10r/s × 50MB 上传 = 500MB/s 入站，
# 只限速率不限并发，带宽仍会被单 IP 打满。
limit_conn_zone $binary_remote_addr zone=dsb_conn:10m;
```

> `10m` 共享内存约可存 16 万个 IP 的桶状态，对本站点量级绰绰有余。
> 若日后要按站点区分，可另加 `limit_req_zone $server_name zone=dsb_srv:1m rate=100r/s;` 做二级兜底。

### 5.2 server 级：`dsb.0668xgwl.com.conf` 的 `/api/parse` 与 `/api/process`

替换现有的两个 location 块（第 104–132 行）：

```nginx
    # ---- 解析入口：严格限流 ----
    location = /api/parse {
        limit_req  zone=dsb_parse burst=20 nodelay;
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
        limit_req  zone=dsb_parse burst=20 nodelay;
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

### 5.3 参数取值理由

| 参数 | 取值 | 理由 |
|---|---|---|
| `rate` | `10r/s` | 人类手点上传，正常 ≤ 1r/s；10r/s 留 10 倍余量，脚本刷立刻撞墙 |
| `burst` | `20` | 覆盖「选错文件重试 + 前端自动重发」的短时连发；`nodelay` 让突发请求立即处理而非排队（排队会把超时转嫁给应用） |
| `limit_conn` | `4` | 4 × 50MB ≈ 200MB 在途，单 IP 吃不掉带宽；正常用户 1 条连接 |
| `limit_req_status` | `429` | 语义正确（Too Many Requests），且带 `Retry-After` 语义可让前端退避；默认 503 会被误判成服务故障 |
| `limit_conn_status` | `429` | 同上。nginx 1.26 支持 `limit_conn_status`（1.19+） |

**为什么从 `10r/m` 改成 `10r/s`**：当前线上 `10r/m + burst 2` 实测「连发第 4 次就 429」
（见 §3.4 实验 1）。这个值把正常用户的「重选文件再传一次」都挡了，
也让我们的自动化验收脚本 `Failed to fetch`——**过紧和过松一样是故障**。

### 5.4 影响面隔离（为什么不会影响另外 15 个站点）

| 隔离手段 | 说明 |
|---|---|
| zone 名带 `dsb_` 前缀 | `dsb_parse` / `dsb_conn`，与 `yx_*` / `maison_*` / `echo5_*` 无交集 |
| http 级只「定义」不「引用」 | zone 定义本身无任何运行时行为，只有 location 里 `limit_req zone=...` 才生效 |
| 只在 dsb 的 server 块里引用 | 其余 15 个站点的 server 块不含 `dsb_parse`，配置零变化 |
| `limit_req_status` 未做全局修改 | 该指令已是 http 级 429（既有配置），本次不改 |

**实测存活抽样**（改动前基线，2026-11-13 00:58 UTC）：

| Host | 状态码 | 说明 |
|---|---|---|
| dsb.0668xgwl.com | 200 | 本站 |
| harness.example.com | 401 | 它自己的 basic auth，正常 |
| site-d.example | 308 | 它自己的跳转规则，正常 |
| site-b.example | 200 | 正常 |
| site-c.example | 502 | **上游 13000 端口无监听**，2026-10-14 起就如此，与本次无关 |
| site-e.example | 502 | **上游 8300 容器未运行**，2026-11-12 起就如此，与本次无关 |

> 诚实标注：16 个站点里有 2 个是 502，但都是**上游服务没起**（`connect() failed (111: Connection refused)`），
> 与 nginx 配置无关，也不是本次改动造成的。开工前就是这个状态。

---

## 6. 应用层真实 IP 处理（FastAPI 侧）

### 6.1 现状核查

| 项 | 现状 |
|---|---|
| `serve_parser.py` 是否读客户端 IP | **完全不读**（全文件无 `client.host` / `X-Forwarded` / `X-Real-IP`） |
| uvicorn 版本 | 0.54.0 |
| `proxy_headers` 默认 | `True` |
| `forwarded_allow_ips` 默认 | `None` → 回落到 `127.0.0.1` |
| 容器内看到的 nginx 来源 IP | **`172.23.0.1`**（docker bridge 网关） |

**推论**：`172.23.0.1 ≠ 127.0.0.1`，所以 uvicorn **当前不会信任**任何 XFF，
`request.client.host` 恒为 `172.23.0.1`。**安全性上是过关的，但是「靠巧合过关」**——
一旦有人加了 `FORWARDED_ALLOW_IPS=*` 或把 `forwarded_allow_ips` 改成容器网段，防线立刻破。

### 6.2 加固建议（待批准，与限流一起上）

**nginx 侧**：把 `X-Forwarded-For $proxy_add_x_forwarded_for` 改成 `$remote_addr`。

`$proxy_add_x_forwarded_for` 的语义是「客户端传来的 XFF + 逗号 + $remote_addr」，**会保留伪造值**。
改成 `$remote_addr` 是**覆盖**，客户端传什么都会被丢弃。
（`proxy_set_header X-Real-IP $remote_addr` 本身就是覆盖语义，已经是安全的。）

**应用侧**：三行改动，显式关掉 uvicorn 的代理头解析。

```python
# serve_parser.py 末尾
uvicorn.run(
    app, host=bind_host, port=bind_port,
    proxy_headers=False,        # 不解析 X-Forwarded-For，杜绝伪造
)
```

**代码里要取真实 IP 时**（当前不需要，留作规范）：

```python
def client_ip(request: Request) -> str:
    """取真实客户端 IP。

    优先级：
    1. X-Real-IP —— nginx 用 $remote_addr 覆盖写入，客户端无法伪造；
    2. 回落到 request.client.host（TCP 对端）。

    绝不读 X-Forwarded-For：它是多值链，任何一段都可能被伪造，
    一旦用来做限流/鉴权判据就是漏洞。
    """
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")
```

> 顺带：`X-Forwarded-For` 仍然可以记进日志（用于看代理链路），
> 但**只作日志、不作判据**。

---

## 7. 安全红线（不变）

限流是**网关层的减噪**，不是安全边界。真正的闸门仍然是应用层：

```
ICEX_WORKBENCH_ALLOW_PARSE=0
  → /api/parse 第一行判断，命中即返回 FROZEN
  → 不读请求体、不落盘、不起 worker、parse_pdf_calls=0
```

已实测（2026-11-13 00:58 UTC）：

```
POST /api/parse  →  {"status":"FROZEN", "llm_called":false,
                     "database_written":false, "classifier_llm_calls":0}
```

限流再怎么配错，最坏结果是**可用性问题**（误伤正常用户）；
`ALLOW_PARSE=0` 一旦被改成 `1`，才是**安全问题**。
两者的变更权限必须分开。

---

## 8. 上线与回滚

### 上线步骤

```bash
# 1. 备份
cp /www/server/panel/vhost/nginx/dsb.0668xgwl.com.conf{,.bak-$(date +%Y%m%d-%H%M%S)}
cp /www/server/panel/vhost/nginx/dsb/dsb-limit-req.conf{,.bak-$(date +%Y%m%d-%H%M%S)}

# 2. 改两个文件（见 §5.1 / §5.2）

# 3. 语法检查（必须先过）
nginx -t

# 4. 生效
nginx -s reload

# 5. 复验
curl -s -o /dev/null -w "%{http_code}\n" -k -H "Host: dsb.0668xgwl.com" https://127.0.0.1/
curl -s -o /dev/null -w "%{http_code}\n" -k -H "Host: dsb.0668xgwl.com" https://127.0.0.1/api/health
```

### 回滚（两个层级）

```bash
# 软回滚：只放宽限流，不动配置结构
sed -i 's/rate=10r\/s/rate=10r\/m/' /www/server/panel/vhost/nginx/dsb/dsb-limit-req.conf
nginx -t && nginx -s reload

# 硬回滚：整个 server 块还原
cp /www/server/panel/vhost/nginx/dsb.0668xgwl.com.conf.bak-YYYYMMDD-HHMMSS \
   /www/server/panel/vhost/nginx/dsb.0668xgwl.com.conf
nginx -t && nginx -s reload
```

> 出事故时**第一动作不是回滚 nginx，是冻结应用**：
> `deploy/dsb/rollback.sh freeze`（改一个文件，下一个请求即生效，无需 reload）。
> 因为限流配错顶多是可用性问题，而解析跑起来才是真事故。

---

## 9. 待 Reviewer 决策的三个问题

1. **方案 A 还是 B？**（是否接受 `nginx.conf` 里那 2 行 include）
2. **`10r/s + burst 20 + conn 4` 是否合适？** 是否要对 `/api/page`（页面渲染，也是重接口）一并限流？
3. **应用层加固是否同批上？**（`proxy_headers=False` + XFF 改覆盖语义）需要重建镜像并重启容器，
   会导致约 15 秒不可用，建议与限流分开窗口执行。

---

*本报告全部数据来自 2026-11-13 00:55–01:05 UTC 对 159.89.190.225 的只读采集与实测，配置文本为 `cat -n` 原文。*

---

## 修订记录 · 2026-11-13 01:10 UTC（Reviewer 反馈后）

Reviewer 已认可**方案 A**与**XFF 覆盖策略**，并要求补齐 7 项落地证据。
证据包见 `deploy/dsb/evidence/ratelimit/`。本报告有 **3 处结论被实测修正**：

### 修正 1：`10r/s` 撤回，改推 `2r/s + burst 10`

§5.3 原写 `rate=10r/s + burst 20`。实测该值瞬时容量 21 个、持续 600 次/分钟，
对一个单次耗时 13 秒、单文件 2.6MB 的重接口**闸门形同虚设**。Reviewer 暂缓是对的。

四组参数 15 连发实测（每发换伪造 XFF，截断点均严格对应 burst）：

| 参数组 | rate | burst | 首个 429 | 持续速率 |
|---|---|---|---|---|
| A 当前线上 | `10r/m` | 2 | 第 4 次 | 10 次/分钟 |
| B | `2r/s` | 5 | 第 7 次 | 120 次/分钟 |
| C | `5r/s` | 10 | 第 13 次 | 300 次/分钟 |
| **D 推荐** | **`2r/s`** | **10** | **第 12 次** | **120 次/分钟** |

规律：**瞬时容量 = `burst + 1`，首个 429 在第 `burst + 2` 次**（rate 高时补桶会略微后移）。

### 修正 2：`10r/m` 的误伤已量化，不只是"偏紧"

§3.4 只说了"连发第 4 次就 429"。实测**人手 2 秒间隔连点 3 次**：

```
第 1 次 -> 429
第 2 次 -> 429
第 3 次 -> 200
```

正常用户选错文件、重选再传，前两次直接被 429。之前外网浏览器测试的
`Failed to fetch`，根因就是它。

### 修正 3（新发现）：`limiting requests` 日志平时看不见

dsb vhost 第 86 行 `error_log ...error.log;` **没写级别 = 默认 `error`**，
而 `limit_req_log_level` 在 http 级被设成 `warn`（`site-a.example.conf` 第 36 行）。
两者叠加的结果：**`limiting requests` 被过滤掉，生产上根本抓不到限流日志**。

本次取证临时改成 `warn` 才抓到（取证后已还原）。建议上线时一并定为 `warn`，
否则出问题无法复盘。

### 其他补充

- §5.2 的 `X-Forwarded-For $proxy_add_x_forwarded_for` 改为 `$remote_addr`（覆盖语义）
- §6.2 的 `proxy_headers=False` 已确认**零副作用**：`serve_parser.py` 对
  `request.url.scheme` / `request.client.host` / `url_for` 全无依赖（穷举 grep 见证据 5）
- `limit_conn` 在 HTTP/2 下按并发请求计数（nginx 1.19.7+），多路复用绕不过去，本站 1.26.3 符合
