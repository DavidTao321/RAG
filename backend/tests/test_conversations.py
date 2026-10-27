"""会话管理接口：列表分页/新建/改名/删除（消息级联）/历史消息分页 + 越权防护。"""
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from app.core.security import hash_password
from app.models import Conversation, Message, User
from tests.conftest import auth_headers


@pytest_asyncio.fixture()
async def other_user(db_session_factory) -> User:
    """第二个普通用户（bob），用于越权防护用例。"""
    async with db_session_factory() as db:
        user = User(username="bob", password_hash=hash_password("bob123456"), is_admin=False)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


@pytest_asyncio.fixture()
async def alice_conversation(client, normal_user) -> dict:
    """Alice 通过接口新建的一个会话，返回响应 JSON（含 id）。"""
    res = await client.post(
        "/api/conversations", json={"title": "Alice 的会话"}, headers=auth_headers(normal_user)
    )
    assert res.status_code == 201
    return res.json()


async def _create_conv(db_session, user_id: int, title: str = "新会话", updated_at: datetime | None = None) -> Conversation:
    """直接落库建会话，可指定 updated_at 以构造确定的排序场景。"""
    conv = Conversation(user_id=user_id, title=title, updated_at=updated_at)
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)
    return conv


# ---------- 未登录（401） ----------


@pytest.mark.asyncio
async def test_conversation_endpoints_require_auth(client):
    """五个会话接口未携带 token 时一律返回 401。"""
    assert (await client.get("/api/conversations")).status_code == 401
    assert (await client.post("/api/conversations", json={})).status_code == 401
    assert (await client.get("/api/conversations/1/messages")).status_code == 401
    assert (await client.patch("/api/conversations/1", json={"title": "x"})).status_code == 401
    assert (await client.delete("/api/conversations/1")).status_code == 401


# ---------- 新建（POST） ----------


@pytest.mark.asyncio
async def test_create_conversation_default_title(client, db_session, normal_user):
    """不带 body / 空 body 新建时标题为默认「新会话」，且归属当前用户。"""
    for kwargs in ({}, {"json": {}}):
        res = await client.post("/api/conversations", headers=auth_headers(normal_user), **kwargs)
        assert res.status_code == 201
        data = res.json()
        assert data["title"] == "新会话"
        conv = await db_session.get(Conversation, data["id"])
        assert conv.user_id == normal_user.id


@pytest.mark.asyncio
async def test_create_conversation_custom_title(client, db_session, normal_user):
    """自定义标题生效并正确落库。"""
    res = await client.post(
        "/api/conversations", json={"title": "产品参数咨询"}, headers=auth_headers(normal_user)
    )
    assert res.status_code == 201
    data = res.json()
    assert data["title"] == "产品参数咨询"
    conv = await db_session.get(Conversation, data["id"])
    assert conv.title == "产品参数咨询"
    assert conv.user_id == normal_user.id


# ---------- 列表分页（GET /api/conversations） ----------


@pytest.mark.asyncio
async def test_list_conversations_pagination_and_order(client, db_session, normal_user):
    """按 updated_at 倒序（相同时按 id 倒序），分页正确、total 正确。"""
    base = datetime(2026, 1, 1, 10, 0, 0)
    ids = []
    for i in range(5):
        # 前 4 个 updated_at 相同（验证 id 倒序兜底），最后一个最新
        updated = base if i < 4 else base + timedelta(seconds=1)
        conv = await _create_conv(db_session, normal_user.id, f"会话{i + 1}", updated)
        ids.append(conv.id)

    headers = auth_headers(normal_user)
    page1 = (await client.get("/api/conversations", params={"page": 1, "size": 2}, headers=headers)).json()
    assert page1["total"] == 5
    assert page1["page"] == 1
    assert page1["size"] == 2
    assert [it["id"] for it in page1["items"]] == [ids[4], ids[3]]  # 最新的在前

    page2 = (await client.get("/api/conversations", params={"page": 2, "size": 2}, headers=headers)).json()
    assert [it["id"] for it in page2["items"]] == [ids[2], ids[1]]

    page3 = (await client.get("/api/conversations", params={"page": 3, "size": 2}, headers=headers)).json()
    assert [it["id"] for it in page3["items"]] == [ids[0]]

    page4 = (await client.get("/api/conversations", params={"page": 4, "size": 2}, headers=headers)).json()
    assert page4["items"] == []
    assert page4["total"] == 5

    # 返回字段完整
    first = page1["items"][0]
    assert set(first) == {"id", "title", "created_at", "updated_at"}


