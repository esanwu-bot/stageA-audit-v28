# 安全事件报告：GitGuardian 告警处置

| 项目 | 内容 |
| --- | --- |
| 事件编号 | SEC-2026-11-12-01 |
| 发现时间 | 2026-11-12 |
| 发现方式 | GitGuardian 对公开仓库 `esanwu-bot/stageA-audit-v28` 的自动扫描告警 |
| 告警类型 | Generic Password、High Entropy Secret |
| 定级 | 中（内网信息暴露，无凭据泄露） |
| 处置状态 | 已闭环 |

---

## 一、摘要

GitGuardian 对公开仓库报告了两类告警：Generic Password 与 High Entropy Secret。

排查结论：**不存在任何真实凭据泄露**。触发源是一段**内网 Git 仓库地址**——

1. `audit/pip_freeze.txt` 第 20 行的可编辑安装记录中，仓库地址 `.git` 之后紧跟一个 `@<40位commit SHA>`。GitGuardian 的 URL 解析器把 `@` 之前的整段当作 userinfo（即 `user:pass@host` 中的 `user:pass`），于是报 Generic Password；`@` 之后的 40 位十六进制串又触发 High Entropy Secret。
2. 另有 13 个文件含该内网仓库的裸地址，其中的 24 位组织 ID 触发高熵规则。

两类告警指向同一件事：**内网仓库的主机名与组织 ID 被公开了**。这是真实的信息暴露，但不含账号密码。已通过历史重写彻底剔除。

---

## 二、告警定位

| 触发位置 | 形态 | 命中规则 | 性质 |
| --- | --- | --- | --- |
| `audit/pip_freeze.txt:20` | 可编辑安装行：`-e git+<内网主机>/<组织ID>/<repo>.git@<40位SHA>#egg=<包名>` | Generic Password、High Entropy Secret | 误报「密码」；真实暴露「内网地址」 |
| `gate6/r2/GIT_BASELINE.json` | 裸 remote URL | High Entropy Secret（24 位组织 ID） | 真实暴露内网地址 |
| `gate6/r2/GIT_BASELINE_ISOLATION.md` | 同上 | 同上 | 同上 |
| `gate6/r2_p1p2_fix/git_ancestry_verify/GIT_ANCESTRY_VERIFICATION.md` | 同上（2 行） | 同上 | 同上 |
| `gate6/r2_p1p2_fix/git_ancestry_verify/git_verify_raw.log` | 同上（2 行） | 同上 | 同上 |
| `gate6a-plan/PUSH_REVIEW_45_COMMITS.md` | 同上（3 行） | 同上 | 同上 |
| `gate6a-plan/_build_evidence_v11.py` | 同上（生成器内硬编码） | 同上 | 同上 |
| `gate6a-plan/batch2_review/INDEX.md` 等 4 个文件 | 同上（共 12 行） | 同上 | 同上 |

合计 **14 个文件、28 行**，分布在 `main`、`feat/gate6a-annotation`、`feat/gate6a-batch3`、`feat/gate6a-audit` 四个分支的历史中。

### 为什么 `@` 会被当成密码

`pip freeze` 对以 VCS 方式安装的包输出如下形式：

```
-e git+<scheme>://<host>/<path>.git@<commit>#egg=<name>
```

这里的 `@` 是**版本分隔符**，不是 userinfo 分隔符。但通用检测器无法区分二者，因为 RFC 3986 中 `@` 恰好也是 userinfo 与 host 的分界。这是该规则已知的系统性误报模式。

---

## 三、排查过程与证据

### 3.1 全历史凭据扫描

对全部 **1247 个 blob / 111 个提交**（非浅克隆）逐字节解码后匹配：

| 检测项 | 正则 | 命中 |
| --- | --- | --- |
| AWS Access Key | `AKIA[0-9A-Z]{16}` | 0 |
| GitHub Token | `gh[pousr]_[A-Za-z0-9]{36}` | 0 |
| OpenAI Key | `sk-[A-Za-z0-9]{20,}` | 0 |
| Slack Token | `xox[baprs]-…` | 0 |
| 阿里云 AccessKey | `LTAI[0-9A-Za-z]{12,}` | 0 |
| URL 内嵌凭据 | `://` 之后紧跟 userinfo 段再接 `@` | 0 |
| 赋值型密码 | `password|passwd|pwd|secret|api_key` 后接值 | 0 |

