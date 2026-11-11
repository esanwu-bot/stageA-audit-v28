# Batch 2 复审包 v1.5 · 入口

Gate 6A Batch 2 Gold Set 第六次送审。**数据一行没动**（24 行仍 OK=24 / SUSPECT=0 / ERROR=0），
本轮只做一件事：把 `validate_annotation.py` 里 **4 处 Fail-Open** 关掉，并补上证明它们真关掉的
**8 个负面测试**。

Fail-Open 的意思是"本该报错的地方没报错"。它比"漏查一项"更危险——漏查的报告至少有人会去补，
Fail-Open 的报告是绿的，看的人以为自己查过了。

- 代码仓：`[REDACTED-INTERNAL-REPO]`
- 送审分支：`feat/gate6a-annotation`
  - `2725f90` v1.2 数据 → `2c7881b` 证据
  - `5f5cc29` v1.3 数据 → `db785b7` 证据
  - `9097ed6` v1.4 数据 → `a87ba4a` 证据
  - **`0e0af78` v1.5 数据 → `4aa3863` 证据（分支 tip）**
- `main` 未动，仍为 `853a80d`

## 先看这五个

| 顺序 | 文件 | 看什么 |
| --- | --- | --- |
| 1 | `selftest_report.txt` | **30 例，30/30**；末尾 8 行就是本轮 N1–N8 |
| 2 | `validation_report.txt` | A/B 双模式 OK=24，C 段是"拒绝出报告"的实拍输出 |
| 3 | `validate_annotation.py` | 4 处改动：`FatalInput`、`open_doc`、`check_provenance`、`hash_bad` |
| 4 | `Batch2_Gate6A_README.md` | 第四节 Fail-Open 对照表 + 30 例明细 |
| 5 | `git_evidence_v15.txt` / `git_evidence_commit_chain.txt` | 0e0af78 的 4 条命令、四轮父子关系 |

## 1. F1：溯源表读不到，不许"提示一句"就继续

v1.4 的实现：

```python
if prov is None:
    notes.append("未找到 Batch2_PDF_PROVENANCE.csv，跳过三处互校（只做 CSV ↔ sidecar）")
```

三处互校里，CSV 和 sidecar 都是我们自己生成的，provenance 是唯一的"第三方参照"。
它一缺席，所谓"互校"就退化成自己跟自己对账——对得再齐也证明不了什么。而报告仍然会打出
`结论：三处溯源一致`、`OK=24`。

v1.5：`load_provenance()` 在文件不存在 / 读不了 / 为空时抛 `FatalInput`；
`check_provenance()` 收到 `None` 也抛（双重保险）。表现是

```
[ERROR] 拒绝出报告：溯源表不存在：E:\nonexistent\prov.csv（它是第三方参照，缺了就只能自己跟自己对账）
退出码 2
```

## 2. F2：空字段不是"无所谓"，是"这条链断了"

v1.4 的三处判断都长这样：

```python
if fname and node.get("file_name") and fname != node["file_name"]:      # 任一侧空就整条跳过
if model and node.get("device_model") and model != node["device_model"]:
if a and b and a != b:
```

结果是：把 sidecar 里的 `file_name` 清空、把 provenance 的 `page_count` 清空，机检一声不响地
跳过该字段，报告还是绿的。**"缺"被当成了"不需要"，而实际上"缺"是最该报错的状态。**

v1.5 统一为 `if not a or not b or a != b: ERROR`，并把字段对应关系写死、印在报告里：

| 比对 | 参与字段 | 为什么 |
| --- | --- | --- |
| CSV ↔ sidecar | `file_name`、`device_model` | CSV 没有 `sha256` / `page_count` 列，这两项无从比 |
| sidecar ↔ provenance | `file_name`、`device_model`、`sha256`、`page_count` | 四项都该有 |

```
字段对应：CSV↔sidecar 比 file_name/device_model；
          sidecar↔provenance 比 file_name/device_model/sha256/page_count
判据：任一侧为空 或 两侧不等 → ERROR（空字段不再当作“跳过”）
```

顺带把"provenance 有、sidecar 没有"的条目从"提示"升级为 ERROR——那也是链断了一节。

## 3. F3：PDF 缺失不许静默降级

v1.4 有个很舒服、也很危险的兜底：`--pdf-dir` 指错了，就自动去读 `page_text.json`，
只打一行"提示"。于是"我想验证 PDF 原件"和"我只看了随包的页文本"在报告上几乎看不出区别。

v1.5 把三种情况全部改成硬失败：

| 情况 | v1.4 | v1.5 |
| --- | --- | --- |
| `--pdf-dir` 目录不存在 / 不是目录 / 缺 PyMuPDF | 掉头读 sidecar，一行提示 | `FatalInput` → 退出码 2 |
| 目录在，但该样本的 PDF 不在 | `CANNOT_VERIFY`（看起来只是"缺页文本"） | 该样本 **ERROR**："PDF 缺失…（PDF 模式不做离线降级）" |
| PDF 打不开 / 哈希算不了 | 静默返回 None | 该样本 **ERROR**："PDF 打不开 / 无法计算哈希" |

