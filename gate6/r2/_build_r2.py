#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gate 6 第二轮交付件生成器（只读，不实现代码、不建库、不跑解析）。

职责：
1. 从 gate6/FIELD_MAPPING.csv 生成可读全量表 FIELD_MAPPING_FULL.md；
2. 生成逐项审查矩阵 FIELD_MAPPING_REVIEW.csv（六维判定 + 待批默认值）；
3. 生成 Git 基线冻结清单 BASELINE_FREEZE.csv 与隔离统计；
4. 生成 ROUND2_VERIFY.json 与 SHA256SUMS.txt。
"""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path("E:/workspace/icpdf-extractor")
STAGE = ROOT / "runs" / "stage_a_350"
G6 = STAGE / "gate6"
OUT = STAGE / "gate6_r2"

# 六维判定编码。每行与 FIELD_MAPPING.csv 的数据行严格一一对应。
# 字段顺序：one_to_one, unit_rule, min_typ_max, package_dimension,
#           evidence_isolation, default_or_implicit_conversion, focus
REVIEW = [
    ("1:1_VERBATIM", "N/A", "N/A", "N/A", "MUST_RECOMPUTE_SHA", "NONE",
     "哈希必须由 source.pdf 重算，清单字符串不得直接采信"),
    ("1:1_VERBATIM", "N/A", "N/A", "N/A", "N/A", "EXPLICIT_DEFAULT_PENDING_APPROVAL",
     "requested_mpn 是调用方事实；默认值来源需在验收前指定"),
    ("1:1_CONDITIONAL", "N/A", "N/A", "N/A", "IDENTITY_EVIDENCE_REQUIRED", "EXPLICIT_DEFAULT_PENDING_APPROVAL",
     "normalized_mpn 默认等于 requested_mpn 属显式默认，待批"),
    ("1:1_CONDITIONAL", "N/A", "N/A", "N/A", "UNRESOLVED_IF_MISSING", "NONE",
     "厂商名须页码+原文证据，否则留观察区"),
    ("QUARANTINE", "N/A", "N/A", "N/A", "QUARANTINE_ONLY", "NONE",
     "自由分类文本无 Domain 字段，不进 formal 容器"),
    ("QUARANTINE", "N/A", "N/A", "N/A", "QUARANTINE_ONLY", "NONE", "同上"),
    ("QUARANTINE", "N/A", "N/A", "N/A", "QUARANTINE_ONLY", "NONE", "描述文案不得当参数或证据"),
    ("QUARANTINE", "N/A", "N/A", "N/A", "UNRESOLVED_IF_MISSING", "NONE",
     "空 URL 是 P1 溯源缺陷，禁止补猜测值"),
    ("N:1_ENUM", "N/A", "N/A", "N/A", "UNRESOLVED_IF_MISSING", "EXPLICIT_ENUM_PENDING_APPROVAL",
     "device/board/onboard_device/unknown 枚举映射规则待批"),
    ("NONE_NO_MAP", "N/A", "N/A", "N/A", "N/A", "NONE", "置信度分数完全不映射"),
    ("1:1_CONDITIONAL", "N/A", "N/A", "N/A", "MUST_BIND_PAGE_AND_RAW_TEXT", "NONE",
     "缺 kind/page_number/raw_text 不得构造 IdentityEvidence"),
    ("1:1_VERBATIM", "N/A", "N/A", "N/A", "MUST_BIND_CELL", "NONE",
     "原文参数名保留，同义归一只是提示不是 canonical id"),
    ("1:1_VERBATIM", "PRESERVE_VERBATIM", "NOT_SPLIT_KEEP_VALUE", "PRESERVE_IN_CONDITIONS",
     "MUST_BIND_CELL", "NO_IMPLICIT_COERCION", "禁止 5V→5、±2000→2000、范围折叠"),
    ("1:1_VERBATIM", "PRESERVE_VERBATIM", "N/A", "N/A", "MUST_BIND_CELL", "NO_IMPLICIT_COERCION",
     "单位分列保留，禁止合并后丢单位"),
    ("1:1_VERBATIM", "PRESERVE_VERBATIM", "N/A", "PRESERVE_IN_CONDITIONS", "MUST_BIND_CELL", "NONE",
     "条件须与数值同源同行"),
    ("GAP_FROM_CANDIDATES", "FROM_CANDIDATE_CELL_ONLY", "FROM_BOUND_CELLS_ONLY", "PRESERVE_IN_CONDITIONS",
     "MUST_BIND_CELL", "NO_BACK_PARSE", "不得从塌缩 value 反推 MIN/TYP/MAX"),
    ("GAP_FROM_CANDIDATES", "N/A", "N/A", "N/A", "MUST_BIND_CELL", "NO_FABRICATION",
     "table_id 必填；反查不到即 UNRESOLVED"),
    ("GAP_FROM_CANDIDATES", "N/A", "N/A", "N/A", "MUST_BIND_CELL", "NO_FABRICATION",
     "evidence_ids 不得用选页列表冒充"),
    ("1:1_ENUM", "N/A", "N/A", "N/A", "FORMAL_GATE", "EXPLICIT_DEFAULT_PENDING_APPROVAL",
     "旧行一律 UNRESOLVED 是显式默认，待批"),
    ("1:1_VERBATIM", "N/A", "N/A", "N/A", "FORMAL_GATE", "NONE", "unresolved_reason 不得为空"),
    ("1:N_EXPAND", "PRESERVE_VERBATIM", "NOT_SPLIT_KEEP_VALUE", "EXPAND_PER_VARIANT",
     "MUST_BIND_CELL", "NONE", "多封装列逐列展开，禁止只抽第一列"),
    ("GAP_FROM_CANDIDATES", "N/A", "N/A", "N/A", "UNRESOLVED_IF_MISSING", "NO_FABRICATION",
     "requested_mpn 不得冒充已证明的适用型号"),
    ("GATED_CONTAINER", "N/A", "N/A", "N/A", "FORMAL_GATE", "NONE",
     "formal 容器接收范围 {verified,audited}，需评审确认"),
    ("1:1_ENUM", "PRESERVE_VERBATIM", "NOT_SPLIT_KEEP_VALUE", "PRESERVE_IN_CONDITIONS",
     "MUST_BIND_CELL", "EXPLICIT_ENUM_PENDING_APPROVAL", "ABSOLUTE_MAXIMUM 分类规则待批"),
    ("1:1_ENUM", "PRESERVE_VERBATIM", "NOT_SPLIT_KEEP_VALUE", "PRESERVE_IN_CONDITIONS",
     "MUST_BIND_CELL", "EXPLICIT_ENUM_PENDING_APPROVAL", "THERMAL 分类与 Rθ 同义归并待批"),
    ("QUARANTINE", "PRESERVE_VERBATIM", "N/A", "N/A", "QUARANTINE_ONLY", "EXPLICIT_ENUM_PENDING_APPROVAL",
     "ParameterCategory 无 ESD，是否扩枚举需契约升级评审"),
    ("1:1_VERBATIM", "PRESERVE_VERBATIM", "N/A", "PRESERVE_STRING", "MUST_BIND_CELL", "NONE",
     "封装名保留字符串，不转代码"),
    ("QUARANTINE", "N/A", "N/A", "NO_PACKAGE_MODEL", "QUARANTINE_ONLY", "NONE", "Domain 无 Pin 模型"),
    ("QUARANTINE", "PRESERVE_VERBATIM", "N/A", "N/A", "QUARANTINE_ONLY", "NONE", "尺寸文本不进参数容器"),
    ("QUARANTINE", "PRESERVE_VERBATIM", "NOT_SPLIT_KEEP_VALUE", "N/A", "QUARANTINE_ONLY",
     "EXPLICIT_ENUM_PENDING_APPROVAL", "温度范围分类 OTHER/THERMAL 未定"),
    ("QUARANTINE", "PRESERVE_VERBATIM", "N/A", "N/A", "QUARANTINE_ONLY", "NONE", "与 operating 不得混用"),
    ("N:1_ENUM", "N/A", "N/A", "N/A", "UNRESOLVED_IF_MISSING", "EXPLICIT_ENUM_PENDING_APPROVAL",
     "与第 9 行须同一套确定性规则，避免双规则"),
    ("QUARANTINE", "N/A", "N/A", "NO_PACKAGE_MODEL", "QUARANTINE_ONLY", "NONE",
     "Domain 无 Pin/Pinout 模型；pin 号不得写进参数值或伪造模型"),
    ("1:N_CONDITIONAL", "N/A", "N/A", "EXPAND_PER_VARIANT", "MUST_BIND_CELL", "NONE",
     "多型号逐型号展开，仅在有证据时作 applicable_mpn 来源"),
    ("QUARANTINE", "N/A", "N/A", "N/A", "QUARANTINE_ONLY", "NONE", "替代料号不属于新契约"),
    ("QUARANTINE", "N/A", "N/A", "N/A", "QUARANTINE_ONLY", "NONE", "文案数值不得当参数来源"),
    ("NONE_NO_MAP", "N/A", "N/A", "N/A", "NO_FABRICATION", "NONE", "选页集合不是来源页码"),
    ("NONE_NO_MAP", "N/A", "N/A", "N/A", "NO_FABRICATION", "NONE", "NONE 是分类器证据页状态"),
    ("NONE_NO_MAP", "N/A", "N/A", "N/A", "N/A", "NONE", "置信度不映射、不参与判定"),
    ("GAP_FILL", "N/A", "N/A", "N/A", "N/A", "NO_FABRICATION", "须记录真实模型名，不得硬编码"),
    ("GAP_FILL", "N/A", "N/A", "N/A", "N/A", "NO_FABRICATION", "新链须有自己的 prompt_version"),
    ("QUARANTINE", "N/A", "N/A", "N/A", "QUARANTINE_ONLY", "NO_IMPLICIT_COERCION",
     "旧时间戳不得覆盖 Document.created_at"),
    ("QUARANTINE", "N/A", "N/A", "N/A", "QUARANTINE_ONLY", "NONE", "QC 留痕不等于 Schema 校验通过"),
    ("1:1_ENUM", "N/A", "N/A", "N/A", "UNRESOLVED_IF_MISSING", "EXPLICIT_DEFAULT_PENDING_APPROVAL",
     "空串→None + UNRESOLVED 是显式判定，待批"),
    ("1:1_ENUM", "PRESERVE_VERBATIM", "N/A", "N/A", "UNRESOLVED_IF_MISSING", "EXPLICIT_DEFAULT_PENDING_APPROVAL",
     "占位符→UNRESOLVED 是显式判定，待批"),
    ("1:1_ENUM", "N/A", "N/A", "N/A", "UNRESOLVED_IF_MISSING", "EXPLICIT_DEFAULT_PENDING_APPROVAL",
     "缺 key 与空串/占位符必须区分，待批"),
]

REVIEW_HEADER = [
    "row_no", "legacy_field", "domain_target", "one_to_one", "unit_rule",
    "min_typ_max", "package_dimension", "evidence_isolation",
    "default_or_implicit_conversion", "needs_reviewer_approval", "reviewer_focus",
]


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*args: str) -> str:
    # 不能 strip()：git status --short 的第一列是状态位，" M path" 的前导空格
    # 是有效语义，strip 会把已跟踪修改误判成未跟踪/丢失。
    return subprocess.run(["git", *args], cwd=str(ROOT), stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, check=False).stdout.rstrip("\n")


def build_mapping() -> tuple[list[list[str]], list[list[str]]]:
    with (G6 / "FIELD_MAPPING.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    header, data = rows[0], rows[1:]
    assert len(data) == 46, len(data)
    assert all(len(r) == 7 for r in data)
    assert len(REVIEW) == len(data), (len(REVIEW), len(data))

    md = [
        "# FIELD_MAPPING.csv 完整 46 行内容与逐项审查矩阵",
        "",
        "来源：`gate6/FIELD_MAPPING.csv`（Gate 6 第一轮交付，未修改）。",
        "本文件由 `_build_r2.py` 从该 CSV **逐行原样生成**，不含人工改写，",
        "用于解决「46 行 × 7 列只能证明规模、不能证明映射正确」的问题。",
        "",
        "**证据边界**：以下全部是**设计稿**，不是已实现代码；逐项判定是提交方自审，",
        "不等于 Reviewer 已核准。`FIELD_MAPPING_REVIEW.csv` 给出六维逐行判定与待批项。",
        "",
        "## 一、原文件完整性",
        "",
        "| 项 | 值 |",
        "| --- | --- |",
        "| 路径 | `runs/stage_a_350/gate6/FIELD_MAPPING.csv` |",
        "| SHA-256 | `%s` |" % sha256_file(G6 / "FIELD_MAPPING.csv"),
        "| 数据行 | 46 |",
        "| 列数 | 7（每行一致，已逐行校验） |",
        "| BOM | 无 |",
        "| 字段 | %s |" % " / ".join("`%s`" % h for h in header),
        "",
        "## 二、46 行完整内容（原样）",
        "",
        "| # | legacy_field | legacy_example | domain_target | mapping_rule | forbidden_action | risk | verdict |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for i, r in enumerate(data, 1):
        cells = [str(i)] + [c.replace("|", "\\|").replace("\n", " ") for c in r]
        md.append("| " + " | ".join(cells) + " |")

    md += [
        "",
        "## 三、Reviewer 六项重点的逐行判定",
        "",
        "机器可读版见 `FIELD_MAPPING_REVIEW.csv`（46 行，与本节一一对应）。",
        "",
        "### 3.1 源字段与目标字段是否一一对应",
        "",
        "- `1:1_VERBATIM`：逐字映射，不改写。",
        "- `1:1_CONDITIONAL`：一对一但需证据条件成立。",
        "- `1:1_ENUM`：一对一但需枚举/状态判定，**规则待批**。",
        "- `1:N_EXPAND` / `1:N_CONDITIONAL`：一行拆多行（多封装/多型号）。",
        "- `N:1_ENUM`：多行归并到一个枚举字段，须共用同一套确定性规则。",
        "- `GAP_FROM_CANDIDATES`：旧输出缺该字段，须由 `candidates.json` 绑定单元格反查，**不得凭空生成**。",
        "- `GATED_CONTAINER` / `GAP_FILL` / `QUARANTINE` / `NONE_NO_MAP`：不进 formal 容器。",
        "",
        "### 3.2 单位转换规则",
        "",
        "**本设计不做单位换算**，只做原文保留：",
        "",
        "- R-U1：`value` 与 `unit` 在旧输出中已分列 → 分别写入 `Parameter.value` / `Parameter.unit`，不得合并。",
        "- R-U2：出现 `\"5V\"` 这类合并串 → 整串保留到 `value`，`unit=None`，",
        "  并标记 `unit_normalization_required` 进 `unresolved_reason`；**禁止**转成数字 5 丢掉 V。",
        "- R-U3：`±2000`、`-40°C to 85°C`、`0 to 0.55` 等符号/范围原样保留，不做浮点化。",
        "- R-U4：`unit` 本身是字符串，`µA` / `°C/W` / `dBFS/Hz` 不得归一化成 `uA` / `C/W`。",
        "- R-U5：若未来要引入单位换算表，须作为**独立契约版本**提交审批；本轮不含任何换算表。",
        "",
        "### 3.3 MIN/TYP/MAX 是否独立保留",
        "",
        "- Domain 有独立 `min` / `typ` / `max`（`str | None`）。",
        "- 旧链在 `ELEC_RULES_V3` 下把三列塌缩进单个 `value`（如 `\"2.0 to 3.6\"`），",
        "  并在 `condition` 追加 `; min=..., max=...`。**禁止**从塌缩串反推三列。",
        "- 三列唯一合法来源是 `candidates.json` 中 `column_role = min/typ/max` 的绑定单元格；",
        "  取不到就只保留 `value` 原串，并在 `conditions` 留痕，三列留 `None`。",
        "- 第 16 行即该规则；该规则**待 Reviewer 批准**，未批准前不得实现。",
        "",
        "### 3.4 多封装参数保持封装维度",
        "",
        "- 旧 `condition` 含 `New Chip; DCY (SOT-223) 4 PINS` 等变体文字。",
        "- 每个 `(name, package, applicable_mpn, table_id, conditions)` 组合生成独立 `Parameter`，",
        "  `parameter_id` 唯一；`Parameter.package` 另存封装字符串。",
        "- 禁止把多列压成一行、禁止只抽第一列；同参数不同封装不是重复行。",
        "- 第 21 行 `EXPAND_PER_VARIANT`、第 34 行 `1:N_CONDITIONAL` 覆盖该维度。",
        "",
        "### 3.5 Evidence 缺失时是否明确进入隔离状态",
        "",
        "- 旧输出无 `table_id` / `bbox` / 单元格原文，故**所有旧参数行默认 `UNRESOLVED`**。",
        "- `UNRESOLVED` 必须带 `unresolved_reason`；`FormalParameterSet` 构造期拒绝非 formal 状态。",
        "- 证据不足的行写入设想的 `parameters_unresolved.json`（**设计，未实现**），",
        "  不进 formal 容器；不得用 `selected_pages`、`evidence_page_no=NONE`、",
        "  `identity_confidence`、`metadata.confidence` 充当证据。",
        "- 第 17/18/22/23 行是主要闸门；第 37/38/39 行明确禁止三类伪证据。",
        "",
        "### 3.6 未经批准的默认值或隐式转换（如实列出，不声明为零）",
        "",
        "本设计**存在显式默认值**，全部标为 `needs_reviewer_approval=YES`，未经批准不得实现：",
        "",
        "| 编号 | 默认值 / 判定 | 涉及行 | 风险 |",
        "| --- | --- | --- | --- |",
        "| D-01 | `normalized_mpn = requested_mpn` | 3 | 若无身份证据，会把请求值当观测值 |",
        "| D-02 | 旧参数行一律 `UNRESOLVED` | 19, 44, 45, 46 | 保守但需确认不会掩盖可验证行 |",
        "| D-03 | 空串 → `None` + `UNRESOLVED` | 44 | 空串与占位符语义差异需确认 |",
        "| D-04 | 占位符 → `UNRESOLVED` + `source_cell_placeholder` | 45 | 同上 |",
        "| D-05 | 缺 key → `UNRESOLVED` + `legacy_key_missing` | 46 | 同上 |",
        "| D-06 | 类别枚举 `ELECTRICAL/ABSOLUTE_MAXIMUM/THERMAL/OTHER` | 24, 25, 30, 32 | 枚举归属需评审 |",
        "| D-07 | `identity_scope` 的 device/board/onboard_device/unknown 规则 | 9, 32 | 须单一规则源 |",
        "| D-08 | `FormalParameterSet` 只接收 `{verified, audited}` | 23 | 沿用 Domain 现有定义，需确认 |",
        "| D-09 | `requested_mpn` 的取值来源 | 2 | 须指定来自清单/驱动哪个字段 |",
        "| D-10 | ESD / Pin / Ordering / SEO 全部进 `unmapped_legacy` | 26, 28, 33, 36 等 | 不扩枚举、不临时造模型 |",
        "",
        "**不存在**的隐式转换（明确保证）：无单位换算、无字符串转数值、无范围折叠、",
        "无占位符转 0/None、无页码推测、无 candidate_id/table_id 编造、无置信度转状态。",
        "",
        "## 四、本轮不做什么",
        "",
        "- 不修改 `FIELD_MAPPING.csv`（保持 Gate 6 第一轮字节不变）。",
        "- 不实现任何映射代码、不写 `legacy_adapter.py`、不改 Domain 模型。",
        "- 不把本节判定称为「已通过审核」；待 Reviewer 逐项给出关闭条件。",
    ]

    review_rows = []
    for i, (r, rev) in enumerate(zip(data, REVIEW), 1):
        review_rows.append([
            str(i), r[0], r[2], rev[0], rev[1], rev[2], rev[3], rev[4], rev[5],
            "YES" if rev[5].startswith("EXPLICIT_") else "NO", rev[6],
        ])
    return md, review_rows


def build_freeze() -> tuple[list[list[str]], dict]:
    head = git("rev-parse", "HEAD")
    branch = git("branch", "--show-current")
    remote = git("remote", "get-url", "origin")
    tracked = git("ls-files").splitlines()
    status = git("status", "--short").splitlines()  # 原样（含 git 引号转义），供报告展示
    status_plain = git("-c", "core.quotePath=false", "status", "--short").splitlines()
    others = git("-c", "core.quotePath=false", "ls-files", "--others",
                 "--exclude-standard").splitlines()
    rows = [["category", "path", "bytes", "sha256", "note"]]

    # B 类：已跟踪且工作区修改
    modified = [l[3:].strip('"') for l in status_plain if l.startswith(" M ")]
    for p in modified:
        f = ROOT / p
        rows.append(["B_TRACKED_MODIFIED", p, str(f.stat().st_size),
                     sha256_file(f), "不得混入正式代码提交；HEAD 版本另记"])
    head_cli = subprocess.run(["git", "show", "HEAD:src/icpdf/cli.py"], cwd=str(ROOT),
                              stdout=subprocess.PIPE, check=False).stdout  # 原始字节，不经文本换行转换
    rows.append(["A_HEAD_REFERENCE", "HEAD:src/icpdf/cli.py", str(len(head_cli)),
                 hashlib.sha256(head_cli).hexdigest(), "HEAD 基线版本哈希，用于对比"])

    # C/D 类：未跟踪文件
    c_prefixes = ("src/icpdf/classification/", "tools/stage_a/", "tools/stage_b/",
                  "tests/unit/test_classification_")
    for p in others:
        f = ROOT / p
        if not f.is_file():
            continue
        cat = "C_UNTRACKED_SOURCE" if p.startswith(c_prefixes) else "D_UNTRACKED_AUDIT_MATERIAL"
        rows.append([cat, p, str(f.stat().st_size), sha256_file(f),
                     "待单独评审后单独提交" if cat.startswith("C_") else "审计/文档材料，不得进代码提交"])

    info = {
        "branch": branch, "head": head, "remote": remote,
        "tracked_file_count": len(tracked),
        "status_entry_count": len(status),
        "status_short": status,
        "tracked_modified": modified,
        "untracked_file_count": len([r for r in rows if r[0].startswith(("C_", "D_"))]),
        "runs_ignored_rule": ".gitignore:18 runs/",
        "runs_file_count": sum(1 for _ in (ROOT / "runs").rglob("*") if _.is_file()),
        "untracked_plain_count": len(others),
        "git_add_performed": False,
        "git_commit_performed": False,
        "main_repo_push_performed": False,
        "note": "冻结 = 只读写哈希清单，不是 git 操作；主项目 CodeUp 仓库零提交。",
    }
    return rows, info


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    md, review = build_mapping()
    # 原样附上源 CSV，便于 Reviewer 直接对 46 行复核（字节与 gate6/ 保持一致）
    (OUT / "FIELD_MAPPING_SOURCE.csv").write_bytes((G6 / "FIELD_MAPPING.csv").read_bytes())
    (OUT / "FIELD_MAPPING_FULL.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    with (OUT / "FIELD_MAPPING_REVIEW.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(REVIEW_HEADER)
        w.writerows(review)

    freeze, gitinfo = build_freeze()
    with (OUT / "BASELINE_FREEZE.csv").open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(freeze)
    (OUT / "GIT_BASELINE.json").write_text(
        json.dumps(gitinfo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    checks = []

    def chk(cid, desc, cond, detail=""):
        checks.append({"id": cid, "desc": desc, "result": "PASS" if cond else "FAIL",
                       "detail": detail})

    with (G6 / "FIELD_MAPPING.csv").open(newline="", encoding="utf-8") as f:
        src = list(csv.reader(f))[1:]
    with (OUT / "FIELD_MAPPING_REVIEW.csv").open(newline="", encoding="utf-8") as f:
        rev = list(csv.reader(f))[1:]
    chk("R1", "全量表由源 CSV 生成且 46 行齐全",
        len(src) == 46 and all(r[0] in (OUT / "FIELD_MAPPING_FULL.md").read_text(encoding="utf-8")
                               for r in src))
    chk("R2", "审查矩阵 46 行且与源 CSV 逐行对齐",
        len(rev) == 46 and all(rev[i][1] == src[i][0] and rev[i][2] == src[i][2]
                               for i in range(46)))
    chk("R3", "审查矩阵每行 11 列", all(len(r) == 11 for r in rev))
    chk("R4", "待批默认值全部标记 needs_reviewer_approval=YES",
        all(r[9] == "YES" for r in rev if r[8].startswith("EXPLICIT_")),
        "count=%d" % sum(1 for r in rev if r[9] == "YES"))
    untracked_paths = [l[3:].strip('"') for l in
                       git("-c", "core.quotePath=false", "status", "--short").splitlines()
                       if l.startswith("??")]
    chk("R5", "冻结清单覆盖全部未跟踪条目", all(
        any(row[1] == p or row[1].startswith(p.rstrip("/") + "/")
            for row in freeze[1:])
        for p in untracked_paths), "entries=%d" % len(untracked_paths))
    chk("R6", "Git HEAD 与 Gate 6 第一轮一致",
        gitinfo["head"] == "3ed22a4a83564b36ca238792af4b2328fd966469")
    chk("R7", "主项目无新增提交", git("rev-parse", "HEAD") == gitinfo["head"])
    chk("R8", "B 类已跟踪修改被登记（cli.py 不得漏记）",
        "src/icpdf/cli.py" in gitinfo["tracked_modified"],
        "modified=%s" % gitinfo["tracked_modified"])
    chk("R9", "工作区 cli.py 与 HEAD 版本哈希不同且均已登记", any(
        r[0] == "B_TRACKED_MODIFIED" and r[1] == "src/icpdf/cli.py" for r in freeze[1:])
        and any(r[0] == "A_HEAD_REFERENCE" for r in freeze[1:]))
    (OUT / "ROUND2_VERIFY.json").write_text(json.dumps({
        "stage": "GATE6_ROUND2_DELIVERABLES_ONLY",
        "checks": checks, "total": len(checks),
        "passed": sum(1 for c in checks if c["result"] == "PASS"),
        "failed": sum(1 for c in checks if c["result"] == "FAIL"),
        "all_pass": all(c["result"] == "PASS" for c in checks),
        "evidence_boundary": "本文件证明交付件内部一致性与文件完整性，"
                             "不证明字段映射正确、方案获批或审计结论通过独立审核",
        "no_code_change": True, "no_db_created": True, "no_trial_started": True,
        "no_llm_call": True,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    for p in sorted(OUT.iterdir()):
        if p.is_file() and p.name != "SHA256SUMS.txt" and not p.name.startswith("."):
            lines.append("%s  %s\n" % (sha256_file(p), p.name))
    (OUT / "SHA256SUMS.txt").write_text("".join(lines), encoding="utf-8", newline="\n")
    print("[r2] verify=%d/%d sha_lines=%d freeze_rows=%d" % (
        sum(1 for c in checks if c["result"] == "PASS"), len(checks),
        len(lines), len(freeze) - 1))
    for c in checks:
        print("  %-4s %s %s" % (c["id"], c["result"], c["desc"]))


if __name__ == "__main__":
    main()
