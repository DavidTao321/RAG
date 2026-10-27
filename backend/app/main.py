"""FastAPI 应用入口：中间件、生命周期（建表/种子/预热）、路由与异常处理。"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from .api import admin_stats, auth, chat, conversations, documents, feedback, health
from .config import settings
from .core.exceptions import (
    BusinessError,
    business_error_handler,
    validation_error_handler,
)
from .core.rate_limit import limiter
from .database import Base, async_session, engine
from .models import *  # noqa: F401,F403 确保 create_all 前全部模型已注册
from .seeds import seed_admin

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动前置校验：JWT 密钥为空或仍是占位默认值时直接拒绝启动（token 可被伪造）
    if not settings.jwt_secret or settings.jwt_secret == "change-me-to-a-random-secret":
        raise RuntimeError(
            "JWT_SECRET 未配置或仍为占位值，请在 backend/.env 中设置随机密钥："
            'python -c "import secrets; print(secrets.token_hex(32))"'
        )
    # dashscope 原生 SDK（TextReRank）从环境变量/模块属性读 key，不接收 api_key 参数，
    # 而 .env 不会被自动注入进程环境——这里显式同步
    import os

    import dashscope

    if settings.dashscope_api_key:
        os.environ["DASHSCOPE_API_KEY"] = settings.dashscope_api_key
        dashscope.api_key = settings.dashscope_api_key

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)

    # 建表 + 管理员种子
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_admin()

    # BM25 索引预热 + 缓存后端初始化
    from .services.cache import get_cache
    from .services.rag import bm25

    get_cache()
    async with async_session() as db:
        count = await bm25.rebuild_global_index(db)
    logger.info("应用启动完成，BM25 索引条目数: %d", count)
    yield
    await engine.dispose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# CORS：开发期前端 Vite 地址
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 限流（slowapi）
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "请求过于频繁，请稍后再试"})


@app.exception_handler(BusinessError)
async def business_handler(request: Request, exc: BusinessError):
    return await business_error_handler(request, exc)


app.add_exception_handler(RequestValidationError, validation_error_handler)

# 路由
app.include_router(auth.router)
app.include_router(conversations.router)
app.include_router(chat.router)
app.include_router(documents.router)
app.include_router(feedback.router)
app.include_router(admin_stats.router)
app.include_router(health.router)
