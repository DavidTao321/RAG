"""语义缓存管理器：相似问题匹配 + 后端存储 + 自动降级。

设计：
- 相似度匹配在内存中进行（最近 512 条问题的 embedding 做余弦近邻，LRU 淘汰）；
- 答案载荷存入后端（Redis 或内存 dict，无 Redis 自动降级，逻辑一致）；
- kb_version 不一致的条目直接视为未命中（知识库变更后整体失效）。
"""
from __future__ import annotations

import asyncio
import time

import numpy as np

from ...config import settings
from .base import CachedAnswer, SemanticCache
from .memory_cache import MemoryCache
from .redis_cache import RedisCache

_MAX_ENTRIES = 512


class _RegistryEntry:
    __slots__ = ("key", "question", "embedding", "kb_version", "ts")

    def __init__(self, key: str, question: str, embedding: np.ndarray, kb_version: int):
        self.key = key
        self.question = question
        self.embedding = embedding
        self.kb_version = kb_version
        self.ts = time.time()


class CacheManager:
    def __init__(self, backend: SemanticCache):
        self.backend = backend
        self._entries: list[_RegistryEntry] = []
        self._lock = asyncio.Lock()

    @property
    def is_redis(self) -> bool:
        return self.backend.is_redis

    def _cosine(self, a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))

    async def lookup(self, question: str, embedding: np.ndarray, kb_version: int) -> CachedAnswer | None:
        """相似问题命中返回缓存答案，否则 None。"""
        async with self._lock:
            best, best_sim = None, 0.0
            for e in self._entries:
                if e.kb_version != kb_version:
                    continue
                sim = self._cosine(embedding, e.embedding)
                if sim >= settings.cache_similarity_threshold and sim > best_sim:
                    best, best_sim = e, sim
            if best is None:
                return None
            best.ts = time.time()
            try:
                payload = await self.backend.get(best.key)
            except Exception:  # noqa: BLE001 后端（Redis）挂掉视为未命中，主链路自动降级
                return None
            if payload is None:
                self._entries.remove(best)  # 后端已过期
                return None
            return payload

    async def store(self, question: str, embedding: np.ndarray, kb_version: int, answer: CachedAnswer) -> None:
        """写入缓存并登记匹配条目。"""
        from ...utils.text import md5_hex

        key = f"semcache:{kb_version}:{md5_hex(question)}"
        ttl = settings.cache_ttl_hours * 3600
        async with self._lock:
            await self.backend.set(key, answer, ttl)
            self._entries = [e for e in self._entries if e.key != key]
            self._entries.append(_RegistryEntry(key, question, embedding, kb_version))
            if len(self._entries) > _MAX_ENTRIES:  # LRU 淘汰：登记表与后端载荷一并清除
                self._entries.sort(key=lambda e: e.ts)
                evicted = self._entries[:-_MAX_ENTRIES]
                self._entries = self._entries[-_MAX_ENTRIES:]
                for e in evicted:
                    await self.backend.delete(e.key)

    async def invalidate_all(self) -> None:
        """清空匹配条目与全部载荷。"""
        async with self._lock:
            self._entries.clear()
            await self.backend.clear()

    async def close(self) -> None:
        await self.backend.close()


_manager: CacheManager | None = None


def get_cache() -> CacheManager:
    """全局缓存单例：优先 Redis，连接失败自动降级内存。"""
    global _manager
    if _manager is None:
        if settings.redis_url:
            try:
                backend = RedisCache(settings.redis_url)
                # 同步探测一次（启动期调用，代价可接受）
                import asyncio as _asyncio

                try:
                    loop = _asyncio.get_event_loop()
                    if loop.is_running():
                        # 运行中不可同步探测，交由首次读写失败降级
                        _manager = CacheManager(backend)
                        return _manager
                    loop.run_until_complete(backend.get("__ping__"))
                except Exception:  # noqa: BLE001
                    backend = MemoryCache()
            except Exception:  # noqa: BLE001
                backend = MemoryCache()
        else:
            backend = MemoryCache()
        _manager = CacheManager(backend)
    return _manager


def reset_cache() -> None:
    """清空单例（测试用）。"""
    global _manager
    _manager = None
