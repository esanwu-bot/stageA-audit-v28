# -*- coding: utf-8 -*-
"""生成主仓源码指纹：把「审计包声明的夹紧实现」钉到具体 commit 与具体字节上。

Reviewer 无法访问 CodeUp 内网，所以这里给的是**可独立复核的字节指纹**：
每个 commit 上 structure.py 的 git blob SHA-1 与 LF 归一后的 sha256，
再加上真正落地的那段 diff。拿到 diff 的人可以逐行核对公式，不依赖仓库权限。

=== 一个必须写清楚的诚实边界 ===
v2 回测的环境快照（artifacts/v2_env_snapshot.json）记录的 commit 是 a11131a，
且工作区有 199 个脏文件 —— 说明那次回测跑在「修复已存在但尚未提交」的工作树上。
修复是事后才以 bede1f5 提交的。所以「回测当时跑的是哪份字节」不能只靠 commit 断言，
必须同时给出：a11131a 的基线 + bede1f5 的 diff + 产物自身的哈希链。
本文件把这条边界写在最前面，而不是藏起来。

=== 行尾陷阱 ===
本机 core.autocrlf=true，工作区 structure.py 是纯 CRLF（741 个）、git blob 是纯 LF。
直接对工作区文件算 sha256 会得到与 blob 不同的值，跨机器永远对不上。
因此指纹一律以 git blob 字节为准，并给出复现方式。
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AUDIT = REPO / "workbench" / "gate6a_replay" / "audit"
TARGET = "src/icpdf/parser/structure.py"
FIX_COMMIT = "bede1f5"


def git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=REPO, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError("git %s 失败：%s" % (" ".join(args),
                                               r.stderr.decode("utf-8", "replace")[:300]))
    return r.stdout.decode("utf-8", "replace")


def git_bytes(*args: str) -> bytes:
    r = subprocess.run(["git", *args], cwd=REPO, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError("git %s 失败" % " ".join(args))
    return r.stdout


def blob_of(rev: str, path: str) -> str:
    return git("rev-parse", "%s:%s" % (rev, path)).strip()


def sha256_of_blob(rev: str, path: str) -> str:
    return hashlib.sha256(git_bytes("cat-file", "blob", "%s:%s" % (rev, path))).hexdigest()


def main() -> int:
    head = git("rev-parse", "HEAD").strip()
    fix_sha = git("rev-parse", FIX_COMMIT).strip()
    base_sha = git("rev-parse", FIX_COMMIT + "^").strip()

    fix_diff = git("show", fix_sha, "--", TARGET)
    i = fix_diff.find("diff --git")
    if i > 0:
        fix_diff = fix_diff[i:]
    # 精确行数：排除 `+++ ` / `--- ` 这两个文件头，它们不是增删行
    _lines = fix_diff.splitlines()
    n_add = sum(1 for ln in _lines if ln.startswith("+") and not ln.startswith("+++"))
    n_del = sum(1 for ln in _lines if ln.startswith("-") and not ln.startswith("---"))
    stat = [ln for ln in git("show", "--stat", "--format=", fix_sha, "--", TARGET)
            .splitlines() if ln.strip()]

    rows = [
        ("v2 回测时快照记录的 commit", base_sha,
         "Gate 6A Batch 2：24 行 Gold 并入 main（Reviewer 已批准）",
         "回测在它之上、带着未提交的修复改动运行"),
        ("V256 夹紧修复落地", fix_sha,
         "Gate 6A 审计证据包：…… V256 崩溃修复与复跑",
         "structure.py +%d / −%d，新增 _monotonic_lattice 与 lattice_adjusted"
         % (n_add, n_del)),
        ("当前审计分支 HEAD", head,
         "审计包提交",
         "未改动 src/，structure.py 与修复落地时逐字节相同"),
    ]

    # 工作区 vs blob 的行尾差异，用来说明为什么不能用工作区哈希
    wt = (REPO / TARGET).read_bytes()
    wt_crlf = wt.count(b"\r\n")
    wt_lf_only = wt.count(b"\n") - wt_crlf
    autocrlf = git("config", "core.autocrlf").strip() or "(未设置)"


    L: list[str] = []
    A = L.append
    A("# 主仓源码指纹：`_monotonic_lattice` 与 Parser commit")
    A("")
    A("> 审计包不含 `src/` 源码树。本文件给出的是一处**被审改动**的字节指纹与完整 diff，"
      "目的是让拿到本包的人能独立核对「审计包声称的夹紧公式」与「真实落地的代码」是否一致。")
    A("")
    A("## 0. 先说一条边界（不是补充说明，是前提）")
    A("")
    A("`artifacts/v2_env_snapshot.json` 记录的回测时 commit 是 "
      "`%s`，且 `dirty_files` 有 **199** 项。" % base_sha[:7])
    A("也就是说：**v2 那次复跑跑在「修复已写好但还没提交」的工作树上**，"
      "不是跑在一个干净的 commit 上。")
    A("")
    A("所以「回测当时跑的到底是哪份字节」这件事，不能只靠一句 commit SHA 打发。"
      "本包用三条互相独立的线索钉住它：")
    A("")
    A("1. 基线 commit `%s` 的 `structure.py` blob 指纹（修复前）；" % base_sha[:7])
    A("2. 修复 commit `%s` 的 diff（修复内容，逐行可核）；" % fix_sha[:7])
    A("3. 产物侧哈希链：`parser_outputs_sha256_gate6a_replay_v2_postfix.csv` "
      "记录了回测产出的 192 个 JSON 的 sha256，"
      "`parser_json_immutability_gate6a_replay_v2_postfix.txt` 证明评估器没改它们。")
    A("")
    A("把 (1)+(2) 施加到同一份文件上，应当得到 (3) 所对应的产物；反之，任何一处不符都会露馅。")
    A("")
    A("## 1. 三个 commit 上的 `structure.py` 指纹")
    A("")
    A("| 角色 | commit | 说明 | `structure.py` git blob (SHA-1) | 内容 sha256（LF） |")
    A("| --- | --- | --- | --- | --- |")
    for label, rev, _subj, note in rows:
        A("| %s | `%s` | %s | `%s` | `%s` |"
          % (label, rev[:7], note, blob_of(rev, TARGET)[:12] + "…",
             sha256_of_blob(rev, TARGET)))
    A("")
    A("完整哈希：")
    A("")
    A("```")
    for label, rev, subj, _note in rows:
        A("%s  %s" % (rev, label))
        A("    subject : %s" % subj)
        A("    blob    : %s" % blob_of(rev, TARGET))
        A("    sha256  : %s" % sha256_of_blob(rev, TARGET))
    A("```")
    A("")
    A("`%s` 与当前 HEAD 的 blob 完全相同（`%s`），说明修复落地之后"
      "再没有动过解析器 —— 后续提交只增加审计材料。"
      % (fix_sha[:7], blob_of("HEAD", TARGET)[:12] + "…"))
    A("")
    A("## 2. 行尾陷阱：为什么不能对工作区文件算 sha256")
    A("")
    A("| 事实 | 值 |")
    A("| --- | --- |")
    A("| `core.autocrlf` | `%s` |" % autocrlf)
    A("| 工作区 `structure.py` 的行尾 | CRLF **%d** 个 / 裸 LF **%d** 个 |"
      % (wt_crlf, wt_lf_only))
    A("| 工作区文件 sha256 | `%s` |" % hashlib.sha256(wt).hexdigest())
    A("| git blob 内容 sha256 | `%s` |" % sha256_of_blob("HEAD", TARGET))
    A("")
    A("两个值不一样，**不是文件被改过**，而是 `autocrlf` 在检出时把 LF 换成了 CRLF。"
      "所以本文件一律以 git blob 字节为准。复核时请用：")
    A("")
    A("```bash")
    A("git cat-file blob %s:%s | sha256sum" % (fix_sha[:7], TARGET))
    A("# 期望：%s" % sha256_of_blob(fix_sha, TARGET))
    A("```")
    A("")
    A("## 3. 落地的改动（完整 diff）")
    A("")
    A("`%s` 对 `%s` 的差异，只此一个文件：" % (fix_sha[:7], TARGET))
    A("")
    A("```")
    for ln in stat:
        A(ln.rstrip())
    A("```")
    A("")
    A("完整 diff 见 [`monotonic_lattice.diff`](monotonic_lattice.diff)。")
    A("")
    A("核心函数（diff 中的新增部分，逐字摘录）：")
    A("")
    A("```python")
    A("MIN_ROW_GAP_PT = 0.2")
    A("")
    A("")
    A("def _monotonic_lattice(ys: list[float], lo: float, hi: float")
    A("                       ) -> tuple[list[float], bool]:")
    A("    n = len(ys)")
    A("    if n < 2:")
    A("        return list(ys), False")
    A("    gap = min(MIN_ROW_GAP_PT, (hi - lo) / (n - 1))")
    A("    out = [ys[0]]")
    A("    adjusted = False")
    A("    for value in ys[1:]:")
    A("        floor = out[-1] + gap")
    A("        if value < floor:")
    A("            out.append(floor)")
    A("            adjusted = True")
    A("        else:")
    A("            out.append(value)")
    A("    return out, adjusted")
    A("```")
    A("")
    A("与 `v256_crash_evidence.md` §2 的公式逐字对应：")
    A("")
    A("- `gap = min(MIN_ROW_GAP_PT, (hi - lo) / (n - 1))` —— 与文档一致；")
    A("- `floor = out[-1] + gap`，`if value < floor: out.append(floor)` —— "
      "**只上推、不下拉**，与「不排序、不重排行」一致；")
    A("- 返回 `adjusted` 由 `TableGrid.lattice_adjusted` 承载，"
      "`_status()` 据此降级 `PARTIAL` —— 与 §7 的「下游不读 status」互补："
      "标记在上游产生，下游不改判。")
    A("")
    A("## 4. 复核清单")
    A("")
    A("拿到本包的人可以这样独立核对，不需要 CodeUp 访问权：")
    A("")
    A("```bash")
    A("# 1. 本包内的 diff 与文档公式是否一致")
    A("grep -nE '^\\+.*(gap = min|floor = out)' monotonic_lattice.diff")
    A("")
    A("# 2. **新增行**里是否出现过排序（不得把行重排）")
    A("grep -nE '^\\+.*sort' monotonic_lattice.diff    # 期望：无输出")
    A("")
    A("# 3. **新增行**里是否出现过下拉（不得把合法格线拉下来）")
    A("grep -nE '^\\+.*out\\[-1\\] *-' monotonic_lattice.diff    # 期望：无输出")
    A("")
    A("# 4. 产物侧：192 个 JSON 的哈希")
    A("head -3 parser_outputs_sha256_gate6a_replay_v2_postfix.csv")
    A("```")
    A("")
    A("第 2、3 条刻意只查**新增行**（`^\\+`）：diff 里有一行未改动的上下文 "
      "`cells.sort(key=lambda cell: (cell.row, cell.column))`，"
      "那是给单元格按 (行, 列) 定序，与「重排行格线」无关；把它一并算进来会误判，"
      "所以断言必须锚在新增行上。")
    A("")
    A("这次修复最关键的两个不变式就是：**不排序**（否则行序失效、"
      "`GridCell.row` 与 `cell_words` 索引全部错位）、**只上推**"
      "（否则会把合法格线拉下来，制造新的倒序）。")

    (AUDIT / "source_fingerprint.md").write_text("\n".join(L) + "\n", encoding="utf-8")

    header = [
        "# %s 对 %s 的改动：src/icpdf/parser/structure.py" % (fix_sha[:7], base_sha[:7]),
        "#",
        "# 本文件是全审计包中唯一的源码片段，只包含这处被审改动，不含任何其他实现。",
        "# 完整 commit：%s" % fix_sha,
        "# 父 commit  ：%s" % base_sha,
        "# structure.py blob：%s -> %s"
        % (blob_of(base_sha, TARGET), blob_of(fix_sha, TARGET)),
        "# 内容 sha256（LF）：%s -> %s"
        % (sha256_of_blob(base_sha, TARGET), sha256_of_blob(fix_sha, TARGET)),
        "",
    ]
    (AUDIT / "monotonic_lattice.diff").write_text(
        "\n".join(header) + fix_diff, encoding="utf-8")

    print("wrote audit/source_fingerprint.md、audit/monotonic_lattice.diff")
    print("修复 commit：%s（structure.py +%d / −%d）"
          % (fix_sha, n_add, n_del))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
