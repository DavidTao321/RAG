"""FastAPI 依赖：当前用户 / 管理员校验（JWT + token_version 比对）。"""
import jwt as pyjwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import BusinessError
from ..core.security import decode_access_token
from ..database import get_db
from ..models import User

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise BusinessError(401, "未登录或登录已过期")
    try:
        payload = decode_access_token(credentials.credentials)
    except pyjwt.ExpiredSignatureError:
        raise BusinessError(401, "登录已过期，请重新登录")
    except pyjwt.PyJWTError:
        raise BusinessError(401, "无效的登录凭证")

    user = await db.get(User, int(payload.get("sub", 0)))
    if user is None:
        raise BusinessError(401, "用户不存在")
    # 修改密码后 token_version 已 +1，旧 token 一律失效
    if user.token_version != payload.get("ver"):
        raise BusinessError(401, "登录已失效（密码已修改），请重新登录")
    return user


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise BusinessError(403, "仅管理员可访问该资源")
    return user
