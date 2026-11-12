# 零网络调用证据（六层拦截）

本文件回答一个问题：**这次回测有没有偷偷联网 / 偷偷调大模型。**

结论先说：**没有。** 下面用静态、运行时、对抗三段证据分别支撑，
每一段都可以用仓库里的脚本重跑复现。

## 一、六层拦截点（不是只有 socket）

实现见 `workbench/gate6a_replay/_no_llm_guard.py`，`install()` 一次装齐。

| 层 | 拦截对象 | 具体审计事件 / 机制 | 为什么必须有这一层 |
| --- | --- | --- | --- |
| **L1 凭据** | 模型服务凭据 | 删除 18 个环境变量（API key / base_url / model） | 没有凭据，即使代码想调也调不成 |
| **L2 DNS** | 域名解析 | `socket.getaddrinfo` / `gethostbyname` / `gethostbyaddr` / `sethostname` | 任何按域名出站的请求第一步都是解析，掐这里等于掐住所有域名入口 |
| **L3 传输** | TCP 直连 | `socket.connect` / `socket.create_connection` | 绕过 DNS 直连 IP 的路径 |
| **L4 协议库** | 标准库与三方 HTTP | `urllib.Request` / `http.client.connect` / `ftplib.connect` / `smtplib.connect` / `poplib` / `imaplib` / `telnetlib` | 非 HTTP 协议（FTP/SMTP）是常被忽略的旁路 |
| **L5 子进程** | 进程派生 | `subprocess.Popen` / `os.system` / `os.exec` / `os.posix_spawn` / `os.fork` | **子进程是审计钩子的天然盲区**——它能绕开本进程的一切内存级封堵，所以必须单独封 |
| **L6 Provider 入口** | LLM SDK | `sys.meta_path` 前置钩子，11 个 SDK 模块导入即抛 `ImportError` | 连 client 都构造不出来，不用等它去发请求 |

## 二、对抗测试：16 个向量逐条真发起

每个向量在**独立子进程**里跑（audit hook 装上就无法卸载，同进程测不了多情形）。

| # | 向量 | 设计层 | 说明 | 结果 | 实际拦截层 |
| --- | --- | --- | --- | --- | --- |
| 1 | `dns_getaddrinfo` | L2-DNS | `socket.getaddrinfo` 解析 LLM 域名 | **已拦** | L2-DNS |
| 2 | `dns_gethostbyname` | L2-DNS | `socket.gethostbyname` 解析 LLM 域名 | **已拦** | L2-DNS |
| 3 | `tcp_connect` | L3-TRANSPORT | 裸 socket 直连 1.1.1.1:443（绕过 DNS） | **已拦** | L3-TRANSPORT |
| 4 | `tcp_create_connection` | L3-TRANSPORT | `socket.create_connection` 直连 | **已拦** | L2-DNS |
| 5 | `tcp_connect_ex` | L3-TRANSPORT | `socket.connect_ex`（不抛异常的变体，看钩子是否同等对待） | **已拦** | L3-TRANSPORT |
| 6 | `urllib_urlopen` | L4-PROTOCOL | 标准库 `urllib.request.urlopen` | **已拦** | L4-PROTOCOL |
| 7 | `http_client` | L4-PROTOCOL | 底层 `http.client.HTTPSConnection` | **已拦** | L4-PROTOCOL |
| 8 | `ftplib_connect` | L4-PROTOCOL | `ftplib.FTP.connect`（非 HTTP 协议的旁路） | **已拦** | L4-PROTOCOL |
| 9 | `smtplib_connect` | L4-PROTOCOL | `smtplib.SMTP.connect`（邮件旁路） | **已拦** | L2-DNS |
| 10 | `requests_get` | L4-PROTOCOL | 第三方 `requests.get` | **已拦** | L2-DNS |
| 11 | `httpx_get` | L4-PROTOCOL | 第三方 `httpx.get` | **已拦** | L2-DNS |
| 12 | `subprocess_curl` | L5-PROCESS | `subprocess.run(['curl', ...])` —— 子进程旁路 | **已拦** | L5-PROCESS |
| 13 | `os_system_curl` | L5-PROCESS | `os.system('curl ...')` —— 另一条子进程旁路 | **已拦** | L5-PROCESS |
| 14 | `provider_import_openai` | L6-PROVIDER | `import openai` —— 连 SDK 都不许进来 | **已拦** | L6-PROVIDER |
| 15 | `provider_import_anthropic` | L6-PROVIDER | `import anthropic` | **已拦** | L6-PROVIDER |
| 16 | `provider_custom_transport` | L6→L3 | 模拟一个「自带传输层」的未知 SDK，最终落到 socket | **已拦** | L3-TRANSPORT |

**16 / 16 全部被拦。**

### 2.1 对照组：证明拦截是闸干的，不是机器断网

同一批向量**不装闸**再跑一遍。如果对照组也不通，那只能说明环境离线，
拦截报告就没有说服力——所以这一步不能省。

| 向量 | 不装闸时的结果 |
| --- | --- |
| `dns_getaddrinfo` | **能出网** |
| `dns_gethostbyname` | **能出网** |
| `urllib_urlopen` | **能出网** |

结论：对照组能出网 → 机器是联网的，§二 的拦截确实来自审计钩子，而不是「本来就没网」。

## 三、运行时观测：解析过程中到底有没有发起过请求

用**只观察不拦截**的钩子跑一件真实样本（`V256`，216 页），
记录全部 socket / 子进程事件。

| 项 | 结果 |
| --- | --- |
| 真正出网事件（DNS / connect / urlopen / 子进程） | **0 次**  |
| 本地 socket 调用（`gethostname` 等，不产生网络 I/O） | 1 次 ['socket.gethostname'] |
| `urllib` 子模块 | `urllib`, `urllib.parse` |
| 解析期间新加载的网络类模块 | `urllib` |
| 凭据清理 | 1 个 |

这一点很重要：**出网事件计数为 0，说明是「根本没发生」，而不是「发生了但被拦住」。**

唯一的 `socket.gethostname` 是本地主机名查询，不产生任何网络 I/O；
`urllib` 被加载是上游库的 `urllib.parse` 字符串工具所致，`urllib.Request` 事件一次都没出现，说明从未发起请求。

## 四、回测期间逐件的出网计数

每个 worker 在装闸后自行统计 `blocked_events` 并写进 `_worker_record.json`。

| 批次 | 样本数 | `blocked_events` 取值集合 | 合计 |
| --- | --- | --- | --- |
| 首次回测 v1 | 24 | [0] | 0 |
| 修复后复跑 v2 | 24 | [0] | 0 |

两批共 48 件样本，`blocked_events` 全部为 0，说明生产链路上连一次「尝试出网被拦」都没有——不是被拦住 0 次，是一次都没试。

## 五、环境层的第二道锁

worker 启动即 `scrub_env()`，把凭据类环境变量从进程环境中删除。本次运行命中 **0** 个（见 `env_snapshot.json` 的 `llm.env_vars_present`）。

## 六、一句话总结

| 问题 | 答案 | 证据 |
| --- | --- | --- |
| 有没有偷偷联网 | 没有，运行时出网事件 0 次 | §三 |
| 就算想连能不能连上 | 不能，16 个向量全被拦（含子进程与 SDK 入口） | §二 |
| 拦截是不是「本来就没网」 | 不是，对照组能出网 | §2.1 |
| 有没有偷偷调大模型 | 没有，凭据被清 + SDK 导入即拦 + `llm_blocked` 全 0 | §一 §四 |

