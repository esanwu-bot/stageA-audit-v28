# -*- coding: utf-8 -*-
"""validate_annotation.py 自测（配合 v1.4）：21 行故意做坏的标注 + 1 个篡改场景。

为什么要自测
------------
机检脚本最怕"全都 OK"——那可能是检查根本没生效。这里每一行都埋一个已知的错，
期望值与实测值不一致就退出码 1。

两类用例
--------
* 前 14 例跑真实页文本（page_text.json），覆盖改名、改值、改单位、改型号；
* 后 5 例用一份**合成页文本**（样本 V900），专治"页面上只印了一半"这种情形：
  只有 -2.5 却没有 +2.5、两个端点分列但没有 to 结构。真实语料里未必有人这么写，
  但脚本必须能拦住——这几例就是审稿人要求的反例。
* 最后一个场景是**篡改 PDF**：复制一份真 PDF、在末尾追加字节改变哈希，
  再用 PDF 模式跑，要求判 ERROR（溯源哈希不符）。这一项单跑，因为要独立的 PDF 目录。
"""
import copy
import csv
import os
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOLD = HERE / "Batch2_GOLD_v1.csv"
PAGE_TEXT = HERE / "page_text.json"
PROVENANCE = HERE / "Batch2_PDF_PROVENANCE.csv"
SCRIPT = HERE / "validate_annotation.py"

# ---------- 合成样本：页文本由我们控制，专门造"半对半错"的页面 ----------
SYN_SAMPLE = {
    "file_name": "synthetic_test.pdf",
    "device_model": "TESTDEV",
    "sha256": "0" * 64,            # 合成样本没有真 PDF，给个占位哈希保证三处一致
    "size_bytes": 0,
    "page_count": 6,
    "pages": {
        "1": "TESTDEV Quad Low Power Data Sheet",
        # 只有负号，没有正号 —— 验 ±2.5 应当报错
        "2": "Absolute Maximum Ratings Differential input voltage VID -2.5 V",
        # 两个端点都在，但分列印，没有 to 结构 —— 验范围应当报错
        "3": "Supply range VCC -0.5 7 V",
        # 规范的区间写法
        "4": "Supply range VCC -0.5 to 7 V",
        # 规范的 ± 写法
        "5": "Differential input voltage VID ±2.5 V",
        # 分列的正负号写法
        "6": "Differential input voltage VID +2.5 V -2.5 V",
    },
}

SYN_BASE = {
    "sample_no": "V900",
    "file_name": "synthetic_test.pdf",
    "device_model": "TESTDEV",
    "table_title": "Synthetic",
    "symbol": "VID",
    "parameter_name": "Differential input voltage",
    "min_value": "", "typ_value": "", "max_value": "",
    "unit": "V",
    "row_status": "CONFIRMED",
    "notes": "合成用例",
    "reviewer": "selftest",
    "confidence_score": "0.90",
}

# (说明, 页码, 覆盖字段, 期望判定) —— 全部基于 V900 合成页
SYN_CASES = [
    ("反例：页面只有 -2.5，验 ±2.5 必须报错", "2",
     {"typ_value": "±2.5"}, "ERROR"),
    ("正例：页面写着 ±2.5", "5", {"typ_value": "±2.5"}, "OK"),
    ("正例：页面分列 +2.5 与 -2.5", "6", {"typ_value": "±2.5"}, "OK"),
    ("反例：两端点分列、没有 to 结构，验范围必须报错", "3",
     {"parameter_name": "Supply range", "symbol": "VCC", "min_value": "-0.5 to 7"}, "ERROR"),
    ("正例：页面写着 -0.5 to 7", "4",
     {"parameter_name": "Supply range", "symbol": "VCC", "min_value": "-0.5 to 7"}, "OK"),
]

