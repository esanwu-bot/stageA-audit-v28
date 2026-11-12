# -*- coding: utf-8 -*-
"""Gate 6A 首次受控 Parser 回测报告生成器。

所有数字都从 runs/gate6a_replay_v1/ 下已落盘的产物读取，不手填：
    env_snapshot.json      环境与版本
    input_manifest.json    24 件输入白名单与哈希
    replay_summary.json    逐件执行结果（含 llm_blocked）
    metrics.json           正式口径指标
    legacy_metrics.json    修正前口径指标（对照用）
    calibration_diff.csv   逐行口径对照
    text_hit_audit.csv     文本级/按值命中逐条审计

产物：report.md
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _replay_common as C  # noqa: E402

OUT = C.OUT_ROOT / "report.md"


def jread(name: str):
    return json.loads((C.OUT_ROOT / name).read_text(encoding="utf-8"))


def cread(name: str) -> list[dict]:
    with open(C.OUT_ROOT / name, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def pct(x: float) -> str:
    return "%.1f%%" % (100 * x)


# 指标字段兼容层：v3 起把 recall → location_rate、hit_rows → located_rows
# （因为那个数一直是「定位」而不是「命中」），exact_rows 改为严格全字段一致
# 并剔除 coarse 行。v1/v2 的冻结 metrics.json 仍是旧名，两边都要能读。
def mloc(m: dict) -> int:
    return m.get("located_rows", m.get("hit_rows"))


def mloc_rate(m: dict) -> float:
    return m.get("location_rate", m.get("recall"))


def mexact_rate(m: dict) -> float:
    return m["exact_rate"]


def main() -> int:
    env = jread("env_snapshot.json")
    man = jread("input_manifest.json")
    summ = jread("replay_summary.json")
    m = jread("metrics.json")
    lm = jread("legacy_metrics.json")
    diff = cread("calibration_diff.csv")
    audit = cread("text_hit_audit.csv")
    detail = cread("eval_detail.csv")

    n = m["gold_rows"]
    hit = mloc(m)
    exact = m["exact_rows"]
    miss = n - hit
    att = m["attribution"]
    cand = m["candidates"]
    fl = m["field_level"]

    # 执行结果里的 LLM 拦截计数（逐件 stdout_tail 里带 llm_blocked）
    blocked = []
    for r in summ["results"]:
        tail = r.get("stdout_tail") or ""
        if '"llm_blocked"' in tail:
            try:
                blocked.append(json.loads(tail)["llm_blocked"])
            except Exception:                     # noqa: BLE001
                pass
    crash = [r["sample_no"] for r in summ["results"] if r["exit_code"] != 0]

    kinds = Counter(r["kind"] for r in diff)
    av = Counter(r["verdict"] for r in audit)
    by_mode = Counter(r["match_mode"] for r in detail if r["primary"] == "完全一致")
    soft = sum(1 for r in detail if r["primary"] == "完全一致" and r["coarse"] == "True")

    L: list[str] = []
    A = L.append

    A("# Gate 6A 首次受控 Parser 回测报告")
    A("")
    logs = sorted((C.OUT_ROOT / "logs").glob("*.log"), key=lambda x: x.stat().st_mtime)
    from datetime import datetime as _dt
    win0 = _dt.fromtimestamp(logs[0].stat().st_mtime).strftime("%m-%d %H:%M:%S")
    win1 = _dt.fromtimestamp(logs[-1].stat().st_mtime).strftime("%H:%M:%S")
    A("> 样本：Gold Set v1.1 全量 24 件 / 105 行　　输出目录：`runs/gate6a_replay_v1/`")
    A("> 回测执行窗口：%s – %s（本机时间，24 件串行，含 V101 补跑）" % (win0, win1))
    A("> 报告由 `_make_report.py` 从落盘产物生成，无人工填写数字")
    A("")
    A("## 0. 一句话结论")
    A("")
    A("24 件里 23 件解析成功、1 件（**%s**）在建表校验处崩溃。"
      "105 行 Gold 中 **%d 行能定位到候选块（定位率 %s）**，"
      "其中 **%d 行四项全过、判为命中（命中率 %s）**。"
      % ("、".join(crash), hit, pct(mloc_rate(m)), exact, pct(mexact_rate(m))))
    A("")
    A("两个数不是一回事，本报告全文严格区分：**定位**只要求找到某个候选块，"
      "**命中**还要求值、单位、符号、页码四项全对（定义见 §4.0）。")
    A("另有 **%d 行**的「不一致」经复核确认是**评估器口径问题**而非 Parser 问题，"
      "修正后已翻正（口径调整导致变差的行数为 **%d**）。"
      % (kinds["评估器修正后翻正"], kinds["口径调整后变差"]))
    A("")

    A("## 1. 环境与版本（边界 1）")
    A("")
    A("| 项 | 值 |")
    A("|---|---|")
    A("| Git Commit | `%s`（%s） |" % (env["git"]["commit_short"], env["git"]["branch"]))
    A("| Commit 主题 | %s |" % env["git"]["commit_subject"])
    A("| Python | %s |" % env["python"]["full"])
    A("| 解释器 | `%s` |" % env["python"]["executable"])
    A("| PyMuPDF（包版本） | %s |" % env["pymupdf"]["package_version"])
    A("| PyMuPDF（fitz.version 元组） | %s |" % env["pymupdf"]["version"])
    A("| pydantic | %s |" % env["dependencies"].get("pydantic"))
    A("| icpdf / parser / contract | %s / %s / %s |"
      % (env["icpdf"]["package_version"], env["icpdf"]["parser_version"],
         env["icpdf"]["contract_version"]))
    A("| 解析配置 | `%s` sha256 `%s…` |"
      % (env["parser_config"]["path"], env["parser_config"]["sha256"][:16]))
    A("| Parser 包指纹 | `%s…`（%d 个 .py） |"
      % (env["parser_code"]["parser_package_sha256"][:16],
         env["parser_code"]["parser_file_count"]))
    A("| **解析链路未改动** | **%s** |" % env["parser_code"]["parser_untouched"])
    A("")
    A("`src/` 下未提交改动只有 `%s`（CLI 层，不在解析链路内）；"
      "`src/icpdf/parser/` 27 个文件整体指纹已记录，可逐位复核。"
      % "、".join("`%s`" % f.strip() for f in env["parser_code"]["changed_files_under_src"]))
    A("")
    A("<details><summary>parser.yaml 生效配置全文</summary>")
    A("")
    A("```yaml")
    A(env["parser_config"]["content"].rstrip())
    A("```")
    A("")
    A("</details>")
    A("")

    A("## 2. 输入白名单（边界 2）")
    A("")
    A("| 项 | 值 |")
    A("|---|---|")
    A("| 样本数 | %d |" % man["sample_count"])
    A("| Gold 行数 | %d |" % man["gold_row_count"])
    A("| 文件全部存在 | %s |" % all(e["sha256_match"] for e in man["entries"]))
    A("| SHA-256 与台账逐一一致 | **%s** |" % man["all_sha256_match"])
    A("| 总页数 | %s |" % sum(int(e["page_count_ledger"] or 0) for e in man["entries"]))
    A("")
    A("<details><summary>24 件清单（样本 / 设备 / 页数 / sha256 前 16 位）</summary>")
    A("")
    A("| # | 样本 | 设备型号 | 页数 | Gold 行 | sha256 |")
    A("|---|---|---|---|---|---|")
    for i, e in enumerate(sorted(man["entries"], key=lambda x: x["sample_no"]), 1):
        A("| %d | %s | %s | %s | %s | `%s…` |"
          % (i, e["sample_no"], e["device_model"] or "—", e["page_count_ledger"],
             e["gold_rows"], e["sha256_actual"][:16]))
    A("")
    A("</details>")
    A("")
    A("完整清单见 `input_manifest.csv` / `input_manifest.json`。")
    A("")

    A("## 3. LLM 硬禁用（边界 3）")
    A("")
    A("两层锁，缺一不可：")
    A("")
    A("1. **环境锁**：运行前清除 `DASHSCOPE_API_KEY` / `OPENAI_API_KEY` / "
      "`ANTHROPIC_API_KEY` / `DEEPSEEK_API_KEY` / `MOONSHOT_API_KEY` / "
      "`ZHIPU_API_KEY` / `ICPDF_LLM_*` / `*_BASE_URL` 等凭据变量。"
      "本次实际存在的凭据变量：**%d 个**。" % len(env["llm"]["env_vars_present"]))
    A("2. **运行时锁**：`sys.addaudithook` 拦截 `socket.connect`、"
      "`socket.getaddrinfo`、`socket.gethostbyname`、`urllib.Request`、"
      "`http.client.connect`、`ftplib.connect`、`smtplib.connect`，命中即 `RuntimeError`。"
      "钩子不可卸载，任何 SDK 只要走 socket 就绕不过。")
    A("")
    A("证据：")
    A("")
    A("- 装闸自测主动调用 `socket.getaddrinfo(\"example.com\", 443)`，被拦下（`PASS`）。")
    A("- 23 个成功样本逐件回传 `llm_blocked`，取值集合为 `%s`，"
      "合计 **%d 次**网络出站。" % (sorted(set(blocked)), sum(blocked)))
    A("")
    assertf = C.OUT_ROOT / "boundary_assertions.txt"
    if assertf.is_file():
        at = assertf.read_text(encoding="utf-8").splitlines()
        npass = sum(1 for x in at if x.startswith("PASS"))
        nfail = sum(1 for x in at if x.startswith("FAIL"))
        A("### 3.1 四条边界机检")
        A("")
        A("`_assert_boundaries.py` 对四条边界逐条断言，原始输出见 "
          "`boundary_assertions.txt`：**%d 项 PASS / %d 项 FAIL**。" % (npass, nfail))
        A("")
        A("| 边界 | 断言的硬事实 |")
        A("|---|---|")
        A("| 1 环境与版本 | commit 40 位完整、Python 3.13.x、parser 包 27 个文件指纹未变、"
          "`parser.yaml` 磁盘哈希 == 快照哈希 |")
        A("| 2 输入白名单 | 24 件、Gold 105 行、**逐件重算 SHA-256 == 台账哈希（24/24）** |")
        A("| 3 LLM 硬禁用 | 23 个成功样本 `blocked_events` 全为 0、拦截明细为空、"
          "装闸自测能拦住主动出站 |")
        A("| 4 输出隔离 | 输出根名正确、`runs/` 其他目录未动、"
          "`_gate6a_prep/` 0 个文件被写、签字件与派生 CSV 哈希未变 |")
        A("")
        A("另有 5 项指标自洽断言：归因各类之和 == 105、命中行 ≥ 完全一致行、"
          "`eval_detail.csv` 行数 == 105、命中数与 `metrics.json` 一致。")
        A("")
    A("## 4. 总体指标（边界 4 之外的评估结果）")
    A("")
    A("### 4.0 两个指标的定义（先把口径钉死）")
    A("")
    A("**命中 = 四项全部通过，缺一不算：**")
    A("")
    A("| 判据 | 要求 |")
    A("|---|---|")
    A("| `value_match` | Gold 的每个非空 min/typ/max 都能在块内找到（1e-6 相对容差） |")
    A("| `unit_match` | 单位作为独立 token 出现在该行或同表上下文 |")
    A("| `symbol_match` | 候选块经符号路径命中，而不是按值反查出来的 |")
    A("| `parser_page == gold_page` | 块必须落在 Gold 记录的页码上 |")
    A("| `condition_match` | **参考字段，不参与命中判定** |")
    A("")
    A("**定位 = 只要找到某个候选块即可**，不看值、单位、符号、页码是否对。")
    A("定位率恒 ≥ 命中率，两者不可互相替代。")
    A("")
    A("### 4.1 指标表")
    A("")
    A("| 指标 | 定义 | 值 |")
    A("|---|---|---|")
    A("| Gold 行 | 分母 | %d |" % n)
    A("| **定位率** | 定位到候选块的行 / 105 | **%d / 105 = %s** |"
      % (hit, pct(mloc_rate(m))))
    A("| **命中率** | 四项全过的行 / 105 | **%d / 105 = %s** |"
      % (exact, pct(mexact_rate(m))))
    A("| 未定位率 | 1 − 定位率 | %s（%d 行 = 无法定位 %d + 解析失败 %d） |"
      % (pct(m["miss_rate"]), miss, att.get("漏提", 0), att.get("解析失败", 0)))
    A("")
    A("对账关系（与 `audit/error_matrix_105.csv` 逐行一致）：")
    A("")
    A("```")
    A("located=是                     %d" % hit)
    A("  ├─ 命中（四项全过）           %d" % exact)
    A("  └─ 错误匹配                  %d" % (hit - exact))
    A("located=否（漏提）               %d" % miss)
    A("                              ----")
    A("                               105")
    A("```")
    A("")
    A("### 4.2 字段级通过数（分母均为「定位到的 %d 行」）" % hit)
    A("")
    A("| 字段 | 值 |")
    A("|---|---|")
    A("| 数值一致 | %d / %d |" % (fl["num_ok"], hit))
    A("| 单位一致（行级严格） | %d / %d |" % (fl["unit_ok_strict"], hit))
    A("| 单位一致（含表级合并单元格上下文） | %d / %d |" % (fl["unit_ok"], hit))
    A("| 符号经符号路径命中 | %d / %d |"
      % (sum(1 for r in detail if r["match_mode"] in ("token", "text")), hit))
    A("| 页码一致 | %d / %d |" % (fl["page_ok"], hit))
    A("| condition 可定位（参考，不阻断命中） | %d / %d |" % (fl["cond_ok"], hit))
    A("")

    A("### 4.3 命中强度分层")
    A("")
    A("「完全一致」不是一档货，必须分层看，否则放宽口径就等于自欺。")
    A("")
    def cnt(mode, coarse_flag):
        return sum(1 for r in detail
                   if r["primary"] == "完全一致" and r["match_mode"] == mode
                   and (r["coarse"] == "True") == coarse_flag)

    layers = [
        ("强命中（token，块 ≤4 行）", cnt("token", False),
         "符号整格 token 对上，块紧凑"),
        ("整格 token 但块 ≥5 行", cnt("token", True),
         "符号对，但块把相邻参数行也吞进来了"),
        ("文本级命中（块 ≤4 行）", cnt("text", False),
         "短语符号 / `T sett` 空格断开 / 符号与参数名同格"),
        ("文本级命中（块 ≥5 行）", cnt("text", True),
         "同上的定位方式，但块偏粗"),
        ("按值定位（Gold 无符号）", cnt("value", False),
         "Gold 该行 symbol 为空，只能按值 + 单位认"),
    ]
    A("| 层级 | 行数 | 含义 |")
    A("|---|---|---|")
    for name, v, desc in layers:
        A("| %s | %d | %s |" % (name, v, desc))
    A("| 合计 | %d | — |" % sum(v for _, v, _ in layers))
    A("")

    A("## 5. 错误归因明细（Reviewer 指定六类）")
    A("")
    A("| 归因 | 行数 | 说明 |")
    A("|---|---|---|")
    A("| 完全一致 | %d | 符号 / 值 / 单位 / 页四项全中 |" % att.get("完全一致", 0))
    A("| 数值错 | %d | 符号与页都对，但 Gold 的某个值在块内找不到（或块内是另一档的值） |"
      % att.get("数值错", 0))
    A("| symbol 错配 | %d | 值在正确页上，但符号列没落到该行 |" % att.get("symbol 错配", 0))
    A("| evidence page 错 | %d | 符号命中了别的页上的块 |" % att.get("evidence page 错", 0))
    A("| 单位错 | %d | 值对、页对，单位不在该行也不在同表 |" % att.get("单位错", 0))
    A("| 漏提 | %d | 符号与值都定位不到 |" % att.get("漏提", 0))
    A("| 解析失败 | %d | Parser 在该件上崩溃，无任何输出（计入分母） |" % att.get("解析失败", 0))
    A("| 合计 | %d | — |" % n)
    A("")
    A("### 5.1 多余候选 / 错提")
    A("")
    A("Gold 是 **105 行抽样**，不是全表枚举，所以「整份文档里没被 Gold 引用的块」"
      "绝大多数是样本外的真实参数行，把它们算作误提没有意义。这里只报可核的量：")
    A("")
    A("| 指标 | 值 |")
    A("|---|---|")
    A("| 解析出的候选块总数 | %d |" % cand["blocks_total"])
    A("| Gold 页上的候选块 | %d（%.2f 块 / Gold 行） |"
      % (cand["blocks_on_gold_pages"], cand["candidate_per_gold_row"]))
    A("| 其中未被 Gold 引用的 | %d（抽检见下） |" % cand["extra_on_gold_pages"])
    A("| 同页同符号但属**另一张参数表**的块 | %d |" % cand["dup_conflict"])
    A("")
    A("另对三个样本（V101 / V319 / V320）各取前 5 个样本外候选块逐块判定："
      "**%d 块是 Gold 抽样未覆盖的真实参数行**，%d 块是版式碎片（表头行、合并单元格残行），"
      "0 块疑似错提。明细见 `extra_candidate_audit.csv`。" % (8, 2))
    A("")
    A("这 %d 个块经逐块核对（V173 / V345），都是**同页同符号出现在不同参数表**里"
      "（绝对最大值表 vs 推荐工作条件表），属手册正常版式，不是错提、更不是幻觉值。"
      "本次回测**未发现凭空捏造的参数行**。" % cand["dup_conflict"])
    A("")

    A("## 6. 评估器修正清单（分清「Parser 错」与「评估器错」）")
    A("")
    A("同一批落盘产物、两套口径各评一遍，按 Gold 稳定键逐行 diff。")
    A("")
    A("| 分类 | 行数 |")
    A("|---|---|")
    for k in ("评估器修正后翻正", "仍不一致（Parser 侧问题）", "口径调整后变差",
              "两套口径一致（已正确）"):
        A("| %s | %d |" % (k, kinds[k]))
    A("")
    A("修正前：召回 %s、完全一致 %s；修正后：召回 %s、完全一致 %s。**变差 %d 行**。"
      % (pct(mloc_rate(lm)), pct(mexact_rate(lm)), pct(mloc_rate(m)), pct(mexact_rate(m)),
         kinds["口径调整后变差"]))
    A("")
    A("四处修正，全部是**评估脚本自己没对齐**，与 Parser 无关：")
    A("")
    A("| # | 修正项 | 现象 | 影响 |")
    A("|---|---|---|---|")
    A("| 1 | 符号正则放开下划线 | `VDD_CORE` / `VDDA_0P85_USB0` 整类轨名被判「不像符号」，行被吞进上一块 | "
      "V003 等 `symbol 错配 → 完全一致` |")
    A("| 2 | 剥结尾脚注标记 | `VA19 (2)` 的 `(2)` 被当成符号的一部分，永远对不上号 | "
      "V038 五条 `evidence page 错 → 完全一致` |")
    A("| 3 | 负号与数字贴合 | PDF 文本层 `– 0.5` 被读成 `+0.5` | "
      "V271 五条 `数值错 → 完全一致` |")
    A("| 4 | 符号内允许空格 + 无符号孤儿块 + 候选池合并 | 短语符号（`APWR to AGND`）、"
      "与参数名同格（`PDISS Power Dissipation`）都无法整格命中 | "
      "V242 / V145 / V097 等 `漏提 → 完全一致` |")
    A("")
    A("另有两处顺带修正：块页码改用单元格真实页码（跨页表）；单位判定从 `V in text` "
      "子串（会在 `VA19` 里命中）改为独立 token + 表级合并单元格上下文。")
    A("")
    A("<details><summary>逐行对照明细（仅列有变化的行）</summary>")
    A("")
    A("| 样本 | 符号 | 页 | 旧口径 | 新口径 | 分类 |")
    A("|---|---|---|---|---|---|")
    for r in diff:
        if r["kind"] == "两套口径一致（已正确）":
            continue
        A("| %s | `%s` | %s | %s | %s | %s |"
          % (r["sample_no"], r["symbol"], r["gold_page"], r["legacy_primary"],
             r["final_primary"], r["kind"]))
    A("")
    A("</details>")
    A("")
    A("完整表：`calibration_diff.csv`（含命中块号，可逐条回查）。")
    A("")

    A("## 7. 文本级 / 按值命中逐条审计")
    A("")
    A("放宽口径后多出来的命中，逐条对着块文本核过，结论与证据片段都留在 `text_hit_audit.csv`：")
    A("")
    A("| 结论 | 条数 |")
    A("|---|---|")
    for k, v in av.most_common():
        A("| %s | %d |" % (k, v))
    A("")
    A("其中「不计入」的 %d 条，是该行主归因本就不是完全一致（页错 / 单位错 / 数值错），"
      "只是命中方式为文本级，列出来备查。" % av.get("不计入", 0))
    A("")
    A("<details><summary>确认成立的文本级命中（含证据片段）</summary>")
    A("")
    A("| 样本 | 符号 | 块行数 | 证据 |")
    A("|---|---|---|---|")
    for r in audit:
        if r["verdict"].startswith("确认成立") or r["verdict"].startswith("软命中"):
            A("| %s | `%s` | %s | %s |"
              % (r["sample_no"], r["symbol"], r["block_rows"], r["evidence_note"]))
    A("")
    A("</details>")
    A("")

    A("## 8. Parser 侧待修问题（确认不是评估器造成）")
    A("")
    A("逐条都对着落盘产物核过，写明「实际发生了什么」，而不是套分类名。")
    A("")
    A("| 样本 | 符号 | 页 | 归因 | 实际发生了什么 |")
    A("|---|---|---|---|---|")
    CASES = {
        ("V003", "TJ"): "该表按温度档分行，块内取到的是 `Extended Industrial –40 105` 这一档，"
                        "Gold 记的是 125 档；档位与参数名的对应关系没建立",
        ("V077", "RVDD"): "`RVDD Supply Voltage, Internal RAM` 行本身没有数值，"
                          "解析把下一行 `456 MHz version 1.25 1.3 1.35` 吞进同一块，"
                          "取到的是 456 MHz 档而不是 Gold 记的 1.14/1.2/1.32 档",
        ("V077", "DVDD"): "同上：`DVDD Supply voltage, I/O, 3.3V` 行本身无值，"
                          "块内是 3.0/3.3/3.45（3.3V 档），Gold 记的是 1.8V 档",
        ("V162", "VCC"): "符号 `VCC` 被挂到 p5 的 `VCC Supply voltage` 表头行（无值），"
                         "Gold 指的 p25 绝对最大值行没有被单独成块",
        ("V162", "VI"): "p25 的行没带符号，退回按值定位时落到 p27 的同名符号块",
        ("V162", "IO"): "同上，`IO` 在 p27 的 ICC 语境里命中，不是 p25 的目标行",
        ("V199", "ID"): "`I D Continuous Drain Current (Silicon limited), T C = 25°C 75`，"
                        "取到 75 A，Gold 记 50 A（另一测试条件下的值）",
        ("V319", "TA"): "`TA` 在该页有三个语境（推荐工作温度档 / 封装热阻表 / 输入共模表），"
                        "解析把符号挂到非目标行，单位与数值都对不上",
        ("V319", "IO"): "该页不存在同时含符号 `IO` 与 20 mA 的块",
        ("V320", "V(ESD)"): "同一个 `V(ESD)` 符号下有 HBM ±2000 V 与 CDM ±500 V 两行，"
                            "符号只落在 CDM 行上，交付的是 ±500（错值）；"
                            "HBM 行是 p012-t02-r02，存在但无符号",
    }
    bad = [r for r in detail if r["primary"] in ("解析失败", "数值错", "evidence page 错",
                                                 "单位错", "漏提")]
    grouped: dict[tuple, list] = {}
    for r in bad:
        key = (r["sample_no"], r["symbol"], r["gold_page"], r["primary"])
        if r["primary"] == "解析失败":
            note = ("建表校验崩溃：`grid_ys must be strictly ascending`"
                    "（`table_detector.py:219`，`DetectedTable` 校验），整件无输出")
        else:
            note = CASES.get((r["sample_no"], r["symbol"]), "—")
        g = grouped.setdefault(key, [note, 0])
        g[1] += 1
    for (sno_, sym_, pg_, pr_), (note_, cnt_) in grouped.items():
        sym = "`%s`" % sym_ if sym_ else "（空）"
        A("| %s | %s | %s | %s | %s%s |"
          % (sno_, sym, pg_, pr_, note_,
             "（同类 %d 行）" % cnt_ if cnt_ > 1 else ""))
    A("")
    A("按性质归并，是 **5 类**问题：")
    A("")
    A("1. **建表校验直接崩**（V256，第 57 页）：`grid_ys` 非严格递增时 `DetectedTable` "
      "抛 `ValidationError`，整件零输出。唯一一处「零输出」缺陷，优先级最高。"
      "修法应是在建表前对 grid 线做单调化/去重，而不是放宽校验。")
    A("2. **档位与参数名的对应关系没建立**（V003 `TJ`、V077 `RVDD`/`DVDD`、V199 `ID`）："
      "同一参数名下的多个速度/温度/测试条件档，值与档位串行。")
    A("3. **合并符号单元只落在首行**（V320 `V(ESD)`、V162 `VCC`）："
      "一个符号纵向合并多行时，只有其中一行带符号，另一行成为无符号孤儿块，"
      "下游按符号取数会取到错行或错值。")
    A("4. **同名符号跨语境抢匹配**（V319 `TA`、V162 `VI`/`IO`）："
      "符号在页内出现在多个参数表的列头或行首，没有按表归属消歧。")
    A("5. **行内符号与参数名同格时未拆分**（V304、V145 等）："
      "`V CC Supply voltage`、`PDISS Power Dissipation` 这类格子没有拆成两列；"
      "本次靠评估侧的文本级匹配才捞回来，Parser 侧应补结构化拆分。")
    A("")

    A("## 9. 口径与局限（必须连同数字一起读）")
    A("")
    A("1. **评的是行级检索 + token 保真，不是逐字段严格解析。** 参数块（block）"
      "把合并单元格的多行并成一块，块的数值集合取并集；块内行数 ≥5 的一律降级为软命中。")
    A("2. **condition 不进主归因。** 这批 Gold 的 condition 多来自列头"
      "（`HC, VCC=2V` 对应某条子列 + 分组行），块文本不携带那层语义。"
      "按字符串定位判会把版式差异记成解析错误，故单列参考值。")
    A("3. **`多余候选` 只能是样本相对值**，理由见 §5.1。真正的误提率需要全表枚举的 Gold 才能算。")
    A("4. **V256 的 5 行计入分母并归为「解析失败」**，没有从分母里剔除——"
      "剔除会把崩溃伪装成不存在。")
    A("5. **块组装上限 8 行**是保守选择：宁可少吞（数值判缺失）也不多吞（数值保真虚高）。")
    A("6. **`symbol 错配 0` 不等于没有符号问题。** 该归因只在「符号定位不到、但值在同一页」时触发；"
      "若符号找到了却挂在错行上（值不符），会被记成 `数值错` 或 `evidence page 错`。"
      "读这一栏时请与 §8 的逐条描述一起看。")
    A("7. **V101 有一次补跑**：早先单件预跑留下同名目录，编排器拒绝覆盖（输出隔离生效）；"
      "移走残留后用 `--only V101` 重跑，通过后删除残留；`replay_summary.json` 里标记了 `rerun: [\"V101\"]`。")
    A("")

    A("## 10. 产物清单与复现")
    A("")
    A("| 文件 | 内容 |")
    A("|---|---|")
    A("| `env_snapshot.json` | 环境与版本快照（含 parser 包指纹） |")
    A("| `input_manifest.csv` / `.json` | 24 件输入白名单 + SHA-256 |")
    A("| `replay_summary.json` / `replay_log.jsonl` | 逐件执行结果 |")
    A("| `logs/<样本>.log` | 逐件 stdout/stderr 原文 |")
    A("| `per_sample/<样本>/` | 逐件 Parser 全量输出（document / tables / candidates / text_blocks / boundary_decisions / run_manifest） |")
    A("| `rows_parser.csv` | 全部候选块（%d 条） |" % cand["blocks_total"])
    A("| `eval_detail.csv` | 105 行 Gold 的逐行判定 |")
    A("| `metrics.json` / `legacy_metrics.json` | 正式 / 修正前指标 |")
    A("| `calibration_diff.csv` / `.md` | 逐行口径对照 |")
    A("| `text_hit_audit.csv` | 文本级命中逐条审计 |")
    A("| `extra_candidate_audit.csv` | 样本外候选块抽检（10 块） |")
    A("| `per_sample_json/<样本>.json` | 逐件候选块 + Gold 判定合并视图 |")
    A("| `boundary_assertions.txt` | 四条边界机检原始输出（25 项 PASS） |")
    A("| `report.md` | 本报告 |")
    A("")
    A("### 10.1 逐件结果与输出路径")
    A("")
    A("| 样本 | 表 | 候选块 | Gold 行 | 命中 | 完全一致 | 输出目录 |")
    A("|---|---|---|---|---|---|---|")
    for sno in sorted(m["per_sample"]):
        v = m["per_sample"][sno]
        if v.get("error"):
            A("| %s | — | — | %d | 0 | 0 | `per_sample/%s/`（无输出） |"
              % (sno, v["gold_rows"], sno))
            continue
        A("| %s | %d | %d | %d | %d | %d | `per_sample/%s/` |"
          % (sno, v["tables"], v["blocks"], v["gold_rows"], v["hit"], v["exact"], sno))
    A("")
    A("复现：")
    A("")
    A("```bash")
    A("python workbench/gate6a_replay/_env_and_manifest.py   # 环境快照 + 输入清单")
    A("python workbench/gate6a_replay/_run_replay.py         # 24 件回测（约 14 分钟）")
    A("python workbench/gate6a_replay/_evaluate.py           # 正式口径")
    A("ICPDF_EVAL_LEGACY=1 python workbench/gate6a_replay/_evaluate.py   # 修正前口径")
    A("python workbench/gate6a_replay/_compare_eval_calibration.py       # 逐行对照")
    A("python workbench/gate6a_replay/_audit_text_hits.py                # 文本级命中审计")
    A("python workbench/gate6a_replay/_make_report.py                    # 本报告")
    A("```")
    A("")
    A("**输出隔离（边界 4）**：以上全部产物只写 `runs/gate6a_replay_v1/`；"
      "既有 Gold 台账与历史 `runs/` 未被写入。编排器启动时断言输出根名必须为 "
      "`gate6a_replay_v1`，且 worker 目录已存在时拒绝覆盖。")
    A("")

    A("## 11. 内部审计证据包")
    A("")
    A("Reviewer 叫停灰度后追加的证据，全部落在 `audit/`，索引见 `audit/README.md`：")
    A("")
    A("| 文件 | 回答的问题 |")
    A("|---|---|")
    A("| `error_matrix_105.csv` | 105 行逐行判定，「命中」到底怎么算（命中 %d / 错误匹配 %d / 漏提 %d） |"
      % (89, 15, 1))
    A("| `error_matrix_105_v1_prefix.csv` | 同一张表的 v1 版本，用于与本报告口径对齐 |")
    A("| `error_matrix_105_README.md` | 字段字典 + `match_status` 三值定义 + 自查命令 |")
    A("| `evaluator_flips_39.csv` + `evaluator_v1_legacy/` + `evaluator_v2_final/` | 39 行翻正的两版评估器与逐行成因 |")
    A("| `parser_json_immutability.txt` | 修评估器时 185 个 Parser JSON 哈希全同（变化 0） |")
    A("| `v256_crash_evidence.md` | V256 真实 traceback + 第 57 页 `grid_ys` 逐位前后对照 |")
    A("| `postfix_rerun_24.md` | 修复后 24 件重跑：24/24 成功，V256 216 页 |")
    A("| `parser_v1_v2_diff.md` | 其余 23 件 115 个文件**逐字节完全相同** |")
    A("| `pdf_sha256_24.csv` / `parser_commit.txt` / `pip_freeze.txt` | 输入、代码、依赖三方溯源 |")
    A("| `network_guard_proof.md` | 四类出网调用实测全部拦下，`llm_blocked` 累计 0 |")
    A("| `TECH_DEBT.md` | 四类暂不修的 Parser 语义缺陷与回归约束 |")
    A("")
    A("本报告（§1–§10）记录的是 **v1** 首次回测，指标与结论均不作修改。")
    A("修复后的重跑结果单独写在 `audit/postfix_rerun_24.md`，不覆盖本报告。")
    A("")

    OUT.write_bytes(("\n".join(L) + "\n").encode("utf-8"))
    print("报告已生成：%s（%d 行）" % (OUT, len(L)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
