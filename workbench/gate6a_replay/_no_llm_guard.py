# -*- coding: utf-8 -*-
"""LLM 硬禁用闸（Reviewer 边界 3）。

六层拦截，缺一层就可能被绕：

  L1 凭据层  清掉所有模型服务的 key / model / base_url 环境变量，
             让「万一有代码想调」也拿不到凭据。
  L2 DNS 层  socket.getaddrinfo / gethostbyname / gethostbyaddr / sethostname。
             域名解析是任何出站请求的第一步，掐这里等于掐住所有域名的入口。
  L3 传输层  socket.connect / socket.create_connection。
             audit 事件由 CPython 解释器发出，与用了哪个 HTTP 库无关。
  L4 协议层  urllib.Request / http.client.connect / ftplib.connect / smtplib.connect。
  L5 进程层  subprocess.Popen / os.system / os.exec* / os.posix_spawn / os.fork。
             子进程是审计钩子的天然盲区——它能绕开本进程的一切 monkeypatch，
             所以必须单独封。
  L6 Provider 入口层
             对已安装的 LLM SDK 做入口级封堵（见 PROVIDER_MODULES），
             并配合 L2/L3：即使 SDK 换了自定义传输，最终仍要落到 socket。

audit hook 一旦装上无法卸载，进程内任何模块都绕不过去；
审计事件是解释器层发出的，不是「禁止某个库」——哪怕后来加了个没见过的 SDK，
只要它最终走 socket 或被 subprocess 拉起，就会被拦。
"""
from __future__ import annotations

import os
import sys

# 这些变量一旦存在，说明环境里有调用模型服务的凭据
LLM_ENV_VARS = (
    "DASHSCOPE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
    "DEEPSEEK_API_KEY", "MOONSHOT_API_KEY", "ZHIPU_API_KEY",
    "ARK_API_KEY", "QWEN_API_KEY", "GEMINI_API_KEY", "MISTRAL_API_KEY",
    "ICPDF_LLM_MODEL", "ICPDF_LLM_TIMEOUT", "ICPDF_LLM_BASE_URL",
    "OPENAI_BASE_URL", "DASHSCOPE_BASE_URL", "ANTHROPIC_BASE_URL",
    "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY",
)

# L2/L3/L4：出站与解析类审计事件
NETWORK_EVENTS = (
    # L2 DNS
    "socket.getaddrinfo",
    "socket.gethostbyname",
    "socket.gethostbyaddr",
    "socket.sethostname",
    # L3 传输
    "socket.connect",
    "socket.create_connection",
    # L4 协议库
    "urllib.Request",
    "http.client.connect",
    "ftplib.connect",
    "smtplib.connect",
    "poplib.connect",
    "imaplib.open",
    "nntplib.connect",
    "telnetlib.Telnet.open",
)

# L5：子进程 / 进程派生。子进程能绕开本进程的一切内存级封堵，必须单独封。
PROCESS_EVENTS = (
    "subprocess.Popen",
    "os.system",
    "os.exec",
    "os.posix_spawn",
    "os.spawn",
    "os.fork",
    "os.forkpty",
    "pty.spawn",
)

# L6：已安装的 LLM SDK。导入即拦，连 client 都构造不出来。
PROVIDER_MODULES = (
    "openai", "anthropic", "dashscope", "zhipuai", "google.generativeai",
    "cohere", "mistralai", "groq", "together", "ollama", "litellm",
)

BLOCKED_EVENTS = NETWORK_EVENTS + PROCESS_EVENTS

STATS = {"blocked": 0, "events": [], "env_scrubbed": [], "layer": {}}


def scrub_env() -> list[str]:
    """删掉模型服务相关环境变量，返回实际删掉的变量名。"""
    removed = []
    for name in LLM_ENV_VARS:
        if name in os.environ:
            removed.append("%s=%s" % (name, "***" if "KEY" in name
                                      else os.environ[name]))
            del os.environ[name]
    STATS["env_scrubbed"] = removed
    return removed


def _layer_of(event: str) -> str:
    if event in ("socket.getaddrinfo", "socket.gethostbyname",
                 "socket.gethostbyaddr", "socket.sethostname"):
        return "L2-DNS"
    if event in ("socket.connect", "socket.create_connection"):
        return "L3-TRANSPORT"
    if event in NETWORK_EVENTS:
        return "L4-PROTOCOL"
    return "L5-PROCESS"


def _install_provider_guard() -> list[str]:
    """L6：把 LLM SDK 的导入直接判死，返回受保护的模块名。"""
    class _Blocked:
        def __init__(self, name):
            self._name = name

        def find_spec(self, fullname, path=None, target=None):
            root = fullname.split(".")[0]
            if root in PROVIDER_MODULES:
                raise ImportError(
                    "LLM/网络硬禁用：禁止导入模型 SDK `%s`（命中 %s）。"
                    "本次回测不允许任何外部服务调用。" % (fullname, self._name))
            return None

    sys.meta_path.insert(0, _Blocked("L6-provider"))
    return list(PROVIDER_MODULES)


def install(block_process: bool = True) -> dict:
    """装上审计钩子 + Provider 导入闸；返回可变统计字典（进程内累计）。"""
    blocked = NETWORK_EVENTS + (PROCESS_EVENTS if block_process else ())
    protected = _install_provider_guard()
    STATS["provider_modules_blocked"] = protected
    STATS["block_process"] = block_process

    def _hook(event, args):
        if event in blocked:
            STATS["blocked"] += 1
            layer = _layer_of(event)
            STATS["layer"][layer] = STATS["layer"].get(layer, 0) + 1
            detail = "%s %r" % (event, args)
            STATS["events"].append(detail)
            raise RuntimeError(
                "LLM/网络硬禁用：拦截出站事件 [%s] %s。"
                "本次回测不允许任何外部请求。" % (layer, detail))

    sys.addaudithook(_hook)
    return STATS


def observe() -> dict:
    """只观察不拦截：记录所有网络/子进程类审计事件，用于「零调用」取证。

    与 install() 互斥使用。装上后跑一次解析，事件计数为 0 即证明
    整个解析过程中一次网络尝试都没有——不是「被拦住了」，而是「根本没发生」。
    """
    watched = NETWORK_EVENTS + PROCESS_EVENTS + (
        "socket.__new__", "socket.bind", "socket.getsockname",
        "socket.gethostname", "socket.socketpair",
    )
    seen = {"count": 0, "events": []}

    def _hook(event, args):
        if event in watched:
            seen["count"] += 1
            if len(seen["events"]) < 50:
                seen["events"].append("%s" % event)

    sys.addaudithook(_hook)
    return seen


def self_test() -> dict:
    """确认闸真的关死了：装闸后尝试一次 DNS 解析，必须被拦。"""
    install()
    result = {"blocked_ok": False, "error": ""}
    try:
        import socket
        socket.getaddrinfo("example.com", 443)
    except RuntimeError as exc:
        result["blocked_ok"] = True
        result["error"] = str(exc)[:160]
    except Exception as exc:                      # noqa: BLE001
        result["error"] = "%s: %s" % (type(exc).__name__, exc)
    return result


if __name__ == "__main__":
    removed = scrub_env()
    st = self_test()
    print("环境变量清理：%d 个 %s" % (len(removed), removed))
    print("出站拦截自测：%s" % ("PASS" if st["blocked_ok"] else "FAIL"))
    if st["error"]:
        print("  %s" % st["error"])
    print("累计拦截：%d 次 %s" % (STATS["blocked"], STATS["layer"]))
    raise SystemExit(0 if st["blocked_ok"] else 1)
