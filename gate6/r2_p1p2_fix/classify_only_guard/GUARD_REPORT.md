# classify-only 安全哨兵（`ICEX_CLASSIFY_ONLY`）—— 代码级拦截证明

> 对应 Reviewer 的有条件批准：**先物理切断 Parser 调用路径，再谈只分类探针**。
> 本轮只交付「切断」与「证明」，**没有启动服务、没有打开任何 PDF、没有调用 `classify_one()`**。

---

## 0. 一句话结论

`ICEX_CLASSIFY_ONLY=1` 时，`parse_pdf()` 的调用次数**恒为 0**。

不是靠调用方自觉，而是三层独立拦截，任一层生效即可：
**L1 路由层直接返回 `SAFETY_BLOCKED`（不调度 worker）→ L2 `_execute_parse()` 入口抛 `SafetyBlocked`（连 `run_id` 都不创建）→ L3 `parse_worker.py` 进程内自查，在 `import parser` 之前退出（exit 3）。**

验证：单元测试 5/5 PASS（含 1 个反向对照），静态验收 61/61 PASS，diff 可应用且逐字节还原。

---

## 1. 授权边界（本轮做了什么、没做什么）

| 项 | 状态 |
| --- | --- |
| 改动文件 | `workbench/serve_parser.py`、`workbench/parse_worker.py`（**仅 workbench 层**） |
| 新增文件 | `workbench/_guard/test_classify_only_guard.py`、`workbench/_guard/_diff/`（快照 + diff） |
| 冻结面 | `src/icpdf/parser/pipeline.py`、`src/icpdf/classification/`、`index.html` **未触碰**（`index.html` 哈希仍为 `76407504…`，静态验收 B-index PASS） |
| 是否启动服务 | **否** |
| 是否打开 PDF | **否** |
| 是否调用 `classify_one()` / `parse_pdf()` | **否**（单测中 `_run_child` 被替换为假结果，无真实子进程） |

---

## 2. 正交开关矩阵

`ICEX_CLASSIFY_ONLY` 与既有的 `ICEX_WORKBENCH_ALLOW_PARSE` **完全正交**，两者组合出的状态是显式的、无歧义的：

| `ALLOW_PARSE` | `CLASSIFY_ONLY` | 行为 | `parse_pdf()` 调用次数 |
| --- | --- | --- | --- |
| `0` | 任意 | 全部入口返回 `FROZEN`，**连请求体都不读** | 0 |
| `1` | `0` | 正常：分类 → 仅 `DATASHEET` 才解析 | 0 或 1（取决于分类） |
| `1` | `1` | **只分类**：分类结果照常返回，任何进入 Parser 的尝试都被拦截 | **恒为 0** |

第三行就是本次要批准探针使用的组合。注意它**不是**把 `ALLOW_PARSE=0` 换个名字——`ALLOW_PARSE=0` 连分类都不做，`CLASSIFY_ONLY=1` 是**分类照做、解析不做**。

---

## 3. 三层拦截：代码级证明

### L1-a：`api_parse` 在读请求体之前就拒绝

`serve_parser.py:978`（位于 `_receive_pdf()` 调用**之前**）

```python
async def api_parse(request: Request) -> JSONResponse:
    started = time.time()
    if not _allow_parse():
        return JSONResponse(_frozen_payload(PIPELINE_PARSER_ONLY))
    # /api/parse 是 Parser-only 入口：CLASSIFY_ONLY 下它没有存在意义，直接拒绝。
    # 不读请求体、不落盘、不启动 worker（否则会先上传再失败，留下无主副本）。
    if _classify_only():
        payload = _base_payload(PIPELINE_PARSER_ONLY, "SAFETY_BLOCKED")
        payload["document"] = None
        payload["parser"] = _parser_skipped(
            "SKIPPED",
            "ICEX_CLASSIFY_ONLY=1：/api/parse 为 Parser-only 入口，本模式下拒绝执行；"
            "未读取请求体、未落盘、未启动 worker")
        payload["diagnostics"] = {
            "reason": "只分类模式禁止任何 Parser 调用，包括 Parser-only 测试入口",
            "safety_blocked": True,
            "classify_only": True,
            "safety_guard_layer": "L1:api_parse",
            "parse_worker_started": False,
            "classifier_worker_started": False,
            "parse_pdf_calls": 0,
            "parser_call_count": 0,
        }
        return JSONResponse(payload)
    try:
        body, meta = await _receive_pdf(request, PIPELINE_PARSER_ONLY)
```

