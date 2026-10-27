# API 文档

Base URL：`http://127.0.0.1:8000/api`（前端开发环境经 Vite 代理 `/api` 访问）

认证：除注册/登录/健康检查外，均需请求头 `Authorization: Bearer <access_token>`（JWT，7 天有效）。
错误响应统一为 `{"detail": "错误信息"}`。

## 认证 /api/auth

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /register | 注册，body `{username, password}`（密码≥6位），返回 token+user |
| POST | /login | 登录，body `{username, password}`，返回 `{access_token, token_type, user}` |
| POST | /change-password | 改密，body `{old_password, new_password}`；成功后**旧 token 全部失效** |
| GET | /me | 当前用户信息 |

## 会话 /api/conversations

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /?page=&size= | 会话列表（按更新时间倒序） |
| POST | / | 新建会话，body `{title?}` |
| PATCH | /{id} | 重命名，body `{title}` |
| DELETE | /{id} | 删除会话（级联删消息） |
| GET | /{id}/messages?page=&size= | 历史消息分页（倒序），assistant 消息含 `references` 引用数组 |

## 问答（SSE）POST /api/chat

请求：`{conversation_id?: number, question: string}`；`conversation_id` 缺省时自动新建会话。
限流：20 次/分钟/用户（超出返回 429）。

响应：`Content-Type: text/event-stream`，帧间空行分隔，data 为 JSON：

```
event: meta        data: {"conversation_id":12,"message_id":null,"model":"qwen-plus","cache_hit":false}
event: delta       data: {"content":"星耀"}        ← 逐 token，多次
event: references  data: [{"index":1,"doc_id":3,"doc_name":"手机_1_星耀 X90 Pro 5G_参数价格售后.xlsx","content":"参数片段原文…","score":0.87}]
event: done        data: {"message_id":34,"total_ms":5234,"retrieval_ms":412,"rerank_ms":180,"llm_ms":4600,"prompt_tokens":1500,"completion_tokens":320,"cache_hit":false}
event: error       data: {"detail":"错误信息"}     ← 任一阶段失败
```

## 知识库文档 /api/documents（仅管理员）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /upload | multipart 上传（pdf/docx/xlsx/txt/md，≤20MB），立即返回 `{id, status:"pending"}`，后台异步解析 |
| GET | /?page=&size=&status= | 文档列表（前端 2s 轮询 pending/processing） |
| DELETE | /{id} | 删除（清 Chroma 向量 + chunks + 文件） |
| POST | /{id}/reindex | 重建索引（重新解析入库） |
| GET | /{id}/chunks?page=&size= | 分块预览 |

## 反馈（P1）PUT /api/messages/{message_id}/feedback

body：`{rating: 1|-1, comment?}`，一条消息一条反馈，重复提交覆盖。

## 看板（P1，仅管理员）/api/admin/stats

| 路径 | 说明 |
|---|---|
| GET /overview | 用户数/文档数/分块数/问答总量/token 消耗/赞踩数 |
| GET /qa-trend?days=30 | 按天问答量 + 缓存命中量 |
| GET /performance | 平均检索/重排/生成/端到端耗时、缓存命中率（论文截图） |

## 健康检查 GET /health

mysql 连通性 / chroma 状态 / 缓存模式（redis 或 memory）/ dashscope 配置状态。
