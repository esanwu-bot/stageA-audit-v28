"""主分类逻辑（D2 裁决器 + D5 进程状态机）。

硬约束：
* 只读「文件名 / MPN / PDF 元数据 / 前 N 页文本」，**不解析任何正文参数**；
* 不 import ``icpdf.parser.*``，不触发主解析链路；
* 文件名证据最高只到 MEDIUM，**永远不能单独裁决**（D2）；
* 板级 STRONG 证据与 DS STRONG 证据同时成立 → ``EVIDENCE_CONFLICT``，
  两者都留在 matched_rules 里，交人工复核；
* 单个 native 崩溃（SIGSEGV / access violation）只带走一个子进程：
  整片崩溃就二分重试，二分到单文件仍崩才判该文件 ERROR，且 **不再重试**；
* 每份文件的处理状态持久化：``PENDING -> RUNNING -> SUCCESS / ERROR / TIMEOUT``，
  收尾强制 ``submitted = success + error + timeout + pending`` 且 ``pending == 0``。

裁决档位（D2 六档证据强度表，见设计稿 §2.4）：

===  ==============================  ============================  =============
档   DS 侧                           EVM 侧                        结论
===  ==============================  ============================  =============
1    —                               STRONG（板级标题/原理图）      EVM / 隔离
2    —                               MEDIUM x2（板级词汇 ≥2 类）    EVM / 隔离
3    STRONG                         仅文件名候选                   DS_STRONG
4    MEDIUM x2（含电气/引脚/极限）  仅文件名候选                   DS_STRONG
5    STRONG                          STRONG                         冲突 / 复核
6    WEAK 或空                      仅文件名候选 / 空              DS_WEAK / UNKNOWN
===  ==============================  ============================  =============
"""
from __future__ import annotations

import hashlib
import json
import logging
import multiprocessing as mp
import re
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FutureTimeoutError
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from .evidence import EvidenceCollector
from .rules import (
    DS_GROUP_LABELS,
    Hit,
    hit_groups,
    parse_provenance,
    rule_probes,
    scan_filename,
    scan_evidence_text,
    scan_pages,
)
from .models import (
    CLASSIFIER_VERSION,
    RULE_VERSION,
    Confidence,
    DocType,
    DocumentProvenance,
    EvidenceSource,
    ExtractStatus,
    Extractor,
    ProcessingFailure,
    ProcessingStatus,
    Route,
    RoutingClass,
    RuleStrength,
    SemanticDocType,
    resolve_assigned_type,
    resolve_route,
)

log = logging.getLogger(__name__)

DEFAULT_FIRST_PAGES = 3
DEFAULT_MAX_ROUNDS = 3
#: 每片超时的固定宽限（秒）：给进程创建 / pickling 留余量，不参与分类判定
DEADLINE_GRACE = 5.0
#: 文本层低于此长度视为「没有文本层」，交 OCR，不猜类别
MIN_TEXT_CHARS = 200
#: 板级词汇至少要几个**不同类别**才算板级主体证据
BOARD_TERM_MIN_GROUPS = 2

#: DS 侧可裁决的规则
DS_STRONG_RULES = frozenset({"DS_DOCUMENT_TITLE", "DS_PRODUCT_MODEL_TITLE"})
#: EVM 侧可裁决的规则
EVM_STRONG_RULES = frozenset({"EVM_BOARD_TITLE", "EVM_BOARD_SCHEMATIC"})
#: 文件名层候选（可被页级 DS 证据覆盖时留痕，但**来源**候选永不进 rejected）
FILENAME_CANDIDATES = frozenset({"EVM_FILENAME_SUFFIX", "EVM_FILENAME_WEAK",
                                 "DOCNUMBER_UG"})
#: 主证据标签优先级（写 rejected_rules 的 reason 用）
_DS_LABEL_PRIORITY = ("TITLE_DATASHEET", "SECTION_FEATURES", "SECTION_ELECTRICAL",
                      "SECTION_ABSMAX", "SECTION_PINS", "SECTION_RECOMMENDED",
                      "SECTION_DESCRIPTION", "PRODUCT_MODEL_TITLE")


# --------------------------------------------------------------------- 读取
def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _mpn_from_name(path: Path) -> str:
    stem = path.stem
    return stem.split("__", 1)[0] if "__" in stem else stem


def read_head(path: Path, pages: int
              ) -> tuple[str, str, list[str], str, ProcessingFailure,
                         list[ExtractStatus]]:
    """读取元数据 + 前 N 页纯文本。

    返回 ``(meta_title, meta_subject, pages, read_status, failure, page_statuses)``。
    只取文本，不做表格 / 参数 / 引脚结构抽取。

    V2.2.1：**逐页保留真实抽取状态**。某一页抛异常就是 ``read_error``，
    绝不再折成空字符串冒充 ``text_empty``——那会把「读失败」洗成「没文字」，
    进而把该文档误判为「无文本层，交 OCR」。
    """
    try:
        import pymupdf as fitz           # 延迟导入：mock 模式完全不加载原生库
    except ImportError:                  # pragma: no cover
        try:
            import fitz                  # 兼容旧版绑定
        except ImportError:
            return ("", "", [], "READ_ERROR:pymupdf_missing",
                    ProcessingFailure.READ_ERROR, [])

    doc = None
    try:
        doc = fitz.open(str(path))
        if doc.is_encrypted or doc.needs_pass:
            if not doc.authenticate(""):
                return "", "", [], "ENCRYPTED", ProcessingFailure.ENCRYPTED, []
        md = doc.metadata or {}
        title = re.sub(r"\s+", " ", str(md.get("title") or "")).strip()
        subject = re.sub(r"\s+", " ", str(md.get("subject") or "")).strip()
        if doc.page_count == 0:
            return title, subject, [], "CORRUPT", ProcessingFailure.CORRUPT, []
        texts: list[str] = []
        page_statuses: list[ExtractStatus] = []
        for i in range(min(doc.page_count, max(1, pages))):
            body = ""
            try:
                body = doc[i].get_text("text") or ""
                page_status = (ExtractStatus.SUCCESS if body.strip()
                               else ExtractStatus.TEXT_EMPTY)
            except Exception:
                # 单页抽取失败：正文留空，但状态必须是 read_error。
                # 注意这里**不能**只在 except 里追加空串——那样「读失败」就
                # 变成「这页没字」，正是 D3 要区分开的两种情形。
                page_status = ExtractStatus.READ_ERROR
            texts.append(body)
            page_statuses.append(page_status)
        total = sum(len(t.strip()) for t in texts)
        failed_pages = sum(1 for s in page_statuses
                           if s is ExtractStatus.READ_ERROR)
        if total < MIN_TEXT_CHARS:
            # 有页读不出来时不能声称「无文本层」：那是两种不同的失败
            if failed_pages:
                return (title, subject, texts, "READ_ERROR:page_extract",
                        ProcessingFailure.READ_ERROR, page_statuses)
            return (title, subject, texts, "NO_TEXT_LAYER",
                    ProcessingFailure.NO_TEXT_LAYER, page_statuses)
        return title, subject, texts, "OK", ProcessingFailure.NONE, page_statuses
    except Exception as exc:
        return ("", "", [], "READ_ERROR:%s" % type(exc).__name__,
                ProcessingFailure.READ_ERROR, [])
    finally:
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass


