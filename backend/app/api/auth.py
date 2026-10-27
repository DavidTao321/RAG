"""认证接口：注册 / 登录 / 修改密码 / 当前用户。"""
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..core.exceptions import BusinessError, bad_request, conflict
from ..core.rate_limit import limiter
from ..core.security import create_access_token, hash_password, verify_password
from ..database import get_db
from ..models import User
from ..schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from .deps import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
@limiter.limit(settings.register_rate_limit)
async def register(request: Request, body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(User).where(User.username == body.username))
    if existing is not None:
        raise conflict("用户名已存在")

    user = User(username=body.username, password_hash=hash_password(body.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id, user.token_version)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.login_rate_limit)
async def login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.username == body.username))
    if user is None or not verify_password(body.password, user.password_hash):
        raise BusinessError(401, "用户名或密码错误")

    user.last_login_at = datetime.now()
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id, user.token_version)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(body.old_password, user.password_hash):
        raise bad_request("原密码错误")
    if body.old_password == body.new_password:
        raise bad_request("新密码不能与原密码相同")

    user.password_hash = hash_password(body.new_password)
    # 使该用户所有已签发的 JWT 立即失效（全端下线）
    user.token_version += 1
    await db.commit()
    return {"detail": "密码修改成功，请重新登录"}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return UserOut.model_validate(user)
