"""语义缓存抽象：相似问题命中直接返回缓存答案，跳过检索与生成。"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class CachedAnswer:
    answer: str
    references: list[dict]
    model: str = ""


class SemanticCache(ABC):
    """缓存后端：只负责按 key 存取答案载荷；相似度匹配由 CacheManager 统一处理。"""

    is_redis: bool = False

    @abstractmethod
    async def get(self, key: str) -> CachedAnswer | None: ...

    @abstractmethod
    async def set(self, key: str, answer: CachedAnswer, ttl_seconds: int) -> None: ...

    async def delete(self, key: str) -> None:
        """删除指定载荷（LRU 淘汰时调用，默认无操作）。"""

    async def clear(self) -> None:
        """清空全部载荷。"""

    async def close(self) -> None:
        """释放连接。"""