**为什么放在 `_receive_pdf()` 之前**：如果先落盘再拒绝，上传目录会留下无主副本（当前没有 TTL 回收，见父报告 §9.6）。拦截必须发生在**副作用之前**。

### L1-b：`api_process` 在 `decision == DATASHEET` 之后返回 `SAFETY_BLOCKED`

`serve_parser.py:1141`

```python
    # 只有 DATASHEET 才走到这里：classification 对象保留，parser.called 反映真实调用。
    # L1 拦截：CLASSIFY_ONLY 模式下到这里就返回，不调度 parse_worker、不建 Run 目录。
    if _classify_only():
        payload["status"] = "SAFETY_BLOCKED"
        payload["parser"] = _parser_skipped(
            "SKIPPED",
            "ICEX_CLASSIFY_ONLY=1：分类已完成（decision=%s），但 Parser 调用路径被"
            "哨兵物理切断；不启动 parse_worker、不创建 Run 目录" % decision)
        payload["diagnostics"] = dict(base_diag, **{
            "worker_kind": "classify",
            "gate_decision": decision,
            "safety_blocked": True,
            "classify_only": True,
            "safety_guard_layer": "L1:api_process",
            "evidence_pages": classification["evidence_pages"],
            "reason": ("只分类模式：分类结果如实返回，Parser 阶段被拦截。"
                       "这不是解析失败，是策略性拒绝执行。"),
        })
        return JSONResponse(payload)

    parsed = await _execute_parse(payload, pdf_path, meta, started)
```

**关键语义**：`classification` 对象**完整保留**。探针要看的正是分类结论（`decision` / `doc_type` / `evidence_pages` / 8 项白名单），这些字段一个不少；被切断的只有 `parser` 阶段。`status` 用 `SAFETY_BLOCKED` 而**不是** `PARSE_ERROR`——策略性拒绝不能被误读成技术故障。

### L2：`_execute_parse()` 入口抛异常（真正的安全边界）

`serve_parser.py:742`

```python
async def _execute_parse(payload: dict, pdf_path: Path, meta: dict,
                         started: float) -> dict:
    """..."""
    # L2 拦截：本函数是 parse_pdf() 的唯一上游，任何入口走到这里都被挡住。
    # 放在第一行，保证连 run_id 都不会被创建。
    if _classify_only():
        raise SafetyBlocked(
            "ICEX_CLASSIFY_ONLY=1：本进程禁止调用 parse_pdf()；"
            "拦截点=_execute_parse() 入口（未创建 run_id、未落 Run 目录、未启动 worker）")
    run_id = _new_id("G6A")
```

`serve_parser.py:203` 定义异常：

```python
class SafetyBlocked(RuntimeError):
    """CLASSIFY_ONLY 模式下试图进入 Parser：硬失败，绝不静默降级为「已解析」。"""
```

**为什么 L2 才是边界**：`_execute_parse` 是启动 `parse_worker` 的**唯一**函数（静态断言 S-18 强制此不变量）。L1 是两条已知路由上的「快路径」，L2 覆盖**所有**入口，包括将来新增的。选择 `raise` 而不是 `return`，是为了让「忘记处理返回值」的调用方直接炸掉，而不是拿到一个看起来正常的 dict 继续往下走。

### L3：`parse_worker.py` 进程内自救

`parse_worker.py:65`（位于 `parse_pdf` 的 import 之前）

```python
def _classify_only() -> bool:
    """只分类哨兵：与 serve_parser.py 中的同名函数保持同一语义与默认值。"""
    return os.getenv("ICEX_CLASSIFY_ONLY", "0") == "1"


def main(argv: list[str]) -> None:
    _stage("WORKER_STARTED")
    # L3 拦截：进程内自查。即使本 worker 被单独拉起（绕过 serve_parser.py 的
    # L1/L2），只要 ICEX_CLASSIFY_ONLY=1 就立刻退出，且**在 import parser 之前**，
    # 保证 parse_pdf() 连符号都不会被解析到。
    if _classify_only():
        _stage("SAFETY_BLOCKED")
        raise SafetyBlocked(
            "ICEX_CLASSIFY_ONLY=1：parse_worker 拒绝执行；parse_pdf() 未被调用")
    spec = json.loads(argv[1])
    ...
    from icpdf.parser.pipeline import parse_pdf   # 第 93 行，在拦截之后
```

