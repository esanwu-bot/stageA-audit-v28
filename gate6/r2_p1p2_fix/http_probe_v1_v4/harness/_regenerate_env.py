"""把已捕获的 process_env.json 就地重写为脱敏版。

为什么从旧文件重算而不是重新采集
--------------------------------
旧文件里的 229 个键就是**承载探针那个进程（PID 63240）**当时的环境块，
它与探针证据同源。从中重算脱敏版，可以保证：
* 证据指向的仍是同一个进程实例，不是事后另起一个进程冒名顶替；
* 不需要重新启动服务、不需要重发任何 HTTP 请求。

代价：旧文件里已含有敏感值，重写后立即覆写磁盘，随后再做全历史清理。

安全约束
--------
* 全程不向 stdout 打印任何取值，只打印键名与长度；
* 写完立即回读校验：确认新的 process_env.json 中不含任何「旧文件里的高敏值」。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _env_redact import MASK, redact_env  # noqa: E402

ENV_JSON = HERE.parent / "env" / "process_env.json"

old = json.loads(ENV_JSON.read_text(encoding="utf-8"))
if not isinstance(old, dict) or "vars" in old:
    raise SystemExit("预期旧文件是扁平的 {键: 值}，实际结构不符，停止以免误覆盖")

# 先把「疑似敏感」的旧值收集起来（只在内存里，不打印），用于写后校验
sensitive_values = []
for k, v in old.items():
    s = "" if v is None else str(v)
    if len(s) >= 16:
        sensitive_values.append((k, s))

redacted = redact_env(old)
ENV_JSON.write_text(
    json.dumps(redacted, ensure_ascii=False, indent=1, sort_keys=True),
    encoding="utf-8",
)

# ---- 写后校验：新文件里不得出现任何一个旧高敏值的字面量
new_text = ENV_JSON.read_text(encoding="utf-8")
leaks = []
for k, s in sensitive_values:
    # 只报键名，不报值；命中即视为失败
    if s and s in new_text:
        leaks.append(k)

print("旧键数            :", len(old))
print("保留键数          :", len(redacted["vars"]))
print("被白名单挡掉的键数:", redacted["omitted_count"])
print("挡掉的键族(仅前缀计数):", redacted["omitted_name_prefixes"])
print("保留的键名        :", sorted(redacted["vars"]))
print("其中被兜底闸打码  :", [k for k, v in redacted["vars"].items() if v["redacted"]] or "无")
print("打码字面量        :", MASK)
print()
if leaks:
    print("!! 校验失败：新文件中仍出现旧敏感值，涉及键：", leaks)
    raise SystemExit(1)
print("校验通过：新文件中不含任何旧高敏值字面量")
print("新文件字节数      :", ENV_JSON.stat().st_size)
