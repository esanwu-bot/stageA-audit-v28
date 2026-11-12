# -*- coding: utf-8 -*-
"""把 V003 修复同步进 Batch 3 审计包，并重建 SHA256SUMS / ZIP。

为什么单独写一个同步脚本：手工 cp 最容易漏掉「删旧图」「重算校验」「ZIP 里
也要带上新的 SHA256SUMS」这三步。之前 CRLF 把 sha256sum -c 全线搞挂过一次，
这里全部用 LF、全部按磁盘实算、最后再做一遍自检，不靠记忆。
"""
from __future__ import print_function

import hashlib
import shutil
import zipfile
from pathlib import Path

PREP = Path(__file__).resolve().parent
DST = Path(r"E:\workspace\github\stageA-audit-v28\gate6a-plan\batch3_review")

# 源 → 审计包（相对路径）。INDEX.md 在审计包里直接改，不从工作区覆盖。
SYNC = [
    "Batch3_B2_DRAFT.csv",
    "Batch3_B2_Viewer.html",
    "Batch3_V003_diagnosis.txt",
    "_build_batch3_interactive.py",
    "_fix_v003_b2.py",
    "_sync_batch3_review.py",
    "annotation_reports/V003/b3_AMR_p0101.png",
    "annotation_reports/V003/b3_ROC_p0105.png",
    "annotation_reports/V003/b3_ROC_p0106.png",
]
DROP = ["annotation_reports/V003/b3_ELC_p0014.png"]   # 旧错页图，留着会误导
EXCLUDE = {"SHA256SUMS.txt", "Batch3_review.zip"}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def payloads():
    out = []
    for p in DST.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(DST).as_posix()
        if rel in EXCLUDE:
            continue
        out.append(rel)
    return sorted(out)


def main():
    assert DST.is_dir(), "审计目录不存在：%s" % DST
    for rel in SYNC:
        src = PREP / rel
        dst = DST / rel
        assert src.is_file(), "缺少源文件：%s" % src
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        assert sha(src) == sha(dst), "复制后哈希不一致：%s" % rel
        print("  同步 %-58s %8d 字节" % (rel, dst.stat().st_size))
    for rel in DROP:
        p = DST / rel
        if p.exists():
            p.unlink()
            print("  删除 %-58s （旧错页图）" % rel)

    # 裁图数量回归：B1 15 张 + B2 16 张 = 31 张
    pngs = sorted(p for p in DST.rglob("b3_*.png") if p.is_file())
    print("  裁图总数: %d（应为 31）" % len(pngs))
    assert len(pngs) == 31, "裁图数量不对"
    assert not any("p0014.png" in p.name and "V003" in str(p) for p in pngs), \
        "V003 旧错页图还在审计包里"

    files = payloads()
    print("  载荷文件: %d 个" % len(files))

    # SHA256SUMS.txt：LF 换行，一空格 + 星号（二进制模式），与上一版格式一致。
    lines = ["%s *./%s" % (sha(DST / rel), rel) for rel in files]
    sums = DST / "SHA256SUMS.txt"
    with open(sums, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")

    # ZIP：载荷 + SHA256SUMS.txt 自身；不含 ZIP 自己，避免循环。
    zpath = DST / "Batch3_review.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in files + ["SHA256SUMS.txt"]:
            z.write(DST / rel, rel)

    # 自检 1：清单逐条重算（等价于 sha256sum -c）
    with open(sums, "rb") as fh:
        raw = fh.read()
    assert b"\r\n" not in raw, "SHA256SUMS.txt 出现 CRLF，sha256sum -c 会全线 FAILED"
    ok = 0
    for line in raw.decode("utf-8").splitlines():
        digest, path = line.split(" *", 1)
        assert sha(DST / path[2:]) == digest, "校验失败：%s" % path
        ok += 1
    # 自检 2：ZIP 内每个条目的字节与工作区一致
    with zipfile.ZipFile(zpath) as z:
        names = z.namelist()
        assert len(names) == len(files) + 1, "ZIP 条目数不对"
        for name in names:
            assert z.read(name) == (DST / name).read_bytes(), "ZIP 内容不一致：%s" % name
    print("  校验: sha256sum -c %d/%d OK；ZIP %d 项逐字节一致"
          % (ok, ok, len(names)))
    print("  %s  %d 字节  SHA-256 %s"
          % (zpath.name, zpath.stat().st_size, sha(zpath)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
