---
name: security-audit
description: 安全审计工作手册：查代码硬编码密码/密钥、SQL 注入等注入漏洞、配置文件明文敏感信息，以及认证、XSS、上传、依赖等其它安全隐患。当用户说「安全检查」「安全审计」「查漏洞」「代码安全」「security audit」时使用。
---

# 安全审计工作手册（security-audit）

给项目做安全体检：默认**只检查、出报告，不改代码**；用户明确要求修复时才改，且只做安全相关的改动。

## 铁律

1. **报告里永不出现完整密钥/密码明文**：引用时打码（`rag_app_***`、`sk-abc...xyz`），防止二次泄露到聊天记录。
2. 先定范围再查：用户指定文件/目录就查指定的；没指定就全项目扫（按下方排除清单）。
3. 报告要落到 `文件:行号`，分级标严重度，建议要能直接执行。
4. 检查依赖时注意：本机环境**离线为主**，能查本地（pip list、package-lock）就查本地，别依赖联网查 CVE，查不到就写「需联网复核」。

## 扫描范围

- 扫描：`backend/app/`、`backend/tests/`、`frontend/src/`、`frontend/public/`、`scripts/`、根目录与 `backend/` 下的配置类文件（`.env`、`.env.*`、`*.ini`、`*.toml`、`docker-compose*`、`pytest.ini`、`vite.config.js`、`package.json`）。
- **排除**（不要在这些里面翻，纯浪费）：`backend/venv/`、`frontend/node_modules/`、`frontend/dist/`、`__pycache__/`、`.git/`、`backend/data/`（运行时数据，默认跳过；如用户指定则单独查）。
- `backend/.env.example` 这类模板文件允许占位符（`your_key_here`），不算泄露，但要确认**真实 .env 没被提交进 git**。

## 四大检查板块

### A. 代码硬编码敏感信息

用 Grep 找（排除清单用 glob 过滤）：

- 变量名 + 字面量赋值：`(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|jwt[_-]?secret)\s*[:=]\s*["'][^"']+["']`
- 云厂商 AK/SK 特征：`LTAI[0-9A-Za-z]{12,}`（阿里云）、`AKIA[0-9A-Z]{16}`（AWS）
- 私钥：`-----BEGIN (RSA |EC |)PRIVATE KEY-----`
- 带凭据的连接串：`(mysql|postgres|redis|amqp)://[^@\s]+:[^@\s]+@`
- 手机号/身份证/银行卡正则，扫 `backend/data/` 外全项目（真实数据泄露到代码/文档）

判断口径：

- 🔴 生产可用的真实凭据硬编码（真密码、真 AK、真私钥）。
- 🟡 代码里的**默认值**兜底（如 `mysql_password = "some_default_pwd"`）——哪怕 .env 能覆盖，默认值一旦被部署沿用就是事故，且说明作者有硬编码习惯，需逐处排查。
- 🟢 测试文件里的假密码（`123456` 用于注册测试）、`.env.example` 占位符、文档里的示例值——不算问题，但要确认它们**确实只是测试/示例**（seeds 初始化脚本里的 admin 默认密码是 🟡，不是 🟢）。

### B. SQL 注入与其它注入

SQL 检查：

- 搜 `text(f"`、`text("...".format`、`f"SELECT`、`f"INSERT`、`f"UPDATE"`、`f"DELETE"`、字符串 `+` 拼 SQL。
- 每个 `execute(text(...))` 逐处确认：参数必须走 `:param` 绑定（`text("... WHERE id = :id"), {"id": x}`），**静态无变量的 SQL**（如 `text("SELECT 1")`）才安全。
- SQLAlchemy ORM / `select()` 表达式是安全的，见到即过。
- 发现拼接 → 🔴 确认输入来源是用户可控 → 给参数化改写建议（直接贴改后代码）。

其它注入（一并查，同属板块 B）：

- 命令注入：`os.system`、`subprocess.*shell=True`、`Popen(shell=True)` 且参数含用户输入。
- 代码注入：`eval(`、`exec(`、`pickle.load`/`torch.load` 吃外部数据。
- 路径穿越：文件名/路径由用户输入拼接（`upload_dir / filename`、`FileResponse(path)`、`open(path)`），且没有归一化校验（`Path(...).resolve()` 前缀检查、白名单扩展名）。重点看 `backend/app/api/documents.py` 的下载接口与上传落盘逻辑。
- SSRF：服务端用用户可控 URL 发请求。

### C. 配置文件明文敏感信息

- 逐个读根目录和 `backend/` 下的 `.env`、`docker-compose*.yml`、`*.ini`：真实密钥明文 → 🔴。
- `backend/app/config.py`（pydantic-settings）：逐个看带 `secret/password/key` 字样的字段**默认值**，按板块 A 口径分级。
- `frontend/`：`vite.config.js` 里内联密钥、`src/` 里非 `VITE_` 前缀的密钥被打包进前端产物（前端一切东西用户可见，任何密钥进 bundle = 公开）→ 🔴；`VITE_` 变量只允许放非敏感公开配置。
- Git 泄漏检查（关键）：
  - `git check-ignore backend/.env` 是否被忽略；`.gitignore` 是否漏了 `.env`、`*.local`、`data/`、`venv/`。
  - `git log --all --oneline -- backend/.env`（和 `.env*`）——**曾经提交过的密钥一律按已泄露处理**，建议轮换而不是删除文件了事。