# --------------------------------------------------------------------- 裁决
@dataclass
class Decision:
    doc_type: DocType
    confidence: Confidence
    semantic: SemanticDocType
    failure: ProcessingFailure = ProcessingFailure.NONE
    status: ProcessingStatus = ProcessingStatus.SUCCESS
    read_status: str = "OK"
    rejected: list[tuple[str, str, str, str]] = field(default_factory=list)
    extra_hits: list[Hit] = field(default_factory=list)
    conflict: bool = False

    @property
    def assigned(self) -> RoutingClass:
        # ERROR 只能由 failure 产生，绝不从 doc_type 派生（D1）
        return resolve_assigned_type(self.doc_type, self.failure)

    @property
    def route(self) -> Route:
        # route 由 doc_type + failure 独立解析：assigned_type 是统计档位，
        # OCR 必须在统计上仍是 UNKNOWN、在流水线上真的进 OCR（V2.2.1）。
        return resolve_route(self.doc_type, self.failure)


def _board_description(hits: list[Hit]) -> str:
    groups = sorted({h.group for h in hits
                     if h.rule_id in EVM_STRONG_RULES or h.rule_id == "EVM_BOARD_TERMS"})
    return "/".join(groups) or "board terms"



def _primary_ds_label(hits: list[Hit]) -> str:
    """挑一个最像「主证据」的 DS 标签，写进 rejected_rules 的 reason。"""
    groups = set()
    for h in hits:
        if h.rule_id == "DS_DOCUMENT_TITLE":
            groups.add("TITLE_DATASHEET")
        elif h.rule_id == "DS_ELECTRICAL_SECTIONS":
            groups.add(h.group)
        elif h.rule_id == "DS_PRODUCT_MODEL_TITLE":
            groups.add("PRODUCT_MODEL_TITLE")
    for g in _DS_LABEL_PRIORITY:
        if g in groups:
            return DS_GROUP_LABELS[g]
    return "Datasheet"


def _provenance_only(h: Hit, provenance: DocumentProvenance | None) -> bool:
    """这个候选是否只是**来源产品名**的一部分。

    P2 的落地判定：``AFE7950EVM__afe7950.pdf`` 里的 ``EVM`` 属于来源产品，
    不能被当成「被页面证据推翻的文件名规则」写进 ``rejected_rules``；
    只有落在**文档主体**一侧的 EVM 标记，才是真正参与过裁决的候选。
    """
    if provenance is None or not provenance.source_product_mpn:
        return False
    token = (h.matched_text or "").strip().upper()
    if not token:
        return False
    source = provenance.source_product_mpn.upper()
    subject = (provenance.document_subject_mpn or "").upper()
    return token in source and token not in subject


def assert_route_invariant(doc_type: DocType, route: Route) -> None:
    """全局不变量（约束 2）：``route == IC_PARSE`` **当且仅当**
    ``doc_type == DS_STRONG``。

    生产路径每份结果都会过这道断言；任何「非 DS_STRONG 却进解析」或
    「DS_STRONG 却不进解析」都是硬错误，直接抛，绝不放行。
    """
    if doc_type is DocType.DS_STRONG:
        if route is not Route.IC_PARSE:
            raise AssertionError(
                "路由不变量被破坏：doc_type=DS_STRONG 但 route=%s" % route.value)
    elif route is Route.IC_PARSE:
        raise AssertionError(
            "路由不变量被破坏：doc_type=%s 却进了 IC_PARSE" % doc_type.value)