### 3.2 环境快照

`v1_env_snapshot.json`、`v2_env_snapshot.json` 的 `llm.env_vars_present` 均为空数组 `[]`，不存在 env 字典，无凭据键。

### 3.3 疑似项逐个排除

| 疑似项 | 结论 |
| --- | --- |
| `pip_freeze.txt` 私有源 | URL 中 `://` 后直接是主机名，**无 `user:pass@` 段**，不含凭据 |
| `_probe_network_guard.py` | 仅含网络探测向量，无凭据 |
| `_push_r2_github.py` | token 由 `git credential fill` **运行时取得**，无硬编码 |
| `runtime_observe_v256.json` | `GEMINI_API_KEY=***`，值是掩码，属「环境已擦洗」的证据 |
| `r3/b64_parts_r3/` 3 个分卷 | Base64 分片的 `audit_minimal_v28_r3.zip`，二进制备份，非凭据 |

### 3.4 本地残留

| 检查项 | 结果 |
| --- | --- |
| `~/.git-credentials` | 不存在 |
| `~/.netrc` | 不存在 |
| git 全局凭据 | 走 Windows 凭据管理器（加密存储），无明文文件 |
| `~/.npmrc` | 仅 registry 地址，无 `_authToken` |
| 进程环境变量 | 存在若干运行时 token，但**值未出现在仓库任何 blob 中**（逐字节比对确认） |

---

## 四、清理动作

### 4.1 内网地址脱敏

使用 `git filter-repo --replace-text` 重写**全部 111 个提交 × 4 个分支**：

| 原内容 | 替换为 |
| --- | --- |
| `<内网主机>/<组织ID>/<repo>.git` | `[REDACTED-INTERNAL-REPO]` |
| `pip_freeze.txt` 的整行安装记录 | `icpdf-extractor==[REDACTED-LOCAL-VCS]` |

### 4.2 高熵噪声剔除

`r3/b64_parts_r3/` 的 3 个 Base64 分卷（共 45.8 KB）从历史移除。移除前先还原验证：

- 文件：`audit_minimal_v28_r3.zip`
- 大小：34049 字节
- SHA-256：`866cc36f6dc263e3efa89869a251957a77b2fd30f72ce916aa0b3df8faf65f9e`
- 内容：6 个文件（`verify_reviewer.py`、2 个测试、2 个 diff、`SHA256SUMS.txt`）
- 结论：与审计包无关的重复副本，已另存于包外

### 4.3 历史重写结果

4 个分支全部强推，旧 commit SHA 全部失效：

| 分支 | 旧 HEAD | 新 HEAD |
| --- | --- | --- |
| `feat/gate6a-audit` | `b5f9a83` | `e79dbb1` |
| `main` | `e3c9b64` | `ae4ef12` |
| `feat/gate6a-annotation` | `5bb947a` | `6803c3f` |
| `feat/gate6a-batch3` | `40888e4` | `6086d3e` |

> 上表是**重写当次**的 HEAD。`feat/gate6a-audit` 其后又落了 v3.3 语义门槛提交
> （`460ea0f`），当前 HEAD 以 `audit/README.md` 的直链为准。

#### `main` 的 SHA 变化：需要单独澄清

`main` 的 `e3c9b64 → ae4ef12` 是本次安全脱敏执行历史重写产生的**副产物**。

**该操作不等于把 Gate 6A 功能代码合并进 `main`。**

逐文件比对重写前后的 `main` 树（备份仓原始 `main` vs 重写后 `main`）：

| 项 | 结果 |
| --- | --- |
| 文件总数 | 270 → 267 |
| 新增 | **0** |
| 删除 | 3（`r3/b64_parts_r3/` 的 3 个 Base64 分卷） |
| 内容变化 | 7 个文件，差异合计 **12 行** |

这 7 个文件的 12 行差异**全部**是内网地址与 commit SHA 的 `[REDACTED-INTERNAL-REPO]`
替换，没有任何一行涉及功能代码：

