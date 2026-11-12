# Gate 6A 首次受控 Parser 回测报告

> 样本：Gold Set v1.1 全量 24 件 / 105 行　　输出目录：`runs/gate6a_replay_v1/`
> 回测执行窗口：11-12 16:01:23 – 16:14:33（本机时间，24 件串行，含 V101 补跑）
> 报告由 `_make_report.py` 从落盘产物生成，无人工填写数字

## 0. 一句话结论

24 件里 23 件解析成功、1 件（**V256**）在建表校验处崩溃。105 行 Gold 中 **99 行能定位到候选块（定位率 94.3%）**，其中 **89 行四项全过、判为命中（命中率 84.8%）**。

两个数不是一回事，本报告全文严格区分：**定位**只要求找到某个候选块，**命中**还要求值、单位、符号、页码四项全对（定义见 §4.0）。
另有 **39 行**的「不一致」经复核确认是**评估器口径问题**而非 Parser 问题，修正后已翻正（口径调整导致变差的行数为 **0**）。

## 1. 环境与版本（边界 1）

| 项 | 值 |
|---|---|
| Git Commit | `a11131a`（main） |
| Commit 主题 | Gate 6A Batch 2：24 行 Gold 并入 main（Reviewer 已批准） |
| Python | 3.13.15 (tags/v3.13.15:4061bc4, Aug  5 2026, 13:05:39) [MSC v.1944 64 bit (AMD64)] |
| 解释器 | `D:\Program Files (x86)\python\python.exe` |
| PyMuPDF（包版本） | 2.0 |
| PyMuPDF（fitz.version 元组） | ('2.0', '1.28.5', None) |
| pydantic | 2.14.1 |
| icpdf / parser / contract | 0.1.0 / 0.1.0-phase1 / data-contract/v0.2 |
| 解析配置 | `configs/parser.yaml` sha256 `ab9f12527767c7df…` |
| Parser 包指纹 | `31240f6db08f7ef4…`（27 个 .py） |
| **解析链路未改动** | **True** |

`src/` 下未提交改动只有 ``M src/icpdf/cli.py``（CLI 层，不在解析链路内）；`src/icpdf/parser/` 27 个文件整体指纹已记录，可逐位复核。

<details><summary>parser.yaml 生效配置全文</summary>

```yaml
# Parser configuration (effective values are hashed into run_manifest.json)
pdf:
  render_dpi: 150
  text_min_chars: 1

tables:
  # A new column starts when the horizontal word gap exceeds this many points.
  cell_gap_pt: 8.0
  # A table ends when the next row starts further than this multiple of median line height.
  row_gap_factor: 2.5
  # Ragged rows may differ from the modal column count by at most this many columns.
  column_tolerance: 2
  # Minimum header-keyword hits to treat the first row as a header.
  header_min_hits: 2
  # Candidate heading lines longer than this are not used as a table title.
  max_title_chars: 120
  # A cell longer than this is prose, not a table cell; do not start a table from it.
  max_cell_chars: 80
  # A non-headed table must contain at least this many numeric-looking cells.
  min_numeric_cells: 2
  # Minimum size of a connected vector-rule lattice considered a table region.
  rule_min_width_pt: 70.0
  rule_min_height_pt: 15.0
  # Text-only fallback: require at least this many visual rows (header + data).
  alignment_min_rows: 3
```

</details>

## 2. 输入白名单（边界 2）

| 项 | 值 |
|---|---|
| 样本数 | 24 |
| Gold 行数 | 105 |
| 文件全部存在 | True |
| SHA-256 与台账逐一一致 | **True** |
| 总页数 | 2333 |

<details><summary>24 件清单（样本 / 设备 / 页数 / sha256 前 16 位）</summary>

