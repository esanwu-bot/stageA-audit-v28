# SEC-INCIDENT-01 · 环境取证过度采集导致凭据泄露

- 事件编号：`SEC-INCIDENT-01`
- 发现时间：2026-11-11 11:45（GitHub Secret Scanning 告警转达）
- 处置完成：2026-11-11 11:5x
- 严重级别：高（公开仓库、真实凭据、已存在数小时）
- 影响仓库：`esanwu-bot/stageA-audit-v28`（**public**，0 fork）
- 泄露文件：`gate6/r2_p1p2_fix/http_probe_v1_v4/env/process_env.json`

---

## 0. 结论口径（引用本事件时请按此，禁止简化）

### 0.1 已做到的

泄露文件**已从 `main` 当前分支树彻底移除**。实测：全新克隆 `main` 后，
全历史 **241 个 blob** 中 5 个凭据的字面量命中为 **0**；旧提交 `e14f544`
不在克隆对象库中；`sha256sum -c SHA256SUMS.txt` 29/29 通过。

### 0.2 未做到、且不得声称的

**不得声称「已彻底从 GitHub 删除」。** 由于 Git 的悬空对象（dangling /
unreachable object）机制，旧的 commit SHA 在被 GitHub 服务端垃圾回收之前，
**依然可能通过直接 URL 访问**。

这不是推测，是本项目实测的结论：

| 实测项 | 结果 |
|---|---|
| `raw.githubusercontent.com/<repo>/e14f544…/…/env/process_env.json` | HTTP **200**，28633 字节，内容仍含该 Key |
| `git fetch origin e14f544` | **成功**，旧提交仍可按 SHA 取回 |

正确的表述模板：

> 已从当前分支树彻底移除，但受 Git 悬空对象机制影响，旧 commit SHA 在
> GitHub 完成垃圾回收前仍可能通过直接 URL 访问。

### 0.3 凭据状态（写这句话前必须有证据）

`GEMINI_API_KEY` 及另外 4 个凭据的**吊销尚未执行、也未获确认**——
执行吊销需要 Google Cloud Console / CodeBuddy / WorkBuddy 的登录会话，本 Agent 无此权限。

因此**在吊销被确认之前，任何文档、提交信息或对外说明都不得写「相关 Key 已失效 / 已吊销」。**
写了就是虚假陈述，比泄露本身更难挽回。

待 §6 第 1 项完成、并拿到后台的删除/禁用回执后，才可把 §0.2 的模板升级为：

> 已从当前分支树彻底移除，且相关 Key 已吊销失效；受 Git 悬空对象机制影响，
> 旧 commit SHA 在 GitHub 完成垃圾回收前仍可能通过直接 URL 访问，但内容已无利用价值。

本文件目前的吊销状态字段：**`revocation_status = PENDING_USER_ACTION`**。

---

## 1. 发生了什么

V1–V4 受控 HTTP 探针需要取证「服务进程真实拿到的 `ALLOW_PARSE` / `CLASSIFY_ONLY`」。
我写的探针脚本为了证明「这不是回显 shell 变量」，用

```python
real_env = psutil.Process(pid).environ()
json.dump(real_env, ...)          # ← 错误：dump 了全部 229 个键
```

把**承载探针的进程的完整环境块**写进了 `env/process_env.json`，并随证据包
提交、推送到公开仓库。

该进程由本机 IDE 启动，因此它的环境块里带着 IDE 自身的凭据。

## 2. 泄露范围

采集到 **229** 个环境变量。其中键名命中
`KEY/TOKEN/SECRET/PASSWORD/AUTH/API` 等模式的有 16 个，进一步甄别后
**确认为真实凭据的有 5 个**（下表只列变量名，不列任何取值）：

| 变量名 | 长度 | 性质 |
|---|---|---|
| `GEMINI_API_KEY` | 39 | Google API Key（`AIza` 前缀），即 GitHub 告警所指 |
| `CODEBUDDY_GATEWAY_PASSWORD` | 43 | 网关口令 |
| `CODEBUDDY_DOCUMENT_TOKEN` | 48 | 文档服务 Token |
| `WORKBUDDY_VLM_AUTH_TOKEN` | 43 | 视觉模型鉴权 Token |
| `WORKBUDDY_PAC_RPC_TOKEN` | 32 | PAC RPC Token |

