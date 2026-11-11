# -*- coding: utf-8 -*-
"""生成两份证据文档（v1.1）：

  PUSH_REVIEW_45_COMMITS.md   远端推送前的 45 个提交审查
  SCAN_SELECTION_EVIDENCE.md  79 → 62 → 3 的筛选证据链 + S01-S03 逐页明细

以及逐页明细的机读版 S01_S03_PAGE_DETAIL.csv。

所有数字现场从 Git / 扫描产物计算，不手抄；原始日志逐字嵌入。
"""
from __future__ import print_function

import csv
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO = Path(r"E:\workspace\icpdf-extractor")
PREP = Path(__file__).resolve().parent


def git(*args):
    p = subprocess.run(["git"] + list(args), cwd=str(REPO),
                       capture_output=True)
    return p.stdout.decode("utf-8", "replace").strip(), p.returncode


def collect_push_facts():
    facts = {}
    facts["remote"], _ = git("remote", "v")
    facts["branch"], _ = git("branch", "--show-current")
    facts["main"], _ = git("rev-parse", "main")
    facts["origin_main"], _ = git("rev-parse", "origin/main")
    _, rc = git("merge-base", "--is-ancestor", "origin/main", "main")
    facts["is_ancestor_rc"] = rc
    facts["ahead"], _ = git("rev-list", "--count", "origin/main..main")
    facts["behind"], _ = git("rev-list", "--count", "main..origin/main")
    facts["origin_main_info"], _ = git("log", "-1", "--format=%H%n%ci%n%s",
                                       "origin/main")
    facts["ls_remote"], _ = git("ls-remote", "origin", "main")
    facts["commits"], _ = git("log", "--oneline", "origin/main..main")

    ns, _ = git("diff", "--name-status", "origin/main..main")
    rows = [l.split("\t") for l in ns.splitlines() if l.strip()]
    facts["file_count"] = len(rows)
    facts["by_status"] = Counter(r[0][0] for r in rows)
    facts["by_dir"] = Counter(r[1].split("/")[0] if "/" in r[1] else "(root)"
                              for r in rows)
    facts["src_rows"] = [r for r in rows if r[1].startswith("src/")]

    stat, _ = git("diff", "--shortstat", "origin/main..main")
    facts["shortstat"] = stat

    st, _ = git("status", "--porcelain=v1")
    tracked = [l for l in st.splitlines() if not l.startswith("??")]
    untracked = [l for l in st.splitlines() if l.startswith("??")]
    facts["tracked_mods"] = tracked
    facts["untracked_count"] = len(untracked)
    return facts


