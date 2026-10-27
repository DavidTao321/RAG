"""内存缓存后端：进程内 dict 存储（无 Redis 时的自动降级方案）。"""
import time

from .base import CachedAnswer, SemanticCache


class MemoryCache(SemanticCache):
    def __init__(self):
        self._store: dict[str, tuple[CachedAnswer, float]] = {}  # key -> (payload, expire_ts)

    async def get(self, key: str) -> CachedAnswer | None:
        item = self._store.get(key)
        if item is None:
            return None
        payload, expire_ts = item
        if time.time() > expire_ts:
            self._store.pop(key, None)
            return None
        return payload

    async def set(self, key: str, answer: CachedAnswer, ttl_seconds: int) -> None:
        self._store[key] = (answer, time.time() + ttl_seconds)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def clear(self) -> None:
        self._store.clear()
