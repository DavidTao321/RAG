"""健康检查：数据库 / Chroma / 缓存模式 / DashScope 连通性。"""
from fastapi import APIRouter
from sqlalchemy import text

from ..config import settings
from ..database import engine

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health():
    checks = {}

    # MySQL
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["mysql"] = "ok"
    except Exception as e:  # noqa: BLE001
        checks["mysql"] = f"error: {e.__class__.__name__}"

    # Chroma 持久化目录
    chroma_dir = settings.chroma_dir
    checks["chroma"] = "ok" if (chroma_dir / "chroma.sqlite3").exists() else "empty"

    # 缓存模式
    from ..services.cache import get_cache

    checks["cache_mode"] = "redis" if get_cache().is_redis else "memory"

    # DashScope
    checks["dashscope"] = "configured" if settings.dashscope_api_key else "no_api_key"
    checks["llm_model"] = settings.llm_model

    return {"status": "ok", **checks}
