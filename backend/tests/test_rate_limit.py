"""限流键函数测试：认证用户按 user_id、匿名按 IP；限流器已挂载到 app。"""
from types import SimpleNamespace

from app.core.rate_limit import _rate_key, limiter


def _req(user_id=None, host="10.0.0.8", with_client=True):
    state = SimpleNamespace(user_id=user_id) if user_id is not None else SimpleNamespace()
    client = SimpleNamespace(host=host) if with_client else None
    return SimpleNamespace(state=state, client=client)


def test_rate_key_authenticated_uses_user_id():
    """已登录请求按用户限流，不受 IP 影响。"""
    assert _rate_key(_req(user_id=42)) == "user:42"


def test_rate_key_anonymous_uses_client_ip():
    assert _rate_key(_req()) == "ip:10.0.0.8"


def test_rate_key_no_client_falls_back_loopback():
    """request.client 缺失时回退 127.0.0.1。"""
    assert _rate_key(_req(with_client=False)) == "ip:127.0.0.1"


def test_limiter_mounted_on_app_state():
    """slowapi 限流器已挂载到 FastAPI app.state（main 装配检查）。"""
    from app.main import app

    assert app.state.limiter is limiter