### D. 其它安全隐患（本项目相关的重点）

- **认证**：`backend/app/core/security.py` —— JWT 密钥是否弱默认（`change-me` 类）、解码时是否校验算法与过期；密码存储是否 bcrypt（明文/MD5/无盐 SHA1 → 🔴）、bcrypt rounds < 10 → 🟡。看登录接口是否有限流（防爆破）。
- **CORS**：`backend/app/main.py` —— `allow_origins=["*"]` 且 `allow_credentials=True` → 🔴；开发期域名写死是 ✅（部署时记得收紧）。
- **XSS**：`frontend/src/components/common/MarkdownView.vue` 的 `v-html` —— 渲染前是否经过 sanitize（DOMPurify / marked 白名单）；LLM 输出与知识库内容都是不可信输入，未消毒 → 🔴。
- **前端凭据存放**：token 在 localStorage（`frontend/src/stores/auth.js`）——XSS 一旦得手即可窃取，🟡 提示 httpOnly cookie 方案或至少说明取舍；SSE 若把 token 放 URL query（`frontend/src/api/sse.js`）→ 🟡（会进访问日志）。
- **文件上传**：类型/大小校验、上传文件名是否原样落盘（可传 `.exe`/`.html` 被直接访问执行）。
- **日志**：`logging`/`print` 是否打印密码、token、完整请求体。
- **依赖**：`backend/requirements.txt` / `frontend/package-lock.json` 里知名高危版本（如旧版 Pillow、lxml、任意 `openai<2` 类过时锁版本）；本机离线则基于已知 CVE 知识判断并标注「需联网复核」。
- **调试残留**：`debug=True`、verbose traceback 外抛、`/docs` 生产环境暴露（本项目是毕设演示，说明风险即可）。

## 执行流程

1. 定范围（用户指定 → 只查指定；未指定 → 全项目，按排除清单）。
2. 按板块 A→D 顺序跑 Grep 模式 + 读关键文件（config.py、security.py、main.py、documents.py、sse.js、auth.js、MarkdownView.vue、.env*、docker-compose*）。
3. 每条问题记录 `文件:行号` + 代码片段（密钥打码）+ 分级 + 一句为什么危险。
4. 对疑似误报（测试假数据、占位符）逐条甄别，甄别不掉的标「需人工确认」。
5. 按下方模板出报告。

## 严重度分级

| 级别 | 含义 | 例子 |
|---|---|---|
| 🔴 严重 | 可被利用/已泄露，尽快处理 | 真实密钥硬编码、SQL 拼接用户输入、未消毒 v-html |
| 🟡 警告 | 有风险，视场景处理 | 弱默认值兜底、localStorage 存 token、bcrypt rounds 偏低 |
| 🟢 建议 | 加固建议，不紧急 | 文档暴露、生产 /docs、限流阈值 |
| ✅ 良好 | 顺带确认的亮点 | CORS 收紧、ORM 参数化、bcrypt 已用 |

## 报告模板（大白话）

```markdown
🔒 安全审计报告
- 范围：<目录/文件列表>（排除 venv、node_modules、dist 等）
- 结果：🔴 N 处 / 🟡 N 处 / 🟢 N 处

🔴 严重：
- 文件:行号 — 问题一句话 → 为什么危险 + 改法（可直接粘贴的代码）

🟡 警告：
- 文件:行号 — 问题 → 影响 + 建议

🟢 建议 / ✅ 良好：
- 简列

结论：<一段话总结，先修什么最划算；是否涉及密钥轮换>
```

## 修复模式

用户说「帮我修」时：

- 只做安全相关改动，原则：**密钥挪到 .env / 环境变量**（代码留空字符串默认）、SQL 改参数化、v-html 加消毒、路径加归一化校验。
- **绝不**：把真实密钥写进新代码、把 .env 真实值提交 git、删除密钥前不做轮换建议。
- 改动后重查一遍，报告前后对比；涉及已泄露密钥的，明确提醒用户「必须轮换（改密码/重置 AK）」，光删代码不算修好。
- 改 .gitignore 加 `.env` 后，若 git 历史里已有 `.env`，提醒用户历史无法靠删除抹掉。

## 已知基线（2026-10-27 首查 → 同日修复，后续审计核对是否回潮）

- ✅ 已修复：config.py 的 mysql_password / jwt_secret / admin_password 弱默认值已改空串，main.py lifespan 启动校验 jwt_secret、seeds.py 空密码拒建号；root / rag_app / admin 三个密码已轮换，只存 `backend/.env`（gitignored）
- ✅ 已复核：MarkdownView.vue 的 v-html 有 marked → DOMPurify 消毒管线，无风险
- 🟡 已知取舍（未改）：frontend token 存 localStorage；CORS 白名单为开发期地址（部署前收紧）
- ✅ `backend/app/api/health.py:18` `text("SELECT 1")` 静态 SQL，勿误报
