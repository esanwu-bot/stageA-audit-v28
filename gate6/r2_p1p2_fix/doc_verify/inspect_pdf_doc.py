"""只读文档级核验：元数据 + 关键页文本 + 芯片参数/EVM 特征词命中。

严格只读：
* 不 import `icpdf.parser.*`、不调用 `parse_pdf()`、不调用 `classify_one()`；
* 不写任何文件到 runs/ 或 uploads/；
* 只用 PyMuPDF 打开 PDF 读取元数据与文本层。

用法：
    py -3.13 inspect_pdf_doc.py <pdf> [<pdf> ...]
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

try:  # 新版包名；旧版只有 fitz，会打 FutureWarning 污染 stdout
    import pymupdf as fitz
except ImportError:  # pragma: no cover
    import fitz  # type: ignore[no-redef]

# 芯片 Datasheet 的强特征（正文出现即说明是器件级参数文档）
DS_MARKERS = (
    "Absolute Maximum Ratings",
    "Electrical Characteristics",
    "Recommended Operating Conditions",
    "Pin Configuration",
    "Pin Functions",
    "Switching Characteristics",
    "Thermal Information",
    "Package Outline",
    "Device Information",
)

# EVM / 评估板 / 用户指南的强特征
EVM_MARKERS = (
    "Evaluation Module",
    "Evaluation Board",
    "User's Guide",
    "Users Guide",
    "Bill of Materials",
    "Schematic",
    "PCB Layout",
    "Jumper",
    "Header",
    "Quick Start",
    "Setup and Configuration",
    "Hardware Setup",
)

TOC_RE = re.compile(r"(table of contents|^\s*contents\s*$)", re.IGNORECASE)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def clean(text: str, limit: int) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:limit]


def inspect(path: Path) -> dict:
    doc = fitz.open(str(path))
    try:
        meta = doc.metadata or {}
        pages = doc.page_count
        first = clean(doc[0].get_text("text"), 1400) if pages else ""
        second = clean(doc[1].get_text("text"), 1400) if pages > 1 else ""
        last = clean(doc[pages - 1].get_text("text"), 900) if pages else ""

        toc_page_no = None
        toc_text = ""
        for i in range(min(pages, 8)):
            t = doc[i].get_text("text")
            if TOC_RE.search(t):
                toc_page_no = i + 1
                toc_text = clean(t, 1200)
                break

        head_text = "\n".join(doc[i].get_text("text") for i in range(min(pages, 6)))
        full_text = "\n".join(doc[i].get_text("text") for i in range(pages))
        ds_hits = {m: full_text.count(m) for m in DS_MARKERS if m in full_text}
        evm_hits = {m: full_text.lower().count(m.lower())
                    for m in EVM_MARKERS if m.lower() in full_text.lower()}
        ds_head = {m: head_text.count(m) for m in DS_MARKERS if m in head_text}
        evm_head = {m: head_text.lower().count(m.lower())
                    for m in EVM_MARKERS if m.lower() in head_text.lower()}

        return {
            "file": path.name,
            "path": str(path),
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
            "pages": pages,
            "metadata": {
                "title": meta.get("title") or "",
                "subject": meta.get("subject") or "",
                "author": meta.get("author") or "",
                "creator": meta.get("creator") or "",
                "producer": meta.get("producer") or "",
                "creationDate": meta.get("creationDate") or "",
                "modDate": meta.get("modDate") or "",
                "format": meta.get("format") or "",
            },
            "page1_text": first,
            "page2_text": second,
            "toc_page_no": toc_page_no,
            "toc_text": toc_text,
            "last_page_text": last,
            "ds_markers_in_first_6_pages": ds_head,
            "evm_markers_in_first_6_pages": evm_head,
            "ds_markers_whole_doc": ds_hits,
            "evm_markers_whole_doc": evm_hits,
            "text_layer_chars": len(full_text),
        }
    finally:
        doc.close()


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: inspect_pdf_doc.py <pdf> [...]")
        return 2
    out = []
    for raw in argv[1:]:
        p = Path(raw)
        if not p.is_file():
            print("[MISSING] %s" % p)
            continue
        out.append(inspect(p))
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
