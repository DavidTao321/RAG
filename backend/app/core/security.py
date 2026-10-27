"""认证安全底座：bcrypt 密码哈希 + PyJWT 签发/解码（payload 含 token_version）。"""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from ..config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=settings.bcrypt_rounds)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: int, token_version: int) -> str:
    """签发 JWT；ver 字段与 users.token_version 比对，改密后旧 token 全部失效。"""
    payload = {
        "sub": str(user_id),
        "ver": token_version,
        "exp": datetime.now(timezone.utc) + timedelta(days=settings.jwt_expire_days),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """解码 JWT，失败抛 jwt.PyJWTError。"""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
