# -*- coding: utf-8 -*-
"""validate_annotation.py 自测（配合 v1.6）：31 个用例。

为什么要自测
------------
机检脚本最怕"全都 OK"——那可能是检查根本没生效。这里每一行都埋一个已知的错，
期望值与实测值不一致就退出码 1。

四类用例
--------
* 16 例跑真实页文本（page_text.json），覆盖改名、改值、改单位、改型号；
* 5 例用一份**合成页文本**（样本 V900），专治"页面上只印了一半"这种情形：
  只有 -2.5 却没有 +2.5、两个端点分列但没有 to 结构。真实语料里未必有人这么写，
  但脚本必须能拦住——这几例就是审稿人要求的反例。
* 1 个**篡改 PDF** 场景：复制一份真 PDF、在末尾追加字节改变哈希，
  再用 PDF 模式跑，要求判 ERROR（溯源哈希不符）。
* 9 个 **Fail-Open 负面用例**：溯源表缺失、空字段跳过互校、--pdf-dir 不存在、
  PDF 缺失、PDF 算不了哈希、哈希不符仍读文本（N1–N8），以及 v1.6 补的
  N9「内容损坏但哈希对得上」。
  N8 在同一进程里把 Pages.page_text 换成计数器，断言调用次数为 0——
  "哈希不符就不读页文本"这句话，只有数出来才算数。

关于 SKIP
---------
N8/N9 必须用真实 PDF，所以本脚本**要求** ICPDF_PDF_DIR。没给就直接失败退出，
不把"没跑"当"通过"：SKIP 单独计数，永不计入 PASS。
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
        return ("篡改 PDF 后哈希不符", "ERROR", "跳过（PDF 不可用）", "SKIP",
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


def _read_prov():
    with open(PROVENANCE, encoding="utf-8-sig", newline="") as fh:
        rd = csv.DictReader(fh)
        return rd.fieldnames, list(rd)


def _write_prov(path, rows, cols):
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def _write_csv(path, rows, cols):
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def _write_sidecar(path, mutate):
    data = copy.deepcopy(json.loads(PAGE_TEXT.read_text(encoding="utf-8")))
    mutate(data)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _run_cli(args):
    """跑验证器。强制清掉 ICPDF_PDF_DIR，免得环境变量把离线用例改成 PDF 模式。"""
    env = {k: v for k, v in os.environ.items() if k != "ICPDF_PDF_DIR"}
    proc = subprocess.run([sys.executable, str(SCRIPT)] + args,
                          capture_output=True, text=True, encoding="utf-8", env=env)
    return (proc.stdout or "") + (proc.stderr or ""), proc.returncode


def _v(ok):
    return "PASS" if ok else "FAIL"


def _label(code, cond):
    """实测列的写法：达标就写判定，没达标才写退出码，别让"期望 ERROR / 实测 退出码1"看着像没对上。"""
    if not cond:
        return "退出码%d（未达预期）" % code
    return "退出码2 + ERROR" if code == 2 else "ERROR"


def neg_tests():
    """Fail-Open 负面测试：N1–N9。

    每一例都构造"本该报错"的输入，断言它确实报错；只看退出码不看提示文字是不够的——
    还要断言输出里没有那句"跳过/降级"的自我安慰。
    """
    cols, gold_rows = load_gold()
    prov_cols, prov_rows = _read_prov()
    v101 = [r for r in gold_rows if r["sample_no"] == "V101"]
    res = []

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)

        # ---- N1：provenance 表读不到 → 退出码 2，且不许出现"跳过三处互校"
        out, code = _run_cli(["--csv", str(GOLD), "--page-text", str(PAGE_TEXT),
                              "--provenance", str(td / "no_such_prov.csv")])
        cond1 = (code == 2 and "[ERROR]" in out and "溯源表不存在" in out
                 and "跳过三处互校" not in out)
        res.append(("N1 provenance 表读不到", "退出码2 + ERROR", _label(code, cond1),
                    _v(cond1), "不再 notes 跳过"))

        # ---- N2：sidecar 的 file_name 为空（CSV 有值）→ 空字段必须报错，不能跳过
        sc2 = td / "sidecar_no_fname.json"

        def m2(d):
            d["samples"]["V101"]["file_name"] = ""

        _write_sidecar(sc2, m2)
        out, code = _run_cli(["--csv", str(GOLD), "--page-text", str(sc2),
                              "--provenance", str(PROVENANCE)])
        cond2 = code == 1 and "溯源不一致/缺失" in out and "file_name" in out
        res.append(("N2 sidecar file_name 空", "ERROR", _label(code, cond2),
                    _v(cond2), "空字段=ERROR"))

        # ---- N3：CSV 的 device_model 为空（sidecar 有值）→ 同样是 ERROR
        rows3 = [dict(r) for r in gold_rows]
        for r in rows3:
            if r["sample_no"] == "V101":
                r["device_model"] = ""
                break
        c3 = td / "gold_no_model.csv"
        _write_csv(c3, rows3, cols)
        out, code = _run_cli(["--csv", str(c3), "--page-text", str(PAGE_TEXT),
                              "--provenance", str(PROVENANCE)])
        cond3 = code == 1 and "溯源不一致/缺失" in out and "device_model" in out
        res.append(("N3 CSV device_model 空", "ERROR", _label(code, cond3),
                    _v(cond3), "空字段=ERROR"))

        # ---- N4：provenance 的 page_count 为空（sidecar 有值）→ 同样是 ERROR
        rows4 = [dict(r) for r in prov_rows]
        for r in rows4:
            if r["sample_no"] == "V101":
                r["page_count"] = ""
        p4 = td / "prov_no_pc.csv"
        _write_prov(p4, rows4, prov_cols)
        out, code = _run_cli(["--csv", str(GOLD), "--page-text", str(PAGE_TEXT),
                              "--provenance", str(p4)])
        cond4 = code == 1 and "溯源不一致/缺失" in out and "page_count" in out
        res.append(("N4 provenance page_count 空", "ERROR", _label(code, cond4),
                    _v(cond4), "空字段=ERROR"))

        # ---- N5：--pdf-dir 指向不存在的目录 → 退出码 2，绝不回落离线模式
        out, code = _run_cli(["--csv", str(GOLD), "--page-text", str(PAGE_TEXT),
                              "--provenance", str(PROVENANCE),
                              "--pdf-dir", str(td / "no_such_pdf_dir")])
        cond5 = (code == 2 and "[ERROR]" in out and "不存在" in out
                 and "使用随包的 page_text.json" not in out)
        res.append(("N5 --pdf-dir 目录不存在", "退出码2 + ERROR", _label(code, cond5),
                    _v(cond5), "不降级到离线"))

        # ---- N6：PDF 模式但目录里没有该样本的 PDF → ERROR，不是 CANNOT_VERIFY
        empty = td / "empty_pdfs"
        empty.mkdir()
        c6 = td / "v101_only.csv"
        _write_csv(c6, v101, cols)
        out, code = _run_cli(["--csv", str(c6), "--pdf-dir", str(empty),
                              "--page-text", str(PAGE_TEXT), "--provenance", str(PROVENANCE)])
        cond6 = code == 1 and "PDF 缺失" in out and "CANNOT_VERIFY" not in out
        res.append(("N6 PDF 文件缺失", "ERROR", _label(code, cond6),
                    _v(cond6), "不是 CANNOT_VERIFY"))

        # ---- N7：同名路径是目录，哈希算不出来 → ERROR
        conflict = td / "pdf_dir_conflict"
        conflict.mkdir()
        (conflict / v101[0]["file_name"]).mkdir()
        out, code = _run_cli(["--csv", str(c6), "--pdf-dir", str(conflict),
                              "--page-text", str(PAGE_TEXT), "--provenance", str(PROVENANCE)])
        cond7 = code == 1 and "无法计算哈希" in out
        res.append(("N7 PDF 无法计算哈希", "ERROR", _label(code, cond7),
                    _v(cond7), "打不开=ERROR"))

    # ---- N8：哈希不符 → 该样本全部行 ERROR，且 page_text() 一次都不调用
    res.append(hash_shortcircuit_test())
    # ---- N9：损坏 PDF（哈希对得上）→ 必须 ERROR，不能退化成 CANNOT_VERIFY
    res.append(corrupt_pdf_test())
    return res


def hash_shortcircuit_test():
    """N8：哈希不符时，page_text() 必须一次都不被调用。

    这条只能在同一进程里做——把 Pages.page_text 换成计数器再跑 main()，
    子进程里的调用次数没法从外面观测。断言 calls == []，就是"没读页文本"的硬证据。
    """
    import contextlib
    import importlib.util
    import io
    import shutil

    pdf_dir = os.environ.get("ICPDF_PDF_DIR")
    src = Path(pdf_dir) / "CD74HCT574EE4__schs183c.pdf" if pdf_dir else None
    if not src or not src.exists():
        return ("N8 哈希不符不读页文本", "page_text=0次", "跳过（PDF 不可用）",
                "SKIP", "需提供 PDF 目录")

    cols, gold_rows = load_gold()
    v101 = [r for r in gold_rows if r["sample_no"] == "V101"]

    spec = importlib.util.spec_from_file_location("va_under_test", str(SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    calls = []
    orig = mod.Pages.page_text

    def spy(self, sno, file_name, page_no):
        calls.append((sno, page_no))
        return orig(self, sno, file_name, page_no)

    mod.Pages.page_text = spy

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        tmp_pdf_dir = td / "pdfs"
        tmp_pdf_dir.mkdir()
        dst = tmp_pdf_dir / src.name
        shutil.copyfile(src, dst)
        with open(dst, "ab") as fh:
            fh.write(b"\n% tampered for selftest\n")   # 哈希必变，PDF 仍可解析

        tmp_csv = td / "v101.csv"
        _write_csv(tmp_csv, v101, cols)

        argv = ["validate_annotation.py", "--csv", str(tmp_csv),
                "--pdf-dir", str(tmp_pdf_dir), "--page-text", str(PAGE_TEXT),
                "--provenance", str(PROVENANCE)]
        old_argv = sys.argv
        sys.argv = argv
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                code = mod.main()
        finally:
            sys.argv = old_argv
            mod.Pages.page_text = orig

    out = buf.getvalue()
    ok = code == 1 and "哈希不符" in out and not calls
    return ("N8 哈希不符不读页文本", "page_text=0次",
            "page_text=%d次" % len(calls), _v(ok),
            "哈希门禁生效" if ok else "调用点: %s" % calls[:3])


def corrupt_pdf_test():
    """N9：内容损坏、但哈希算得出且对得上的 PDF。

    构造方式最狠的一步是"把哈希改成损坏文件的哈希"——这样哈希校验、三处互校全都通过，
    唯独 PDF 本身已经是残的（截断后 fitz 能打开，但 page_count=0）。

    这一例专治"只算哈希不打开文件"：
      v1.5 在这里落到 CANNOT_VERIFY、退出码 0（报告写"无 ERROR"）；
      v1.6 预检执行 open_doc()+page_count()，判样本级 ERROR、退出码 1。
    """
    import hashlib
    import shutil

    pdf_dir = os.environ.get("ICPDF_PDF_DIR")
    src = Path(pdf_dir) / "CD74HCT574EE4__schs183c.pdf" if pdf_dir else None
    if not src or not src.exists():
        return ("N9 损坏 PDF（哈希对得上）", "ERROR", "跳过（PDF 不可用）",
                "SKIP", "需提供 PDF 目录")

    cols, gold_rows = load_gold()
    prov_cols, prov_rows = _read_prov()
    v101 = [r for r in gold_rows if r["sample_no"] == "V101"]

    raw = src.read_bytes()
    broken = raw[: int(len(raw) * 0.30)]        # 截断：能打开，但没有一页
    digest = hashlib.sha256(broken).hexdigest()

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        pd = td / "pdfs"
        pd.mkdir()
        (pd / src.name).write_bytes(broken)

        # sidecar 与 provenance 的 sha256 都改成"坏文件的哈希"，
        # 让溯源检查全部通过——只剩"文件到底能不能读"这一件事没被覆盖
        (td / "pt.json").write_text(
            json.dumps(_side_with_sha("V101", digest), ensure_ascii=False), encoding="utf-8")
        rows2 = [dict(r) for r in prov_rows]
        for r in rows2:
            if r["sample_no"] == "V101":
                r["sha256"] = digest
        _write_prov(td / "prov.csv", rows2, prov_cols)

        csv_path = td / "v101.csv"
        _write_csv(csv_path, v101, cols)

        out, code = _run_cli(["--csv", str(csv_path), "--pdf-dir", str(pd),
                              "--page-text", str(td / "pt.json"),
                              "--provenance", str(td / "prov.csv")])

    opened_bad = ("页数为 0" in out) or ("PDF 打不开" in out)
    no_cannot = "CANNOT_VERIFY" not in out
    no_fallback = "使用随包的 page_text.json" not in out
    ok = code == 1 and opened_bad and no_cannot and no_fallback
    note = "预检 open+page_count 生效" if ok else (
        "退出码%s 打不开=%s 无CANNOT=%s 未降级=%s"
        % (code, opened_bad, no_cannot, no_fallback))
    return ("N9 损坏 PDF（哈希对得上）", "ERROR", _label(code, ok), _v(ok), note)


def _side_with_sha(sno, digest):
    data = copy.deepcopy(json.loads(PAGE_TEXT.read_text(encoding="utf-8")))
    data["samples"][sno]["sha256"] = digest
    return data


def main():
    # ---- 环境门槛：N8/N9 必须用真实 PDF。没有就直说"没跑完"，不拿 SKIP 充 PASS。
    pdf_dir = os.environ.get("ICPDF_PDF_DIR")
    if not pdf_dir or not Path(pdf_dir).is_dir():
        print("FAIL: 缺少 PDF 测试环境，测试不完整")
        print("      需要 ICPDF_PDF_DIR 指向 PDF 语料目录（N8/N9 依赖真实 PDF）。")
        print("      例：ICPDF_PDF_DIR=/path/to/pdfs python %s" % Path(__file__).name)
        return 2

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

    # 三种结果分开计数。SKIP 永远不进 PASS——"没跑"和"通过"是两件事，
    # 混在一起就是变相的 fail-open：环境缺失时报告依然一片绿。
    n_pass = n_fail = n_skip = 0
    skipped = []

    for i, (name, want) in enumerate(expects, start=2):
        have = got[i] if i in got else "缺失"
        ok = have == want
        if ok:
            n_pass += 1
        else:
            n_fail += 1
        print("%-48s %-8s %-8s %s" % (name[:48], want, have, "PASS" if ok else "FAIL"))

    name, want, have, verdict, note = tamper_test()
    print("%-48s %-8s %-8s %s（%s）" % (name[:48], want, have, verdict, note))
    if verdict == "PASS":
        n_pass += 1
    elif verdict == "SKIP":
        n_skip += 1
        skipped.append(name)
    else:
        n_fail += 1

    negs = neg_tests()
    print("-" * 92)
    for name, want, have, verdict, note in negs:
        print("%-48s %-8s %-8s %s（%s）" % (name[:48], want, have, verdict, note))
        if verdict == "PASS":
            n_pass += 1
        elif verdict == "SKIP":
            n_skip += 1
            skipped.append(name)
        else:
            n_fail += 1

    total = len(expects) + 1 + len(negs)
    print("=" * 92)
    print("用例 %d（真实页文本 %d + 合成页文本 %d + 篡改场景 1 + Fail-Open 负面 %d）"
          % (total, len(CASES), len(SYN_CASES), len(negs)))
    print("PASS=%d, FAIL=%d, SKIP=%d" % (n_pass, n_fail, n_skip))

    if n_skip:
        # SKIP 不计入 PASS，而且整体判失败：测试不完整 = 不能签字
        print("FAIL: 缺少 PDF 测试环境，测试不完整")
        print("      跳过 %d 项：%s" % (n_skip, "、".join(skipped)))
        print("      这些项依赖真实 PDF，没跑就等于没验。")
    if n_fail:
        print()
        print("---- 机检原始输出 ----")
        print(out)
    if n_skip or n_fail:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
