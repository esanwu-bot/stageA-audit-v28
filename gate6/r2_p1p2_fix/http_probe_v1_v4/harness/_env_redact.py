"""环境变量脱敏（取证专用）。

事故背景
--------
首版 `_probe_v1_v4.py` 直接把 ``psutil.Process(pid).environ()`` 的**全部 229 个键**
写进 `env/process_env.json` 并提交。父进程是这个 IDE 本身，于是 IDE 的
`GEMINI_API_KEY`、`CODEBUDDY_GATEWAY_PASSWORD`、`WORKBUDDY_VLM_AUTH_TOKEN` 等
**与本次探针毫无关系**的凭据被一并抓到公开仓库。

设计教训：**取证采集必须白名单，不能黑名单**。
黑名单永远会漏（`GEMINI_API_KEY` 里虽有 KEY，但 `WORKBUDDY_VLM_AUTH_TOKEN`
含 AUTH 而非 KEY、`CODEBUDDY_GATEWAY_PASSWORD` 含 PASSWORD……名单只能事后补），
而白名单漏掉的后果只是「少一条证据」，黑名单漏掉的后果是「泄露一个凭据」。

本模块两道闸
------------
1. **白名单**（主闸）：只输出 ``DEFAULT_ALLOWLIST`` 里的键，或调用方显式传入的键。
   其余全部连键名都不出现，只计数为 ``omitted_count``。
2. **黑名单 + 熵检测**（兜底闸）：即使某个键在白名单里，只要它的名字命中
   ``SENSITIVE_NAME_PATTERN``，或值长得很像凭据（长随机串、已知前缀、
   私钥头），也一律打码。防止「有人把密钥塞进了 ICEX_ 前缀」。

白名单里的键，若值命中兜底闸，同样打码 —— 两道闸是 AND 关系，不是 OR。
"""

from __future__ import annotations

import math
import re
from typing import Iterable, Mapping

#: 唯一保留的变量族：本次探针自己的配置开关。
#: 新增变量必须显式加进来，不允许通配。
DEFAULT_ALLOWLIST: frozenset[str] = frozenset({
    "ICEX_WORKBENCH_ALLOW_PARSE",
    "ICEX_CLASSIFY_ONLY",
    "ICEX_WORKBENCH_PORT",
    "ICEX_WORKBENCH_DEPS",
    "ICEX_WORKBENCH_MAX_CONCURRENCY",
    "ICEX_PARSE_TIMEOUT",
    "ICEX_CLASSIFY_TIMEOUT",
    "ICEX_CLASSIFY_WORKERS",
    "ICEX_CLASSIFY_MAX_ROUNDS",
    "ICEX_OCR_ENABLED",
    "PYTHONUNBUFFERED",
    "PYTHONIOENCODING",
})

#: 名字命中即打码（兜底闸，不是唯一防线）
SENSITIVE_NAME_PATTERN = re.compile(
    r"(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH|PRIVATE|SESSION"
    r"|COOKIE|API|DSN|CONN|SALT|SIGNATURE|CERT)",
    re.I,
)

#: 值命中即打码（已知凭据前缀 / 私钥头 / 连接串）
SENSITIVE_VALUE_PATTERNS = [
    re.compile(r"^AIza[0-9A-Za-z_\-]{30,}$"),          # Google API key
    re.compile(r"^sk-[0-9A-Za-z_\-]{16,}$"),           # 常见 LLM key
    re.compile(r"^gh[pousr]_[0-9A-Za-z]{20,}$"),       # GitHub token
    re.compile(r"^github_pat_[0-9A-Za-z_]{20,}$"),
    re.compile(r"^xox[abposr]-[0-9A-Za-z\-]{10,}$"),   # Slack
    re.compile(r"^AKIA[0-9A-Z]{16}$"),                 # AWS access key id
    re.compile(r"^eyJ[0-9A-Za-z_\-]{10,}\.[0-9A-Za-z_\-]{10,}\."),  # JWT
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"^[a-z][a-z0-9+.\-]*://[^\s:@/]+:[^\s@/]+@", re.I),  # 带口令的连接串
]

#: 打码后写入的字面量。按工程规范统一为 ``***``：
#: 既让人一眼看出「此处被脱敏」，又不会因为长度泄漏原值规模。
MASK = "***"

#: 长度阈值：达到此长度且熵足够高，即视为疑似凭据
_ENTROPY_MIN_LEN = 24
_ENTROPY_MIN_BITS_PER_CHAR = 3.2


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts: dict[str, int] = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def looks_sensitive_value(value: str) -> str | None:
    """返回值若疑似凭据，给出原因字符串；否则 None。"""
    if not value:
        return None
    for pat in SENSITIVE_VALUE_PATTERNS:
        if pat.search(value):
            return "known_credential_pattern"
    # 高熵长串：只对「无空格、无路径分隔符」的值生效，
    # 避免把长路径 / 长命令行误判成凭据而丢证据。
    if (len(value) >= _ENTROPY_MIN_LEN
            and " " not in value
            and "\\" not in value
            and "/" not in value
            and _shannon_entropy(value) >= _ENTROPY_MIN_BITS_PER_CHAR):
        return "high_entropy"
    return None


