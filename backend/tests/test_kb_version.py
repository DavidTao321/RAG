"""知识库版本号：初始为 0，每次 bump +1 并落库（语义缓存失效依据）。"""
from app.models import SystemKV
from app.services.kb_version import KB_VERSION_KEY, bump_kb_version, get_kb_version


async def test_kb_version_initial_zero(db_session):
    """无记录时默认版本号 0。"""
    assert await get_kb_version(db_session) == 0


async def test_bump_kb_version_increments(db_session):
    """连续 bump 依次 +1，get 返回最新值。"""
    v1 = await bump_kb_version(db_session)
    v2 = await bump_kb_version(db_session)
    assert (v1, v2) == (1, 2)
    assert await get_kb_version(db_session) == 2


async def test_bump_persists_row(db_session_factory):
    """bump 后版本号落库为 SystemKV 行。"""
    async with db_session_factory() as db:
        await bump_kb_version(db)
        await db.commit()
        kv = await db.get(SystemKV, KB_VERSION_KEY)
        assert kv is not None and kv.value == 1
