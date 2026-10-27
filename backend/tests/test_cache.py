"""语义缓存：命中 / 余弦阈值 / kb_version 失效。"""
import hashlib

import numpy as np
import pytest

from app.services.cache import CacheManager, reset_cache
from app.services.cache.base import CachedAnswer
from app.services.cache.memory_cache import MemoryCache


@pytest.fixture(autouse=True)
def _clean():
    reset_cache()
    yield
    reset_cache()


def _embed(text: str) -> np.ndarray:
    """确定性 8 维向量：按字符哈希生成 [-1,1] 分布（与 FakeEmbeddings 同策略）。"""
    h = hashlib.md5(text.encode("utf-8")).digest()  # noqa: S324
    v = np.asarray([(b / 255.0) * 2 - 1 for b in h[:8]], dtype="float32")
    return v / (np.linalg.norm(v) + 1e-9)


def _unit_vec(index: int, dim: int = 8) -> np.ndarray:
    v = np.zeros(dim, dtype="float32")
    v[index] = 1.0
    return v


def _rotate(v: np.ndarray, cos_sim: float) -> np.ndarray:
    """构造与 v（e0 轴单位向量）余弦相似度恰为 cos_sim 的向量。"""
    w = np.zeros_like(v)
    w[0] = cos_sim
    w[1] = np.sqrt(1 - cos_sim**2)
    return w


@pytest.mark.asyncio
async def test_cache_miss_hit_and_version_invalidation():
    manager = CacheManager(MemoryCache())
    answer = CachedAnswer(answer="答案A", references=[{"index": 1, "doc_name": "d"}], model="qwen-plus")
    question = "星耀X90的电池容量是多少"
    vec = _embed(question)

    # 首次未命中
    assert await manager.lookup(question, vec, 1) is None

    # 写入后：同问题命中
    await manager.store(question, vec, 1, answer)
    hit = await manager.lookup(question, vec, 1)
    assert hit is not None and hit.answer == "答案A"

    # kb_version 变化 → 整体失效
    assert await manager.lookup(question, vec, 2) is None


@pytest.mark.asyncio
async def test_cache_similarity_threshold():
    """余弦 0.95（≥0.92）命中；余弦 0.5（<0.92）不命中。"""
    manager = CacheManager(MemoryCache())
    answer = CachedAnswer(answer="A", references=[], model="m")
    v = _unit_vec(0)

    await manager.store("q", v, 1, answer)

    # 高度相似 → 命中
    similar = _rotate(v, 0.95)
    assert await manager.lookup("相似问法", similar, 1) is not None

    # 中度相似 → 不命中
    distant = _rotate(v, 0.5)
    assert await manager.lookup("不相关问题", distant, 1) is None


@pytest.mark.asyncio
async def test_cache_backend_expiry():
    """后端载荷过期（TTL）→ 视为未命中。"""
    manager = CacheManager(MemoryCache())
    answer = CachedAnswer(answer="A", references=[], model="m")
    v = _unit_vec(0)
    await manager.store("q", v, 1, answer)
    # 手动把过期时间改到过去
    manager.backend._store["semcache:1:" + _key_of("q")] = (answer, 0.0)
    assert await manager.lookup("q", v, 1) is None


def _key_of(q):
    import hashlib as h

    return h.md5(q.encode("utf-8")).hexdigest()  # noqa: S324
