# -*- coding: utf-8 -*-
"""把 V003 修复同步进 Batch 3 审计包，并重建 SHA256SUMS / ZIP。

为什么单独写一个同步脚本：手工 cp 最容易漏掉「删旧图」「重算校验」「ZIP 里
也要带上新的 SHA256SUMS」这三步。之前 CRLF 把 sha256sum -c 全线搞挂过一次，
这里全部用 LF、全部按磁盘实算、最后再做一遍自检，不靠记忆。

顺序约束（第七轮补齐时踩到）：本脚本按审计目录现有文件打包，
所以**本轮 *.diff 必须先在本目录生成、再跑同步**，否则 ZIP 会缺 diff
而上一轮的 diff 反倒在包里，出现「同包内自洽性不一致」。
"""
from __future__ import print_function

import hashlib
import os
import shutil
import zipfile
from pathlib import Path

PREP = Path(__file__).resolve().parent
DST = Path(r"E:\workspace\github\stageA-audit-v28\gate6a-plan\batch3_review")

# 源 → 审计包（相对路径）。INDEX.md 在审计包里直接改，不从工作区覆盖。
SYNC = [
    # B1 第二轮：表头归属、授权链、真源口径、最终复跑
    "Batch3_B1_RESIGNED.csv",
    "Batch3_B1_RESIGNED.xlsx",
    "_make_b1_resigned.py",
    "_build_batch3_b1_report.py",
    "Batch3_B1_validation_report.txt",
    "b1_validation_raw/b1_final_pdf_mode.txt",
    "b1_validation_raw/b1_final_sidecar_mode.txt",
    # B2：V003 重截 + PM 裁定的 condition
    "Batch3_B2_DRAFT.csv",
    "Batch3_B2_Viewer.html",
    "Batch3_V003_diagnosis.txt",
    # CORE_ORDER 正则 + prescan3 表头加固与回归测试
    "_build_batch3_interactive.py",
    "_test_core_order_and_header.py",
    "Batch3_CORE_ORDER_regression.txt",
    "Batch3_validator_selftest.txt",
    "_fix_v003_b2.py",
    "_sync_batch3_review.py",
    # 第三轮：B1 过期备注清理与复跑
    "Batch3_B1_RESIGNED_pre_notes_cleanup.xlsx",
    "_clean_b1_notes.py",
    "b1_validation_raw/b1_notes_clean_pdf_mode.txt",
    "b1_validation_raw/b1_notes_clean_sidecar_mode.txt",
    # 第三轮：B2 最终定稿（不再只有 DRAFT）与机检
    "Batch3_B2_SIGNED_original.xlsx",
    "Batch3_B2_FINAL.csv",
    "Batch3_B2_FINAL.xlsx",
    "Batch3_B2_notes_before_cleanup.txt",
    "page_text_batch3_b2.json",
    "Batch3_B2_PDF_PROVENANCE.csv",
    "Batch3_B2_validation_report.txt",
    "b2_validation_raw/b2_final_pdf_mode.txt",
    "b2_validation_raw/b2_final_sidecar_mode.txt",
    "_make_b2_final.py",
    "_build_batch3_b2_report.py",
    # 第三轮：prescan3 极端场景与真实 PDF 候选页回归
    "_verify_v003_candidates.py",
    "Batch3_prescan3_v003_evidence.txt",
    "annotation_reports/V003/b3_AMR_p0101.png",
    "annotation_reports/V003/b3_ROC_p0105.png",
    "annotation_reports/V003/b3_ROC_p0106.png",
    # 第六轮：B2 授权链封卷（错位撤销 → 正确补签 → 最终机检）
    "Batch3_B2_FINAL_TO_SIGN.xlsx",
    "Batch3_B2_FINAL_SIGNED_correct.xlsx",
    "Batch3_B2_FINAL_SIGNED_approval.xlsx",
    "Batch3_B2_FINAL_pre_approval.xlsx",
    "Batch3_B2_APPROVAL_TARGETS.txt",
    "Batch3_B2_approval_revoke_note.txt",
    "Batch3_B2_approval_authorization.txt",
    "_sync_b2_approval.py",
    "_b2_approval_reset.py",
    "_b2_final_seal.py",
    # 第七轮：跨页污染隔离 + 页级分流 + 签名 Fail-Closed + 真正的 B3 圈选台
    "_test_b2_approval.py",
    "Batch3_B2_approval_regression.txt",
    "Batch3_B2_regeneration.txt",
    "Batch3_B3_generation.txt",
    "Batch3_Viewer.html",               # 正式交付：真正的 B3 六件
    "Batch3_DRAFT.csv",
    "Batch3_B1_Viewer.html",            # B1 旧圈选台留痕（不再冒充交付）
    "Batch3_B1_DRAFT.csv",
    "Batch3_B3_Viewer.html",            # B3 专属副本（与正式版同字节）
    "Batch3_B3_DRAFT.csv",
    "Batch3_BATCH_PLAN.csv",
    # 第七轮补齐（Reviewer 两条硬伤）：clip 静默降级改 Fail-Closed + V256 condition 逐行绑定
    "Batch3_V003_regression.txt",
    "Batch3_DRAFT_before_condition_backfill.csv",
    "Batch3_Viewer_before_condition_backfill.html",
    # 第八轮：B3 定稿（notes 清理 + 19 列 FINAL + v1.6 双模式 + 5 格待补签）
    "_make_b3_final.py",
    "Batch3_B3_FINAL.csv",
    "Batch3_B3_FINAL.xlsx",
    "Batch3_B3_FINAL_TO_SIGN.xlsx",
    "Batch3_B3_SIGNED_original.xlsx",
    "Batch3_B3_notes_before_cleanup.txt",
    "Batch3_B3_APPROVAL_PENDING.txt",
    "Batch3_B3_PDF_PROVENANCE.csv",
    "Batch3_B3_regen_report.txt",
    "page_text_batch3_b3.json",
    "b3_validation_raw/b3_final_pdf_mode.txt",
    "b3_validation_raw/b3_final_sidecar_mode.txt",
    # 第九轮：B3 封卷（5 处 PM 补签按稳定 ID 继承）
    "Batch3_B3_FINAL_SIGNED.xlsx",
    "Batch3_B3_APPROVAL_TARGETS.txt",
    "Batch3_B3_approval_authorization.txt",
    "Batch3_B3_FINAL_pre_seal.csv",
    "_b3_regen_report.py",
    # B3 圈选台左图依赖：9 张裁图必须与 HTML 同包，否则解压后看不到图
    "annotation_reports/V146/b3_ELC_p0004.png",
    "annotation_reports/V244/b3_ELC_p0047.png",
    "annotation_reports/V244/b3_ROC_p0044.png",
    "annotation_reports/V256/b3_AMR_p0008.png",
    "annotation_reports/V256/b3_ELC_p0013.png",
    "annotation_reports/V256/b3_ROC_p0009.png",
    "annotation_reports/V271/b3_AMR_p0117.png",
    "annotation_reports/V271/b3_ELC_p0123.png",
    "annotation_reports/V271/b3_ROC_p0150.png",
    # 第十轮：B4 圈选台（V077/V130/V290 出草稿；V347/V041 逐件 EXCLUDED 理由）
    "Batch3_B4_Viewer.html",
    "Batch3_B4_DRAFT.csv",
    "Batch3_B4_generation.txt",
    # B4 圈选台左图依赖：4 张裁图必须与 HTML 同包
    "annotation_reports/V077/b3_ELC_p0040.png",
    "annotation_reports/V077/b3_ROC_p0038.png",
    "annotation_reports/V130/b3_ELC_p0002.png",
    "annotation_reports/V290/b3_ELC_p0003.png",
    # 第十轮：SCAN 三件登记表（无文本层，EXCLUDED，附 hash/页数溯源）
    "_make_scan_manifest.py",
    "Batch3_SCAN_MANIFEST.csv",
    "Batch3_SCAN_manifest.txt",
    "Batch3_SCAN_Viewer.html",
    "Batch3_SCAN_DRAFT.csv",
    "Batch3_SCAN_generation.txt",
    # 第十轮：write_xlsx 内容幂等（封卷件不因 openpyxl 时间戳漂移而改字节）
    "_patch_idem.py",
    # 第十一轮：封卷保护改硬哈希（废弃内容签名软比较）+ 七场景回归
    "_patch_hardhash_1.py",
    "_patch_hardhash_2.py",
    "_test_seal_guard.py",
    "Batch3_seal_guard_test.txt",
    # 第十一轮：B4 条件绑定与非白名单标注
    "_patch_b4_round2.py",
    "_b2_app.js",                       # 圈选台前端逻辑；状态枚举改为三类话术
    # 第十一轮：33 件总清单
    "_make_master_inventory.py",
    "Batch3_MASTER_INVENTORY.csv",
    "Batch3_MASTER_INVENTORY.txt",
    # 第十二轮：B4 封卷（14 行定稿 / 双模式 OK=14 / 硬哈希登记）
    "_make_b4_final.py",
    "Batch3_B4_ANNOTATED.xlsx",         # PM 14:04 签字件（唯一有效签字凭据）
    "Batch3_B4_FINAL.csv",
    "Batch3_B4_FINAL.xlsx",
    "Batch3_B4_PDF_PROVENANCE.csv",
    "page_text_batch3_b4.json",
    "Batch3_B4_approval_record.txt",
    "b4_validation_raw/b4_final_pdf_mode.txt",
    "b4_validation_raw/b4_final_sidecar_mode.txt",
    # 第十三轮：Reviewer 三处 P0
    "_patch_b4_v2.py",                  # 签字源闸门 + condition 按符号块回填
    "_test_b4_signed_gate.py",          # 闸门正/负向回归（15 项断言）
    "Batch3_b4_signed_gate_test.txt",
    # 第十三轮：PM 在签字件上手改后，定稿事实源改为签字 xlsx 本身
    "_final_from_signed_xlsx.py",       # 签字 xlsx -> CSV / sidecar / provenance
    "_diff_pm_edit.py",                 # PM 手改与上一版定稿的逐格差异（留证）
    "Batch3_B4_approval_record_r13.txt",
    # 第十三轮追加：新事实源脚本的定向测试（六场景 29 项断言）
    "_test_b4_final_from_signed.py",
    "Batch3_b4_final_from_signed_test.txt",
]
DROP = ["annotation_reports/V003/b3_ELC_p0014.png"]   # 旧错页图，留着会误导
B3_SNOS = {"V146", "V222", "V244", "V256", "V271", "V328"}
EXCLUDE = {"SHA256SUMS.txt", "Batch3_review.zip"}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_preserving(src, dst):
    """目标被 Excel / 预览占用时 shutil.copy2 会 WinError 32。

    改成「写同目录临时文件 + os.replace 原子替换」。若目标仍被独占、
    replace 也失败，只有在**源文件与目标字节完全一致**时才允许跳过，
    并把这个事实返回给调用方打印出来 —— 绝不静默放过内容不一致的文件。
    """
    tmp = dst.with_name(dst.name + ".wb_tmp")
    try:
        shutil.copy2(src, tmp)
        try:
            os.replace(tmp, dst)
            return "覆盖"
        except PermissionError:
            if sha(src) == sha(dst):
                return "跳过（目标被占用，字节一致）"
            raise PermissionError(
                "目标被占用且内容不一致，拒绝静默跳过：%s" % dst)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


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
        how = copy_preserving(src, dst)
        assert sha(src) == sha(dst), "%s 后哈希不一致：%s" % (how, rel)
        print("  同步 %-58s %8d 字节  %s" % (rel, dst.stat().st_size, how))
    for rel in DROP:
        p = DST / rel
        if p.exists():
            p.unlink()
            print("  删除 %-58s （旧错页图）" % rel)

    # 裁图数量回归：B1 15 + B2 16 = 31 张，B3 9 张，第十轮新增 B4 4 张 = 44 张
    pngs = sorted(p for p in DST.rglob("b3_*.png") if p.is_file())
    old = [p for p in pngs if p.parent.name not in B3_SNOS]
    new = [p for p in pngs if p.parent.name in B3_SNOS]
    print("  裁图总数: %d（B1/B2/B4 %d 张 + B3 %d 张）"
          % (len(pngs), len(old), len(new)))
    assert len(old) == 35 and len(new) == 9, \
        "裁图数量不对：非 B3 %d（应 35）/ B3 %d（应 9）" % (len(old), len(new))
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