@pytest.mark.asyncio
async def test_list_conversations_scoped_to_current_user(client, db_session, normal_user, other_user):
    """列表只包含当前用户自己的会话，看不到他人会话。"""
    mine = await _create_conv(db_session, normal_user.id, "Alice 的")
    await _create_conv(db_session, other_user.id, "Bob 的")

    res = await client.get("/api/conversations", headers=auth_headers(normal_user))
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert [it["id"] for it in data["items"]] == [mine.id]


# ---------- 改名（PATCH） ----------


@pytest.mark.asyncio
async def test_rename_conversation(client, db_session, alice_conversation, normal_user):
    """改名成功后接口返回与数据库中的标题都被更新。"""
    res = await client.patch(
        f"/api/conversations/{alice_conversation['id']}",
        json={"title": "电池参数"},
        headers=auth_headers(normal_user),
    )
    assert res.status_code == 200
    assert res.json()["title"] == "电池参数"
    conv = await db_session.get(Conversation, alice_conversation["id"])
    assert conv.title == "电池参数"


@pytest.mark.asyncio
async def test_rename_conversation_empty_title_rejected(client, alice_conversation, normal_user):
    """空标题不合法，返回 422 且不改库。"""
    res = await client.patch(
        f"/api/conversations/{alice_conversation['id']}",
        json={"title": ""},
        headers=auth_headers(normal_user),
    )
    assert res.status_code == 422


# ---------- 删除（DELETE） ----------


@pytest.mark.asyncio
async def test_delete_conversation_cascades_messages(client, db_session, db_session_factory, normal_user):
    """删除会话时其消息一并级联删除。"""
    conv = await _create_conv(db_session, normal_user.id, "待删除")
    msgs = [
        Message(conversation_id=conv.id, user_id=normal_user.id, role="user", content="问题"),
        Message(conversation_id=conv.id, user_id=normal_user.id, role="assistant", content="回答"),
    ]
    db_session.add_all(msgs)
    await db_session.commit()

    res = await client.delete(f"/api/conversations/{conv.id}", headers=auth_headers(normal_user))
    assert res.status_code == 200
    assert res.json() == {"detail": "会话已删除"}

    # 用新会话验证落库，避开 db_session 的 identity map 缓存旧对象
    async with db_session_factory() as db:
        assert await db.get(Conversation, conv.id) is None
        left = await db.scalar(
            select(func.count()).select_from(Message).where(Message.conversation_id == conv.id)
        )
        assert left == 0


# ---------- 历史消息分页（GET /{id}/messages） ----------


