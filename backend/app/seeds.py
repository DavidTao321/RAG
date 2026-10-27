"""启动种子数据：创建管理员账号（账号密码均从 .env 读取）。"""
import logging

from sqlalchemy import select

from .config import settings
from .core.security import hash_password
from .database import async_session
from .models import User

logger = logging.getLogger(__name__)


async def seed_admin() -> None:
    # 未配置管理员密码时拒绝建号，避免空密码/弱默认口令的管理员落库
    if not settings.admin_password:
        logger.warning("ADMIN_PASSWORD 未在 .env 配置，跳过管理员种子")
        return
    async with async_session() as db:
        existing = await db.scalar(select(User).where(User.username == settings.admin_username))
        if existing is None:
            db.add(
                User(
                    username=settings.admin_username,
                    password_hash=hash_password(settings.admin_password),
                    is_admin=True,
                )
            )
            await db.commit()
