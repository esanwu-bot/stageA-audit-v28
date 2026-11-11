# Gate 6A · Batch 2 Gold Set（v1.1）

## 这批是什么

6 件样本，每件取最规整的电气参数，共 **24 行**。全部经人工逐行比对 PDF 页面后签名
（`row_status=CONFIRMED`，`reviewer=wuxiaoxian`）。

| 样本 | 型号 | 页 | 保留参数 | 行数 |
| --- | --- | --- | --- | --- |
| V101 | CD74HCT574 | 3 | VIH / VIL / VOH，各按 VCC 分 3 行 | 9 |
| V097 | DEM-OPA | 3 / 8 | VID / Slew rate / Settling time | 3 |
| V162 | SN74LVTH18504A | 25 | VCC 范围 / VI 范围 / IO 低电平电流 | 3 |
| V349 | ADC3541 | 5 / 9 | TJ / Tstg / 噪声谱密度 | 3 |
| V145 | DAC7750 | 12 | PDISS / VSENSEP 电流 / 建立时间 | 3 |
| V111 | DS90C | 6 / 7 | VDD / Tstg / 失调电压 | 3 |

### v1 → v1.1 的唯一改动：V101 按 VCC 拆行

Reviewer 指出 v1 只留了 VCC=2V 一列，丢了 4.5V 与 6V 的条件。已按页面结构拆成 3×3=9 行，
`condition` 填 `HC, VCC=2V` / `HC, VCC=4.5V` / `HC, VCC=6V`。

取值依据（V101 第 3 页词坐标实测，`TEST CONDITIONS` 列的 `2` / `4.5` / `6` 是三行行条件，
不是三个列头，所以按行读取 MIN/MAX 列）：

| 参数 | VCC=2V | VCC=4.5V | VCC=6V | 取值列 |
| --- | --- | --- | --- | --- |
| VIH（MIN） | 1.5 | 3.15 | 4.2 | MIN |
| VIL（MAX） | 0.5 | 1.35 | 1.8 | MAX |
| VOH（MIN） | 1.9 | 4.4 | 5.9 | MIN |

> 附带修正：v1 曾把 VOH 的第三组误写成 4.4（与 4.5V 那行重复），实测页面是 **5.9**。

## 保留标准（四条硬规则）

1. **参数名必须能在该页原文里原样搜到**，不是模型转述、不是条件、不是残词；
2. `min/typ/max` 只放纯数字，单位一律进 `unit` 列，禁止出现 `Continuous`、`See Note` 这类词；
3. 单位必须出现在该页；
4. 同一参数若在页面按条件（VCC / 温度 / 负载）分组，**按条件拆行、条件写进 `condition`**，
   而不是只取一列或重复占位。

这四条全部由 `validate_annotation.py` 机检复核，本批 **24/24 OK，0 ERROR**。

## 相比初稿删掉了什么

初稿 82 行（VLM 预标注 + 人工点选），本批保留 24 行（其中 V101 由 3 行拆为 9 行），**剔除 64 行**：

- **残词/断句**：`Input volta`、`LVDS Outpu`、`Short-Circuit Durati`、`LVC MOS Input Voltage`；
- **把条件当参数名**：`VNEG_IN_x`、`VPOS_IN_x`、`For VI < or VI > VCC`；
- **数值列里塞英文**：`Continuous`、`See Thermal Information Table`、`VDD + 0.3`、`0.66V_DD`；
- **表达式而非数值**：`MIN(2.1, AVDD+0.3)`、`V_CC-0.2`、`160 (320)`；
- **同参数重复行**：V349 的 SNR 有 5 行、V145 的 "Input voltage" 有 8 行。

判定全部基于页面对照：名字截断的，先在页面里找完整词，找得到才补全（`High Level Output
Voltage CMOS Loa` → `...Loads`），找不到的直接删，不做猜测。

## 已知局限（请 Reviewer 一并裁定）

1. ~~V101 的 VIH/VIL/VOH 只取一列~~ —— **v1.1 已按 VCC 拆行解决**，见上表。
2. **V162 的名字带列后缀**（`Supply voltage range, VCC`），因为页面上就是连写的，
   这样能通过"名字可验真"检查；若统一去后缀，则名字会与页面不一致。
3. `confidence_score` 是机器分（纯 det 分，VLM 自报置信度未掺入——实测它恒为 1.00，
   掺进去只会给所有行统一加分、抹平区分度），**仅供参考，未经校准**，不能当准确率上界。
4. 分母口径未变：准确率 = Gold `CONFIRMED` 行；漏提取分母 = Gold 应有总数；
   错提取分母 = Parser 输出候选总数。本批不得外推到 28 件全集。

## 文件

| 文件 | 说明 |
| --- | --- |
| `Batch2_GOLD_v1.csv` | 交付 Gold，UTF-8 带 BOM，Excel 可直接打开 |
| `Batch2_GOLD_v1.xlsx` | 同内容 Excel |
| `Batch2_DRAFT_FIXED.csv` | 82 行机器草稿，Gold 的筛选来源（可追溯） |
| `validate_annotation.py` | 机检脚本（含 15 行脏数据自测） |
| `git_evidence_gate6a.txt` | Reviewer 指定的 4 条 Git 命令终端原始输出 |
| `_build_batch2_interactive.py` | 圈选台生成器 |
| `_draft_extract.py` | 零 Parser 依赖的草稿提取器 |
| `_vl_extract.py` | Qwen3-VL 预标注（带磁盘缓存） |
| `_build_batch2_viewer.py` | 早期的标题定位/目录页过滤实现 |
| `_b2_app.js` | 圈选台前端逻辑（预载草稿 / 减法 / CSV 回导 / Blob+BOM 下载） |

复现：

```
cd workbench/_gate6a_prep
python validate_annotation.py --csv Batch2_GOLD_v1.csv
```
