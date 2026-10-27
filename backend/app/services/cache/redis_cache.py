"""Redis 缓存后端：跨进程共享，TTL 过期。"""
import json

import redis.asyncio as redis

from .base import CachedAnswer, SemanticCache


class RedisCache(SemanticCache):
    is_redis = True

    def __init__(self, url: str):
        self._client = redis.from_url(url, decode_responses=True, socket_timeout=3)

    async def get(self, key: str) -> CachedAnswer | None:
        raw = await self._client.get(key)
        if not raw:
            return None
        data = json.loads(raw)
        return CachedAnswer(**data)

    async def set(self, key: str, answer: CachedAnswer, ttl_seconds: int) -> None:
        await self._client.set(key, json.dumps(answer.__dict__, ensure_ascii=False), ex=ttl_seconds)

    async def delete(self, key: str) -> None:
        try:
            await self._client.delete(key)
        except Exception:  # noqa: BLE001 Redis 异常时删除失败不影响主流程
            pass

    async def clear(self) -> None:
        try:
            await self._client.flushdb()
        except Exception:  # noqa: BLE001
            pass

    async def close(self) -> None:
        try:
            await self._client.aclose()
        except Exception:  # noqa: BLE001
            pass