`parse_worker.py:111`

```python
if __name__ == "__main__":
    try:
        main(sys.argv)
    except SafetyBlocked as exc:
        # 单独归类：父进程据此判 SAFETY_BLOCKED，而不是 PARSE_ERROR。
        _emit({
            "ok": False,
            "safety_blocked": True,
            "parser_call_entered": False,
            "error_type": "SafetyBlocked",
            "error": str(exc),
        })
        sys.exit(3)
```

**为什么 L3 不可省**：L1/L2 都在父进程里。如果 worker 被别的方式拉起（人工调试、未来的批处理脚本、CI 用例），父进程的检查形同虚设。L3 把判断搬进 worker 自己，并且刻意放在 `from icpdf.parser.pipeline import parse_pdf` **之前**——拦截生效时，`parse_pdf` 这个符号根本不会被加载进 `sys.modules`。单测用 `runpy` 直接拉起 worker，断言退出码为 3 且 `"icpdf.parser.pipeline" not in sys.modules`。

退出码用 **3** 而非 1，是为了与「普通异常」区分开：父进程据此把状态判成 `SAFETY_BLOCKED`，而不是 `PARSE_ERROR`（`serve_parser.py:788` 附近的 `elif worker_json.get("safety_blocked"):` 分支）。

---

## 4. 单元测试：5 个用例，含反向对照

文件：`_guard/test_classify_only_guard.py`（230 行）
运行：`py -3.13 -m pytest workbench/_guard/test_classify_only_guard.py -v`
结果：**5 passed**（日志见 `_pytest_guard.log`）

| # | 用例 | 注入 / 手法 | 断言 |
| --- | --- | --- | --- |
| 1 | `test_L2_execute_parse_raises_and_never_spawns_worker` | 直接调 `_execute_parse()` | 抛 `SafetyBlocked`；`_run_child` 调用 **0** 次；`_new_id` 调用 **0** 次 |
| 2 | `test_L1_api_process_forced_datasheet_returns_safety_blocked` | 假 stdout 强行注入「分类器自信判 `DATASHEET`」 | `decision == "DATASHEET"` **且** `doc_type == "DS_STRONG"`；但 `status == "SAFETY_BLOCKED"`；`parser.called == false`；`parse_pdf_calls == 0`；`parse_worker_started == false`；`_execute_parse` 调用 **0** 次 |
| 3 | `test_L1_api_parse_refused_in_classify_only` | 向 `/api/parse` 发真实 POST | `SAFETY_BLOCKED`；`safety_guard_layer == "L1:api_parse"`；`parse_pdf_calls == 0` |
| 4 | `test_L3_worker_refuses_and_never_imports_parser` | `runpy.run_path` 单独拉起 worker | 退出码 **3**；stdout 含 `[WORKER] SAFETY_BLOCKED`；`safety_blocked: true`；`icpdf.parser.pipeline` **未被 import** |
| 5 | `test_reverse_control_normal_mode_still_reaches_execute_parse` | **反向对照**：同一注入场景，`CLASSIFY_ONLY=0` | 必须走到 `_execute_parse`（`called == 1`） |

### 用例 2 是怎么「强行注入 DATASHEET」的

不 mock 分类器内部，而是替换 `_run_child`，直接返回一段伪造的 worker stdout——这段 stdout 声称分类器进入了、返回了 `route=IC_PARSE` / `doc_type=DS_STRONG` / `source_sha256` 与上传体一致 / `evidence_conflict=false`，足以通过 Workbench 的 8 项白名单和 `check_route_invariant`：

```python
async def _fake_run_child(script, spec, timeout):
    return {
        "start_failed": False, "timed_out": False, "returncode": 0,
        "stdout": _forced_datasheet_stdout(),   # 伪造的 DATASHEET 结论
        "stderr": "", "start_error": None,
        "stages": {
            "stages_seen": ["WORKER_STARTED", "CLASSIFIER_CALL_ENTERED",
                            "CLASSIFIER_CALL_RETURNED"],
            "worker_started_marker": True,
            "parser_call_entered": False, "parser_call_returned": False,
            "classifier_call_entered": True, "classifier_call_returned": True,
        },
    }
```

