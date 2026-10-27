"""管理员数据看板接口：访问控制（离线可验证）+ 数据聚合（SQLite 无 IF() 的用例标 xfail）。

说明：overview/qa-trend/performance 的业务 SQL 使用 MySQL 专用 IF() 聚合函数（SQLAlchemy
func.if_），SQLite 测试库无此函数，离线环境必然 500，故标 xfail(strict=False) 以记录现状；
若未来业务代码改为跨方言写法（如 case），这些用例将直接转为正常通过（XPASS 不阻塞）。
"""
import pytest

from app.models import Chunk, Conversation, Document, Feedback, Message, QueryStats
from tests.conftest import auth_headers

_sqlite_if_xfail = pytest.mark.xfail(
    reason="业务代码使用 MySQL 专用 IF() 聚合（func.if_），SQLite 无此函数，端点离线返回 500",
    strict=False,
)


async def _seed_stats(db_session_factory, admin_user):
    """造 2 文档、1 分块、1 问答统计（含 token/耗时/缓存命中）、1 条点赞反馈。"""
    async with db_session_factory() as db:
        db.add(Document(filename="a.xlsx", stored_name="s1", file_type="xlsx", file_size=10, file_hash="h1", created_by=admin_user.id))
        db.add(Document(filename="b.txt", stored_name="s2", file_type="txt", file_size=10, file_hash="h2", created_by=admin_user.id))
        await db.flush()
        db.add(Chunk(document_id=1, chunk_index=0, content="电池 5800mAh"))
        conv = Conversation(user_id=admin_user.id)
        db.add(conv)
        await db.flush()
        msg = Message(conversation_id=conv.id, user_id=admin_user.id, role="assistant", content="a")
        db.add(msg)
        await db.flush()
        db.add(Feedback(message_id=msg.id, user_id=admin_user.id, rating=1))
        db.add(
            QueryStats(
                user_id=admin_user.id,
                question="电池多大",
                retrieval_ms=100,
                rerank_ms=50,
                llm_ms=200,
                total_ms=350,
                prompt_tokens=100,
                completion_tokens=50,
                cache_hit=True,
            )
        )
        await db.commit()


# ===== 访问控制（不触碰 IF() SQL，离线直接通过）=====

async def test_overview_requires_admin(client, normal_user):
    res = await client.get("/api/admin/stats/overview", headers=auth_headers(normal_user))
    assert res.status_code == 403


async def test_qa_trend_requires_admin(client, normal_user):
    res = await client.get("/api/admin/stats/qa-trend", headers=auth_headers(normal_user))
    assert res.status_code == 403


async def test_performance_requires_admin(client, normal_user):
    res = await client.get("/api/admin/stats/performance", headers=auth_headers(normal_user))
    assert res.status_code == 403


async def test_admin_stats_requires_auth(client):
    res = await client.get("/api/admin/stats/overview")
    assert res.status_code == 401


async def test_qa_trend_days_out_of_range_422(client, admin_user):
    """days 参数越界由 Query 校验拦截（发生在业务 SQL 之前），返回 422。"""
    res = await client.get("/api/admin/stats/qa-trend?days=0", headers=auth_headers(admin_user))
    assert res.status_code == 422


# ===== 数据聚合（SQLite 上受 IF() 限制，xfail 记录）=====

@_sqlite_if_xfail
async def test_overview_aggregates(client, admin_user, db_session_factory):
    await _seed_stats(db_session_factory, admin_user)
    res = await client.get("/api/admin/stats/overview", headers=auth_headers(admin_user))
    assert res.status_code == 200
    data = res.json()
    assert data["user_count"] == 1
    assert data["document_count"] == 2
    assert data["chunk_count"] == 1
    assert data["qa_count"] == 1
    assert data["total_prompt_tokens"] == 100
    assert data["total_completion_tokens"] == 50
    assert data["feedback_like"] == 1
    assert data["feedback_dislike"] == 0


@_sqlite_if_xfail
async def test_qa_trend_groups_by_day(client, admin_user, db_session_factory):
    await _seed_stats(db_session_factory, admin_user)
    res = await client.get("/api/admin/stats/qa-trend?days=30", headers=auth_headers(admin_user))
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    assert data[0]["count"] == 1 and data[0]["cache_hit_count"] == 1


@_sqlite_if_xfail
async def test_performance_averages(client, admin_user, db_session_factory):
    await _seed_stats(db_session_factory, admin_user)
    res = await client.get("/api/admin/stats/performance", headers=auth_headers(admin_user))
    assert res.status_code == 200
    data = res.json()
    assert data["avg_retrieval_ms"] == 100.0
    assert data["avg_rerank_ms"] == 50.0
    assert data["avg_llm_ms"] == 200.0
    assert data["avg_total_ms"] == 350.0
    assert data["total_qa"] == 1
    assert data["cache_hit_rate"] == 1.0


@_sqlite_if_xfail
async def test_performance_empty_db_zero_rate(client, admin_user):
    """无问答记录时 cache_hit_rate 为 0 而非除零异常。"""
    res = await client.get("/api/admin/stats/performance", headers=auth_headers(admin_user))
    assert res.status_code == 200
    data = res.json()
    assert data["total_qa"] == 0 and data["cache_hit_rate"] == 0.0