def _decide_matrix(hits: list[Hit], page_evidence: list[dict], read_status: str,
                   mpn: str, filename: str,
                   provenance: DocumentProvenance | None = None) -> Decision:
    """六档裁决器（纯函数，可脱离 PDF 用合成证据单测）。

    V2.2 纪律（Reviewer P2）：**文件名候选永不进 ``rejected_rules``**。
    候选不是「被否决」，只是「不足以裁决」——它的存在由 ``matched_rules``
    （MEDIUM 强度）+ ``provenance`` 承载。``rejected_rules`` 只记录真正被
    **页级强证据推翻**或**文档种类否决**的规则，这样「没证据」与「被推翻」
    在审计上不会混为一谈。
    """
    rejected: list[tuple[str, str, str, str]] = []
    extra: list[Hit] = []
    ds_hits = [h for h in hits if h.rule_id in DS_STRONG_RULES
               or h.rule_id == "DS_ELECTRICAL_SECTIONS"]
    board_strong = [h for h in hits if h.rule_id in EVM_STRONG_RULES]
    board_terms = hit_groups(hits, "EVM_BOARD_TERMS")
    ug_titles = hit_groups(hits, "EVM_BOARD_TITLE") & {"USER_GUIDE"}
    docnumber_ug = any(h.rule_id == "DOCNUMBER_UG" for h in hits)

    # ---- NVM 守卫：字符串近似不得当成 EVM 后缀
    #      注意（约束 2）：守卫只产生 matched_rules 里的 GUARD 命中，
    #      **不写 rejected_rules**——它不是 DS/EVM 页面裁决的败者，
    #      也和来源（provenance）无关。
    # ---- 档 0：处理失败（绝不折算成 UNKNOWN）
    #      文件名候选不做「否决」记录：我们只是没读到页内证据，
    #      候选本身并没有被推翻（P2）。
    if read_status == "NO_TEXT_LAYER":
        extra.append(Hit("PAGE_TEXT_UNAVAILABLE", "<no text layer>",
                         EvidenceSource.FIRST_PAGE, None, RuleStrength.STRONG,
                         Confidence.HIGH, "TEXT_EMPTY", Extractor.PYMUPDF,
                         ExtractStatus.TEXT_EMPTY))
        return Decision(DocType.OCR, Confidence.LOW, SemanticDocType.OCR_REQUIRED,
                        failure=ProcessingFailure.NO_TEXT_LAYER,
                        status=ProcessingStatus.SUCCESS,
                        read_status=read_status, rejected=rejected, extra_hits=extra)

    if read_status.startswith(("ENCRYPTED", "CORRUPT", "READ_ERROR")):
        kind = ("ENCRYPTED" if read_status.startswith("ENCRYPTED")
                else "CORRUPT" if read_status.startswith("CORRUPT")
                else "READ_ERROR")
        extra.append(Hit("PAGE_TEXT_UNAVAILABLE", read_status,
                         EvidenceSource.FIRST_PAGE, None, RuleStrength.STRONG,
                         Confidence.HIGH, kind, Extractor.PYMUPDF,
                         ExtractStatus.READ_ERROR))
        return Decision(DocType.UNKNOWN, Confidence.LOW, SemanticDocType.UNREADABLE,
                        failure=ProcessingFailure(kind),
                        status=ProcessingStatus.ERROR,
                        read_status=read_status, rejected=rejected, extra_hits=extra)

    ds_title = [h for h in hits if h.rule_id in DS_STRONG_RULES]
    ds_title_strong = bool(ds_title)
    ds_groups = hit_groups(hits, "DS_ELECTRICAL_SECTIONS")
    # 组合 DS 证据：≥2 类章节且含电气/极限/引脚之一
    ds_combo = (len(ds_groups) >= 2
                and bool(ds_groups & {"SECTION_ELECTRICAL", "SECTION_ABSMAX",
                                      "SECTION_PINS"}))
    ds_strong = ds_title_strong or ds_combo
    board_body = bool(board_strong) or len(board_terms) >= BOARD_TERM_MIN_GROUPS
    if not board_body and ug_titles and (board_terms or docnumber_ug):
        board_body = True
    # ---- 档 5：两侧都有 STRONG 标题级证据 → 冲突，人工复核
    if board_strong and ds_title_strong:
        conflict_text = "DS=%s; EVM=%s" % (
            ",".join(sorted({h.group for h in ds_title if h.group})),
            ",".join(sorted({h.group for h in board_strong if h.group})))
        extra.append(Hit("EVIDENCE_CONFLICT", conflict_text,
                         EvidenceSource.FIRST_PAGE, None, RuleStrength.STRONG,
                         Confidence.HIGH, "CONFLICT", Extractor.PYMUPDF))
        return Decision(DocType.UNKNOWN, Confidence.LOW, SemanticDocType.UNKNOWN,
                        read_status=read_status, extra_hits=extra, conflict=True)

    # ---- 档 1：板级 STRONG 证据 → EVM（隔离，不删除）
    #      板级标题比「电气章节组合」更硬：UG 里出现被测 IC 的电气章节属于常态
    if board_strong:
        for h in ds_hits:
            rejected.append((h.rule_id, h.matched_text,
                             "overridden by board evidence (%s); IC 参数不能代表整板"
                             % _board_description(hits),
                             "overridden_by_board_evidence"))
        return Decision(DocType.EVM, Confidence.HIGH, SemanticDocType.EVM,
                        read_status=read_status, rejected=rejected, extra_hits=extra)

    # ---- 档 3/4：DS 组合证据足够 → DS_STRONG（P1：本体优先，不受来源影响）
    #      rejected 只记录「真正参与过 DS vs EVM 裁决但败下阵来」的文件名候选；
    #      来源产品名里的 EVM 属于 provenance，永不进 rejected（P2）。
    if ds_strong:
        label = _primary_ds_label(hits)
        reason = "overridden by page_text %s (Datasheet evidence)" % label
        for h in hits:
            if h.rule_id not in FILENAME_CANDIDATES:
                continue
            if _provenance_only(h, provenance):
                continue
            rejected.append((h.rule_id, h.matched_text, reason,
                             "overridden_by_page_text_datasheet_evidence"))
        return Decision(DocType.DS_STRONG, Confidence.HIGH, SemanticDocType.IC_DATASHEET,
                        read_status=read_status, rejected=rejected, extra_hits=extra)

    # ---- 档 2：只有板级词汇（≥2 类）→ EVM，中等置信度
    if board_body:
        for h in ds_hits:
            rejected.append((h.rule_id, h.matched_text,
                             "overridden by board terms (%s)"
                             % _board_description(hits),
                             "overridden_by_board_terms"))
        return Decision(DocType.EVM, Confidence.MEDIUM, SemanticDocType.EVM,
                        read_status=read_status, rejected=rejected, extra_hits=extra)

    # ---- 明确非 DS 文档本体（AN / RD / SMD / UG）
    other = {h.group for h in hits if h.rule_id == "OTHER_TITLE"}
    if "AN_TITLE" in other:
        return Decision(DocType.AN, Confidence.MEDIUM, SemanticDocType.APP_NOTE,
                        read_status=read_status, rejected=rejected, extra_hits=extra)
    if "RD_TITLE" in other:
        return Decision(DocType.UNKNOWN, Confidence.MEDIUM,
                        SemanticDocType.REFERENCE_DESIGN,
                        read_status=read_status, rejected=rejected, extra_hits=extra)
    if "SMD_MARKER" in other:
        return Decision(DocType.SMD, Confidence.MEDIUM, SemanticDocType.UNKNOWN,
                        read_status=read_status, rejected=rejected, extra_hits=extra)
    if ug_titles:
        for h in ds_hits:
            rejected.append((h.rule_id, h.matched_text,
                             "User's Guide 里出现电气章节，不作为 Datasheet 准入",
                             "support_only_in_user_guide"))
        return Decision(DocType.UG, Confidence.MEDIUM, SemanticDocType.USER_GUIDE,
                        read_status=read_status, rejected=rejected, extra_hits=extra)

    # ---- 档 6a：只有弱 DS 证据 → DS_WEAK（强制 REVIEW）
    if ds_groups:
        return Decision(DocType.DS_WEAK, Confidence.LOW, SemanticDocType.IC_DATASHEET,
                        read_status=read_status, rejected=rejected, extra_hits=extra)

    # ---- 档 6b：只有文件名候选 → UNKNOWN / REVIEW（候选保留，不做否决记录）
    return Decision(DocType.UNKNOWN, Confidence.LOW, SemanticDocType.UNKNOWN,
                    read_status=read_status, rejected=rejected, extra_hits=extra)