也就是说：**分类门禁被完全放开、分类结论是 DATASHEET**，这是最有利于「进入 Parser」的情形。在这个前提下，`status` 仍然是 `SAFETY_BLOCKED`、`parse_pdf_calls` 仍然是 0。这正是 Reviewer 要求证明的命题。

### 为什么还需要用例 5（反向对照）

一个「永远返回 SAFETY_BLOCKED」的实现也能让用例 1–4 全绿，但那样探针就永远拿不到分类结果，等于把哨兵做成了砖头。用例 5 在同一注入场景下把 `CLASSIFY_ONLY` 关掉，断言必须走到 `_execute_parse`——证明拦截是**条件性**的，不是无条件全拦。

### 关于「`parse_pdf()` 调用次数」的口径

`serve_parser.py` **从不 import `parse_pdf`**（静态断言 S-18 强制这一点），所以无法、也不需要去 mock `parse_pdf` 本身。这里的证明链是更强的形态：

> `parse_pdf` 只能由 `parse_worker.py` 子进程执行 → 拉起该 worker 的唯一函数是 `_execute_parse` → `_execute_parse` 第一行就抛异常 → 因此 `parse_pdf` 不可能被调用。

再叠加 L3：即使 worker 被绕过父进程拉起，它也在 `import parse_pdf` 之前退出。

---

## 5. 静态验收：61/61 PASS（新增 S-11 ~ S-18）

脚本 `_verify_p1p2_static.py` 从 53 项扩到 **61** 项，新增 8 条全部用 **AST 判定**（防止注释或文档字符串里出现关键字就被算作通过）：

| ID | 断言 | 结果 |
| --- | --- | --- |
| S-11 | `ICEX_CLASSIFY_ONLY` 默认关闭，serve 与 worker 两处一致 | PASS |
| S-12 | **L2**：`_execute_parse()` 第一条可执行语句即抛 `SafetyBlocked` | PASS |
| S-13 | **L2** 拦截先于 `run_id` 创建（连 Run 目录都不会建） | PASS |
| S-14 | **L1**：`api_process` 在调用 `_execute_parse` 之前返回 `SAFETY_BLOCKED` | PASS |
| S-15 | **L1**：`api_parse` 在读请求体之前就拒绝 | PASS |
| S-16 | **L3**：worker 自查位于 `import parser` 之前 | PASS |
| S-17 | **L3**：被拦截时 emit `parser_call_entered=False` 并以 3 退出 | PASS |
| S-18 | `parse_worker` 启动点唯一位于 `_execute_parse`（L2 覆盖全部入口） | PASS |

### 一处需要说明的判据变更：G-03

`G-03`（`/api/parse` 处理器不引用分类器）原先用朴素子串匹配 `"classif" not in parse_src.lower()`。本轮 L1-a 新增的诊断键 `"classifier_worker_started": False` 触发了它——但这个键的语义恰恰是**断言分类器没有启动**，属于误报。

处理方式：把 G-03 升级为 **AST 级**，只统计真实的符号引用（`ast.Name` / `ast.Attribute` 且名字含 `classif`），并豁免哨兵本身 `_classify_only`。**这是严格更强的判据**——字符串字面量不可能调用任何东西，旧写法会同时产生误报（本例）和漏报（比如 `getattr(mod, "classify_one")` 这类动态调用）。

---

## 6. diff 自验证

`_diff/CLASSIFY_ONLY_GUARD.diff`（168 行）覆盖两个文件、9 个补丁点。

| 验证项 | 方法 | 结果 |
| --- | --- | --- |
| 可应用 | 在 `pre_guard/` 快照副本上 `git apply -p1` | `Applied patch ... cleanly`（两文件） |
| 逐字节还原 | `cmp` 应用结果 vs 工作区现文件 | **BYTE-IDENTICAL**（两文件） |

哈希对照：

| 文件 | guard 前 | guard 后 |
| --- | --- | --- |
| `serve_parser.py` | `32d06672…f18f83` | `05b9885a…c2a41a` |
| `parse_worker.py` | `4fb0e1e5…75d380` | `5c599e77…6433f3` |

