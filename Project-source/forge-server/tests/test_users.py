"""Integration test — operator (user) management endpoints + lockout guards + session invalidation.

Run: FORGE_INTEGRATION=1 pytest tests/test_users.py
"""

import uuid

import pytest
import pytest_asyncio

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture(autouse=True)
async def _isolate_login_state():
    from app.services.ratelimit import RateLimiter

    async def _clear():
        rl = RateLimiter()
        await rl.clear_login_failures("forge@navtra.ai")
        for pattern in ("rl:login_ip:*", "rl:login_fail*"):
            async for key in rl.redis.scan_iter(pattern):
                await rl.redis.delete(key)

    await _clear()
    yield
    await _clear()


async def _login_super(client):
    r = await client.post("/admin-api/v1/auth/login",
                          json={"email": "forge@navtra.ai", "password": "forge@navtra.ai", "code": None})
    assert r.status_code == 200, r.text
    return {"forge_admin_session": r.cookies.get("forge_admin_session")}


@pytest.mark.asyncio
async def test_operator_lifecycle_and_guards():
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ck = await _login_super(client)
        email = f"op-{uuid.uuid4().hex[:8]}@navtra.ai"

        # create operator (password defaults to email per §11.1)
        r = await client.post("/admin-api/v1/users", cookies=ck,
                              json={"email": email, "username": "Op", "role": "admin"})
        assert r.status_code == 201, r.text
        uid = r.json()["id"]
        assert r.json()["role"] == "admin" and r.json()["is_active"] is True

        # duplicate email rejected
        dup = await client.post("/admin-api/v1/users", cookies=ck,
                                json={"email": email, "username": "Op2", "role": "auditor"})
        assert dup.status_code == 409 and dup.json()["code"] == "RESOURCE_CONFLICT"

        # the new operator can log in with password == email, then gets demoted → sessions killed
        opck = {"forge_admin_session": (await client.post(
            "/admin-api/v1/auth/login",
            json={"email": email, "password": email, "code": None})).cookies.get("forge_admin_session")}
        assert (await client.get("/admin-api/v1/me", cookies=opck)).status_code == 200

        # list shows the operator
        lst = await client.get("/admin-api/v1/users", cookies=ck)
        assert lst.status_code == 200 and any(u["id"] == uid for u in lst.json()["data"])

        # update role admin -> auditor (session invalidation kicks in)
        up = await client.patch(f"/admin-api/v1/users/{uid}", cookies=ck, json={"role": "auditor"})
        assert up.status_code == 200 and up.json()["role"] == "auditor"
        # the operator's old session was destroyed by the role change
        assert (await client.get("/admin-api/v1/me", cookies=opck)).status_code == 401

        # reset password
        rp = await client.post(f"/admin-api/v1/users/{uid}/reset-password", cookies=ck,
                               json={"new_password": "BrandNewPass123"})
        assert rp.status_code == 200 and rp.json()["data"]["reset"] is True

        # delete operator
        dl = await client.delete(f"/admin-api/v1/users/{uid}", cookies=ck)
        assert dl.status_code == 200 and dl.json()["data"]["deleted"] is True

        # --- lockout guards on the super-admin themselves ---
        me = await client.get("/admin-api/v1/me", cookies=ck)
        my_id = me.json()["id"] if "id" in me.json() else None
        if my_id:
            self_disable = await client.patch(f"/admin-api/v1/users/{my_id}", cookies=ck,
                                              json={"is_active": False})
            assert self_disable.status_code == 409
            assert self_disable.json()["code"] in ("USER_SELF_LOCKOUT", "USER_LAST_SUPER_ADMIN")


@pytest.mark.asyncio
async def test_non_super_admin_cannot_manage_users():
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ck = await _login_super(client)
        email = f"aud-{uuid.uuid4().hex[:8]}@navtra.ai"
        await client.post("/admin-api/v1/users", cookies=ck,
                          json={"email": email, "username": "Aud", "role": "auditor"})
        audck = {"forge_admin_session": (await client.post(
            "/admin-api/v1/auth/login",
            json={"email": email, "password": email, "code": None})).cookies.get("forge_admin_session")}
        # auditor lacks platform.user.read
        r = await client.get("/admin-api/v1/users", cookies=audck)
        assert r.status_code == 403, r.text
