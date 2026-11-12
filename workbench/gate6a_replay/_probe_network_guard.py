# -*- coding: utf-8 -*-
"""零网络调用取证：逐条测试各层拦截点。

每个向量都在**独立子进程**里跑，理由有二：
  1. audit hook 装上就无法卸载，同一进程里测不了「装闸 / 不装闸」两种情形；
  2. 一个向量被拦不影响后面的向量。

对照组（`--control`）刻意**不装闸**，用来回答「拦截到底是闸干的，
还是这台机器本来就断网」。两条结论缺一不可：
  - 对照组能通 → 网络是通的，拦截确实是闸生效；
  - 对照组也不通 → 只能说明环境本身离线，闸的有效性要靠 Agent 侧独立证据。

用法：
  python _probe_network_guard.py            # 跑全部向量，输出 Markdown 表
  python _probe_network_guard.py --json     # 输出 JSON（供 _make_env_evidence.py 消费）
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _no_llm_guard as guard  # noqa: E402

HOST = "api.openai.com"
IP = "1.1.1.1"

# (标识, 层, 说明, 代码)
VECTORS = [
    ("dns_getaddrinfo", "L2-DNS",
     "`socket.getaddrinfo` 解析 LLM 域名",
     "import socket; socket.getaddrinfo(%r, 443)" % HOST),
    ("dns_gethostbyname", "L2-DNS",
     "`socket.gethostbyname` 解析 LLM 域名",
     "import socket; socket.gethostbyname(%r)" % HOST),
    ("tcp_connect", "L3-TRANSPORT",
     "裸 socket 直连 1.1.1.1:443（绕过 DNS）",
     "import socket; s=socket.socket(); s.settimeout(3); s.connect((%r, 443))" % IP),
    ("tcp_create_connection", "L3-TRANSPORT",
     "`socket.create_connection` 直连",
     "import socket; socket.create_connection((%r, 443), timeout=3)" % IP),
    ("tcp_connect_ex", "L3-TRANSPORT",
     "`socket.connect_ex`（不抛异常的变体，看钩子是否同等对待）",
     "import socket; s=socket.socket(); s.settimeout(3); print('rc=', s.connect_ex((%r, 443)))" % IP),
    ("urllib_urlopen", "L4-PROTOCOL",
     "标准库 `urllib.request.urlopen`",
     "import urllib.request; urllib.request.urlopen('https://%s/v1/models', timeout=3)" % HOST),
    ("http_client", "L4-PROTOCOL",
     "底层 `http.client.HTTPSConnection`",
     "import http.client; c=http.client.HTTPSConnection(%r, timeout=3); c.request('GET','/')" % HOST),
    ("ftplib_connect", "L4-PROTOCOL",
     "`ftplib.FTP.connect`（非 HTTP 协议的旁路）",
     "import ftplib; ftplib.FTP().connect('ftp.example.com', 21, timeout=3)"),
    ("smtplib_connect", "L4-PROTOCOL",
     "`smtplib.SMTP.connect`（邮件旁路）",
     "import smtplib; smtplib.SMTP(timeout=3).connect('smtp.example.com', 25)"),
    ("requests_get", "L4-PROTOCOL",
     "第三方 `requests.get`",
     "import requests; requests.get('https://%s', timeout=3)" % HOST),
    ("httpx_get", "L4-PROTOCOL",
     "第三方 `httpx.get`",
     "import httpx; httpx.get('https://%s', timeout=3)" % HOST),
    ("subprocess_curl", "L5-PROCESS",
     "`subprocess.run(['curl', ...])` —— 子进程旁路",
     "import subprocess; subprocess.run(['curl','-sS','-m','3','https://example.com'], capture_output=True)"),
    ("os_system_curl", "L5-PROCESS",
     "`os.system('curl ...')` —— 另一条子进程旁路",
     "import os; os.system('curl -sS -m 3 https://example.com > /dev/null 2>&1')"),
    ("provider_import_openai", "L6-PROVIDER",
     "`import openai` —— 连 SDK 都不许进来",
     "import openai"),
    ("provider_import_anthropic", "L6-PROVIDER",
     "`import anthropic`",
     "import anthropic"),
    ("provider_custom_transport", "L6→L3",
     "模拟一个「自带传输层」的未知 SDK，最终落到 socket",
     "import socket; s=socket.socket(); s.settimeout(3); s.connect((%r, 443))" % IP),
]


def _run_child(code: str, with_guard: bool) -> dict:
    """在独立子进程里跑一段代码，返回是否被拦、拦在哪一层。"""
    prelude = ""
    if with_guard:
        prelude = (
            "import sys, json\n"
            "sys.path.insert(0, %r)\n"
            "import _no_llm_guard as g\n"
            "g.scrub_env()\n"
            "st = g.install()\n" % str(HERE)
        )
    src = prelude + (
        "import json as _j\n"
        "try:\n"
        "    " + code.replace("\n", "\n    ") + "\n"
        "    print(_j.dumps({'blocked': False, 'err': ''}))\n"
        "except BaseException as e:\n"
        "    m = str(e)\n"
        "    layer = ''\n"
        "    if '[L2-DNS]' in m: layer='L2-DNS'\n"
        "    elif '[L3-TRANSPORT]' in m: layer='L3-TRANSPORT'\n"
        "    elif '[L4-PROTOCOL]' in m: layer='L4-PROTOCOL'\n"
        "    elif '[L5-PROCESS]' in m: layer='L5-PROCESS'\n"
        "    elif 'LLM/网络硬禁用：禁止导入' in m: layer='L6-PROVIDER'\n"
        "    print(_j.dumps({'blocked': bool(layer), 'layer': layer,\n"
        "                    'err': type(e).__name__ + ': ' + m[:200]}))\n"
    )
    proc = subprocess.run([sys.executable, "-c", src], capture_output=True,
                          timeout=120)
    out = (proc.stdout or b"").decode("utf-8", "replace").strip().splitlines()
    for line in reversed(out):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except Exception:  # noqa: BLE001
                break
    return {"blocked": False, "layer": "",
            "err": "subprocess rc=%s %s" % (proc.returncode,
                                            (proc.stderr or b"").decode("utf-8", "replace")[-160:])}


def main() -> int:
    as_json = "--json" in sys.argv
    control = "--control" in sys.argv

    results = []
    for key, layer, desc, code in VECTORS:
        r = _run_child(code, with_guard=not control)
        results.append({"vector": key, "layer": layer, "desc": desc,
                        "blocked": r.get("blocked", False),
                        "blocked_at": r.get("layer", ""),
                        "error": r.get("err", "")})
        sys.stderr.write("%-30s %s %s\n" % (key, "BLOCKED " if r.get("blocked") else "passed? ",
                                            r.get("layer", "")))

    # 对照组：同一批向量不装闸，看环境本身能不能出网
    controls = []
    if not control:
        for key, layer, desc, code in VECTORS[:2] + VECTORS[5:6]:
            r = _run_child(code, with_guard=False)
            controls.append({"vector": key, "blocked": r.get("blocked", False),
                             "error": r.get("err", "")})

    if as_json:
        print(json.dumps({"results": results, "controls": controls},
                         ensure_ascii=False, indent=2))
        return 0

    print("| # | 向量 | 层 | 说明 | 结果 | 拦截层 |")
    print("| --- | --- | --- | --- | --- | --- |")
    for i, r in enumerate(results, 1):
        mark = "**已拦**" if r["blocked"] else "未拦"
        print("| %d | `%s` | %s | %s | %s | %s |"
              % (i, r["vector"], r["layer"], r["desc"], mark,
                 r["blocked_at"] or "—"))
    if controls:
        print()
        print("对照组（不装闸）：")
        for c in controls:
            print("- `%s` → %s" % (c["vector"],
                                   "能出网" if not c["blocked"] else "也不通：%s" % c["error"][:80]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