def _guard_veto(hits: list[Hit]) -> tuple[str, str, str, str] | None:
    """NVM 字符串守卫的文件名级冲突裁决（**不是**溯源信息）。

    ``ADC_NVM_IMAGE`` 里的 ``NVM`` 与 ``EVM`` 只差一个字母，守卫主动阻断了
    EVM 后缀候选。这属于「文件名层冲突裁决」：候选确实被否决了，且否决
    理由与来源关联无关，因此必须写进 ``rejected_rules``，否则审计上会退化成
    「根本没检查过 EVM 后缀」。
    """
    for h in hits:
        if h.rule_id == "EVM_NVM_GUARD":
            return ("EVM_FILENAME_SUFFIX", h.matched_text,
                    "blocked by NVM string guard (%s)：NVM 与 EVM 仅一字母之差，"
                    "不得据此判为评估板" % h.matched_text,
                    "nvm_guard")
    return None


def decide(hits: list[Hit], page_evidence: list[dict], read_status: str,
           mpn: str, filename: str,
           provenance: DocumentProvenance | None = None) -> Decision:
    """六档裁决的公开入口：裁决矩阵 + 文件名层守卫的否决留痕。

    守卫只在**没有判成 EVM**时才补记否决——真判成 EVM 时「EVM 后缀被阻断」
    这句话本身就是误导，不能写进审计记录。
    """
    d = _decide_matrix(hits, page_evidence, read_status, mpn, filename, provenance)
    if d.doc_type is not DocType.EVM:
        veto = _guard_veto(hits)
        if veto is not None and veto not in d.rejected:
            d.rejected.append(veto)
    return d


# --------------------------------------------------------------------- 单份
def assemble_record(*, file_path: str, filename: str, mpn: str, sha: str,
                    hits: list[Hit], page_evidence: list[dict],
                    read_status: str, mock: bool, original: dict[str, str],
                    rule_version: str = RULE_VERSION,
                    sha256_status: ExtractStatus = ExtractStatus.SUCCESS
                    ) -> dict[str, Any]:
    """由「已取到的证据」组装最终记录（裁定 + 溯源 + 严格契约）。

    抽出来是为了让合成证据测试走**完全相同的生产路径**：
    provenance 解析 → 六档裁决 → 证据收集 → 契约落盘，一步不少。
    """
    # P1 的前置：先拆「来源」与「本体」，再用**文档主体**做页内交叉验证
    provenance = parse_provenance(filename)
    subject = provenance.document_subject_mpn or mpn

    # provenance 必须传进裁决器，否则 P2 的「来源候选不进制裁」永不生效
    decision = decide(hits, page_evidence, read_status, subject, filename,
                      provenance)
    hits = list(hits) + list(decision.extra_hits)
    assert_route_invariant(decision.doc_type, decision.route)

    collector = EvidenceCollector(sha, rule_version, CLASSIFIER_VERSION,
                                  source_hash_status=sha256_status)
    for h in hits:
        collector.add(h)
    for rule_id, text, reason, code in decision.rejected:
        collector.reject(rule_id, text, reason, code)
    collector.set_probes(rule_probes(hits, read_status, pages_checked=not mock))
    collector.set_page_evidence(page_evidence)

    result, compat = collector.build(
        doc_type=decision.doc_type,
        doc_confidence=decision.confidence,
        route=decision.route,
        semantic_type=decision.semantic,
        assigned_type=decision.assigned,
        read_status=read_status,
        classification_status=decision.status,
        failure_kind=decision.failure,
        evidence_conflict=decision.conflict,
        provenance=provenance,
    )
    return {
        "document_id": "doc_%s" % (sha[:16] or "nohash"),
        "mpn": mpn,
        "file_path": file_path,
        "original_doc_type": original.get("doc_type", ""),
        "original_assigned_type": original.get("assigned_type", ""),
        "result": result.model_dump(mode="json"),
        "classification": compat["classification"],
        "routing": compat["routing"],
        "evidence_text": collector.bundle.evidence_text(),
    }