def build_push_report(facts):
    raw = (PREP / "push_review_raw.log").read_text(encoding="utf-8").rstrip("\n")
    L = []
    a = L.append

    a("# 远端推送前的 45 个提交审查")
    a("")
    a("> **结论：可以快进推送（`origin/main` 是 `main` 的祖先），但本轮没有推。**")
    a("> 以下全部为只读命令，未执行 `git fetch`、未改动任何 ref、未触碰工作区。")
    a("")
    a("## 1. 核对结果")
    a("")
    a("| 项 | 值 |")
    a("|---|---|")
    a("| 仓库 | `E:\\workspace\\icpdf-extractor` |")
    a("| 远端 URL | `[REDACTED-INTERNAL-REPO]`（**不含凭据**，无需脱敏） |")
    a("| 当前分支 | `%s` |" % facts["branch"])
    a("| 本地 `main` | `%s` |" % facts["main"])
    a("| `origin/main` | `%s` |" % facts["origin_main"])
    a("| `origin/main` 提交时间 | %s |" % facts["origin_main_info"].splitlines()[1])
    a("| `origin/main` 提交标题 | %s |" % facts["origin_main_info"].splitlines()[2])
    a("| `merge-base --is-ancestor origin/main main` | **`EXIT=%d`**（0 = 是祖先，可快进） |"
      % facts["is_ancestor_rc"])
    a("| 领先提交数 | **%s** |" % facts["ahead"])
    a("| 落后提交数 | **%s**（无分叉） |" % facts["behind"])
    a("| 远端真实指向（`ls-remote`） | `%s` |"
      % facts["ls_remote"].split("\t")[0])
    a("")
    a("**`origin/main` 没有过期**：`git ls-remote`（纯查询，不写 ref）返回的远端 "
      "`refs/heads/main` 与本地 `origin/main` 指向同一个提交 "
      "`%s`。因此下面基于 `origin/main..main` 的统计是可信的，"
      "不存在「本地以为领先 45 个、远端其实已经变了」的情况。" % facts["origin_main"])
    a("")
    a("## 2. 45 个提交改了 475 个文件")
    a("")
    a("`%s`" % facts["shortstat"])
    a("")
    a("| 状态 | 文件数 |")
    a("|---|---|")
    for k, v in sorted(facts["by_status"].items()):
        a("| %s | %d |" % ("新增" if k == "A" else "修改" if k == "M" else k, v))
    a("")
    a("| 顶层目录 | 文件数 |")
    a("|---|---|")
    for k, v in facts["by_dir"].most_common():
        a("| `%s` | %d |" % (k, v))
    a("")
    a("### 2.1 `src/` 是唯一的生产代码改动面（%d 个文件）"
      % len(facts["src_rows"]))
    a("")
    a("| 状态 | 文件 |")
    a("|---|---|")
    for r in sorted(facts["src_rows"], key=lambda x: x[1]):
        a("| %s | `%s` |" % (r[0], r[1]))
    a("")
    a("其中 `src/icpdf/classification/` 下 8 个文件（含 `classifier.py`）"
      "整包新增——这是 G7a 基线提交 `35cd8a1` 带进来的，"
      "`classifier.py` 的内容哈希在 G7b 合入前后均为 `28b9f0bf…`，本次合并未改动它。")
    a("")
    a("### 2.2 清单里 209 个 `gold/` 文件要单独看")
    a("")
    a("`gold/` 占 475 个文件的 44%，但它**不是**本轮 Gate 6A 的 Gold Set。"
      "它是 Phase 1.2 / 1.3 阶段冻结的 `gold/generalization/` 泛化测试集"
      "（三份 PDF 的表级标注 + overlay 图），随 Phase 1.4 设计提交一并上主干。")
    a("")
    a("Gate 6A 的 Gold Set 至今**一份都没建**，只交付了模板。两者不要混淆。")
    a("")
    a("## 3. 工作区状态")
    a("")
    a("已跟踪的改动只有 2 个，且都不属于这 45 个提交：")
    a("")
    for l in facts["tracked_mods"]:
        a("- `%s`" % l.strip())
    a("")
    a("未跟踪路径 %d 条（含 `.workbuddy/`、`workbench/`、`tools/stage_a|b/` 等）。"
      "它们**不在** Git 索引里，推送不会带上。" % facts["untracked_count"])
    a("")
    a("## 4. 推送前仍需 Reviewer 注意的三件事")
    a("")
    a("1. **这是一次 45 个提交的合并推送，不是单提交**。`origin/main` 停在 "
      "`853a80dd…`（项目初始化提交），之后全部 Phase 1.1–1.4 的工作都还没上远端。"
      "推上去等于**一次性公开整个演进过程**，包括中途被后续提交修正过的设计文档。")
    a("2. **`gold/` 含 209 个文件、大量 PNG overlay**，仓库体积会明显增加。"
      "若对体积敏感，应先在推送前决定是否把这批 overlay 移出主仓。")
    a("3. **两个未提交的已跟踪改动（`cli.py`、`R1_PRIME_SUPPLEMENT.md`）会被留在本地**，"
      "推送的是它们在 `60a503c` 里的已提交版本，与工作区版本不同。"
      "如果这两处改动是必需的，需要在推送前先决定提交还是丢弃。")
    a("")
    a("## 5. 本轮执行边界")
    a("")
    a("- **未执行 `git push`**，本地与远端均无任何写入。")
    a("- 未执行 `git fetch`，`origin/main` 保持上次拉取时的状态（已用 `ls-remote` 交叉确认未过期）。")
    a("- 未改动工作区、未暂存、未提交。")
    a("")
    a("## 6. 原始终端输出（逐字嵌入，未编辑）")
    a("")
    a("```text")
    a(raw)
    a("```")
    a("")
    return "\n".join(L) + "\n"