其余 11 个命中模式的键为会话 ID（`CLAUDE_SESSION_ID`、`CODEBUDDY_SESSION_ID`、
`SANDBOX_IPC_TRACE_SESSION`）、功能开关（`*_DISABLED`）、`SESSIONNAME`、
路径（`CODEBUDDY_SESSION_SKILL_DIRS`）与空值（`WECOM_MEDIA_API_EXTRA_QUERY`），
不构成凭据，但同样属于**不应外泄的宿主环境信息**。

按前缀族统计，被不当采集的主要是：
`CODEBUDDY_` 66 个、`WORKBUDDY_` 31 个、`CLIENT_` 9 个、`WECOM_` 6 个、
`ACC_` 4 个、`ANDROID_` 4 个、`BASH_` 4 个、`SANDBOX_` 4 个、`TENCENT_` 2 个……

**结论：这次采集与探针目的（只要 3 个 `ICEX_*` 开关）严重不匹配，
属于取证范围失控，不是「多抓了一两个变量」。**

## 3. 根因

1. **采集策略错误：全量 dump 而非白名单。** 取证的原则应当是「只采集被证明需要的东西」，
   而我按「先把环境全存下来，回头再挑」的思路做，等于把宿主机的全部秘密复制进了产物。
2. **缺少提交前扫描。** `SHA256SUMS.txt` 只校验完整性，不检查内容敏感性；
   入库前没有对 `env/*.json` 做一次敏感值扫描。
3. **告警盲区：** `.gitattributes` 设了 `* -text`、逐文件哈希校验也做了 25/25，
   这些机制保证了**字节保真**，却完全不涉及**内容是否该被公开**。
   校验做得越漂亮，越容易让人误以为「已验证 = 可安全发布」。

## 4. 已完成的处置

| # | 动作 | 状态 |
|---|---|---|
| 1 | 引入脱敏模块 `harness/_env_redact.py`：**白名单为主闸**，未列入 `allowlist` 的变量连键名都不写；白名单内的变量再过「敏感名 + 已知凭据形状 + 高熵值」兜底闸；命中一律置 `***` | 完成 |
| 2 | 改写 `harness/_probe_v1_v4.py`：环境采集改走 `redact_env()`，不再 dump 全量 | 完成 |
| 3 | 重新生成 `env/process_env.json`：229 → **4** 个键（`ICEX_WORKBENCH_ALLOW_PARSE`、`ICEX_CLASSIFY_ONLY`、`ICEX_WORKBENCH_PORT`、`PYTHONIOENCODING`），其余 225 个仅保留前缀族计数；写后回读校验，确认不含任何原始高敏值 | 完成 |
| 4 | 重写引入该文件的提交并强制推送，使其离开 `main` 的提交链（原提交 `e14f544d4b40b5d2b0e79663111f7a06d55d4cb6`，含密 blob `24ac7b0d05411e512841f2993eac683c908e4606`；新提交 `25cb7c1e7ce741d2cc0cb2fefefddb00cb7e38ab`） | 完成 |
| 5 | 全量重扫历史，确认 `main` 可达的 241 个 blob 中已无这 5 个凭据的字面量 | 完成，命中 0 |
| 6 | 实测 GitHub 侧旧提交是否仍可访问 | **仍可访问，见 §5** |
| 7 | 新增 `harness/_selftest_env_redact.py`：注入 16 个敏感样例（覆盖 `KEY/TOKEN/SECRET/PASS/AUTH` 五族 + 值形态闸 + 非白名单闸），产出 `env/redaction_selftest.json`，逐条记录期望/实际/是否泄漏 | 完成，17 项全 PASS |
| 8 | 新增单测 `tests/unit/test_env_redact.py`（pytest），把上述契约锁进 CI | 完成，15 项全通过 |

选择「重写该提交」而不是「新提交覆盖」的理由：
仓库是 **public**，新提交覆盖后旧 blob 仍可通过 `e14f544` 这个 SHA 直接访问；
且**泄露文件只存在于这一个提交里**，它恰好是 main 的 tip，
因此重写 tip 不触碰任何更早提交——`_d_prime/`（9/9）与 HTTP 探针原始响应
等既有审计哈希全部逐字节不变，`SHA256SUMS.txt` 中除 `env/process_env.json`
自身外无一行需要改动。

**但必须明确：重写 + 强推只解决了「main 分支链上不再包含它」，
没有解决「按 SHA 仍能取到它」。** 见下一节实测。

## 5. 重写之后的实测结果（重要）