def _classify_worker(path_str: str, rule_version: str, first_pages: int,
                     mock: bool, original: dict[str, str]) -> dict[str, Any]:
    """子进程入口（模块级函数，Windows spawn 可 pickle）。"""
    path = Path(path_str)
    filename = path.name
    mpn = _mpn_from_name(path)

    try:
        sha = sha256_of(path)
        hash_status = ExtractStatus.SUCCESS
    except Exception as exc:
        # P0（V2.2.1）：绝不拿路径字符串的哈希冒充源文件指纹。
        # 读不到字节 → 哈希为空 + 状态标注，去重判 NOT_CHECKED，必须重跑。
        log.warning("源文件哈希计算失败 %s: %s", path_str, type(exc).__name__)
        sha = ""
        hash_status = ExtractStatus.READ_ERROR

    provenance = parse_provenance(filename)
    # 溯源不可用时退回文件名型号码（只用于页内交叉验证）；不写回 provenance
    subject = provenance.document_subject_mpn or mpn

    hits: list[Hit] = list(scan_filename(filename, mpn))
    page_evidence: list[dict] = []
    page_statuses: list[ExtractStatus] | None = None
    if mock:
        read_status = "NOT_CHECKED"
    else:
        meta_title, meta_subject, pages, read_status, _failure, page_statuses = \
            read_head(path, first_pages)
        if pages:
            page_hits, page_evidence = scan_pages(pages, meta_title, meta_subject,
                                                  subject, page_statuses)
            hits.extend(page_hits)

    return assemble_record(file_path=str(path.resolve()), filename=filename,
                           mpn=mpn, sha=sha, hits=hits,
                           page_evidence=page_evidence, read_status=read_status,
                           mock=mock, original=original,
                           rule_version=rule_version,
                           sha256_status=hash_status)


def classify_one(path: str | Path, *, rule_version: str = RULE_VERSION,
                 first_pages: int = DEFAULT_FIRST_PAGES, mock: bool = False,
                 original: dict[str, str] | None = None) -> dict[str, Any]:
    """单份分类（同步，便于单测与 mock CLI）。"""
    return _classify_worker(str(path), rule_version, first_pages, mock, original or {})


# --------------------------------------------------------------------- 状态机
class IllegalStateTransition(RuntimeError):
    """非法的台账状态迁移（fail-closed，不静默容忍）。

    ``counts`` 的语义是「当前处于各状态的文档数」，不是「累计迁移次数」。
    一旦允许终态复活或跨状态跳跃，``counts`` 就与真实流水线脱节，收尾的
    ``submitted = success + error + timeout + pending`` 也就失去意义。
    所以这里建显式迁移表，越界直接抛错——宁可让批次炸掉，也不留一份
    自己都对不上账的 summary。
    """

    def __init__(self, file_path: str, prev: str, nxt: str) -> None:
        self.file_path = file_path
        self.prev = prev
        self.next = nxt
        super().__init__(
            "非法状态迁移：%s 不能从 %s 直接进入 %s（允许：%s）"
            % (file_path, prev, nxt,
               sorted(_ALLOWED_TRANSITIONS.get(prev, frozenset())) or "无（终态）"))


# 允许的迁移表：旧状态 -> 可进入的新状态集合。**同态重复设置（幂等）不在表内**，
# 由 ``TaskLedger.set()`` 单独放行（重复 set 不能把计数加成 2）。
#
# 逐条对应真实调用：
# * PENDING -> RUNNING            派发（run_batch 每轮开头）
# * PENDING -> SUCCESS/ERROR/TIMEOUT   单文件同步路径，无中间态
# * RUNNING -> SUCCESS/ERROR/TIMEOUT   正常收口
# * TIMEOUT -> RETRY_PENDING -> RUNNING   二分重试的「等下一轮」
# * SUCCESS 是绝对终点：跑完的文档不允许再被塞回队列（否则重复计数）
_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    ProcessingStatus.PENDING.value: frozenset({
        ProcessingStatus.RUNNING.value,
        ProcessingStatus.RETRY_PENDING.value,
        ProcessingStatus.SUCCESS.value,
        ProcessingStatus.ERROR.value,
        ProcessingStatus.TIMEOUT.value,
    }),
    ProcessingStatus.RUNNING.value: frozenset({
        ProcessingStatus.SUCCESS.value,
        ProcessingStatus.ERROR.value,
        ProcessingStatus.TIMEOUT.value,
        ProcessingStatus.RETRY_PENDING.value,
    }),
    ProcessingStatus.RETRY_PENDING.value: frozenset({
        ProcessingStatus.RUNNING.value,
    }),
    # 终态：只能原地重复（幂等），不能复活。
    # ERROR / TIMEOUT 例外——二分重试允许把它们重新排队；SUCCESS 不允许。
    ProcessingStatus.SUCCESS.value: frozenset(),
    ProcessingStatus.ERROR.value: frozenset({
        ProcessingStatus.RETRY_PENDING.value,
    }),
    ProcessingStatus.TIMEOUT.value: frozenset({
        ProcessingStatus.RETRY_PENDING.value,
    }),
}


