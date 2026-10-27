"""限流：slowapi 内存存储，按用户 ID（未登录回退 IP）作为限流键。"""
from slowapi import Limiter
from slowapi.util import get_remote_address


def _rate_key(request) -> str:
    """已认证请求按用户限流，否则按客户端 IP。"""
    user_id = getattr(request.state, "user_id", None)
    return f"user:{user_id}" if user_id else f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=_rate_key)
