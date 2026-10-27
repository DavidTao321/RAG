"""知识库版本号：文档任何增删改都会 +1，语义缓存据此整体失效。

并发安全：多任务同时 bump 时用 asyncio.Lock 串行化（单 worker 部署下有效）。
"""
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import SystemKV

KB_VERSION_KEY = "kb_version"
_lock = asyncio.Lock()


async def get_kb_version(db: AsyncSession) -> int:
    kv = await db.get(SystemKV, KB_VERSION_KEY)
    return kv.value if kv else 0


async def bump_kb_version(db: AsyncSession) -> int:
    """返回自增后的新版本号。"""
    async with _lock:
        kv = await db.get(SystemKV, KB_VERSION_KEY)
        if kv is None:
            kv = SystemKV(key=KB_VERSION_KEY, value=1)
            db.add(kv)
        else:
            kv.value += 1
        await db.flush()
        return kv.value