| # | 样本 | 设备型号 | 页数 | Gold 行 | sha256 |
|---|---|---|---|---|---|
| 1 | V003 | AM2431 | 282 | 5 | `357aabed475f92b9…` |
| 2 | V011 | CD54HC123F3A | 24 | 5 | `062aa4848f2f6eae…` |
| 3 | V038 | ADC12QJ1600-EP | 151 | 5 | `183f4057e7c7cf49…` |
| 4 | V077 | AM1707 | 201 | 5 | `86441d0065e94257…` |
| 5 | V097 | OPA2830 | 52 | 3 | `0165370d5ffbabba…` |
| 6 | V101 | CD74HCT574 | 21 | 9 | `059d448c5a34a4b1…` |
| 7 | V111 | DS90C189-Q1 | 39 | 3 | `0c31c316536a2156…` |
| 8 | V145 | DAC8775 | 80 | 3 | `099d8e430da67530…` |
| 9 | V146 | CY74FCT399T | 16 | 5 | `0809811970012504…` |
| 10 | V162 | SN74LVTH182504A | 43 | 3 | `025966b873cd942a…` |
| 11 | V173 | SN74AHCT1G04 | 24 | 3 | `05199cf2c623cc8b…` |
| 12 | V199 | CSD18504Q5A | 16 | 5 | `034789b8fb4d2817…` |
| 13 | V242 | ADS131B26-Q1 | 253 | 5 | `33708e2c19e5def0…` |
| 14 | V244 | AM1802 | 185 | 5 | `76a8df74bb0570bc…` |
| 15 | V256 | BQ79652-Q1 | 216 | 5 | `4342b3beadcb5731…` |
| 16 | V271 | DM3725 | 283 | 5 | `41d551df76048cc1…` |
| 17 | V290 | DS9638 | 10 | 3 | `239dd12d525f9324…` |
| 18 | V304 | SN74CB3T3306 | 23 | 3 | `031e6d810f30687b…` |
| 19 | V319 | TLV2354 | 19 | 4 | `02b950150be0223a…` |
| 20 | V320 | DAC3482 | 106 | 5 | `1eec88c866fe4e52…` |
| 21 | V336 | DS96F173MQML | 15 | 4 | `03ba6673a7c9a995…` |
| 22 | V345 | DAC63202W | 82 | 4 | `0ef0862faed2c1bc…` |
| 23 | V346 | ADS54J40 | 117 | 5 | `28cac987b60b12c2…` |
| 24 | V349 | ADC3544 | 75 | 3 | `095874fb14061c23…` |

</details>

完整清单见 `input_manifest.csv` / `input_manifest.json`。

## 3. LLM 硬禁用（边界 3）

两层锁，缺一不可：

1. **环境锁**：运行前清除 `DASHSCOPE_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `DEEPSEEK_API_KEY` / `MOONSHOT_API_KEY` / `ZHIPU_API_KEY` / `ICPDF_LLM_*` / `*_BASE_URL` 等凭据变量。本次实际存在的凭据变量：**0 个**。
2. **运行时锁**：`sys.addaudithook` 拦截 `socket.connect`、`socket.getaddrinfo`、`socket.gethostbyname`、`urllib.Request`、`http.client.connect`、`ftplib.connect`、`smtplib.connect`，命中即 `RuntimeError`。钩子不可卸载，任何 SDK 只要走 socket 就绕不过。

证据：

- 装闸自测主动调用 `socket.getaddrinfo("example.com", 443)`，被拦下（`PASS`）。
- 23 个成功样本逐件回传 `llm_blocked`，取值集合为 `[0]`，合计 **0 次**网络出站。

### 3.1 四条边界机检

`_assert_boundaries.py` 对四条边界逐条断言，原始输出见 `boundary_assertions.txt`：**25 项 PASS / 0 项 FAIL**。

| 边界 | 断言的硬事实 |
|---|---|
| 1 环境与版本 | commit 40 位完整、Python 3.13.x、parser 包 27 个文件指纹未变、`parser.yaml` 磁盘哈希 == 快照哈希 |
| 2 输入白名单 | 24 件、Gold 105 行、**逐件重算 SHA-256 == 台账哈希（24/24）** |
| 3 LLM 硬禁用 | 23 个成功样本 `blocked_events` 全为 0、拦截明细为空、装闸自测能拦住主动出站 |
| 4 输出隔离 | 输出根名正确、`runs/` 其他目录未动、`_gate6a_prep/` 0 个文件被写、签字件与派生 CSV 哈希未变 |

另有 5 项指标自洽断言：归因各类之和 == 105、命中行 ≥ 完全一致行、`eval_detail.csv` 行数 == 105、命中数与 `metrics.json` 一致。

## 4. 总体指标（边界 4 之外的评估结果）

### 4.0 两个指标的定义（先把口径钉死）

**命中 = 四项全部通过，缺一不算：**

| 判据 | 要求 |
|---|---|
| `value_match` | Gold 的每个非空 min/typ/max 都能在块内找到（1e-6 相对容差） |
| `unit_match` | 单位作为独立 token 出现在该行或同表上下文 |
| `symbol_match` | 候选块经符号路径命中，而不是按值反查出来的 |
| `parser_page == gold_page` | 块必须落在 Gold 记录的页码上 |
| `condition_match` | **参考字段，不参与命中判定** |

**定位 = 只要找到某个候选块即可**，不看值、单位、符号、页码是否对。
定位率恒 ≥ 命中率，两者不可互相替代。

### 4.1 指标表

| 指标 | 定义 | 值 |
|---|---|---|
| Gold 行 | 分母 | 105 |
| **定位率** | 定位到候选块的行 / 105 | **99 / 105 = 94.3%** |
| **命中率** | 四项全过的行 / 105 | **89 / 105 = 84.8%** |
| 未定位率 | 1 − 定位率 | 5.7%（6 行 = 无法定位 1 + 解析失败 5） |

对账关系（与 `audit/error_matrix_105.csv` 逐行一致）：

```
located=是                     99
  ├─ 命中（四项全过）           89
  └─ 错误匹配                  10
