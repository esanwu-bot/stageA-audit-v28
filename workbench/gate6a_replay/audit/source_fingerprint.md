# 主仓源码指纹：`_monotonic_lattice` 与 Parser commit

> 审计包不含 `src/` 源码树。本文件给出的是一处**被审改动**的字节指纹与完整 diff，目的是让拿到本包的人能独立核对「审计包声称的夹紧公式」与「真实落地的代码」是否一致。

## 0. 先说一条边界（不是补充说明，是前提）

`artifacts/v2_env_snapshot.json` 记录的回测时 commit 是 `a11131a`，且 `dirty_files` 有 **199** 项。
也就是说：**v2 那次复跑跑在「修复已写好但还没提交」的工作树上**，不是跑在一个干净的 commit 上。

所以「回测当时跑的到底是哪份字节」这件事，不能只靠一句 commit SHA 打发。本包用三条互相独立的线索钉住它：

1. 基线 commit `a11131a` 的 `structure.py` blob 指纹（修复前）；
2. 修复 commit `bede1f5` 的 diff（修复内容，逐行可核）；
3. 产物侧哈希链：`parser_outputs_sha256_gate6a_replay_v2_postfix.csv` 记录了回测产出的 192 个 JSON 的 sha256，`parser_json_immutability_gate6a_replay_v2_postfix.txt` 证明评估器没改它们。

把 (1)+(2) 施加到同一份文件上，应当得到 (3) 所对应的产物；反之，任何一处不符都会露馅。

## 1. 三个 commit 上的 `structure.py` 指纹

| 角色 | commit | 说明 | `structure.py` git blob (SHA-1) | 内容 sha256（LF） |
| --- | --- | --- | --- | --- |
| v2 回测时快照记录的 commit | `a11131a` | 回测在它之上、带着未提交的修复改动运行 | `fd3ce1607c21…` | `23b4cd8b926e66e5978a3667da9f6d9418c9ffef45ba4f68e95ac63f2b49c3f4` |
| V256 夹紧修复落地 | `bede1f5` | structure.py +47 / −2，新增 _monotonic_lattice 与 lattice_adjusted | `39280973ed1b…` | `1e75279f9e408127051a54dfa240c14db063471306a3218767703768489952aa` |
| 当前审计分支 HEAD | `62bfc3d` | 未改动 src/，structure.py 与修复落地时逐字节相同 | `39280973ed1b…` | `1e75279f9e408127051a54dfa240c14db063471306a3218767703768489952aa` |

完整哈希：

```
a11131a80474f3d5bea5ab6fb5204e77b8839eed  v2 回测时快照记录的 commit
    subject : Gate 6A Batch 2：24 行 Gold 并入 main（Reviewer 已批准）
    blob    : fd3ce1607c21ea9edbcebad032ca81a8bc3e6203
    sha256  : 23b4cd8b926e66e5978a3667da9f6d9418c9ffef45ba4f68e95ac63f2b49c3f4
bede1f581945331fa0f213a8be5d1171601639ae  V256 夹紧修复落地
    subject : Gate 6A 审计证据包：…… V256 崩溃修复与复跑
    blob    : 39280973ed1bb950b64c65da188abb47d47e7942
    sha256  : 1e75279f9e408127051a54dfa240c14db063471306a3218767703768489952aa
62bfc3d829104278b730f68954dd1c5f8c16c64d  当前审计分支 HEAD
    subject : 审计包提交
    blob    : 39280973ed1bb950b64c65da188abb47d47e7942
    sha256  : 1e75279f9e408127051a54dfa240c14db063471306a3218767703768489952aa
```

`bede1f5` 与当前 HEAD 的 blob 完全相同（`39280973ed1b…`），说明修复落地之后再没有动过解析器 —— 后续提交只增加审计材料。

## 2. 行尾陷阱：为什么不能对工作区文件算 sha256

| 事实 | 值 |
| --- | --- |
| `core.autocrlf` | `true` |
| 工作区 `structure.py` 的行尾 | CRLF **741** 个 / 裸 LF **0** 个 |
| 工作区文件 sha256 | `5ce20999d3de6f76b1a725d6a9c21c4746a804a81aecede66846adb15fa8cb53` |
| git blob 内容 sha256 | `1e75279f9e408127051a54dfa240c14db063471306a3218767703768489952aa` |

两个值不一样，**不是文件被改过**，而是 `autocrlf` 在检出时把 LF 换成了 CRLF。所以本文件一律以 git blob 字节为准。复核时请用：

```bash
git cat-file blob bede1f5:src/icpdf/parser/structure.py | sha256sum
# 期望：1e75279f9e408127051a54dfa240c14db063471306a3218767703768489952aa
```

## 3. 落地的改动（完整 diff）

`bede1f5` 对 `src/icpdf/parser/structure.py` 的差异，只此一个文件：

```
 src/icpdf/parser/structure.py | 49 +++++++++++++++++++++++++++++++++++++++++--
 1 file changed, 47 insertions(+), 2 deletions(-)
```

完整 diff 见 [`monotonic_lattice.diff`](monotonic_lattice.diff)。

核心函数（diff 中的新增部分，逐字摘录）：

```python
MIN_ROW_GAP_PT = 0.2


def _monotonic_lattice(ys: list[float], lo: float, hi: float
                       ) -> tuple[list[float], bool]:
    n = len(ys)
    if n < 2:
        return list(ys), False
    gap = min(MIN_ROW_GAP_PT, (hi - lo) / (n - 1))
    out = [ys[0]]
    adjusted = False
    for value in ys[1:]:
        floor = out[-1] + gap
        if value < floor:
            out.append(floor)
            adjusted = True
        else:
            out.append(value)
    return out, adjusted
```

与 `v256_crash_evidence.md` §2 的公式逐字对应：

- `gap = min(MIN_ROW_GAP_PT, (hi - lo) / (n - 1))` —— 与文档一致；
- `floor = out[-1] + gap`，`if value < floor: out.append(floor)` —— **只上推、不下拉**，与「不排序、不重排行」一致；
- 返回 `adjusted` 由 `TableGrid.lattice_adjusted` 承载，`_status()` 据此降级 `PARTIAL` —— 与 §7 的「下游不读 status」互补：标记在上游产生，下游不改判。

## 4. 复核清单

拿到本包的人可以这样独立核对，不需要 CodeUp 访问权：

```bash
# 1. 本包内的 diff 与文档公式是否一致
grep -nE '^\+.*(gap = min|floor = out)' monotonic_lattice.diff

# 2. **新增行**里是否出现过排序（不得把行重排）
grep -nE '^\+.*sort' monotonic_lattice.diff    # 期望：无输出

# 3. **新增行**里是否出现过下拉（不得把合法格线拉下来）
grep -nE '^\+.*out\[-1\] *-' monotonic_lattice.diff    # 期望：无输出

# 4. 产物侧：192 个 JSON 的哈希
head -3 parser_outputs_sha256_gate6a_replay_v2_postfix.csv
```

第 2、3 条刻意只查**新增行**（`^\+`）：diff 里有一行未改动的上下文 `cells.sort(key=lambda cell: (cell.row, cell.column))`，那是给单元格按 (行, 列) 定序，与「重排行格线」无关；把它一并算进来会误判，所以断言必须锚在新增行上。

这次修复最关键的两个不变式就是：**不排序**（否则行序失效、`GridCell.row` 与 `cell_words` 索引全部错位）、**只上推**（否则会把合法格线拉下来，制造新的倒序）。