强推完成后立即做了两项验证：

| 验证 | 结果 |
|---|---|
| 全新克隆 `main`，扫描全部 241 个 blob | 凭据字面量命中 **0** |
| 全新克隆中旧提交 `e14f544` 是否存在 | **不存在** |
| `sha256sum -c SHA256SUMS.txt`（29 条） | 29/29 OK |
| `raw.githubusercontent.com/.../e14f544.../env/process_env.json` | **HTTP 200，28633 字节，仍含 `AIza` 形态与 `GEMINI_API_KEY` 键名** |
| `git fetch origin e14f544` | **成功，旧提交仍可按 SHA 取回** |

结论：GitHub 对「已被强推丢弃、但仍在服务端对象库中」的提交，
在一段时间内仍提供按 SHA 的访问。**因此这次泄露不能认为已在服务端消除。**

## 5.1 消除服务端残留的三条路（按建议顺序）

1. **把仓库改为 private（最快、最有效）。** Settings → General → Danger Zone →
   Change visibility → Private。改完该 URL 立即不再公开可读。
   本仓库是纯文件传输用途、0 fork、无外部依赖，改私有不影响任何审计流程。
2. **向 GitHub Support 申请清除不可达对象。** 提工单说明：已强推重写历史，
   请求 *purge unreachable commits / remove cached views*，并附上原 SHA
   `e14f544`。这是唯一能让该 URL 真正失效的官方途径。
3. **极端情况：删除并重建仓库。** 若判定必须彻底，可删除该 repo 后重建再推一次
   当前 `main`（内容已在本地完整保存，`25cb7c1` 可直接重推）。
   代价是丢失 issue/PR/star 等元数据，本仓库基本为空，代价很小。

**无论走哪条，第 6 节的凭据吊销都是必须做的**——它才是止损的根本。

## 6. 必须由人完成、我无法代做的动作

**这两项我都没有权限执行，不能假装已完成。**

1. **吊销凭据（最高优先级）。** 我没有 Google Cloud Console、CodeBuddy、WorkBuddy
   的任何登录会话。
   - Google：`console.cloud.google.com` → APIs & Services → Credentials →
     找到 `AIza` 开头的该 Key → Delete（或先 Disable）。
   - 另外 4 个 Token 建议一并轮换：
     CodeBuddy 网关口令与文档 Token（重新登录/重置）、WorkBuddy VLM 与 PAC Token（重新授权）。
   - **注意：历史重写不能替代吊销。** 该 Key 已公开数小时，必须视为已泄露；
     GitHub 的缓存与第三方镜像可能仍留有副本。
2. **在 GitHub 关闭告警。** Security → Secret scanning → 找到该告警 →
   `Resolve alert` → 理由选 *Revoked*（若已吊销）或 *False positive*（不适用）。
   若选 *Revoked* 而实际未吊销，属于错误陈述，请务必先完成第 1 项。
3. **向 GitHub Support 申请清除不可达对象（建议与第 1 条并行，不是可选项）。**
   实测已证明强推后旧 SHA 仍可访问，所以这一步在「必须消除服务端残留」的前提下
   是必需的，仅靠改 private 只是限制了公开面，对象仍在服务端。

   工单要点：仓库 `esanwu-bot/stageA-audit-v28`；已强推重写历史；请求
   *purge unreachable / dangling commits and cached views*；附原 SHA
   `e14f544d4b40b5d2b0e79663111f7a06d55d4cb6` 与 blob
   `24ac7b0d05411e512841f2993eac683c908e4606`。

## 7. 教训（已写入项目规范）

1. **取证采集一律白名单。** 黑名单永远补不完——`GEMINI_API_KEY` 含 `KEY`，
   但 `WORKBUDDY_VLM_AUTH_TOKEN` 含的是 `AUTH`，`CODEBUDDY_GATEWAY_PASSWORD`
   含的是 `PASSWORD`；靠列举关键词只能事后补救。白名单漏掉只损失一条证据，
   黑名单漏掉就是泄露一个凭据。
2. **「完整性校验通过」不等于「可以公开」。** 哈希只能证明没被篡改，
   不能证明内容无害。二者必须分开检查。
3. **交接产物的默认假设应是「会进入公开仓库」。** 凡是把宿主机状态落盘的动作，
   默认按要公开来处理，而不是等出事再脱敏。
4. **任何 dump 环境 / dump 配置的动作，都要先问「这里面最坏能有什么」。**