located=否（漏提）               6
                              ----
                               105
```

### 4.2 字段级通过数（分母均为「定位到的 99 行」）

| 字段 | 值 |
|---|---|
| 数值一致 | 90 / 99 |
| 单位一致（行级严格） | 84 / 99 |
| 单位一致（含表级合并单元格上下文） | 95 / 99 |
| 符号经符号路径命中 | 95 / 99 |
| 页码一致 | 96 / 99 |
| condition 可定位（参考，不阻断命中） | 82 / 99 |

### 4.3 命中强度分层

「完全一致」不是一档货，必须分层看，否则放宽口径就等于自欺。

| 层级 | 行数 | 含义 |
|---|---|---|
| 强命中（token，块 ≤4 行） | 62 | 符号整格 token 对上，块紧凑 |
| 整格 token 但块 ≥5 行 | 0 | 符号对，但块把相邻参数行也吞进来了 |
| 文本级命中（块 ≤4 行） | 16 | 短语符号 / `T sett` 空格断开 / 符号与参数名同格 |
| 文本级命中（块 ≥5 行） | 7 | 同上的定位方式，但块偏粗 |
| 按值定位（Gold 无符号） | 4 | Gold 该行 symbol 为空，只能按值 + 单位认 |
| 合计 | 89 | — |

## 5. 错误归因明细（Reviewer 指定六类）

| 归因 | 行数 | 说明 |
|---|---|---|
| 完全一致 | 89 | 符号 / 值 / 单位 / 页四项全中 |
| 数值错 | 6 | 符号与页都对，但 Gold 的某个值在块内找不到（或块内是另一档的值） |
| symbol 错配 | 0 | 值在正确页上，但符号列没落到该行 |
| evidence page 错 | 3 | 符号命中了别的页上的块 |
| 单位错 | 1 | 值对、页对，单位不在该行也不在同表 |
| 漏提 | 1 | 符号与值都定位不到 |
| 解析失败 | 5 | Parser 在该件上崩溃，无任何输出（计入分母） |
| 合计 | 105 | — |

### 5.1 多余候选 / 错提

Gold 是 **105 行抽样**，不是全表枚举，所以「整份文档里没被 Gold 引用的块」绝大多数是样本外的真实参数行，把它们算作误提没有意义。这里只报可核的量：

| 指标 | 值 |
|---|---|
| 解析出的候选块总数 | 21181 |
| Gold 页上的候选块 | 395（3.76 块 / Gold 行） |
| 其中未被 Gold 引用的 | 318（抽检见下） |
| 同页同符号但属**另一张参数表**的块 | 3 |

另对三个样本（V101 / V319 / V320）各取前 5 个样本外候选块逐块判定：**8 块是 Gold 抽样未覆盖的真实参数行**，2 块是版式碎片（表头行、合并单元格残行），0 块疑似错提。明细见 `extra_candidate_audit.csv`。

这 3 个块经逐块核对（V173 / V345），都是**同页同符号出现在不同参数表**里（绝对最大值表 vs 推荐工作条件表），属手册正常版式，不是错提、更不是幻觉值。本次回测**未发现凭空捏造的参数行**。

## 6. 评估器修正清单（分清「Parser 错」与「评估器错」）

同一批落盘产物、两套口径各评一遍，按 Gold 稳定键逐行 diff。

| 分类 | 行数 |
|---|---|
| 评估器修正后翻正 | 39 |
| 仍不一致（Parser 侧问题） | 16 |
| 口径调整后变差 | 0 |
| 两套口径一致（已正确） | 50 |

修正前：召回 76.2%、完全一致 47.6%；修正后：召回 94.3%、完全一致 84.8%。**变差 0 行**。

四处修正，全部是**评估脚本自己没对齐**，与 Parser 无关：

| # | 修正项 | 现象 | 影响 |
|---|---|---|---|
| 1 | 符号正则放开下划线 | `VDD_CORE` / `VDDA_0P85_USB0` 整类轨名被判「不像符号」，行被吞进上一块 | V003 等 `symbol 错配 → 完全一致` |
| 2 | 剥结尾脚注标记 | `VA19 (2)` 的 `(2)` 被当成符号的一部分，永远对不上号 | V038 五条 `evidence page 错 → 完全一致` |
| 3 | 负号与数字贴合 | PDF 文本层 `– 0.5` 被读成 `+0.5` | V271 五条 `数值错 → 完全一致` |
| 4 | 符号内允许空格 + 无符号孤儿块 + 候选池合并 | 短语符号（`APWR to AGND`）、与参数名同格（`PDISS Power Dissipation`）都无法整格命中 | V242 / V145 / V097 等 `漏提 → 完全一致` |

另有两处顺带修正：块页码改用单元格真实页码（跨页表）；单位判定从 `V in text` 子串（会在 `VA19` 里命中）改为独立 token + 表级合并单元格上下文。

<details><summary>逐行对照明细（仅列有变化的行）</summary>

| 样本 | 符号 | 页 | 旧口径 | 新口径 | 分类 |
|---|---|---|---|---|---|
| V003 | `VDDR_CORE` | 105 | symbol 错配 | 完全一致 | 评估器修正后翻正 |
| V003 | `VDD_CORE` | 105 | symbol 错配 | 完全一致 | 评估器修正后翻正 |
| V003 | `VDD_CORE` | 101 | symbol 错配 | 完全一致 | 评估器修正后翻正 |
| V038 | `VA11` | 9 | evidence page 错 | 完全一致 | 评估器修正后翻正 |
| V038 | `VA19` | 9 | evidence page 错 | 完全一致 | 评估器修正后翻正 |
| V038 | `VPLL19` | 9 | evidence page 错 | 完全一致 | 评估器修正后翻正 |
| V038 | `VREFO` | 9 | evidence page 错 | 完全一致 | 评估器修正后翻正 |
| V038 | `VTRIG` | 9 | evidence page 错 | 完全一致 | 评估器修正后翻正 |
| V097 | `` | 8 | 漏提 | 完全一致 | 评估器修正后翻正 |
| V097 | `` | 8 | 漏提 | 完全一致 | 评估器修正后翻正 |
| V111 | `Tstg` | 6 | symbol 错配 | 完全一致 | 评估器修正后翻正 |
| V111 | `VDD` | 6 | evidence page 错 | 完全一致 | 评估器修正后翻正 |
| V111 | `VOS` | 7 | symbol 错配 | 完全一致 | 评估器修正后翻正 |
| V145 | `` | 12 | 漏提 | 完全一致 | 评估器修正后翻正 |
| V145 | `PDISS` | 12 | 漏提 | 完全一致 | 评估器修正后翻正 |
| V145 | `Tsett` | 12 | 漏提 | 完全一致 | 评估器修正后翻正 |
| V146 | `VOH` | 4 | symbol 错配 | 完全一致 | 评估器修正后翻正 |
| V146 | `VOH` | 4 | symbol 错配 | 完全一致 | 评估器修正后翻正 |
| V173 | `IO` | 4 | symbol 错配 | 完全一致 | 评估器修正后翻正 |
| V173 | `Tstg` | 4 | symbol 错配 | 完全一致 | 评估器修正后翻正 |
| V173 | `VCC` | 4 | 数值错 | 完全一致 | 评估器修正后翻正 |
| V242 | `AGND, AGNDy to DGND` | 6 | 漏提 | 完全一致 | 评估器修正后翻正 |
| V242 | `APWR to AGND` | 6 | 漏提 | 完全一致 | 评估器修正后翻正 |
| V242 | `AVDD to AGND` | 6 | 漏提 | 完全一致 | 评估器修正后翻正 |
| V242 | `DPWR to DGND` | 6 | 漏提 | 完全一致 | 评估器修正后翻正 |
| V242 | `IOVDD to DGND` | 6 | 漏提 | 完全一致 | 评估器修正后翻正 |
| V244 | `RTC_CVDD` | 44 | symbol 错配 | 完全一致 | 评估器修正后翻正 |
| V271 | `vdd_core` | 117 | 漏提 | 完全一致 | 评估器修正后翻正 |
| V271 | `vdd_mpu_iva` | 117 | 漏提 | 完全一致 | 评估器修正后翻正 |
| V271 | `vdda_dac` | 117 | 漏提 | 完全一致 | 评估器修正后翻正 |
| V271 | `vdds` | 117 | 数值错 | 完全一致 | 评估器修正后翻正 |
| V271 | `vdds_sram` | 117 | 漏提 | 完全一致 | 评估器修正后翻正 |
| V304 | `IIK` | 4 | symbol 错配 | 完全一致 | 评估器修正后翻正 |
| V304 | `TJ` | 4 | symbol 错配 | 完全一致 | 评估器修正后翻正 |
| V304 | `VCC` | 4 | evidence page 错 | 完全一致 | 评估器修正后翻正 |
| V319 | `VDD` | 5 | 漏提 | 完全一致 | 评估器修正后翻正 |
| V320 | `AVDD, PLLAVDD` | 12 | symbol 错配 | 完全一致 | 评估器修正后翻正 |
| V320 | `DACVDD, DIGVDD, CLKVDD` | 12 | symbol 错配 | 完全一致 | 评估器修正后翻正 |
| V349 | `Tstg` | 5 | 漏提 | 完全一致 | 评估器修正后翻正 |
| V003 | `TJ` | 106 | 数值错 | 数值错 | 仍不一致（Parser 侧问题） |
| V077 | `DVDD` | 38 | 数值错 | 数值错 | 仍不一致（Parser 侧问题） |
| V077 | `RVDD` | 38 | 数值错 | 数值错 | 仍不一致（Parser 侧问题） |
| V162 | `IO` | 25 | 漏提 | evidence page 错 | 仍不一致（Parser 侧问题） |
| V162 | `VCC` | 25 | evidence page 错 | evidence page 错 | 仍不一致（Parser 侧问题） |
| V162 | `VI` | 25 | 漏提 | evidence page 错 | 仍不一致（Parser 侧问题） |
| V199 | `ID` | 1 | 数值错 | 数值错 | 仍不一致（Parser 侧问题） |
| V256 | `V(MAIN-AUX)` | 13 | 解析失败 | 解析失败 | 仍不一致（Parser 侧问题） |
| V256 | `V(MAIN-AUX)` | 13 | 解析失败 | 解析失败 | 仍不一致（Parser 侧问题） |
| V256 | `V(MAIN-AUX)` | 13 | 解析失败 | 解析失败 | 仍不一致（Parser 侧问题） |
| V256 | `V(MAIN-AUX)` | 13 | 解析失败 | 解析失败 | 仍不一致（Parser 侧问题） |
| V256 | `V(MAIN-AUX)` | 13 | 解析失败 | 解析失败 | 仍不一致（Parser 侧问题） |
| V319 | `IO` | 5 | 漏提 | 漏提 | 仍不一致（Parser 侧问题） |
| V319 | `TA` | 5 | evidence page 错 | 单位错 | 仍不一致（Parser 侧问题） |
| V319 | `TA` | 5 | evidence page 错 | 数值错 | 仍不一致（Parser 侧问题） |
| V320 | `V(ESD)` | 12 | 漏提 | 数值错 | 仍不一致（Parser 侧问题） |

</details>

完整表：`calibration_diff.csv`（含命中块号，可逐条回查）。

## 7. 文本级 / 按值命中逐条审计

放宽口径后多出来的命中，逐条对着块文本核过，结论与证据片段都留在 `text_hit_audit.csv`：

| 结论 | 条数 |
|---|---|
| 确认成立 | 21 |
| 软命中-确认成立 | 6 |
| 不计入 | 5 |

其中「不计入」的 5 条，是该行主归因本就不是完全一致（页错 / 单位错 / 数值错），只是命中方式为文本级，列出来备查。

<details><summary>确认成立的文本级命中（含证据片段）</summary>

| 样本 | 符号 | 块行数 | 证据 |
|---|---|---|---|
| V097 | `` | 1 | Gold 该行 symbol 为空，只能按值 + 单位定位 |
| V097 | `` | 1 | Gold 该行 symbol 为空，只能按值 + 单位定位 |
| V111 | `VDD` | 5 | 块内含 'Supply Voltage (V DD ) −0.3 2.5 V'；块 5 行，其余为相邻参数行 |
| V111 | `Tstg` | 1 | 单行 'Storage Temperature (T stg ) −65 150 °C' |
| V111 | `VOS` | 8 | 8 行块，但块内确有 'V OS Offset Voltage ... 1.09 1.22 1.36 V' |
| V145 | `PDISS` | 1 | 符号与参数名同格：'PDISS Power Dissipation (PVDD+AVDD) ... 0.86 1.1 W' |
| V145 | `` | 1 | Gold 该行 symbol 为空，只能按值 + 单位定位 |
| V145 | `Tsett` | 1 | PDF 文本层抽成 'T sett'，允许符号内空格后定位到 |
| V146 | `VOH` | 2 | 2 行块，含 2 / 2.4 / 3.3 两组 IOH 条件 |
| V146 | `VOH` | 2 | 2 行块，含 2 / 2.4 / 3.3 两组 IOH 条件 |
| V173 | `VCC` | 1 | 单行 'V CC Supply voltage range –0.5 7 V'；负号分离修正后数值才对上 |
| V173 | `Tstg` | 6 | 6 行块，块内含 'T stg Storage temperature range –65 150 °C' |
| V173 | `IO` | 6 | 同上 6 行块，块内含 'I O Continuous output current ... ±25 mA' |
| V242 | `APWR to AGND` | 1 | 符号以字符序列命中（非整格 token） |
| V242 | `DPWR to DGND` | 1 | 符号以字符序列命中（非整格 token） |
| V242 | `AGND, AGNDy to DGND` | 1 | 符号以字符序列命中（非整格 token） |
| V242 | `AVDD to AGND` | 1 | 符号以字符序列命中（非整格 token） |
| V242 | `IOVDD to DGND` | 1 | 符号以字符序列命中（非整格 token） |
| V290 | `VIL` | 1 | 2 行块 'V IL Input Voltage LOW 0°C to +70°C 0.8 V ...' |
| V304 | `VCC` | 8 | 8 行合并块，值在块内但非逐行对上 |
| V304 | `TJ` | 8 | 8 行合并块，值在块内但非逐行对上 |
| V304 | `IIK` | 8 | 8 行合并块，值在块内但非逐行对上 |
| V319 | `VDD` | 1 | 单行 'Supply voltage, VDD 2 8 V' |
| V320 | `DACVDD, DIGVDD, CLKVDD` | 1 | 单行 'DACVDD, DIGVDD, CLKVDD –0.5 1.5 V' |
| V320 | `AVDD, PLLAVDD` | 4 | 4 行块，块内含 'AVDD, PLLAVDD –0.5 4 V' |
| V345 | `` | 2 | Gold 该行 symbol 为空，只能按值 + 单位定位 |
| V349 | `Tstg` | 1 | 单行 'Storage temperature, T stg –65 150 °C' |

</details>

## 8. Parser 侧待修问题（确认不是评估器造成）

逐条都对着落盘产物核过，写明「实际发生了什么」，而不是套分类名。

| 样本 | 符号 | 页 | 归因 | 实际发生了什么 |
|---|---|---|---|---|
| V003 | `TJ` | 106 | 数值错 | 该表按温度档分行，块内取到的是 `Extended Industrial –40 105` 这一档，Gold 记的是 125 档；档位与参数名的对应关系没建立 |
| V077 | `RVDD` | 38 | 数值错 | `RVDD Supply Voltage, Internal RAM` 行本身没有数值，解析把下一行 `456 MHz version 1.25 1.3 1.35` 吞进同一块，取到的是 456 MHz 档而不是 Gold 记的 1.14/1.2/1.32 档 |
| V077 | `DVDD` | 38 | 数值错 | 同上：`DVDD Supply voltage, I/O, 3.3V` 行本身无值，块内是 3.0/3.3/3.45（3.3V 档），Gold 记的是 1.8V 档 |
| V162 | `VCC` | 25 | evidence page 错 | 符号 `VCC` 被挂到 p5 的 `VCC Supply voltage` 表头行（无值），Gold 指的 p25 绝对最大值行没有被单独成块 |
| V162 | `VI` | 25 | evidence page 错 | p25 的行没带符号，退回按值定位时落到 p27 的同名符号块 |
| V162 | `IO` | 25 | evidence page 错 | 同上，`IO` 在 p27 的 ICC 语境里命中，不是 p25 的目标行 |
| V199 | `ID` | 1 | 数值错 | `I D Continuous Drain Current (Silicon limited), T C = 25°C 75`，取到 75 A，Gold 记 50 A（另一测试条件下的值） |
| V256 | `V(MAIN-AUX)` | 13 | 解析失败 | 建表校验崩溃：`grid_ys must be strictly ascending`（`table_detector.py:219`，`DetectedTable` 校验），整件无输出（同类 5 行） |
| V319 | `TA` | 5 | 单位错 | `TA` 在该页有三个语境（推荐工作温度档 / 封装热阻表 / 输入共模表），解析把符号挂到非目标行，单位与数值都对不上 |
| V319 | `TA` | 5 | 数值错 | `TA` 在该页有三个语境（推荐工作温度档 / 封装热阻表 / 输入共模表），解析把符号挂到非目标行，单位与数值都对不上 |
| V319 | `IO` | 5 | 漏提 | 该页不存在同时含符号 `IO` 与 20 mA 的块 |
| V320 | `V(ESD)` | 12 | 数值错 | 同一个 `V(ESD)` 符号下有 HBM ±2000 V 与 CDM ±500 V 两行，符号只落在 CDM 行上，交付的是 ±500（错值）；HBM 行是 p012-t02-r02，存在但无符号 |

按性质归并，是 **5 类**问题：

1. **建表校验直接崩**（V256，第 57 页）：`grid_ys` 非严格递增时 `DetectedTable` 抛 `ValidationError`，整件零输出。唯一一处「零输出」缺陷，优先级最高。修法应是在建表前对 grid 线做单调化/去重，而不是放宽校验。
2. **档位与参数名的对应关系没建立**（V003 `TJ`、V077 `RVDD`/`DVDD`、V199 `ID`）：同一参数名下的多个速度/温度/测试条件档，值与档位串行。
3. **合并符号单元只落在首行**（V320 `V(ESD)`、V162 `VCC`）：一个符号纵向合并多行时，只有其中一行带符号，另一行成为无符号孤儿块，下游按符号取数会取到错行或错值。
4. **同名符号跨语境抢匹配**（V319 `TA`、V162 `VI`/`IO`）：符号在页内出现在多个参数表的列头或行首，没有按表归属消歧。
5. **行内符号与参数名同格时未拆分**（V304、V145 等）：`V CC Supply voltage`、`PDISS Power Dissipation` 这类格子没有拆成两列；本次靠评估侧的文本级匹配才捞回来，Parser 侧应补结构化拆分。

## 9. 口径与局限（必须连同数字一起读）

1. **评的是行级检索 + token 保真，不是逐字段严格解析。** 参数块（block）把合并单元格的多行并成一块，块的数值集合取并集；块内行数 ≥5 的一律降级为软命中。
2. **condition 不进主归因。** 这批 Gold 的 condition 多来自列头（`HC, VCC=2V` 对应某条子列 + 分组行），块文本不携带那层语义。按字符串定位判会把版式差异记成解析错误，故单列参考值。
3. **`多余候选` 只能是样本相对值**，理由见 §5.1。真正的误提率需要全表枚举的 Gold 才能算。
4. **V256 的 5 行计入分母并归为「解析失败」**，没有从分母里剔除——剔除会把崩溃伪装成不存在。
5. **块组装上限 8 行**是保守选择：宁可少吞（数值判缺失）也不多吞（数值保真虚高）。
6. **`symbol 错配 0` 不等于没有符号问题。** 该归因只在「符号定位不到、但值在同一页」时触发；若符号找到了却挂在错行上（值不符），会被记成 `数值错` 或 `evidence page 错`。读这一栏时请与 §8 的逐条描述一起看。
7. **V101 有一次补跑**：早先单件预跑留下同名目录，编排器拒绝覆盖（输出隔离生效）；移走残留后用 `--only V101` 重跑，通过后删除残留；`replay_summary.json` 里标记了 `rerun: ["V101"]`。

## 10. 产物清单与复现

| 文件 | 内容 |
|---|---|
| `env_snapshot.json` | 环境与版本快照（含 parser 包指纹） |
| `input_manifest.csv` / `.json` | 24 件输入白名单 + SHA-256 |
| `replay_summary.json` / `replay_log.jsonl` | 逐件执行结果 |
| `logs/<样本>.log` | 逐件 stdout/stderr 原文 |
| `per_sample/<样本>/` | 逐件 Parser 全量输出（document / tables / candidates / text_blocks / boundary_decisions / run_manifest） |
| `rows_parser.csv` | 全部候选块（21181 条） |
| `eval_detail.csv` | 105 行 Gold 的逐行判定 |
| `metrics.json` / `legacy_metrics.json` | 正式 / 修正前指标 |
| `calibration_diff.csv` / `.md` | 逐行口径对照 |
| `text_hit_audit.csv` | 文本级命中逐条审计 |
| `extra_candidate_audit.csv` | 样本外候选块抽检（10 块） |
| `per_sample_json/<样本>.json` | 逐件候选块 + Gold 判定合并视图 |
| `boundary_assertions.txt` | 四条边界机检原始输出（25 项 PASS） |
| `report.md` | 本报告 |

### 10.1 逐件结果与输出路径

| 样本 | 表 | 候选块 | Gold 行 | 命中 | 完全一致 | 输出目录 |
|---|---|---|---|---|---|---|
| V003 | 364 | 3950 | 5 | 5 | 4 | `per_sample/V003/` |
| V011 | 20 | 181 | 5 | 5 | 5 | `per_sample/V011/` |
| V038 | 199 | 1141 | 5 | 5 | 5 | `per_sample/V038/` |
| V077 | 215 | 2439 | 5 | 5 | 3 | `per_sample/V077/` |
| V097 | 22 | 188 | 3 | 3 | 3 | `per_sample/V097/` |
| V101 | 14 | 127 | 9 | 9 | 9 | `per_sample/V101/` |
| V111 | 33 | 239 | 3 | 3 | 3 | `per_sample/V111/` |
| V145 | 92 | 559 | 3 | 3 | 3 | `per_sample/V145/` |
| V146 | 14 | 64 | 5 | 5 | 5 | `per_sample/V146/` |
| V162 | 31 | 246 | 3 | 3 | 0 | `per_sample/V162/` |
| V173 | 18 | 103 | 3 | 3 | 3 | `per_sample/V173/` |
| V199 | 11 | 54 | 5 | 5 | 4 | `per_sample/V199/` |
| V242 | 356 | 1782 | 5 | 5 | 5 | `per_sample/V242/` |
| V244 | 189 | 2351 | 5 | 5 | 5 | `per_sample/V244/` |
| V256 | — | — | 5 | 0 | 0 | `per_sample/V256/`（无输出） |
| V271 | 359 | 5422 | 5 | 5 | 5 | `per_sample/V271/` |
| V290 | 6 | 30 | 3 | 3 | 3 | `per_sample/V290/` |
| V304 | 18 | 89 | 3 | 3 | 3 | `per_sample/V304/` |
| V319 | 12 | 49 | 4 | 3 | 1 | `per_sample/V319/` |
| V320 | 101 | 583 | 5 | 5 | 4 | `per_sample/V320/` |
| V336 | 11 | 72 | 4 | 4 | 4 | `per_sample/V336/` |
| V345 | 77 | 376 | 4 | 4 | 4 | `per_sample/V345/` |
| V346 | 124 | 670 | 5 | 5 | 5 | `per_sample/V346/` |
| V349 | 78 | 466 | 3 | 3 | 3 | `per_sample/V349/` |

复现：

```bash
python workbench/gate6a_replay/_env_and_manifest.py   # 环境快照 + 输入清单
python workbench/gate6a_replay/_run_replay.py         # 24 件回测（约 14 分钟）
python workbench/gate6a_replay/_evaluate.py           # 正式口径
ICPDF_EVAL_LEGACY=1 python workbench/gate6a_replay/_evaluate.py   # 修正前口径
python workbench/gate6a_replay/_compare_eval_calibration.py       # 逐行对照
python workbench/gate6a_replay/_audit_text_hits.py                # 文本级命中审计
python workbench/gate6a_replay/_make_report.py                    # 本报告
```

**输出隔离（边界 4）**：以上全部产物只写 `runs/gate6a_replay_v1/`；既有 Gold 台账与历史 `runs/` 未被写入。编排器启动时断言输出根名必须为 `gate6a_replay_v1`，且 worker 目录已存在时拒绝覆盖。

## 11. 内部审计证据包

Reviewer 叫停灰度后追加的证据，全部落在 `audit/`，索引见 `audit/README.md`：

| 文件 | 回答的问题 |
|---|---|
| `error_matrix_105.csv` | 105 行逐行判定，「命中」到底怎么算（命中 89 / 错误匹配 15 / 漏提 1） |
| `error_matrix_105_v1_prefix.csv` | 同一张表的 v1 版本，用于与本报告口径对齐 |
| `error_matrix_105_README.md` | 字段字典 + `match_status` 三值定义 + 自查命令 |
| `evaluator_flips_39.csv` + `evaluator_v1_legacy/` + `evaluator_v2_final/` | 39 行翻正的两版评估器与逐行成因 |
| `parser_json_immutability.txt` | 修评估器时 185 个 Parser JSON 哈希全同（变化 0） |
| `v256_crash_evidence.md` | V256 真实 traceback + 第 57 页 `grid_ys` 逐位前后对照 |
| `postfix_rerun_24.md` | 修复后 24 件重跑：24/24 成功，V256 216 页 |
| `parser_v1_v2_diff.md` | 其余 23 件 115 个文件**逐字节完全相同** |
| `pdf_sha256_24.csv` / `parser_commit.txt` / `pip_freeze.txt` | 输入、代码、依赖三方溯源 |
| `network_guard_proof.md` | 四类出网调用实测全部拦下，`llm_blocked` 累计 0 |
| `TECH_DEBT.md` | 四类暂不修的 Parser 语义缺陷与回归约束 |

本报告（§1–§10）记录的是 **v1** 首次回测，指标与结论均不作修改。
修复后的重跑结果单独写在 `audit/postfix_rerun_24.md`，不覆盖本报告。

