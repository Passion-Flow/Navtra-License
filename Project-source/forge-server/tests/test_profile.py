"""Integration test — self-service profile endpoints (/me/profile, /me/password).

Run: FORGE_INTEGRATION=1 pytest tests/test_profile.py
"""

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


async def _login(client, password="forge@navtra.ai"):
    r = await client.post("/admin-api/v1/auth/login",
                          json={"email": "forge@navtra.ai", "password": password, "code": None})
    assert r.status_code == 200, r.text
    return {"forge_admin_session": r.cookies.get("forge_admin_session")}


@pytest.mark.asyncio
async def test_self_service_profile_and_password():
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ck = await _login(client)

        # edit own username + avatar
        avatar = "data:image/png;base64,iVBORw0KGgo="
        r = await client.patch("/admin-api/v1/me/profile",
                               json={"username": "Passion", "avatar": avatar}, cookies=ck)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["username"] == "Passion"
        assert body["avatar"] == avatar

        # /me reflects the change
        me = (await client.get("/admin-api/v1/me", cookies=ck)).json()
        assert me["username"] == "Passion" and me["avatar"] == avatar

        # wrong current password is rejected
        r = await client.post("/admin-api/v1/me/password",
                              json={"current_password": "nope", "new_password": "NewPass123"}, cookies=ck)
        assert r.status_code == 401, r.text

        # correct current password changes it, and the new one logs in
        r = await client.post("/admin-api/v1/me/password",
                              json={"current_password": "forge@navtra.ai", "new_password": "NewPass123"}, cookies=ck)
        assert r.status_code == 200, r.text
        await _login(client, password="NewPass123")

        # restore defaults so the suite stays idempotent
        ck2 = await _login(client, password="NewPass123")
        await client.post("/admin-api/v1/me/password",
                          json={"current_password": "NewPass123", "new_password": "forge@navtra.ai"}, cookies=ck2)
        await client.patch("/admin-api/v1/me/profile",
                           json={"username": "Admin", "avatar": ""}, cookies=ck2)
