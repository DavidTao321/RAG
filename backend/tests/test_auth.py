"""认证链路：注册 / 登录 / 改密后旧 token 失效（token_version 机制）。"""
import pytest

from app.core.security import create_access_token


@pytest.mark.asyncio
async def test_register_success(client):
    res = await client.post("/api/auth/register", json={"username": "bob", "password": "bob123456"})
    assert res.status_code == 201
    data = res.json()
    assert data["access_token"]
    assert data["user"]["username"] == "bob"
    assert data["user"]["is_admin"] is False


@pytest.mark.asyncio
async def test_register_duplicate_username(client):
    await client.post("/api/auth/register", json={"username": "carol", "password": "carol123"})
    res = await client.post("/api/auth/register", json={"username": "carol", "password": "other123"})
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_login_wrong_password(client, admin_user):
    res = await client.post("/api/auth/login", json={"username": "admin", "password": "wrong-pass"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_login_admin_success(client, admin_user):
    res = await client.post("/api/auth/login", json={"username": "admin", "password": "123456"})
    assert res.status_code == 200
    assert res.json()["user"]["is_admin"] is True


@pytest.mark.asyncio
async def test_change_password_invalidates_old_token(client, db_session_factory, normal_user):
    old_token = create_access_token(normal_user.id, normal_user.token_version)
    # 改密成功
    res = await client.post(
        "/api/auth/change-password",
        json={"old_password": "alice123456", "new_password": "newpass888"},
        headers={"Authorization": f"Bearer {old_token}"},
    )
    assert res.status_code == 200
    # 旧 token 立即失效（token_version 已 +1）
    res2 = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {old_token}"})
    assert res2.status_code == 401
    # 新密码可登录
    res3 = await client.post("/api/auth/login", json={"username": "alice", "password": "newpass888"})
    assert res3.status_code == 200


@pytest.mark.asyncio
async def test_change_password_wrong_old_password(client, normal_user):
    res = await client.post(
        "/api/auth/change-password",
        json={"old_password": "wrong-old", "new_password": "newpass888"},
        headers=auth_headers_after(normal_user),
    )
    assert res.status_code == 400


def auth_headers_after(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.token_version)}"}