保留的唯一例外：自动探测的 `./pdfs` 不存在不算错——那只是"没提供 PDF"，不是"提供了却不能用"。

## 4. F4：哈希不符之后，不许再读页内文字

v1.4 已经能发现哈希不符，但发现之后**照样**调 `pages.page_text()` 去核对页内文字，
只是把错误信息附在行上。这在逻辑上讲不通：文件都已经不是溯源记录里的那一份了，
"这一页面上有没有这个数"核得再对也没有意义。

v1.5 引入 `hash_bad` 集合：PDF 模式先逐样本算哈希，不符即入集合；行循环里

```python
if sno in hash_bad:
    verdicts.append(("ERROR", idx, sno, list(prov_issues.get(sno))))
    continue                      # 在 page_count / page_text 之前
```

**这条承诺必须能被验证**，否则只是代码里的一句话。所以 N8 把 `Pages.page_text` 换成计数器，
在同一进程里跑 `main()`，断言调用次数为 **0**。

## 5. 8 个负面测试（N1–N8）

| # | 构造的坏输入 | 断言 | 实测 |
| --- | --- | --- | --- |
| N1 | `--provenance` 指向不存在的文件 | 退出码 2 + `[ERROR]`，且**不含**"跳过三处互校" | PASS |
| N2 | sidecar 的 `file_name` 置空 | ERROR | PASS |
| N3 | CSV 的 `device_model` 置空 | ERROR | PASS |
| N4 | provenance 的 `page_count` 置空 | ERROR | PASS |
| N5 | `--pdf-dir` 指向不存在的目录 | 退出码 2 + `[ERROR]`，且**不含**"使用随包的 page_text.json" | PASS |
| N6 | PDF 模式 + 目录里没有该样本 PDF | ERROR，且**不是** `CANNOT_VERIFY` | PASS |
| N7 | 同名路径是目录，哈希算不出 | ERROR（"无法计算哈希"） | PASS |
| N8 | 篡改 PDF 触发哈希不符 | 全行 ERROR + `page_text()` 调用 **0 次** | PASS |

N1、N5 特意加了"**不含**某句话"的断言。只验"有 ERROR"是不够的——旧代码在那些场景下也
可能因为别的原因碰巧报错，但"跳过三处互校""使用随包的 page_text.json"这两句一旦出现，
就说明它还是走了那条绕路。断言否命题，才是真的关门。

N8 是唯一跑在同一进程里的用例：子进程的调用次数从外面看不到，只能换成计数器。

## 6. 结论

| 项 | 结果 |
| --- | --- |
| 机检（PDF 模式） | OK=24 / SUSPECT=0 / ERROR=0，PDF 实算哈希已比对，三处溯源一致，退出码 0 |
| 机检（离线模式） | 同上，退出码 0 |
| 自测 | 30 例，30/30 通过 |
| 数据 | 24 行、6 件样本，与 v1.4 逐字相同 |
| 退出码语义 | `0` 无 ERROR；`1` 有 ERROR 行；`2` 判据/环境不可用（拒绝出报告） |

## 7. 复核命令

```bash
python validate_annotation.py                                     # OK=24，退出码 0
python validate_annotation.py --pdf-dir <PDF 目录>                 # 实算哈希：已比对
python _selftest_validator_v2.py                                   # 30/30
ICPDF_PDF_DIR=<PDF 目录> python _selftest_validator_v2.py          # 含篡改 PDF 与 N8 计数断言
python validate_annotation.py --provenance /no/such.csv            # 应退出码 2（F1）
python validate_annotation.py --pdf-dir /no/such/dir               # 应退出码 2（F3）
sha256sum -c SHA256SUMS.txt
```

## 已知局限（本轮又添一条）

1. 型号核对只判"封面上有没有这串字"，拦不住近亲型号（ADC3541 就印在 ADC3544 手册里）。
   溯源一致性只保证"三处写的是同一个型号"，不保证"这个型号是对的"。
2. 单位核对是"出现在页面上"级别，`A` 这种单字母单位正文里随便一个 "a" 就能命中。
3. 参数名语义判不了：`VNEG_IN_x` 只能提示"全大写带下划线、疑似引脚名"。
4. **数值归属判不了**——V162 的 96 mA 是靠人眼看表头才发现的，机检只认"页面上有 128"。
5. `confidence_score` 是纯 det 分，未校准，不能当准确率上界。本批 24 行不得外推到 28 件全集。
6. **"关掉 Fail-Open"不等于"全覆盖"**。本轮关掉的是我们**想到**的四条路径，N1–N8 只能证明
   这四条被关上；没被想到的 fail-open 仍然存在。真正管用的不是这份清单，而是每次新增检查时
   都问一句："它失败的时候，报告会不会还是绿的？"