> **复现时的一个坑**：如果在 Git 仓库**之外**应用这个 diff，全局 `core.autocrlf=true` 会把结果写成 CRLF，导致 `sha256sum` 对不上（差 1201 字节 = 1201 行）。复现请用：
> `git -c core.autocrlf=false apply -p1 CLASSIFY_ONLY_GUARD.diff`

---

## 7. 已知局限（请 Reviewer 一并评估）

这几条不影响本次「只分类探针」的安全性，但必须写清楚，避免哨兵被当成比它实际更强的保证：

1. **哨兵保护的是 Workbench 服务路径，不是 Python 解释器。**
   若有人直接 `python -c "from icpdf.parser.pipeline import parse_pdf; ..."`，三层都不生效——但那时已经绕开 Workbench 了，不在本机制的责任范围内。

2. **`_classify_only()` 每次调用都读环境变量**，因此运行期修改进程环境会实时改变行为。
   Windows 上外部进程无法改写他人环境块，实际风险可忽略；但同进程内的代码可以（单测正是利用这一点注入的）。

3. **L1 是快路径，L2 才是边界。**
   若将来新增入口并直接调 `_execute_parse`，L1 会漏、L2 兜住。S-18 就是为守住这个不变量而设的——一旦有人绕过，静态验收会红。

4. **`parse_pdf_calls=0` 的语义是「确实没调用」**，不是「统计失败」。
   `SAFETY_BLOCKED` 与 `PARSE_ERROR` / `WORKER_START_FAILED` 是三个互斥状态，不应混淆。

5. **端到端行为尚未验证。**
   本轮按授权未启动服务。真实进程下「环境变量注入 → 分类完成 → L1 拦截」的完整链路，属于下一步探针要覆盖的内容。

---

## 8. 文件清单

| 文件 | 说明 |
| --- | --- |
| `GUARD_REPORT.md` | 本文件 |
| `CLASSIFY_ONLY_GUARD.diff` | 统一 diff（168 行，2 文件 / 9 补丁点） |
| `pre_guard/serve_parser.py` | guard 前快照（`32d06672…`），用于复现 diff |
| `pre_guard/parse_worker.py` | guard 前快照（`4fb0e1e5…`） |
| `serve_parser.py` | guard 后全文（`05b9885a…`） |
| `parse_worker.py` | guard 后全文（`5c599e77…`） |
| `test_classify_only_guard.py` | 5 个用例的极简单测 |
| `_verify_p1p2_static.py` | 静态验收脚本（61 项，含 S-11~S-18） |
| `_pytest_guard.log` | 单测原始输出（5 passed） |
| `_p1p2_static_verify_guard.log` | 静态验收原始输出（61/61 PASS） |
| `SHA256SUMS.txt` | 本目录文件校验和 |

> 父目录 `gate6/r2_p1p2_fix/` 的 `SHA256SUMS.txt` **保持不变**——它描述的是 Reviewer 已审阅的冻结快照。本目录是**增量**，自带 manifest。

---

## 9. 下一步（等待 Reviewer 点头后执行）

用新开关启动服务，跑两份真 EVM 负样本的**只分类**探针：

```bash
ICEX_WORKBENCH_ALLOW_PARSE=1 ICEX_CLASSIFY_ONLY=1 \
  py -3.13 workbench/serve_parser.py
```

样本（已由 `doc_verify` 轮确认为真 EVM 文档）：

| 代号 | 文件 | SHA256 前缀 | 页数 |
| --- | --- | --- | --- |
| A | `ADC08060EVM__slau715a.pdf` | `09fabc24…` | 20 |
| B | `BQ25570EVM-206__sluuaa7a.pdf` | `60aac1d0…` | 24 |

判定标准：

- 期望两份都返回 `NON_DATASHEET` → 说明分类门禁对真 EVM 有效，Pre-Parse Gate 成立；
- 若返回 `DATASHEET`，则 `status` 必为 `SAFETY_BLOCKED`、`parse_pdf_calls` 必为 0——**探针不会解析任何东西**，只是把分类器的判断暴露出来；
- 无论结果如何，跑完立即停服并恢复 `ALLOW_PARSE=0` 冻结态。
