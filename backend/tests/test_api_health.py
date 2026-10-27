"""健康检查接口：离线环境下各检查项状态确定（DB 打桩为不可用，无真实 MySQL 连接）。"""
import app.api.health as health_mod
from app.config import settings


class _FakeBrokenEngine:
    """模拟数据库不可用：connect 返回的上下文管理器在进入时抛异常。

    与 SQLAlchemy AsyncEngine.connect() 的真实形态一致（同步方法返回 async 上下文管理器），
    避免测试真实连接 MySQL。
    """

    class _Ctx:
        async def __aenter__(self):
            raise ConnectionError("offline")

        async def __aexit__(self, *a):
            return False

    def connect(self):
        return self._Ctx()


async def test_health_offline_checks(client, monkeypatch):
    """健康检查返回 200：mysql 报错、chroma 空目录、内存缓存、无 API key。"""
    monkeypatch.setattr(health_mod, "engine", _FakeBrokenEngine())
    monkeypatch.setattr(settings, "dashscope_api_key", "")
    res = await client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["mysql"].startswith("error:")
    assert data["chroma"] == "empty"
    assert data["cache_mode"] == "memory"
    assert data["dashscope"] == "no_api_key"
    assert data["llm_model"] == settings.llm_model