class TaskLedger:
    """处理状态持久化：每行一个状态迁移，进程被杀也不会丢进度（D5）。

    ``counts`` 永远是**当前快照**：迁移时从旧状态扣减、向新状态增加，
    扣到 0 就删键（不保留 0 值键，避免 ``PENDING: 0`` 混进 summary）。
    每次迁移后立刻自检 ``sum(counts.values()) == len(states)``，
    不等收尾才炸——这样崩溃时留下的最后一行也一定是自洽的。
    """

    def __init__(self, path: str | Path | None = None, *, resume: bool = False):
        """``resume=True``：从已落盘的 JSONL 重放并重建 states / counts，
        之后以追加模式续写（模拟主进程崩溃后重启接续）。"""
        self.path = Path(path) if path else None
        self.states: dict[str, str] = {}
        self.counts: dict[str, int] = {}
        #: 各目标状态的**迁移事件数**（只在 ``set()`` 累加，``_replay()`` 不计）。
        #: 用于 summary 的 retry_count：RETRY_PENDING 的进入次数就是重排队次数。
        self.transitions_by_state: dict[str, int] = {}
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if resume and self.path.exists():
                self._replay()
                self._fh = open(self.path, "a", encoding="utf-8")
            else:
                self._fh = open(self.path, "w", encoding="utf-8")
        else:
            self._fh = None

    # ------------------------------------------------------------ 内部
    def _assert_consistent(self) -> None:
        """任意时刻的一致性不变量：计数总和必须等于文档数，且不出现非正计数。"""
        total = sum(self.counts.values())
        if total != len(self.states):
            raise RuntimeError(
                "台账计数不一致：sum(counts)=%d, len(states)=%d, counts=%r"
                % (total, len(self.states), self.counts))
        if any(v <= 0 for v in self.counts.values()):
            raise RuntimeError("台账出现非正计数：%r" % (self.counts,))

    def _apply(self, file_path: str, state: ProcessingStatus) -> None:
        """只改内存快照，不落盘：``set()`` 与 ``_replay()`` 共用同一套算术。"""
        prev = self.states.get(file_path)
        if prev is not None:
            left = self.counts.get(prev, 0) - 1
            if left < 0:
                raise RuntimeError(
                    "台账扣减越界：%s 在 %s 上的计数已为 0" % (file_path, prev))
            if left == 0:
                self.counts.pop(prev, None)
            else:
                self.counts[prev] = left
        self.states[file_path] = state.value
        self.counts[state.value] = self.counts.get(state.value, 0) + 1
        self._assert_consistent()

    def _replay(self) -> int:
        """重放已有台账，重建 ``states`` / ``counts``；返回有效行数。

        **残行与坏行必须区别对待**（V2.2.1 D5）：

        * 末尾残行：崩溃时最后一条 ``write`` 只落了一半——**没有换行符**，
          说明这行本来就没写完。记 warning，截断到最后一个完整行，继续。
        * 写完却解析不了：行尾带 ``\\n``，说明这条记录已经完整落盘，解析失败
          只能是**内容损坏**（磁盘坏块、被并发覆写、被手工改坏）。此时无论
          在末尾还是中间，一律抛 ``RuntimeError`` 且**不动文件**。
        * 中间坏行：坏行之后还有数据，台账同样不可信，抛错要求人工介入。

        最后这条容易被写成「到文件尾就当残行」——那会把「末尾一条完整记录被
        写坏」误判成断电残行而静默截断，正好把磁盘损坏掩盖掉。
        """
        assert self.path is not None
        good_bytes = 0
        size = self.path.stat().st_size
        with open(self.path, "rb") as fh:
            while True:
                raw = fh.readline()
                if not raw:
                    break
                try:
                    rec = json.loads(raw.decode("utf-8"))
                    fp = rec["file_path"]
                    st = rec["state"]
                    if not isinstance(fp, str) or not isinstance(st, str):
                        raise ValueError("字段类型非法")
                    state = ProcessingStatus(st)
                except (UnicodeDecodeError, json.JSONDecodeError,
                        KeyError, ValueError) as exc:
                    if not raw.endswith(b"\n") and fh.tell() >= size:
                        # 没写完的最后一条：断电残行，正常截断
                        log.warning("台账末尾残行，截断到 %d 字节：%s",
                                    good_bytes, self.path)
                        break
                    if fh.tell() >= size:
                        raise RuntimeError(
                            "末尾损坏，拒绝截断：%s（偏移 %d/%d，末行已写完但解析"
                            "失败，%s）"
                            % (self.path, good_bytes, size, type(exc).__name__))
                    raise RuntimeError(
                        "台账中间存在损坏记录，拒绝静默截断：%s（偏移 %d/%d，%s）"
                        % (self.path, good_bytes, size, type(exc).__name__))
                prev = self.states.get(fp)
                if prev is not None and prev != state.value:
                    allowed = _ALLOWED_TRANSITIONS.get(prev, frozenset())
                    if state.value not in allowed:
                        raise RuntimeError(
                            "台账含非法状态迁移，拒绝继续恢复：%s（%s: %s -> %s）"
                            % (self.path, fp, prev, state.value))
                self._apply(fp, state)
                good_bytes += len(raw)
        if good_bytes != size:
            with open(self.path, "r+b") as fh:
                fh.truncate(good_bytes)
        return len(self.states)

    # ------------------------------------------------------------ 公开
    def set(self, file_path: str, state: ProcessingStatus, detail: str = "",
            attempt: int = 0) -> None:
        """状态迁移：**从旧状态扣减，向新状态增加**（V2.2.1 D5 计数修正）。

        旧实现有一个漏洞：``if prev and prev != PENDING`` 跳过了对 PENDING 的
        扣减，于是每个文件都会在 ``counts["PENDING"]`` 里留一个永不消失的 1。
        现在统一按「有旧状态就扣」处理，并在扣到 0 时删掉键，使
        ``counts`` 恒等于「当前各状态的文档数」，而不是累计迁移次数。

        同态重复设置是幂等的（不报错、不重复计数）；终态复活或跨状态跳跃
        抛 :class:`IllegalStateTransition`。

        ``detail`` / ``attempt`` 只写进 JSONL 台账（复盘用），不参与计数。
        """
        prev = self.states.get(file_path)
        if prev is not None and prev != state.value:
            allowed = _ALLOWED_TRANSITIONS.get(prev)
            if allowed is None:
                raise IllegalStateTransition(file_path, prev, state.value)
            if state.value not in allowed:
                raise IllegalStateTransition(file_path, prev, state.value)
        self._apply(file_path, state)
        self.transitions_by_state[state.value] = (
            self.transitions_by_state.get(state.value, 0) + 1)
        if self._fh:
            self._fh.write(json.dumps({
                "file_path": file_path, "state": state.value,
                "attempt": attempt, "detail": detail,
            }, ensure_ascii=False) + "\n")
            self._fh.flush()

    def snapshot(self) -> dict[str, int]:
        """当前计数快照的**副本**（测试与 summary 用，防止外部改坏内部状态）。"""
        return dict(self.counts)

    def transitions(self, file_path: str) -> list[str]:
        """从台账文件里读出某个文件的完整状态序列（复盘用）。

        只想看最终态用 ``states[file_path]``；想查「到底怎么走到这一步的」，
        用这个方法拿 ``PENDING -> RUNNING -> RETRY_PENDING -> ...`` 全链路。
        """
        if not self.path or not self.path.exists():
            return []
        out: list[str] = []
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("file_path") == file_path:
                    out.append(str(rec.get("state", "")))
        return out

    def close(self) -> None:
        if self._fh:
            self._fh.close()
            self._fh = None


