# Batch 2 复审包 v1.6 · 入口

Gate 6A Batch 2 Gold Set 第七次送审。**数据一行没动**（24 行仍 OK=24 / SUSPECT=0 / ERROR=0）。
本轮收掉 v1.5 剩下的两个硬伤：**损坏 PDF 能变成 CANNOT_VERIFY**、**SKIP 被算进 PASS**，
并补上 N9 与 v1.4/v1.5 的实证记录。

- 代码仓：`[REDACTED-INTERNAL-REPO]`
- 送审分支：`feat/gate6a-annotation`
  - `2725f90` v1.2 → `2c7881b` ｜ `5f5cc29` v1.3 → `db785b7`
  - `9097ed6` v1.4 → `a87ba4a` ｜ `0e0af78` v1.5 → `4aa3863`
  - **`695bb92` v1.6 数据 → `df67dfd` 证据（分支 tip）**
- `main` 未动，仍为 `853a80d`

## 先看这五个

| 顺序 | 文件 | 看什么 |
| --- | --- | --- |
| 1 | `validation_report.txt` | **C 段是本轮重点**：历史版本同命令对照的原始输出与退出码 |
| 2 | `selftest_report.txt` | 31 例，末行 `PASS=31, FAIL=0, SKIP=0` |
| 3 | `_mk_corrupt_pdf_fixture.py` | 造"损坏但哈希对得上"的夹具，C.3 与 N9 都用它 |
| 4 | `validate_annotation.py` | 预检里 `open_doc()` + `page_count()`，以及 `pc is not None` |
| 5 | `Batch2_Gate6A_README.md` | 第四节 F5、N9 明细、SKIP 口径 |

## 1. F5：哈希对得上，文件却已经读不了

v1.5 的 PDF 预检只调 `pdf_sha256()`。这件事有个盲区：

- 哈希证明"字节没变"，**证明不了"这文件还能读"**；
- 更麻烦的是，如果溯源表里的哈希被同步改成了残文件的哈希，三处互校全过、哈希全对，
  而 PDF 本身已经一页都没有了。

这种情况下 v1.5 会在行循环的 `page_count()` 才第一次 `open`，失败后 `ptext` 变 None，
落到 **CANNOT_VERIFY**——而 CANNOT_VERIFY 不触发非零退出，报告照写"无 ERROR"、退出码 0。
这是第七条 fail-open，也是最隐蔽的一条：前六条至少还能从日志里看出"跳过/降级"的痕迹，
这条在报告上只是一句"缺页文本，需人工复看"。

v1.6 三处改动：

| 位置 | 改动 |
| --- | --- |
| 预检 | 对每个样本**无条件** `open_doc()` + `page_count()`（与哈希结果无关），打不开即样本级 ERROR |
| 预检 | `page_count == 0`（被截断）也判 ERROR |
| 行循环 | `if pc and page > pc` → `if pc is not None and page > pc`，别让 0 被 falsy 吃掉 |

`page_count == 0` 这条单看很不起眼，但它是同一个洞的第二个入口：截断的 PDF 在 `fitz` 里
**能打开**，只是 `page_count` 为 0；老代码那句 `if pc and page > pc` 遇到 0 直接跳过判断，
后面照样落到 CANNOT_VERIFY。

## 2. 实证：不是"分析代码路径"，是把旧版本跑了一遍

`validation_report.txt` 的 C 段原样收录了终端命令、输出和退出码。摘录：

| 场景 | v1.4 / v1.5 | v1.6 |
| --- | --- | --- |
| C.1 溯源表不存在 | `提示 未找到…跳过三处互校` → `OK=24` → **退出码 0** | `[ERROR] 拒绝出报告` → **退出码 2** |
| C.2 `--pdf-dir` 不存在 | `提示 使用随包的 page_text.json` → `OK=24` → **退出码 0** | `[ERROR]` → **退出码 2** |
| C.3 损坏 PDF（哈希对得上） | `CANNOT_VERIFY=9` → `无 ERROR` → **退出码 0** | `ERROR=9` → **退出码 1** |

C.3 的夹具生成方式（`_mk_corrupt_pdf_fixture.py`）：

1. 把真 PDF 截到 30% —— `fitz` 仍能打开，但 `page_count=0`；
2. 把残文件的 SHA-256 写进 sidecar 和 provenance —— **刻意让哈希全对**；
3. 生成只含该样本行的 CSV。