@pytest.mark.asyncio
async def test_list_messages_pagination_desc(client, db_session, normal_user):
    """消息按 id 倒序（新→旧）分页，total 正确。"""
    conv = await _create_conv(db_session, normal_user.id, "历史")
    msgs = [
        Message(
            conversation_id=conv.id,
            user_id=normal_user.id,
            role="user" if i % 2 == 0 else "assistant",
            content=f"消息{i}",
        )
        for i in range(5)
    ]
    db_session.add_all(msgs)
    await db_session.commit()
    ids = [m.id for m in msgs]  # 1..5，按插入顺序

    headers = auth_headers(normal_user)
    page1 = (
        await client.get(f"/api/conversations/{conv.id}/messages", params={"page": 1, "size": 2}, headers=headers)
    ).json()
    assert page1["total"] == 5
    assert [m["id"] for m in page1["items"]] == ids[::-1][:2]  # [5, 4]
    assert page1["items"][0]["content"] == "消息4"
    assert page1["items"][0]["role"] == "user"  # i=4 为偶数 → user
    assert page1["items"][1]["role"] == "assistant"

    page2 = (
        await client.get(f"/api/conversations/{conv.id}/messages", params={"page": 2, "size": 2}, headers=headers)
    ).json()
    assert [m["id"] for m in page2["items"]] == ids[::-1][2:4]  # [3, 2]

    page3 = (
        await client.get(f"/api/conversations/{conv.id}/messages", params={"page": 3, "size": 2}, headers=headers)
    ).json()
    assert [m["id"] for m in page3["items"]] == ids[::-1][4:]  # [1]
    assert page3["total"] == 5


@pytest.mark.asyncio
async def test_list_messages_serializes_references(client, db_session, normal_user):
    """assistant 消息的引用快照 / model / cache_hit 被正确序列化返回。"""
    conv = await _create_conv(db_session, normal_user.id)
    refs = [{"index": 1, "doc_id": 3, "doc_name": "商品参数.xlsx", "content": "片段原文", "score": 0.87}]
    db_session.add(
        Message(
            conversation_id=conv.id,
            user_id=normal_user.id,
            role="assistant",
            content="回答",
            references_json=refs,
            model="qwen-max",
            cache_hit=True,
        )
    )
    await db_session.commit()

    res = await client.get(
        f"/api/conversations/{conv.id}/messages", headers=auth_headers(normal_user)
    )
    assert res.status_code == 200
    item = res.json()["items"][0]
    assert item["role"] == "assistant"
    assert item["content"] == "回答"
    assert item["references"] == refs
    assert item["model"] == "qwen-max"
    assert item["cache_hit"] is True


# ---------- 越权防护（403 / 404） ----------


@pytest.mark.asyncio
async def test_other_user_cannot_view_messages(client, alice_conversation, other_user):
    """用户 B 读用户 A 会话的历史消息返回 403。"""
    res = await client.get(
        f"/api/conversations/{alice_conversation['id']}/messages", headers=auth_headers(other_user)
    )
    assert res.status_code == 403
    assert res.json()["detail"] == "无权访问该会话"


@pytest.mark.asyncio
async def test_other_user_cannot_rename(client, db_session, alice_conversation, other_user):
    """用户 B 改用户 A 会话的标题返回 403，且标题未被篡改。"""
    res = await client.patch(
        f"/api/conversations/{alice_conversation['id']}",
        json={"title": "被篡改的标题"},
        headers=auth_headers(other_user),
    )
    assert res.status_code == 403
    conv = await db_session.get(Conversation, alice_conversation["id"])
    assert conv.title == "Alice 的会话"


@pytest.mark.asyncio
async def test_other_user_cannot_delete(client, db_session, alice_conversation, other_user):
    """用户 B 删用户 A 的会话返回 403，会话仍然存在。"""
    res = await client.delete(
        f"/api/conversations/{alice_conversation['id']}", headers=auth_headers(other_user)
    )
    assert res.status_code == 403
    assert await db_session.get(Conversation, alice_conversation["id"]) is not None


@pytest.mark.asyncio
async def test_nonexistent_conversation_404(client, normal_user):
    """访问/改名/删除不存在的会话一律返回 404。"""
    headers = auth_headers(normal_user)
    missing_id = 999999
    assert (
        await client.get(f"/api/conversations/{missing_id}/messages", headers=headers)
    ).status_code == 404
    assert (
        await client.patch(f"/api/conversations/{missing_id}", json={"title": "x"}, headers=headers)
    ).status_code == 404
    assert (await client.delete(f"/api/conversations/{missing_id}", headers=headers)).status_code == 404