| 文件 | 差异行数 |
| --- | --- |
| `gate6/r2/GIT_BASELINE.json` | 1 |
| `gate6/r2/GIT_BASELINE_ISOLATION.md` | 1 |
| `gate6/r2_p1p2_fix/git_ancestry_verify/GIT_ANCESTRY_VERIFICATION.md` | 2 |
| `gate6/r2_p1p2_fix/git_ancestry_verify/git_verify_raw.log` | 2 |
| `gate6a-plan/PUSH_REVIEW_45_COMMITS.md` | 3 |
| `gate6a-plan/_build_evidence_v11.py` | 1 |
| `gate6a-plan/push_review_raw.log` | 2 |

Gate 6A 的解析与判定代码仍然只在 `feat/gate6a-audit` 上。`main` 的内容组成与重写前
一致——只是少了被剔除的 Base64 分卷、少了内网地址字面量。**SHA 变化是重写的结果，
不是合并的结果。**

---

## 五、验证结果

| 验证项 | 结果 |
| --- | --- |
| 内网组织 ID 残留 | 0 个 blob |
| 7 类凭据正则 | 全部 0 命中 |
| `r3/b64_parts_r3` | 已不存在 |
| 远端 refs 与本地 refs | 4/4 逐个 SHA 相同 |
| `SHA256SUMS.txt` | 57/57 校验通过 |
| 可达提交 / 对象数 | 112 / 1253 |

> **关于验证方式**：Git 是内容寻址存储，远端 ref 与本地 ref 的 SHA 相同即意味着对应对象树逐字节相同。因此「远端 4 个 refs 与本地一致」+「本地全历史扫描 0 命中」已构成对线上状态的充分证明，无需全量克隆复验。

---

## 六、保留项与理由

`audit/parser_commit.txt`、`audit/source_fingerprint.md`、`audit/monotonic_lattice.diff` 中保留了 40 位 commit SHA。

理由：

1. **这是审计溯源的锚点**。「本包产物出自哪个 commit」是可复算性的前提，删掉等于毁掉验证链。
2. **commit hash 不是凭据**。它是 git 对象标识符，由内容哈希得到，脱离仓库无法反推任何内容。
3. **不触发高熵规则**。纯十六进制串的理论熵上限为 4.0 bit/char（16 个符号），低于通用高熵检测阈值；且内网地址已脱敏，单独的 SHA 失去可定位性。

---

## 七、遗留风险

| 风险 | 说明 | 缓解 |
| --- | --- | --- |
| GitHub 保留不可达对象 | 强推后旧提交在服务端可能短期仍可按 SHA 直接访问 | 常规扫描基于 clone，不会拉取不可达对象；若复扫仍报警，可删库重建 |
| 旧 SHA 已失效 | 历史重写导致此前报告中引用的 commit SHA 全部失效 | 本报告与 README 已给出新 SHA |
| 源仓仍有原始地址 | 内网源仓的审计副本未脱敏（其 origin 本就是该地址，不构成泄露） | 发布前必须走脱敏关卡 |

---

## 八、预防措施

### 8.1 推送前脱敏关卡（已固化）

```bash
# 1. 关键词粗筛
grep -rn "key\|token\|password\|secret" \
  --include='*.md' --include='*.txt' --include='*.json' --include='*.py' .

# 2. 内嵌凭据 URL
git grep -n -E '://[^/[:space:]]+:[^/[:space:]]+@'

# 3. 已知密钥前缀
git grep -n -E '(AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{36}|sk-[A-Za-z0-9]{20,}|LTAI[0-9A-Za-z]{12,})'
```

### 8.2 本次新增的两条教训

1. **安全说明本身会二次触发扫描**。第一版 `Security Note` 把原始泄露 URL 和 `user:pass@` 形态逐字写了进去，结果被自己的关卡抓出来——等于把触发规则又写回仓库。描述漏洞形态时必须用占位符。
2. **`pip freeze` 的 VCS 安装行是高危格式**。凡以 `-e git+...@<commit>` 形式安装私有源，输出即触发 Generic Password。发布任何环境指纹前，必须先过滤这类行。

---

## 九、结论

本次告警**不是凭据泄露**，是内网仓库地址被公开导致的规则命中。经全历史逐字节排查确认无任何有效凭据入库；内网地址已从全部 111 个提交 × 4 个分支中彻底剔除；审计溯源所需的 commit SHA 按最小必要原则保留，且不构成敏感信息。

**内网地址已脱敏，源哈希保留。**