三条一起看，v1.5 的 `OK=24 / 无 ERROR / 退出码 0` 与 v1.6 的 `拒绝出报告 / ERROR=9` 是
同一份输入跑出来的，不是推断。

## 3. N9：损坏 PDF 必须 ERROR，且不许退回 sidecar

| 断言 | 结果 |
| --- | --- |
| 退出码 = 1 | ✅ |
| 输出含"页数为 0"或"PDF 打不开" | ✅（证明预检真的打开过） |
| 输出**不含** `CANNOT_VERIFY` | ✅ |
| 输出**不含**"使用随包的 page_text.json" | ✅（没降级） |

第三、四条是否命题断言——只验"有 ERROR"不够，还要证明它没有换个姿势绕过去。

## 4. SKIP 口径：SKIP 永远不计入 PASS

v1.5 的汇总用 `total - bad` 当"通过数"，SKIP 既不进 bad 也不进 pass，
于是**跳过的项被算进了通过数**。这本身就是一次 fail-open：环境不全，报告一片绿。

v1.6 改成三计数：

```
用例 31（真实页文本 16 + 合成页文本 5 + 篡改场景 1 + Fail-Open 负面 9）
PASS=31, FAIL=0, SKIP=0
```

并且：

| 情形 | 行为 |
| --- | --- |
| 没给 `ICPDF_PDF_DIR` | 直接打印 `FAIL: 缺少 PDF 测试环境，测试不完整`，**退出码 2** |
| 环境给了但 PDF 不在，N8/N9 跳过 | 打出 `PASS=x, FAIL=y, SKIP=z` + `FAIL: 缺少 PDF 测试环境，测试不完整` + 列出被跳过的项，**退出码 1** |

两种情形都在 `validation_report.txt` C.4 段有实跑记录。

## 5. 结论

| 项 | 结果 |
| --- | --- |
| 机检（PDF 模式） | OK=24 / SUSPECT=0 / ERROR=0，实算哈希已比对，三处溯源一致，退出码 0 |
| 机检（离线模式） | 同上，退出码 0 |
| 自测 | 31 例，`PASS=31, FAIL=0, SKIP=0`，退出码 0 |
| 数据 | 24 行 / 6 样本，与 v1.4 逐字相同 |
| 退出码语义 | `0` 无 ERROR；`1` 有 ERROR 行或测试不完整；`2` 判据/环境不可用 |

## 6. 复核命令

```bash
python validate_annotation.py                                   # OK=24，退出码 0
python validate_annotation.py --pdf-dir <PDF>                   # 实算哈希已比对 + 预检打开每个 PDF
ICPDF_PDF_DIR=<PDF> python _selftest_validator_v2.py            # PASS=31, FAIL=0, SKIP=0
python _selftest_validator_v2.py                                # 缺环境：FAIL + 退出码 2
python _mk_corrupt_pdf_fixture.py --pdf-dir <PDF> --out /tmp/cc # 造 N9 夹具，再跑 C.3 两条命令
sha256sum -c SHA256SUMS.txt
```

## 已知局限

1. 型号核对只判"封面上有没有这串字"，拦不住近亲型号（ADC3541 就印在 ADC3544 手册里）。
2. 单位核对是"出现在页面上"级别，`A` 这种单字母单位正文里随便一个 "a" 就能命中。
3. 参数名语义判不了：`VNEG_IN_x` 只能提示"全大写带下划线、疑似引脚名"。
4. **数值归属判不了**——V162 的 96 mA 是靠人眼看表头才发现的，机检只认"页面上有 128"。
5. `confidence_score` 是纯 det 分，未校准，不能当准确率上界；本批 24 行不得外推到 28 件全集。
6. **"关掉 Fail-Open"不等于"全覆盖"**。目前关掉的是 F1–F5 五条，自测只能证明这五条被关上。
   管用的不是这份清单，而是每次新增检查时问一句："它失败的时候，报告会不会还是绿的？"
7. **预检打开只证明"能打开"，不证明"内容对"**。N9 用整份截断，`page_count=0` 一眼可见；
   若坏文件恰好还能打开、页数也对，就只有哈希能救——哈希与可读性两道闸，谁也不能替谁。
