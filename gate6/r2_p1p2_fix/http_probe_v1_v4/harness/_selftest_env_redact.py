"""脱敏过滤器自检：证明「注入敏感环境变量后，输出 JSON 中确实是 ***」。

这不是「跑一下没报错」式的自检，而是产出**可复核的证据文件**：
`env/redaction_selftest.json` 逐条记录「注入了什么名字的变量 / 期望是什么 /
实际输出是什么 / 是否通过」，以及最关键的一条——
**把整份输出 JSON 序列化后，逐个搜索注入的原始凭据字面量，必须全部搜不到。**

设计约束
--------
1. 敏感样例值**运行期拼接**生成，源码里不出现可被 GitHub Secret Scanning
   匹配的字面量（否则会像 SEC-INCIDENT-01 那样触发误报告警）。
2. 证据文件里**只写变量名与打码后的值**，绝不写原始凭据值。
3. 覆盖指令点名的五个关键词族：`KEY` / `TOKEN` / `SECRET` / `PASS` / `AUTH`，
   外加「白名单键但值是凭据」这条最容易漏的路径。
4. 全部用例断言失败即 `exit 1`，便于 CI 拦截。

用法：py -3.13 _selftest_env_redact.py [--out path]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _env_redact import DEFAULT_ALLOWLIST, MASK, redact_env  # noqa: E402

CST = timezone(timedelta(hours=8))

# ---- 运行期拼接伪造凭据（源码中不出现可匹配的字面量）---------------------
FAKE_GOOGLE = "AI" + "za" + ("Q" * 35)          # 命中已知凭据形状
FAKE_SK = "sk" + "-" + ("b" * 40)               # 命中已知凭据形状
FAKE_JWT = "ey" + "J" + ("c" * 30) + "." + ("d" * 30) + "." + ("e" * 20)
FAKE_PRIVKEY = "-----BEGIN " + "RSA PRIVATE KEY-----"
FAKE_OPAQUE = "Zq7" + "9fK2mXp4Lr8Tn6Wv1Yb3Hc5Jd0"   # 高熵、无明显前缀

#: 注入的敏感变量：键名 + 值 + 期望结果
#: expect == "***" 表示必须被打码；expect == "OMITTED" 表示连键名都不应出现
INJECTED = [
    # --- 指令点名的五个关键词族，且都放进白名单，强制走「值/名兜底闸」 ---
    ("ICEX_INJECT_FAKE_API_KEY",       FAKE_GOOGLE,  "***"),
    ("ICEX_INJECT_FAKE_TOKEN",         "tok" + ("A" * 40), "***"),
    ("ICEX_INJECT_FAKE_SECRET",        "s3cr3t" + ("B" * 30), "***"),
    ("ICEX_INJECT_FAKE_PASSWORD",      "pa55" + ("C" * 30), "***"),
    ("ICEX_INJECT_FAKE_AUTH",          "auth" + ("D" * 30), "***"),
    # --- 名字人畜无害，但值是凭据形状：只能靠「值」这道闸拦住 ---
    ("ICEX_INJECT_BENIGN_NAME",        FAKE_GOOGLE,  "***"),
    ("ICEX_INJECT_BENIGN_SK",          FAKE_SK,      "***"),
    ("ICEX_INJECT_BENIGN_JWT",         FAKE_JWT,     "***"),
    ("ICEX_INJECT_BENIGN_PRIVKEY",     FAKE_PRIVKEY, "***"),
    ("ICEX_INJECT_BENIGN_OPAQUE",      FAKE_OPAQUE,  "***"),
    # --- 不在白名单：必须整体消失（连键名都不出现）---
    ("GEMINI_API_KEY",                 FAKE_GOOGLE,  "OMITTED"),
    ("WORKBUDDY_VLM_AUTH_TOKEN",       "vlm" + ("E" * 40), "OMITTED"),
    ("CODEBUDDY_GATEWAY_PASSWORD",     "gw" + ("F" * 40), "OMITTED"),
    # --- 正常配置：必须原样保留，不能被误伤 ---
    ("ICEX_WORKBENCH_ALLOW_PARSE",     "1",           "1"),
    ("ICEX_CLASSIFY_ONLY",             "1",           "1"),
    ("ICEX_WORKBENCH_PORT",            "8765",        "8765"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE.parent / "env" / "redaction_selftest.json"))
    args = ap.parse_args()

    # 只把 ICEX_INJECT_* 放进白名单，让它们走「白名单内的兜底闸」这条路径；
    # GEMINI_API_KEY 等三个真实感名字**故意不放白名单**，用来验证主闸把它们整体挡掉。
    allow = set(DEFAULT_ALLOWLIST) | {
        n for n, _, _ in INJECTED if n.startswith("ICEX_INJECT_")
    }
    env = {n: v for n, v, _ in INJECTED}
    # 再塞一个不在白名单的系统变量，验证「连键名都不出现」
    env["PATH"] = r"C:\Windows\system32"

    result = redact_env(env, allowlist=allow)
    serialized = json.dumps(result, ensure_ascii=False)

    cases = []
    all_ok = True
    for name, value, expect in INJECTED:
        got = result["vars"].get(name, {}).get("value", "OMITTED")
        if expect == "OMITTED":
            ok = name not in result["vars"]
            note = "键名未出现在输出中" if ok else "键名泄漏"
            leaked = False
        else:
            ok = got == expect
            note = "符合预期"
            leaked = False
            # 仅对「应被打码」的凭据值做字面量搜索：
            # 对 "1" / "8765" 这类正常配置值做子串搜索必然误命中（它们会作为
            # JSON 数字/长度/键名片段出现），不能作为泄漏判据。
            if expect == MASK and value:
                leaked = value in serialized
                if leaked:
                    ok = False
                    note = "原始值出现在输出 JSON 中"
        all_ok = all_ok and ok
        cases.append({
            "variable": name,
            "expected": expect,
            "actual": got,
            "original_value_leaked": leaked,
            "pass": ok,
            "note": note,
        })

    # 白名单外的系统变量
    path_present = "PATH" in result["vars"]
    all_ok = all_ok and (not path_present)
    cases.append({
        "variable": "PATH",
        "expected": "OMITTED",
        "actual": "OMITTED" if not path_present else "PRESENT",
        "original_value_leaked": result["vars"].get("PATH", {}).get("value", "") in serialized
        if path_present else False,
        "pass": not path_present,
        "note": "非白名单键整体挡掉",
    })

    # 全局兜底：所有「应被打码」的注入值逐个再扫一次序列化文本
    leaked_anywhere = sorted(
        n for n, v, exp in INJECTED if exp == MASK and v and v in serialized
    )

    report = {
        "test": "env_redact_selftest",
        "generated_at": datetime.now(CST).isoformat(timespec="seconds"),
        "policy_mode": result["policy"]["mode"],
        "mask_literal": MASK,
        "theme": "证明敏感环境变量注入后，输出 JSON 中的值确实是 ***",
        "injected_count": len(INJECTED),
        "omitted_count": result["omitted_count"],
        "cases": cases,
        "secrets_leaked_in_output": leaked_anywhere,
        "all_pass": bool(all_ok and not leaked_anywhere),
        "assertions": [
            "白名单内、键名命中 KEY/TOKEN/SECRET/PASS/AUTH 的变量，值必须为 ***",
            "白名单内、键名无害但值是凭据形状的变量，值必须为 ***",
            "非白名单变量不得出现在输出中（连键名都不出现）",
            "正常配置项不得被误伤",
            "任何原始凭据值不得出现在输出 JSON 的任何位置",
        ],
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("注入变量数: %d" % len(INJECTED))
    print("%-34s %-10s %-10s %s" % ("变量", "期望", "实际", "结果"))
    for c in cases:
        print("%-34s %-10s %-10s %s" % (
            c["variable"], c["expected"], str(c["actual"])[:10],
            "PASS" if c["pass"] else "FAIL  " + c["note"]))
    print()
    print("输出 JSON 中泄漏的原始凭据:", leaked_anywhere or "无")
    print("总体结果:", "全部通过" if report["all_pass"] else "存在失败")
    print("证据文件:", out)
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
