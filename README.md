# 基于 LangChain 的企业级 RAG 知识库问答系统

毕业设计项目：面向电商商品知识库的企业级 RAG 问答系统。用户通过浏览器进行知识库问答，回答严格引用知识库内容并展示引用片段；支持多用户多会话、历史持久化、管理员知识库管理、性能优化与数据看板。

## 技术栈

| 层 | 选型 |
|---|---|
| 大模型 | 通义千问 API（DashScope）：`qwen-plus` 生成 + `text-embedding-v3` 向量化 + `qwen3-rerank` 重排 |
| RAG 框架 | LangChain 1.x（langchain-openai 兼容模式 / langchain-chroma / langchain-text-splitters） |
| 后端 | Python 3.11 + FastAPI + Uvicorn + SQLAlchemy(async) |
| 向量库 | Chroma（嵌入式持久化，chunks 表为事实源可重建） |
| 关系库 | MySQL 8.4（用户/会话/消息/文档/分块/反馈/统计） |
| 缓存 | 语义缓存：Redis 可选，缺失自动降级内存缓存 |
| 前端 | Vue3 + Vite + Element Plus + Pinia + Vue Router + ECharts |
| 认证 | JWT（含 token_version 改密全端下线）+ bcrypt |

## 核心功能

- 多用户注册/登录/修改密码；`admin` 种子管理员（密码在 `backend/.env` 的 `ADMIN_PASSWORD` 配置）
- **仅管理员**可进入知识库管理页：上传 PDF/Word/Excel/TXT/Markdown、异步解析分块向量化、删除、重建索引、分块预览
- RAG 问答：SSE 流式输出；回答内 `[n]` 引用编号可点击，右侧引用面板显示来源文档与片段原文，双向高亮联动
- 多会话管理：会话列表/重命名/删除，历史消息分页加载，重新登录可找回
- 多轮对话：上下文感知 + 短问题指代消解（拼接上轮问题检索）
- 用户反馈（赞/踩）与管理员数据看板（KPI/问答趋势/性能指标，论文数据来源）

## 企业级性能优化（论文素材）

| 优化项 | 说明 |
|---|---|
| 混合检索 | 向量检索 + BM25 关键词检索（jieba 分词）并行执行，RRF 融合——精确型号词必中 |
| Rerank 重排 | qwen3-rerank 精排 + 相关度阈值过滤，上下文压缩约 50% |
| 语义缓存 | 相似问题（余弦≥0.92）命中直接流式回放，端到端 ~5s → <100ms，kb_version 失效机制 |
| 流式输出 | 逐 token SSE 推送，首字延迟 <1s |
| 异步入库 | 上传即返回（<100ms），后台解析分块，批量 embedding（25条/批，API 调用降 96%） |
| 数据库 | SQLAlchemy 异步 + 连接池 + 复合索引；限流 20 次/分/用户防配额击穿 |
| 数据兜底 | sha256 去重、Chroma 可随时从 MySQL chunks 表重建索引 |

每轮问答的分段耗时/token/缓存命中均落库（`query_stats` 表），`/api/admin/stats/performance` 与看板可直接截图用于论文对比。

## 目录结构

```
backend/          FastAPI 后端（app/api 路由 · app/services RAG与业务 · app/models 表 · tests 测试）
frontend/         Vue3 前端（views 页面 · components 组件 · stores 状态 · api 请求层）
scripts/          mysql 启停脚本、样例数据生成器、样例数据 sample_data/
docs/             API 文档、部署指南、答辩演示脚本
```

## 快速开始

### 1. 环境

- Python 3.11（本机已装）、Node 18+（本机 v24）
- MySQL 8.4（本机已装，数据目录 `D:\mysql-data`，用户态运行）

### 2. 启动 MySQL

```bat
scripts\mysql_start.bat      # 启动（退出 bat 窗口后 MySQL 仍在后台）
scripts\mysql_stop.bat       # 停止
```

> 首次使用如数据库/账号不存在，用 root 执行：
> `mysql -u root -p`（密码见 `backend/.env` 的 `MYSQL_ROOT_PASSWORD`）后按需建库建号（本机已配置完成：库 `rag_kb`，账号 `rag_app`，密码见 `backend/.env`）。

### 3. 配置并启动后端

```bash
cd backend
copy .env.example .env        # 已生成 .env，只需填入 DASHSCOPE_API_KEY
venv\Scripts\python run.py    # http://127.0.0.1:8000
```

在 [阿里云百炼](https://bailian.console.aliyun.com/) 开通服务并创建 API Key（新用户有免费额度），填入 `.env` 的 `DASHSCOPE_API_KEY`。

### 4. 启动前端

```bash
cd frontend
npm install                   # 已装
npm run dev                   # http://127.0.0.1:5173，/api 已代理到后端
```

### 5. 导入样例知识库

```bash
cd backend
venv\Scripts\python ..\scripts\generate_sample_data.py   # 生成 21 个样例文档
# 用 admin 登录（密码见 backend/.env）→ 管理后台 → 文档管理 → 上传 scripts/sample_data/ 中的文件
```

## 测试

```bash
cd backend
venv\Scripts\python -m pytest -q        # 20 个用例全离线（SQLite + fake LLM）
```

## 常用账号

| 账号 | 密码 | 权限 |
|---|---|---|
| admin | 见 backend/.env 的 ADMIN_PASSWORD | 管理员（知识库管理 + 数据看板） |
| 任意注册用户 | — | 知识库问答 |

## 文档

- [API 文档](docs/API.md)：REST + SSE 事件协议
- [部署指南](docs/部署指南.md)：本机 / 有 Docker 两条路径、生产 Nginx 要点
- [答辩演示脚本](docs/答辩演示脚本.md)：演示步骤与论文截图清单