def redact_env(
    env: Mapping[str, str],
    allowlist: Iterable[str] | None = None,
) -> dict:
    """把环境块转成可安全提交的结构。

    返回结构（不含任何未被允许的键名与值）::

        {
          "policy": {...},
          "vars": {<允许的键>: {"value": <值或 MASK>, "redacted": bool, "reason": str|null}},
          "omitted_count": <int>,          # 被白名单挡掉的键**数量**（不给键名）
          "omitted_name_prefixes": {...},  # 仅按前缀聚合计数，如 {"GEMINI_": 1}，本身不含密钥
        }
    """
    allow = frozenset(allowlist) if allowlist is not None else DEFAULT_ALLOWLIST
    out: dict[str, dict] = {}
    omitted = 0
    prefix_counts: dict[str, int] = {}

    for k, v in env.items():
        if k not in allow:
            omitted += 1
            # 只统计到第一个下划线之前的前缀族，用于向 Reviewer 说明「挡掉了哪些族」，
            # 前缀本身不含密钥值。
            fam = k.split("_", 1)[0] + "_"
            prefix_counts[fam] = prefix_counts.get(fam, 0) + 1
            continue

        sv = "" if v is None else str(v)
        reason = None
        if SENSITIVE_NAME_PATTERN.search(k):
            reason = "sensitive_name"
        else:
            reason = looks_sensitive_value(sv)

        if reason:
            out[k] = {"value": MASK, "redacted": True, "reason": reason}
        else:
            out[k] = {"value": sv, "redacted": False, "reason": None}

    return {
        "policy": {
            "mode": "allowlist_then_denylist",
            "allowlist": sorted(allow),
            "sensitive_name_pattern": SENSITIVE_NAME_PATTERN.pattern,
            "value_checks": [
                "known_credential_pattern", "high_entropy",
            ],
            "mask": MASK,
            "note": ("白名单为主闸：未列入 allowlist 的变量**连键名都不出现**，"
                     "只计数。allowlist 内的变量仍过敏感名/高熵兜底闸。"),
        },
        "vars": out,
        "omitted_count": omitted,
        "omitted_name_prefixes": dict(sorted(prefix_counts.items())),
    }


def flatten_for_report(redacted: Mapping[str, object]) -> dict[str, str | None]:
    """把 redact_env 的结果摊平成 {键: 值}，供 probe_record.json 的
    ``process_env_subset`` 使用（保持与旧字段兼容，但值已脱敏）。"""
    vars_ = redacted.get("vars") or {}
    return {k: (v.get("value") if isinstance(v, dict) else v) for k, v in vars_.items()}


if __name__ == "__main__":  # 自检：确认关键凭据形状一定被打码
    # 【注意】这里刻意用运行期拼接构造伪造样例，**源码里不出现任何可被正则匹配的字面量**。
    # 若写成 "AIza" + "x"*35 的完整字面量，提交后会被 GitHub Secret Scanning
    # 当作真实 Google Key 再报一次误告警（SEC-INCIDENT-01 的教训之一）。
    fake_google = "AI" + "za" + ("x" * 35)
    fake_tok = "Z" * 43
    fake_sk = "sk" + "-" + ("a" * 40)

    sample = {
        "ICEX_WORKBENCH_ALLOW_PARSE": "1",
        "ICEX_CLASSIFY_ONLY": "1",
        "ICEX_WORKBENCH_PORT": "8765",
        "FAKE_PROVIDER_KEY": fake_google,       # 走「已知凭据形状」闸
        "FAKE_SERVICE_TOKEN": fake_tok,         # 走「敏感名」闸
        "PATH": r"C:\Windows\system32",         # 非白名单，应被整体挡掉
        "PYTHONUNBUFFERED": "1",
        "ICEX_LEAKY": fake_sk,                  # 白名单内但值是凭据 → 兜底闸打码
    }
    r = redact_env(sample, allowlist=set(DEFAULT_ALLOWLIST) | {"ICEX_LEAKY"})
    for k, v in r["vars"].items():
        print("%-32s %-26s %s" % (k, v["reason"] or "-", v["value"][:24]))
    print("omitted_count =", r["omitted_count"])
    print("prefixes =", r["omitted_name_prefixes"])
    # 非白名单键必须连键名都不出现（主闸生效）
    assert "FAKE_PROVIDER_KEY" not in r["vars"]
    assert "FAKE_SERVICE_TOKEN" not in r["vars"]
    assert "PATH" not in r["vars"]
    # 白名单内但值是凭据 → 兜底闸必须打码
    assert r["vars"]["ICEX_LEAKY"]["redacted"] is True
    assert r["vars"]["ICEX_LEAKY"]["value"] == "***"
    # 正常配置项不得被误伤
    assert r["vars"]["ICEX_WORKBENCH_PORT"]["value"] == "8765"
    print("自检通过：非白名单键整体挡掉；白名单内的凭据值被打码；正常配置未误伤")