# (说明, 样本, 页码, 覆盖字段, 期望判定) —— 基于真实 Gold 与真实页文本
CASES = [
    ("原样 Gold 行（V101 VIH 1.5V @2V）", "V101", 3, {}, "OK"),
    ("参数名被截断成残词 volta", "V101", 3,
     {"parameter_name": "High Level Input volta"}, "SUSPECT"),
    ("把条件当参数名 VNEG_IN_x", "V145", 12,
     {"parameter_name": "VNEG_IN_x", "symbol": "VNEG_IN_x"}, "SUSPECT"),
    ("数值写公式 VCC-0.2", "V101", 3, {"min_value": "VCC-0.2"}, "ERROR"),
    ("数值写 MIN(2.1, AVDD+0.3)", "V101", 3, {"min_value": "MIN(2.1, AVDD+0.3)"}, "ERROR"),
    ("数值写 Continuous", "V101", 3, {"min_value": "Continuous"}, "ERROR"),
    ("数值混单位 0.5V", "V101", 3, {"min_value": "0.5V"}, "ERROR"),
    ("正负值 ±2.5（真实页面就印 ±2.5）", "V097", 3,
     {"min_value": "", "typ_value": "±2.5", "max_value": ""}, "OK"),
    ("范围 -0.5 to 7（真实页面有该结构）", "V101", 3,
     {"min_value": "-0.5 to 7", "max_value": ""}, "OK"),
    ("值 5.9 填错页（p1 是封面）", "V101", 1,
     {"min_value": "5.9", "max_value": ""}, "ERROR"),
    ("整行与第 2 行完全重复", "V101", 3, {}, "SUSPECT"),
    ("CONFIRMED 却没签名", "V101", 3, {"reviewer": ""}, "ERROR"),
    ("单位写成页面上没有的 dBm", "V101", 3, {"unit": "dBm"}, "ERROR"),
    # v1.4 起，型号与溯源表不一致属于"溯源不一致"，直接 ERROR（比"封面找不到"更严重）
    ("型号与溯源不一致（ADC9999 vs ADC3544）", "V349", 5,
     {"device_model": "ADC9999"}, "ERROR"),
    ("空符号但没填裁定码", "V101", 3, {"symbol": ""}, "SUSPECT"),
    ("裁定码写成不存在的 BOGUS", "V101", 3,
     {"symbol": "", "human_adjudication": "BOGUS"}, "ERROR"),
]


def load_gold():
    with open(GOLD, encoding="utf-8-sig", newline="") as fh:
        rd = csv.DictReader(fh)
        return rd.fieldnames, list(rd)


def build_rows(cols, gold_rows):
    first = {}
    for r in gold_rows:
        first.setdefault(r["sample_no"], r)

    rows, expects = [], []
    for i, (name, sno, page, patch, want) in enumerate(CASES, start=1):
        r = dict(first[sno])
        r["evidence_page"] = str(page)
        r.update(patch)
        if "重复" in name:
            r = dict(rows[0])                 # 与第 1 例完全一致，才叫重复
        else:
            # 每例加唯一条件，免得被"重复行"规则误伤（重复用例本身除外）
            r["condition"] = (r.get("condition") or "") + " #case%d" % i
        rows.append(r)
        expects.append((name, want))

    for i, (name, page, patch, want) in enumerate(SYN_CASES, start=len(CASES) + 1):
        r = dict(SYN_BASE)
        r["evidence_page"] = page
        r["condition"] = "synthetic #s%d" % i
        r.update(patch)
        rows.append({c: r.get(c, "") for c in cols})
        expects.append((name, want))
    return rows, expects