@dataclass
class BatchOutcome:
    records: list[dict[str, Any]]
    failures: dict[str, str]
    rounds: int
    crashed_files: list[str]
    states: dict[str, str] = field(default_factory=dict)
    accounting: dict[str, int] = field(default_factory=dict)


def _terminate_children(children: set[Any]) -> None:
    """显式回收子进程：terminate → join → kill。不做这一步会留下僵尸进程。"""
    for proc in list(children):
        try:
            if proc.is_alive():
                proc.terminate()
        except Exception:                       # pragma: no cover
            pass
    for proc in list(children):
        try:
            proc.join(timeout=1.0)
        except Exception:                       # pragma: no cover
            pass
    for proc in list(children):
        try:
            if proc.is_alive():
                proc.kill()
                proc.join(timeout=0.5)
        except Exception:                       # pragma: no cover
            pass


def _chunks(items: list[str], size: int) -> list[list[str]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


class ClassifierV2:
    """分类器入口；批量读取走进程池隔离 + 二分定位崩溃文件。

    三个关键字参数是**只给测试用的注入缝**（默认值与线上完全一致）：
    ``executor_factory`` / ``worker`` / ``deadline_grace``。
    有了它们，二分回收逻辑可以用纯模拟对象验证，不必真的制造 SIGSEGV。
    """

    def __init__(self, rule_version: str = RULE_VERSION,
                 first_pages: int = DEFAULT_FIRST_PAGES, *,
                 executor_factory: Callable[..., Any] | None = None,
                 worker: Callable[..., dict[str, Any]] | None = None,
                 deadline_grace: float = DEADLINE_GRACE):
        self.rule_version = rule_version
        self.first_pages = first_pages
        self._executor_factory = executor_factory or ProcessPoolExecutor
        self._worker = worker or _classify_worker
        self.deadline_grace = deadline_grace

    def classify(self, path: str | Path) -> dict[str, Any]:
        return classify_one(path, rule_version=self.rule_version,
                            first_pages=self.first_pages)

    # ------------------------------------------------------------- 批量
    def run_batch(self, paths: Iterable[str], *, workers: int = 4,
                  per_file_timeout: float = 20.0, mock: bool = False,
                  original_map: dict[str, dict[str, str]] | None = None,
                  max_rounds: int = DEFAULT_MAX_ROUNDS,
                  ledger_path: str | Path | None = None) -> BatchOutcome:
        items = sorted({str(Path(p).resolve()) for p in paths})
        workers = max(1, int(workers))
        original_map = original_map or {}
        records: dict[str, dict[str, Any]] = {}
        failures: dict[str, str] = {}
        final: dict[str, ProcessingStatus] = {}
        crashed: set[str] = set()
        attempts: dict[str, int] = {p: 0 for p in items}
        rounds = 0
        chunk_size = max(1, workers * 4)
        ledger = TaskLedger(ledger_path)
        for p in items:
            ledger.set(p, ProcessingStatus.PENDING)

        def execute(slice_paths: list[str]) -> None:
            """执行一片；崩溃则二分，二分到单文件仍崩才判该文件 ERROR。"""
            if not slice_paths:
                return
            ex = self._executor_factory(max_workers=min(workers, len(slice_paths)))
            baseline = set(mp.active_children())
            futs = {
                ex.submit(self._worker, p, self.rule_version, self.first_pages,
                          mock, original_map.get(p, {})): p
                for p in slice_paths
            }
            children = set(mp.active_children()) - baseline
            done: set[str] = set()
            crashed_here = False
            timed_out = False
            deadline = per_file_timeout * max(
                1.0, len(slice_paths) / float(workers)) + self.deadline_grace
            try:
                for fut in as_completed(futs, timeout=deadline):
                    p = futs[fut]
                    try:
                        records[p] = fut.result()
                        done.add(p)
                        ledger.set(p, ProcessingStatus.SUCCESS, attempt=attempts[p])
                    except BrokenProcessPool:
                        crashed_here = True
                        break
                    except Exception as exc:        # 读取层异常：该文件 ERROR
                        detail = "classify_error:%s:%s" % (
                            type(exc).__name__, str(exc)[:120])
                        failures[p] = detail
                        final[p] = ProcessingStatus.ERROR
                        done.add(p)
                        ledger.set(p, ProcessingStatus.ERROR, detail, attempts[p])
            except FutureTimeoutError:
                timed_out = True
            finally:
                ex.shutdown(wait=False, cancel_futures=True)
                _terminate_children(children)

            remaining = [p for p in slice_paths
                         if p not in done and p not in final]
            if crashed_here:
                if not remaining:
                    return
                if len(remaining) == 1:
                    p = remaining[0]
                    failures[p] = "worker_crash:BrokenProcessPool"
                    final[p] = ProcessingStatus.ERROR
                    crashed.add(p)
                    ledger.set(p, ProcessingStatus.ERROR,
                               "worker_crash:BrokenProcessPool", attempts[p])
                    return
                # 二分定位：崩溃只带走一个子进程，逐半重试直到锁定单文件
                mid = len(remaining) // 2
                execute(remaining[:mid])
                execute(remaining[mid:])
                return
            if timed_out:
                for p in remaining:
                    ledger.set(p, ProcessingStatus.TIMEOUT,
                               "slice deadline %.1fs exceeded" % deadline, attempts[p])
                    if attempts[p] >= max_rounds:
                        failures[p] = "timeout:max_rounds"
                        final[p] = ProcessingStatus.TIMEOUT

        while True:
            pending = [p for p in items
                       if p not in records and p not in final
                       and attempts[p] < max_rounds]
            if not pending or rounds >= max_rounds:
                break
            rounds += 1
            for p in pending:
                attempts[p] += 1
                # 第 2 轮起是重试：先落一个 RETRY_PENDING，让台账能区分
                # 「等下一轮」与「从未开始」，也才能复盘二分重试的轮次。
                if attempts[p] > 1:
                    ledger.set(p, ProcessingStatus.RETRY_PENDING, "requeue",
                               attempts[p])
                ledger.set(p, ProcessingStatus.RUNNING, "dispatch", attempts[p])
            for sl in _chunks(pending, chunk_size):
                execute(sl)

        # 收尾：轮次耗尽仍未出结果的，一律判 TIMEOUT，绝不留 PENDING
        for p in items:
            if p in records or p in final:
                continue
            failures[p] = "timeout:unresolved_after_%d_rounds" % max_rounds
            final[p] = ProcessingStatus.TIMEOUT
            ledger.set(p, ProcessingStatus.TIMEOUT,
                       "rounds exhausted", attempts[p])

        success = len(records)
        error = sum(1 for p in items if final.get(p) is ProcessingStatus.ERROR)
        timeout = sum(1 for p in items if final.get(p) is ProcessingStatus.TIMEOUT)
        pending_left = len(items) - success - error - timeout
        # 执行/路由状态报告字段（Reviewer 阶段 A 第 4 项）：
        # * retry_count         进入 RETRY_PENDING 的次数 = 重排队事件数
        # * recovered_count     最终成功、但经历过至少 2 轮派发的文件数
        # * duplicate_execution 同一文件被重复派发的总次数（sum(attempts-1)）
        # * missing_output      台账记 SUCCESS、却没有产出记录的文件数（必须为 0）
        retry_count = ledger.transitions_by_state.get(
            ProcessingStatus.RETRY_PENDING.value, 0)
        recovered_count = sum(1 for p in records if attempts.get(p, 0) >= 2)
        duplicate_execution = sum(max(0, a - 1) for a in attempts.values())
        missing_output = sum(
            1 for p, st in ledger.states.items()
            if st == ProcessingStatus.SUCCESS.value and p not in records)
        accounting = {
            "submitted": len(items), "success": success, "error": error,
            "timeout": timeout, "pending": pending_left,
            "retry_count": retry_count, "recovered_count": recovered_count,
            "duplicate_execution": duplicate_execution,
            "missing_output": missing_output,
        }
        ledger.close()
        if success + error + timeout + pending_left != len(items):
            raise RuntimeError(
                "accounting 等式不成立：submitted=%d != success+error+timeout+"
                "pending=%d；%s" % (len(items),
                                    success + error + timeout + pending_left,
                                    accounting))
        if missing_output:                      # 记了成功却没有产物：账实不符
            raise RuntimeError(
                "台账记 SUCCESS 但无产出记录：%d 个文件；%s"
                % (missing_output, accounting))
        if pending_left != 0:                   # 不变量：绝不允许静默丢文件
            # 这条不变量是最终验收线（Reviewer D5）：只要它成立就不追查计数细节；
            # 一旦不成立，错误信息必须能直接定位——列出残留文件与台账路径，
            # 让人拿着 JSONL 就能复盘每个文件的最终状态，而不是只看到一个数字。
            stuck = sorted(p for p in items
                           if p not in records and final.get(p) is None)
            raise RuntimeError(
                "任务台账不平衡：%s；pending 文件 %d 个：%s；台账：%s"
                % (accounting, len(stuck),
                   ", ".join(stuck[:10]) + (" ..." if len(stuck) > 10 else "")
                   if stuck else "-",
                   ledger.path or "<未落盘>"))
        return BatchOutcome(
            records=[records[p] for p in sorted(records)],
            failures=failures, rounds=rounds,
            crashed_files=sorted(crashed),
            states=dict(ledger.states), accounting=accounting,
        )

    # ------------------------------------------------------------- 重映射
    @staticmethod
    def remap_existing(row: dict[str, str]) -> dict[str, Any]:
        """「不重扫 PDF」通道：由 v1 结果 + 证据串重映射到 v2 路由。

        原分类原样保留在 original_* 字段，绝不覆盖。
        """
        path = row.get("file_path") or row.get("FilePath") or ""
        mpn = row.get("mpn") or row.get("MPN") or ""
        old = (row.get("assigned_type") or row.get("doc_type")
               or row.get("DocType") or "").strip()
        evidence = row.get("evidence_text") or row.get("EVM_Evidence") or ""
        sha = (row.get("source_sha256") or row.get("Source_SHA256") or "").strip()
        # P0（V2.2.1）：不再用路径字符串哈希顶替源文件指纹。
        # 上游给了合法 SHA 就用；否则尝试现算；都拿不到就留空并标注状态。
        sha256_status = (ExtractStatus.SUCCESS if len(sha) == 64
                         else ExtractStatus.NOT_CHECKED)
        if sha256_status is not ExtractStatus.SUCCESS and path:
            try:
                sha = sha256_of(Path(path))
                sha256_status = ExtractStatus.SUCCESS
            except OSError:
                sha = ""
                sha256_status = ExtractStatus.READ_ERROR
        if sha256_status is not ExtractStatus.SUCCESS:
            sha = ""
        name = Path(path).name
        hits = list(scan_filename(name, mpn or _mpn_from_name(Path(path))))
        hits += scan_evidence_text(evidence[:2000])
        record = assemble_record(
            file_path=path, filename=name,
            mpn=mpn or _mpn_from_name(Path(path)), sha=sha, hits=hits,
            page_evidence=[], read_status="REMAPPED_FROM_V1",
            mock=True, original={"doc_type": old, "assigned_type": old},
            rule_version=RULE_VERSION, sha256_status=sha256_status)
        if old:
            # v1 标签另记一条否决：只作留存，不参与 v2 判定
            record["result"]["rejected_rules"].append({
                "rule_id": "V1_LABEL", "matched_text": old,
                "reason": "v1 标签仅作原分类留存，不参与 v2 判定",
                "code": "v1_label_only", "extractor": "regex_filename",
                "extract_status": "success",
            })
        return record
