---
name: unit-test
description: 本项目的单元测试工作手册：如何编写 pytest 测试、执行测试并输出测试报告（离线可跑，SQLite 内存库 + fake LLM/embedding，不依赖真实 MySQL 与 DashScope）。
---

# 单元测试工作手册（企业级 RAG 知识库问答系统）

本手册是给 tester 子代理（或主会话）做单元测试时的标准流程。目标：**写出的测试离线可跑、结果可靠、报告清晰**。

## 1. 运行命令（全部在 backend 目录执行）

```bash
cd backend
./venv/Scripts/python -m pytest -q                       # 全量（当前 21 个用例，全部离线）
./venv/Scripts/python -m pytest tests/test_auth.py -q    # 单个文件
./venv/Scripts/python -m pytest tests/test_auth.py::test_register_success -x --tb=short   # 单个用例
./venv/Scripts/python -m pytest -m "not integration"     # 跳过真实 API 用例
```

- Windows 控制台输出中文可能显示为 GBK 乱码，**不影响结果判断**，以用例名和断言内容为准。
- 测试不需要启动后端、MySQL、Redis——测试基座用 SQLite 内存库 + 假组件全离线运行。

## 2. 测试基座（tests/conftest.py 已有夹具，写新测试优先复用，不要重复造）

| 夹具 | 用途 |
|---|---|
| `client` | httpx 异步测试客户端（ASGITransport，直接调 FastAPI 应用），已覆盖数据库依赖为 SQLite |
| `db_session` / `db_session_factory` | 直连测试库的 SQLAlchemy 会话（查落库结果用） |
| `admin_user` / `normal_user` | 已入库的测试用户（admin/123456 与 alice/alice123456） |
| `auth_headers(user)` | 由用户对象生成 JWT 请求头 |
| `FakeLLM(answer=...)` | 假 LLM，按固定文本分片流式输出，usage 为 dict 形态 |
| `FakeEmbeddings` | 假向量（按文本 md5 生成确定性 8 维向量） |
| autouse `_isolate_rag` | 每个测试自动隔离：临时 Chroma 目录、重置向量库/缓存单例、替换 embedding 工厂 |
| autouse `_isolate_db_services` | 入库后台任务改用 SQLite 会话；上传接口不触发真实后台任务（测试内手动 `await process_document(id)`） |

## 3. 写新测试的规范

1. **文件**：`tests/test_<模块>.py`，用例名 `test_<行为描述>`，中文 docstring 说明验证的行为。
2. **认证/接口类**：用 `client` + `auth_headers(...)` 走完整 HTTP 链路（参考 test_auth.py、test_documents.py）。
3. **RAG 链路类**：参考 test_chat_stream.py 的 `_fake_rag` 夹具——monkeypatch `app.services.chat_service.get_embeddings/get_llm`，mock `dashscope.TextReRank.call`；用 `_parse_sse` 解析事件流断言 meta→delta→references→done 序列。
4. **纯函数/算法类**（BM25、RRF、引用重编号、缓存）：直接构造输入断言输出，不碰 IO（参考 test_retrieval.py、test_cache.py）。
5. **外部依赖必须打桩**：`dashscope.TextReRank.call` 用 monkeypatch 替换；任何真实网络/真实 MySQL 依赖都是违规，除非标 `@pytest.mark.integration`。
6. **入库管线测试**：上传后显式 `await process_document(doc_id)`（后台任务在测试中已禁用），再断言 `status == "done"` 与 chunks 落库。
7. 新增测试后跑一次全量，确认不破坏既有用例。

## 4. 执行流程（接到任务后的标准步骤）

1. 明确目标：被测模块/接口/函数是什么，期望行为是什么。
2. 跑一遍相关测试文件的**基线**（改动前先确认当前是绿的）。
3. 写/修改测试代码。
4. 执行相关用例 → 失败则判断：测试自身问题（修测试）还是疑似业务 bug（只报告不改业务代码）。
5. 全量回归 `pytest -q`。
6. 按下方模板输出测试报告。

## 5. 测试报告模板（每次任务结束必交）

```markdown
# 单元测试报告

**任务**：<一句话描述测了什么>
**测试文件**：<新增/修改的文件路径列表>
**运行命令**：<实际执行的命令>

**结果**：X passed, Y failed（耗时 Zs）

**失败详情**（无失败则写"无"）：
- `tests/xx.py::test_xx` — 断言差异：<expected vs actual>；原因分析：<...>

**疑似业务问题**（无则写"无"）：
- <问题描述 + 失败输出证据 + 建议，不改业务代码>

**结论**：✅ 全部通过 / ⚠️ 存在失败（已分析）
```

## 6. 注意事项（本项目实测的坑）

- 语义缓存单例会跨用例残留——conftest 的 autouse 夹具已处理，新夹具别绕过它。
- `usage_metadata` 是 dict（用 `.get` 取值，别用 `getattr`）；假组件必须与真实形态一致。
- Chroma 集合名 `kb_products`（≥3 字符）；向量库单例在测试间靠 `reset_singletons()` 重置。
- openai SDK 必须 2.x、`check_embedding_ctx_length=False`——这是业务代码的既有约束，测试中替换 embedding 工厂时无需关心，但不要在测试里引入对 openai 3.x 行为的假设。
