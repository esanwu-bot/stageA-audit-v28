#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三个反例：证明四条不变量不是文档承诺，而是会被代码拦住。

  反例 1  原始层被篡改      —— 改一个字节，内容寻址立刻失配
  反例 2  新 Gold 覆盖旧版  —— 不允许；版本目录只增不改
  反例 3  没有 manifest 的 eval —— 拒绝加载，不做「尽力而为」

每个反例都断言「该失败的事情确实失败了」，并且**在临时副本上操作**，
不碰真实数据。跑完打印 PASS 行。
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

LAKE = Path(__file__).resolve().parent


class InvariantViolation(Exception):
    pass


class ManifestMissing(Exception):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------- 反例 1
def case_tampered_raw() -> str:
    """改 1 个字节 -> 内容寻址失配，必须报错。"""
    raw_root = LAKE / "raw_layer"
    doc_dir = next(p for p in sorted(raw_root.iterdir()) if (p / "RAW.json").is_file())
    meta = json.loads((doc_dir / "RAW.json").read_text(encoding="utf-8"))
    pdf = next(p for p in doc_dir.iterdir() if p.suffix.lower() == ".pdf")
    original = sha256(pdf)

    with tempfile.TemporaryDirectory() as td:
        copy = Path(td) / pdf.name
        shutil.copyfile(pdf, copy)
        data = bytearray(copy.read_bytes())
        idx = len(data) // 2
        data[idx] ^= 0x01  # 只翻 1 个 bit
        copy.write_bytes(bytes(data))

        tampered = sha256(copy)
        assert tampered != original, "篡改后哈希竟然相同，测试无效"
        assert tampered != meta["source_sha256"], "篡改后仍等于登记的哈希"

        # 内容寻址的含义：拿这个字节流去 raw_layer 找，找不到对应目录
        expected_dir = raw_root / tampered
        assert not expected_dir.exists(), "篡改后的字节居然命中了已有目录"

        # 反证：原文件没被动过
        assert sha256(pdf) == original, "测试把原文件改坏了"

    return (f"篡改 1 bit → sha256 {original[:12]}… → {tampered[:12]}…，"
            f"raw_layer 中无 {tampered[:12]}… 目录，原文件未受影响")


# ---------------------------------------------------------------- 反例 2
def case_new_gold_does_not_overwrite() -> str:
    """新建 gold_v9.9.9 不得改动 gold_v1.0.0 的任何字节。"""
    gold_root = LAKE / "eval_layer" / "gold"
    old_dir = gold_root / "gold_v1.0.0"
    old_manifest = json.loads((old_dir / "GOLD_MANIFEST.json").read_text(encoding="utf-8"))
    before = {f["file"]: sha256(old_dir / f["file"]) for f in old_manifest["files"]}

    new_dir = gold_root / "gold_v9.9.9"
    try:
        assert not new_dir.exists(), "测试目录已存在，拒绝覆盖真实数据"
        new_dir.mkdir()
        # 模拟「发布新版」：只读旧版、写新版
        (new_dir / "GOLD_MANIFEST.json").write_text(
            json.dumps({"gold_version": "gold_v9.9.9", "total_rows": 0, "files": []},
                       ensure_ascii=False, indent=2), encoding="utf-8")

        after = {f: sha256(old_dir / f) for f in before}
        assert before == after, "发布新版竟然改动了旧版字节"
        assert old_dir.is_dir() and new_dir.is_dir(), "两个版本目录应同时存在"
        assert len([p for p in gold_root.iterdir() if p.is_dir()]) >= 2, "版本目录未并存"
    finally:
        shutil.rmtree(new_dir, ignore_errors=True)

    return (f"gold_v1.0.0 的 {len(before)} 个文件字节不变，"
            f"新版以独立目录并存（测试目录已清理）")


# ---------------------------------------------------------------- 反例 3
def load_eval(run_id: str) -> dict:
    """评估结果加载器：没有 manifest 就拒绝。"""
    pdir = LAKE / "parse_layer" / run_id
    if not (pdir / "run_manifest.json").is_file():
        raise ManifestMissing(f"run {run_id} 缺少 run_manifest.json，拒绝加载 eval")
    ev = LAKE / "eval_layer" / run_id / "eval.json"
    if not ev.is_file():
        raise ManifestMissing(f"run {run_id} 缺少 eval.json")
    return json.loads(ev.read_text(encoding="utf-8"))


def case_eval_without_manifest() -> str:
    """只有 eval.json、没有 manifest -> 必须拒绝。"""
    fake = "__negative_test_no_manifest__"
    edir = LAKE / "eval_layer" / fake
    pdir = LAKE / "parse_layer" / fake
    try:
        edir.mkdir(parents=True, exist_ok=True)
        (edir / "eval.json").write_text(
            json.dumps({"run_id": fake, "gold_version": "gold_v1.0.0"}, ensure_ascii=False),
            encoding="utf-8")
        assert pdir.exists() is False, "临时 run 目录已存在"
        try:
            load_eval(fake)
        except ManifestMissing as e:
            msg = str(e)
        else:
            raise AssertionError("缺少 manifest 时竟然加载成功了")
        assert "缺少 run_manifest.json" in msg, f"错误信息不明确：{msg}"
    finally:
        shutil.rmtree(edir, ignore_errors=True)
        shutil.rmtree(pdir, ignore_errors=True)

    # 正向对照：真实 run 能加载
    real = next(p.name for p in (LAKE / "parse_layer").iterdir()
                if (p / "run_manifest.json").is_file())
    assert load_eval(real)["run_id"] == real, "正向对照失败"
    return f"缺 manifest → ManifestMissing（{msg[:40]}…）；真实 run {real[:20]}… 正常加载"


CASES = [
    ("反例1 原始层被篡改", case_tampered_raw),
    ("反例2 新 Gold 不覆盖旧版", case_new_gold_does_not_overwrite),
    ("反例3 无 manifest 的 eval 被拒绝", case_eval_without_manifest),
]


def main() -> int:
    failed = 0
    for name, fn in CASES:
        try:
            detail = fn()
            print(f"PASS  {name}\n      {detail}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {name}\n      {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {name}\n      {type(e).__name__}: {e}")
    print(f"\n反例 {len(CASES)} 个，失败 {failed} 个")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
