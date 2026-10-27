"""反馈接口测试：点赞/点踩、重复覆盖、权限与状态校验（完整 HTTP 链路，离线）。"""
from sqlalchemy import select

from app.models import Conversation, Feedback, Message
from tests.conftest import auth_headers


async def _seed_message(db_session_factory, owner, role="assistant") -> int:
    """造一条属于 owner 的消息，返回消息 id。"""
    async with db_session_factory() as db:
        conv = Conversation(user_id=owner.id, title="测试会话")
        db.add(conv)
        await db.flush()
        msg = Message(
            conversation_id=conv.id,
            user_id=owner.id,
            role=role,
            content="回答内容" if role == "assistant" else "用户问题",
        )
        db.add(msg)
        await db.commit()
        return msg.id


async def test_submit_feedback_like(client, normal_user, db_session_factory):
    """点赞成功返回 200，评分与评论落库。"""
    mid = await _seed_message(db_session_factory, normal_user)
    res = await client.put(
        f"/api/messages/{mid}/feedback",
        json={"rating": 1, "comment": "很好"},
        headers=auth_headers(normal_user),
    )
    assert res.status_code == 200
    assert res.json() == {"detail": "反馈已记录"}
    async with db_session_factory() as db:
        fb = (await db.execute(select(Feedback))).scalars().one()
        assert fb.rating == 1 and fb.comment == "很好" and fb.user_id == normal_user.id


async def test_submit_feedback_overwrites_previous(client, normal_user, db_session_factory):
    """重复反馈覆盖旧记录（唯一约束不冲突，表内仅一行）。"""
    mid = await _seed_message(db_session_factory, normal_user)
    await client.put(f"/api/messages/{mid}/feedback", json={"rating": 1}, headers=auth_headers(normal_user))
    res = await client.put(
        f"/api/messages/{mid}/feedback",
        json={"rating": -1, "comment": "不对"},
        headers=auth_headers(normal_user),
    )
    assert res.status_code == 200
    async with db_session_factory() as db:
        fbs = (await db.execute(select(Feedback))).scalars().all()
        assert len(fbs) == 1
        assert fbs[0].rating == -1 and fbs[0].comment == "不对"


async def test_feedback_rating_zero_rejected(client, normal_user, db_session_factory):
    """rating=0 属于非法值，返回 400。"""
    mid = await _seed_message(db_session_factory, normal_user)
    res = await client.put(f"/api/messages/{mid}/feedback", json={"rating": 0}, headers=auth_headers(normal_user))
    assert res.status_code == 400


async def test_feedback_rating_out_of_range_422(client, normal_user, db_session_factory):
    """rating 超出 [-1,1] 由 Pydantic 校验拦截，返回 422。"""
    mid = await _seed_message(db_session_factory, normal_user)
    res = await client.put(f"/api/messages/{mid}/feedback", json={"rating": 2}, headers=auth_headers(normal_user))
    assert res.status_code == 422


async def test_feedback_message_not_found(client, normal_user):
    """消息不存在返回 404。"""
    res = await client.put("/api/messages/9999/feedback", json={"rating": 1}, headers=auth_headers(normal_user))
    assert res.status_code == 404


async def test_feedback_other_users_message_forbidden(client, normal_user, admin_user, db_session_factory):
    """不能对他人会话的消息反馈，返回 403。"""
    mid = await _seed_message(db_session_factory, admin_user)
    res = await client.put(f"/api/messages/{mid}/feedback", json={"rating": 1}, headers=auth_headers(normal_user))
    assert res.status_code == 403


async def test_feedback_on_user_role_message_rejected(client, normal_user, db_session_factory):
    """只能对 assistant 回答反馈，对 user 消息反馈返回 400。"""
    mid = await _seed_message(db_session_factory, normal_user, role="user")
    res = await client.put(f"/api/messages/{mid}/feedback", json={"rating": 1}, headers=auth_headers(normal_user))
    assert res.status_code == 400


async def test_feedback_requires_auth(client, normal_user, db_session_factory):
    """未登录返回 401。"""
    mid = await _seed_message(db_session_factory, normal_user)
    res = await client.put(f"/api/messages/{mid}/feedback", json={"rating": 1})
    assert res.status_code == 401
