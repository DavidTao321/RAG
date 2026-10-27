"""测试基座：SQLite 内存库 + fake LLM/embedding，全部离线可跑。"""
from __future__ import annotations

import hashlib

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.core.security import create_access_token, hash_password
from app.database import Base, get_db
from app.main import app
from app.models import User


class FakeEmbeddings:
    """确定性假向量：按文本哈希生成 8 维向量。"""

    def _vec(self, text: str) -> list[float]:
        h = hashlib.md5(text.encode("utf-8")).digest()  # noqa: S324 测试用确定性向量
        return [(b / 255.0) * 2 - 1 for b in h[:8]]

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)

    async def aembed_documents(self, texts):
        return self.embed_documents(texts)

    async def aembed_query(self, text):
        return self.embed_query(text)


class FakeChunk:
    def __init__(self, content: str):
        self.content = content
        # 与 langchain-openai 流式真实形态一致：usage_metadata 为 dict
        self.usage_metadata = {"input_tokens": 10, "output_tokens": 5}


class FakeLLM:
    """假 LLM：按输入输出固定带引用的回答片段。"""

    def __init__(self, answer: str = "电池容量为 5800mAh[1]，支持 120W 快充。"):
        self.answer = answer

    async def astream(self, messages):
        for i in range(0, len(self.answer), 5):
            yield FakeChunk(self.answer[i : i + 5])


@pytest.fixture()
def test_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    return engine


@pytest_asyncio.fixture()
async def db_session_factory(test_engine):
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    yield factory
    await test_engine.dispose()


@pytest_asyncio.fixture()
async def db_session(db_session_factory):
    async with db_session_factory() as session:
        yield session


@pytest.fixture()
def client(db_session_factory):
    async def _override_get_db():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest_asyncio.fixture()
async def admin_user(db_session_factory) -> User:
    async with db_session_factory() as db:
        user = User(username="admin", password_hash=hash_password("123456"), is_admin=True)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


@pytest_asyncio.fixture()
async def normal_user(db_session_factory) -> User:
    async with db_session_factory() as db:
        user = User(username="alice", password_hash=hash_password("alice123456"), is_admin=False)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


def auth_headers(user: User) -> dict:
    token = create_access_token(user.id, user.token_version)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _disable_rate_limit():
    """测试中关闭 slowapi 限流（反复登录/注册会触发 429 干扰断言）。"""
    from app.core.rate_limit import limiter

    limiter.enabled = False
    yield
    limiter.enabled = True


@pytest.fixture(autouse=True)
def _isolate_rag(tmp_path, monkeypatch):
    """每个测试隔离：临时 Chroma 目录 + 重置单例 + 假 embedding。"""
    from app.services.rag import vector_store
    from app.services.rag.llm_factory import get_embeddings

    vector_store.reset_singletons()
    get_embeddings.cache_clear()
    monkeypatch.setattr(settings, "chroma_dir", tmp_path / "chroma")
    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(get_embeddings, "__wrapped__", None)
    import app.services.rag.llm_factory as lf

    monkeypatch.setattr(lf, "get_embeddings", lambda: FakeEmbeddings())
    # 模块导入期绑定的引用也一并替换
    import app.services.ingestion as ing

    monkeypatch.setattr(ing, "get_embeddings", lambda: FakeEmbeddings())
    # 缓存单例也按测试隔离
    from app.services.cache import reset_cache

    reset_cache()
    yield
    reset_cache()


@pytest.fixture(autouse=True)
def _isolate_db_services(db_session_factory, monkeypatch):
    """后台入库任务改用 SQLite 会话；上传接口不触发真实后台任务（测试内手动 await）。"""
    import app.services.ingestion as ingestion
    import app.services.document_service as doc_service

    monkeypatch.setattr(ingestion, "async_session", db_session_factory)
    monkeypatch.setattr(doc_service, "schedule_ingestion", lambda doc_id: None)
    yield
