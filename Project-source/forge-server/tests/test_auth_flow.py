"""Integration test — full auth flow against a live postgres + redis.

Run: FORGE_INTEGRATION=1 pytest tests/test_auth_flow.py
Prereqs: services/database/postgres + services/cache/redis up, `forge migrate up`,
`forge bootstrap`, and FORGE_FIELD_ENCRYPTION_KEY set (see README).
"""

import pytest
import pytest_asyncio

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture(autouse=True)
async def _isolate_login_state():
    """Fully isolate shared login rate-limit state so repeated/looped suite runs don't trip
    the per-IP limit or the account lockout (both are global Redis counters)."""
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


@pytest.mark.asyncio
async def test_login_logout_me_roundtrip():
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # default super-admin seeded by `forge bootstrap`
        r = await client.post("/admin-api/v1/auth/login",
                              json={"email": "forge@navtra.ai", "password": "forge@navtra.ai", "code": None})
        assert r.status_code == 200, r.text
        assert r.json()["role"] == "super_admin"
        cookie = r.cookies.get("forge_admin_session")
        assert cookie

        me = await client.get("/admin-api/v1/me", cookies={"forge_admin_session": cookie})
        assert me.status_code == 200
        assert me.json()["email"] == "forge@navtra.ai"

        bad = await client.post("/admin-api/v1/auth/login",
                                json={"email": "forge@navtra.ai", "password": "wrong", "code": None})
        assert bad.status_code == 401
        assert bad.json()["code"] == "AUTH_INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_unauthenticated_me_is_401():
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as client:
        r = await client.get("/admin-api/v1/me")
        assert r.status_code == 401
        assert r.json()["code"] == "AUTH_REQUIRED"
