"""问答接口：SSE 流式（fetch + ReadableStream 解析，EventSource 不支持 POST）。"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..core.rate_limit import limiter
from ..database import get_db
from ..models import User
from ..schemas.chat import ChatRequest
from ..services.chat_service import stream_chat
from .deps import get_current_user

router = APIRouter(prefix="/api", tags=["chat"])


async def _resolve_user_and_set_rate_key(
    request: Request, user: User = Depends(get_current_user)
) -> User:
    """限流键：已认证请求按用户 ID 限流（20 次/分钟/用户）。"""
    request.state.user_id = user.id
    return user


@router.post("/chat")
@limiter.limit(settings.chat_rate_limit)
async def chat(
    body: ChatRequest,
    request: Request,
    user: User = Depends(_resolve_user_and_set_rate_key),
    db: AsyncSession = Depends(get_db),
):
    return StreamingResponse(
        stream_chat(user, body, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 生产 Nginx 需关闭代理缓冲
            "Connection": "keep-alive",
        },
    )
