"""Ds Bit · Pre-Parse Gate 分类子进程（冻结期只写代码，不执行）。

职责边界（不可协商）：
1. 只调用仓库现有 Document Classifier V2 的官方同步入口
   ``icpdf.classification.classifier.classify_one()``。
   不实现任何分类规则、不改阈值、不改路由矩阵、不重造标签。
2. 分类器是纯规则实现：``src/icpdf/classification/`` 内无 LLM Provider、
   无网络客户端、无 PyYAML 依赖。本 worker 因此零 Token、零模型调用。
3. 用唯一哨兵包裹 JSON 载荷，避免 PyMuPDF C 层把 ``MuPDF error: ...``
   直接写到 fd 1 时污染 stdout（Gate 0/1 已实测该问题）。
4. 分类同样在独立子进程中执行：``read_head()`` 会打开 PDF 并加载原生
   PyMuPDF，损坏文件可能 SIGSEGV；由父进程超时强杀隔离，不拖垮 Web 服务。
5. 不 import ``icpdf.parser.*``、不调用 ``parse_pdf()``、不建数据库。

文件名证据与磁盘名的隔离
------------------------
父进程落盘用的是 ``<uuid4>.pdf``（物理名，与用户输入零耦合），但分类器
需要从**文件名**取 mpn / provenance。因此本 worker 在自己的私有临时目录内
用清洗后的证据名对物理文件建**硬链接**（跨卷时退回复制），把链接路径交给
``classify_one()``，分类结束立即删除整个临时目录。

硬链接不复制字节，``source_sha256`` 仍是同一份上传字节的哈希；
用户提交名永远不会出现在 ``UPLOAD_DIR`` 之下，也不会参与路径拼接。

阶段标记：父进程通过 stdout 上的 ``[WORKER] ...`` 行判断分类器是否真的
被调用，避免把「崩溃/超时但已调用」错记成 0 次。

本文件被 ``serve_parser.py`` 的 ``/api/process`` 使用；``/api/parse``
（Gate 6A Parser-only 测试入口）绝不引用本文件。
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

BEGIN = "__ICEX_CLASSIFY_JSON_BEGIN__"
END = "__ICEX_CLASSIFY_JSON_END__"

STAGES: list[str] = []


def _stage(name: str) -> None:
    """阶段标记逐行写出并立即 flush；native 崩溃时已输出的行仍可被父进程读到。"""
    STAGES.append(name)
    sys.stdout.write("[WORKER] %s\n" % name)
    sys.stdout.flush()


def _emit(payload: dict) -> None:
    """载荷写入后立即 flush，保证父进程能拿到完整 JSON。"""
    payload = dict(payload)
    payload["stages"] = list(STAGES)
    sys.stdout.write(BEGIN + "\n")
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.write(END + "\n")
    sys.stdout.flush()


def _evidence_name(raw: str) -> str:
    """把父进程传来的证据名再压一遍：只保留单段 basename。

    父进程已经清洗过；这里再做一次是为了让本 worker 即使被单独调用
    （例如未来新增调用方）也不会把 ``../`` 带进临时目录。
    """
    name = Path(str(raw or "")).name.replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(
        "_" if (ch in '<>:"/\\|?*' or ord(ch) < 32) else ch for ch in name)
    name = name.strip(" .")
    if name in ("", ".", ".."):
        name = "upload"
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name


def _link_for_evidence(physical: Path, evidence: str) -> tuple[Path, Path]:
    """在私有临时目录内建立证据名 -> 物理文件的硬链接（失败则复制）。"""
    tmp_dir = Path(tempfile.mkdtemp(prefix="icpdf-cls-"))
    target = tmp_dir / evidence
    if not target.resolve().is_relative_to(tmp_dir.resolve()):
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise RuntimeError("证据名越界：%s 不在 %s 内" % (target, tmp_dir))
    try:
        os.link(physical, target)
    except OSError:
        # 跨卷 / 文件系统不支持硬链接时退回复制；字节完全相同，SHA-256 不变。
        shutil.copyfile(physical, target)
    return tmp_dir, target


def main(argv: list[str]) -> None:
    _stage("WORKER_STARTED")
    spec = json.loads(argv[1])
    src_dir = Path(spec["src_dir"])
    physical = Path(spec["pdf_path"])
    evidence = _evidence_name(spec.get("original_filename") or physical.name)

    # 分类模块不依赖 PyYAML，只需把仓库源码加入 sys.path。
    # 与 parse_worker.py 不同，这里刻意不注入 _deps：分类链不得悄悄
    # 依赖解析器侧的隔离环境，也不得借分类之名加载 Parser 依赖。
    sys.path.insert(0, str(src_dir))

    from icpdf.classification.classifier import classify_one

    tmp_dir, target = _link_for_evidence(physical, evidence)
    _stage("EVIDENCE_LINK_READY")
    try:
        _stage("CLASSIFIER_CALL_ENTERED")
        # 交给分类器的是临时目录里的证据名链接，不是 uploads 下的物理名。
        record = classify_one(str(target))
        _stage("CLASSIFIER_CALL_RETURNED")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    _stage("EVIDENCE_LINK_REMOVED")

    _emit({
        "ok": True,
        "classifier_call_entered": True,
        "entry_point": "icpdf.classification.classifier.classify_one",
        "evidence_filename": evidence,
        "physical_path": str(physical),
        "record": record,
    })


if __name__ == "__main__":
    try:
        main(sys.argv)
    except Exception as exc:  # noqa: BLE001  需把异常类型与文本回传给父进程分类
        _stage("CLASSIFIER_CALL_FAILED")
        _emit({
            "ok": False,
            "classifier_call_entered": "CLASSIFIER_CALL_ENTERED" in STAGES,
            "error_type": type(exc).__name__,
            "error": str(exc),
        })
        sys.exit(1)