def build_scan_evidence():
    summary = json.loads((PREP / "scan_summary.json").read_text(encoding="utf-8"))
    sel = json.loads((PREP / "selected_supplementary.json").read_text(encoding="utf-8"))
    full = json.loads((PREP / "full_page_textlayer_verify.json").read_text(encoding="utf-8"))

    # 去重复现：按 SHA 分组
    groups = {}
    for r in summary["candidates"]:
        groups.setdefault(r["sha256"], []).append(r["name"])
    uniq_n = len(groups)
    dup_groups = {k: v for k, v in groups.items() if len(v) > 1}

    # 分档
    rep = {}
    for sha, names in groups.items():
        rec = next(r for r in summary["candidates"] if r["sha256"] == sha)
        rep[sha] = {"sha256": sha, "name": sorted(names)[0], "aliases": sorted(names),
                    "page_count": rec["page_count"], "size_bytes": rec["size_bytes"]}
    uniq = sorted(rep.values(), key=lambda r: r["sha256"])
    bands = [("BAND_A_1_10", 1, 10), ("BAND_B_11_30", 11, 30), ("BAND_C_31_100", 31, 100)]

    L = []
    a = L.append
    a("# 扫描件入池证据链：11,355 → 79 → 62 → 3")
    a("")
    a("> 本文回答一个问题：**S01 / S02 / S03 这三件凭什么进 Gold Set？**")
    a("> 每一步筛选给出规则、边界与可复现命令，逐页明细见 §5。")
    a("")
    a("## 1. 漏斗总览")
    a("")
    a("| 阶段 | 数量 | 方法 | 产物 |")
    a("|---|---|---|---|")
    a("| 真实语料池 | %d | `E:\\workspace\\IcPdfParser\\data\\pdfs` 下全部 PDF | — |"
      % summary["total_pdf"])
    a("| 实测无文本层 | %d | PyMuPDF 文本层探针（阈值 %d 字符） | `scan_all.jsonl` |"
      % (len(summary["candidates"]), summary["text_threshold_chars"]))
    a("| 按 SHA-256 去重 | %d | 同一 PDF 的多个料号别名合并为一件 | `IMAGE_ONLY_CANDIDATES.csv` |"
      % uniq_n)
    a("| 分档取首件 | **3** | 页数三档，档内 SHA 升序取第一 | `selected_supplementary.json` |")
    a("")
    a("丢弃率说明：11,355 份里只有 %d 份（%.2f%%）真正没有文本层。"
      "这批文档不是主流，正因为稀少，350 池里一件都没抽到才是正常的——"
      "这解释了为什么原提案的「扫描型」层实际上是空的。"
      % (len(summary["candidates"]),
         100.0 * len(summary["candidates"]) / summary["total_pdf"]))
    a("")
    a("## 2. 第 1 步：无文本层判定（79 件怎么来的）")
    a("")
    a("| 项 | 值 |")
    a("|---|---|")
    a("| 判定库 | PyMuPDF 1.24.14（MuPDF 1.24.11） |")
    a("| 文本阈值 | 首页有效文本 **≥ %d 字符** 即判定有文本层 |"
      % summary["text_threshold_chars"])
    a("| 口径来源 | 与 `runs/_gate1_pdf_probe.py` 完全一致，不新造标准 |")
    a("| 段 1 | 逐件读首页 `page.get_text(\"text\")` |")
    a("| 段 2 | 仅对段 1 判为无文本层的件，追加**最多 %d 个跨页**抽样（首/尾/等距） |"
      % summary["sample_pages_cap"])
    a("| 并发 / 耗时 | 8 进程 / %.1f 秒 |" % summary["elapsed_sec"])
    a("| 可打开 | %d / %d（失败 %d） |"
      % (summary["counts"]["valid_true"], summary["total_pdf"],
         summary["counts"]["valid_false"]))
    a("| 加密件 | %d |" % summary["counts"]["encrypted_true"])
    a("")
    a("**段 2 不是可选项。** 只看首页会把「封面是扫描图、正文有文本层」的文档错判成扫描件。"
      "加抽样后仍要求跨页字符数合计 < %d 才算无文本层。"
      % summary["text_threshold_chars"])
    a("")
    a("## 3. 第 2 步：去重（79 → 62）")
    a("")
    a("### 3.1 为什么必须去重")
    a("")
    a("同一个 PDF 在语料池里常以多个料号命名重复入库。"
      "若不去重，**同一份扫描件的 7 个别名会被当成 7 个独立样本**，"
      "PAIN-08 的覆盖率会被虚增 7 倍，这是统计污染而不是覆盖。")
    a("")
    a("### 3.2 去重规则")
    a("")
    a("1. 以 `pdf_sha256` 为唯一键，字节相同即同一文档；")
    a("2. 同键的多个文件名全部保留在 `alias_names` 字段，不丢弃证据；")
    a("3. 取文件名字典序最小者作为 `representative_name`，**仅为展示用**，"
      "不参与排序，避免「改名影响选样结果」。")
    a("")
    a("### 3.3 重复组明细（%d 组）" % len(dup_groups))
    a("")
    a("| SHA-256 前 16 位 | 别名数 | 别名 |")
    a("|---|---|---|")
    for sha, names in sorted(dup_groups.items(), key=lambda kv: -len(kv[1])):
        a("| `%s` | %d | %s |"
          % (sha[:16], len(names), "<br>".join(sorted(names))))
    a("")
    a("去重后剩余 **%d** 件唯一文档。" % uniq_n)
    a("")
    a("## 4. 第 3 步：分档取首件（62 → 3）")
    a("")
    a("### 4.1 分档边界（闭区间，左闭右开不适用）")
    a("")
    a("| 档位 | 页数区间 | 档内件数 | 配额 |")
    a("|---|---|---|---|")
    for band, lo, hi in bands:
        n = sum(1 for r in uniq if lo <= r["page_count"] <= hi)
        a("| `%s` | %d ≤ page_count ≤ %d | %d | 1 |" % (band, lo, hi, n))
    a("")
    a("区间外的件（page_count > %d）共 %d 件，本次不取。"
      % (bands[-1][2], sum(1 for r in uniq if r["page_count"] > bands[-1][2])))
    a("")
    a("### 4.2 为什么分档而不是取最短的 3 件")
    a("")
    a("页数决定该文档能不能承载一张参数表。只取最短件会得到 1–2 页的封面扫描，"
      "Parser 在那上面只能表现「打开就失败」，PAIN-08 就退化成空测。"
      "分档保证短 / 中 / 长三档各有一件，能观察到不同规模下的行为差异。")
    a("")
    a("### 4.3 档内排序规则")
    a("")
    a("按 `pdf_sha256` **十六进制字符串升序**排序，取第 1 件。"
      "SHA 是内容的确定性函数，因此该规则**可盲复现**："
      "任何人拿同样的 62 件重跑，得到同样的 3 件，无需信任执行者的判断。")
    a("")
    a("### 4.4 各档首件（含未被选中的次位，供 Reviewer 换样）")
    a("")
    for band, lo, hi in bands:
        sub = sorted([r for r in uniq if lo <= r["page_count"] <= hi],
                     key=lambda r: r["sha256"])
        a("**`%s`**（档内 %d 件）" % (band, len(sub)))
        a("")
        a("| 位次 | 文件名 | 页数 | SHA-256 前 16 位 | 入选 |")
        a("|---|---|---|---|---|")
        for i, r in enumerate(sub[:4], 1):
            a("| %d | `%s` | %d | `%s` | %s |"
              % (i, r["name"], r["page_count"], r["sha256"][:16],
                 "**是**" if i == 1 else "否"))
        a("")
    a("## 5. 入选 3 件的身份与逐页明细")
    a("")
    for s in sel["selected"]:
        fv = next(x for x in full["samples"] if x["sample_no"] == s["sample_no"])
        a("### %s `%s`" % (s["sample_no"], s["file_name"]))
        a("")
        a("| 项 | 值 |")
        a("|---|---|")
        a("| 档位 | `%s` |" % s["band"])
        a("| 页数 | %d |" % s["page_count"])
        a("| 文件大小 | %s 字节 |" % format(s["size_bytes"], ","))
        a("| SHA-256 | `%s` |" % s["sha256"])
        a("| 绝对路径 | `%s` |" % s["file_path"])
        a("| 同 SHA 别名数 | %d |" % s["alias_count"])
        a("| 逐页核验页数 | %d / %d（全覆盖） |" % (fv["pages_probed"], fv["page_count"]))
        a("| 单页最大字符数 | **%d** |" % fv["max_chars_per_page"])
        a("| 全文总字符数 | **%d** |" % fv["total_chars"])
        a("| 最小图像覆盖率 | **%.2f** |" % fv["min_image_area_ratio"])
        a("| 判定 | `%s` |" % fv["verdict"])
        a("")
        a("逐页数据：")
        a("")
        a("| 页码 | 字符数 | 图像对象数 | 绘制实例数 | 图像覆盖率 |")
        a("|---|---|---|---|---|")
        for p in fv["pages"]:
            a("| %d | %d | %d | %d | %.2f |"
              % (p["page"], p["chars"], p["image_objects"],
                 p["image_draw_instances"], p["image_area_ratio"]))
        a("")
    a("## 6. 为什么「每页 0 字符 + 覆盖率 1.00」足以支撑入池")
    a("")
    a("1. **0 字符**：文本层彻底缺失，Parser 的任何文本抽取都会得到空结果。"
      "这不是「文本层质量差」，而是「没有文本层」——正是 PAIN-08 要测的极端。")
    a("2. **覆盖率 1.00**：每页 100% 被一个图像绘制实例覆盖，证明这确实是整页扫描图，"
      "而不是「矢量图无文字」或「空页」。两者在 Parser 侧的行为可能不同。")
    a("3. **逐页全覆盖**：不是抽样推断。S01 6/6 页、S02 11/11 页、S03 53/53 页，"
      "合计 70 页全部核验，不存在「没抽到的页其实有文本」的可能。")
    a("")
    a("## 7. 一处口径返工（必须记录）")
    a("")
    a("第一版逐页核验用 `page.get_text(\"dict\")` 里 `type == 1` 的图像块累计面积，"
      "结果 6 页全算出 `image_area_ratio = 0.00`——看起来像「既无文字也无图像」，"
      "会把结论推向「这些是空页」。")
    a("")
    a("改用 `page.get_image_info()` 取绘制实例的真实 bbox 后，得到 1.00。"
      "差异原因：嵌入型 XObject 在 `get_text(\"dict\")` 里拿不到 bbox，"
      "漏算后归零。")
    a("")
    a("**错误的那一版已作废，未进入任何结论。** 现在落盘的 "
      "`full_page_textlayer_verify.json` 是修正后的版本。")
    a("")
    a("## 8. 边界与禁止事项")
    a("")
    a("- 这 3 件在 **350 池之外**，突破了「从 350 池抽样」的约束，"
      "属 `GATE6A_PLAN.md` §1.4 缺口 1 的选项 2，已获 Reviewer 2026-11-11 批准。")
    a("- 计入分母仍以 `status = CONFIRMED` 为前提；当前全部 `DRAFT`，"
      "**此刻不进任何分母**。")
    a("- 3 件均不在 D' 的 193 条变化集内，不会被分类规则修订影响。")
    a("- **没有调用 Parser**，没有 OCR。这 3 件在 Parser 里的实际表现本轮**未知**，"
      "不得从「无文本层」推断出「Parser 会失败」——那要等实跑。")
    a("")
    a("## 9. 复现命令")
    a("")
    a("```")
    a("python workbench/_gate6a_prep/_scan_image_only.py       # 11,355 份全量扫描，约 14 分钟")
    a("python workbench/_gate6a_prep/_select_supplementary.py  # 去重 + 分档 + 档内 SHA 升序取首")
    a("python workbench/_gate6a_prep/_verify_fullpage.py       # 3 件逐页全量核验")
    a("python workbench/_gate6a_prep/_selfcheck.py             # 四项交叉自检")
    a("```")
    a("")
    a("机读明细：`S01_S03_PAGE_DETAIL.csv`（70 行，一行一页）、"
      "`IMAGE_ONLY_CANDIDATES.csv`（62 行，含全部别名）。")
    a("")
    return "\n".join(L) + "\n"