def tamper_test():
    """篡改 PDF：往文件尾追加几个字节，哈希必变，但 PDF 仍可解析。

    审稿人要求：哈希不符必须直接 ERROR，而不是"照常核对页内文字"。
    """
    import shutil
    pdf_dir = os.environ.get("ICPDF_PDF_DIR")
    src = Path(pdf_dir) / "CD74HCT574EE4__schs183c.pdf" if pdf_dir else None
    if not src or not src.exists():
        return ("篡改 PDF 后哈希不符", "ERROR", "跳过（未设 ICPDF_PDF_DIR）", "SKIP",
                "需提供 PDF 目录")

    cols, gold_rows = load_gold()
    v101 = [r for r in gold_rows if r["sample_no"] == "V101"]

    with tempfile.TemporaryDirectory() as td:
        tmp_pdf_dir = Path(td) / "pdfs"
        tmp_pdf_dir.mkdir()
        dst = tmp_pdf_dir / src.name
        shutil.copyfile(src, dst)
        with open(dst, "ab") as fh:
            fh.write(b"\n% tampered for selftest\n")

        tmp_csv = Path(td) / "v101.csv"
        with open(tmp_csv, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
            w.writeheader()
            w.writerows(v101)

        proc = subprocess.run([sys.executable, str(SCRIPT), "--csv", str(tmp_csv),
                               "--pdf-dir", str(tmp_pdf_dir)],
                              capture_output=True, text=True, encoding="utf-8")
    out = (proc.stdout or "") + (proc.stderr or "")
    got = "缺失"
    for line in out.splitlines():
        m = re.match(r"\[(\w+)\s*\] 行(\d+)", line)
        if m and int(m.group(2)) == 2:
            got = m.group(1)
            break
    hit = "哈希不符" in out
    note = "已提示哈希不符" if hit else "未提示哈希"
    return ("篡改 PDF 后哈希不符", "ERROR", got,
            "PASS" if got == "ERROR" and hit else "FAIL", note)


def main():
    cols, gold_rows = load_gold()
    rows, expects = build_rows(cols, gold_rows)

    # 合成页文本并进真实 page_text.json，只在这一份临时副本里生效
    sidecar = json.loads(PAGE_TEXT.read_text(encoding="utf-8"))
    sidecar = copy.deepcopy(sidecar)
    sidecar["samples"]["V900"] = SYN_SAMPLE

    with tempfile.TemporaryDirectory() as td:
        tmp_csv = Path(td) / "selftest.csv"
        tmp_json = Path(td) / "page_text.json"
        with open(tmp_csv, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        tmp_json.write_text(json.dumps(sidecar, ensure_ascii=False), encoding="utf-8")

        # 三处一致性检查要求 provenance 表也包含合成样本，否则 V900 会被判"表里缺条目"
        with open(PROVENANCE, encoding="utf-8-sig", newline="") as fh:
            prd = csv.DictReader(fh)
            prov_cols = prd.fieldnames
            prov_rows = list(prd)
        prov_rows.append({"sample_no": "V900", "device_model": "TESTDEV",
                          "file_name": "synthetic_test.pdf", "sha256": "0" * 64,
                          "page_count": "6", "size_bytes": "0"})
        tmp_prov = Path(td) / "provenance.csv"
        with open(tmp_prov, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=prov_cols, lineterminator="\n")
            w.writeheader()
            w.writerows(prov_rows)

        # 主用例强制走离线 sidecar：环境里若设了 ICPDF_PDF_DIR，会让验证器优先用 PDF，
        # 而合成样本 V900 根本没有对应 PDF 文件。
        env = {k: v for k, v in os.environ.items() if k != "ICPDF_PDF_DIR"}
        proc = subprocess.run([sys.executable, str(SCRIPT), "--csv", str(tmp_csv),
                               "--page-text", str(tmp_json), "--provenance", str(tmp_prov)],
                              capture_output=True, text=True, encoding="utf-8", env=env)
    out = (proc.stdout or "") + (proc.stderr or "")
    got = {}
    for line in out.splitlines():
        m = re.match(r"\[(\w+)\s*\] 行(\d+)", line)
        if m:
            got[int(m.group(2))] = m.group(1)

    print("=" * 92)
    print("%-48s %-8s %-8s %s" % ("用例", "期望", "实测", "结果"))
    print("=" * 92)
    bad = 0
    for i, (name, want) in enumerate(expects, start=2):
        have = got.get(i, "缺失")
        ok = have == want
        bad += 0 if ok else 1
        print("%-48s %-8s %-8s %s" % (name[:48], want, have, "PASS" if ok else "FAIL"))
    name, want, have, verdict, note = tamper_test()
    print("%-48s %-8s %-8s %s（%s）" % (name[:48], want, have, verdict, note))
    if verdict == "FAIL":
        bad += 1
    elif verdict == "SKIP":
        print("   （要跑这一项：ICPDF_PDF_DIR=/path/to/pdfs python %s）"
              % Path(__file__).name)
    total = len(expects) + 1
    print("=" * 92)
    print("用例 %d（真实页文本 %d + 合成页文本 %d + 篡改场景 1），通过 %d，失败 %d"
          % (total, len(CASES), len(SYN_CASES), total - bad, bad))
    if bad:
        print()
        print("---- 机检原始输出 ----")
        print(out)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