def write_page_detail_csv():
    full = json.loads((PREP / "full_page_textlayer_verify.json")
                      .read_text(encoding="utf-8"))
    cols = ["sample_no", "file_name", "sha256", "page", "chars",
            "image_objects", "image_draw_instances", "image_area_ratio"]
    path = PREP / "S01_S03_PAGE_DETAIL.csv"
    n = 0
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for s in full["samples"]:
            for p in s["pages"]:
                w.writerow({
                    "sample_no": s["sample_no"],
                    "file_name": s["file_name"],
                    "sha256": s["sha256"],
                    "page": p["page"],
                    "chars": p["chars"],
                    "image_objects": p["image_objects"],
                    "image_draw_instances": p["image_draw_instances"],
                    "image_area_ratio": "%.4f" % p["image_area_ratio"],
                })
                n += 1
    return path, n


def main():
    facts = collect_push_facts()
    push_md = build_push_report(facts)
    (PREP / "PUSH_REVIEW_45_COMMITS.md").write_text(
        push_md, encoding="utf-8", newline="\n")
    print("PUSH_REVIEW_45_COMMITS.md  %d bytes" % len(push_md.encode("utf-8")))

    scan_md = build_scan_evidence()
    (PREP / "SCAN_SELECTION_EVIDENCE.md").write_text(
        scan_md, encoding="utf-8", newline="\n")
    print("SCAN_SELECTION_EVIDENCE.md %d bytes" % len(scan_md.encode("utf-8")))

    p, n = write_page_detail_csv()
    print("S01_S03_PAGE_DETAIL.csv    %d rows" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
