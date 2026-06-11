"""Server-side session store in Redis (authentication.md).

Sessions are opaque server-side records keyed by a random sid; the cookie carries only
the sid. Sliding renewal up to an absolute TTL. A per-user index enables global logout
on password change / reset / role change.
"""

from __future__ import annotations

import json
import secrets
import time
from typing import Any

from app.adapters.cache.base import get_cache_adapter
from app.settings import get_settings


class SessionService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.redis = get_cache_adapter(self.settings).client(self.settings.CACHE_DB_SESSION)

    def _key(self, sid: str) -> str:
        return f"forge_admin_session:{sid}"

    def _user_index(self, user_id: str) -> str:
        return f"forge_admin_session:user:{user_id}"

    async def create(self, *, user_id: str, role: str, ip: str, ua: str,
                     twofa_verified: bool, permissions: list[str]) -> str:
        sid = secrets.token_urlsafe(32)
        now = int(time.time())
        data = {
            "sid": sid, "user_id": user_id, "role": role, "ip": ip, "ua": ua,
            "twofa_verified": twofa_verified, "permissions": permissions,
            "created_at": now, "last_activity_at": now,
            "absolute_expiry": now + self.settings.SESSION_ABSOLUTE_TTL_SECONDS,
        }
        await self.redis.set(self._key(sid), json.dumps(data), ex=self.settings.SESSION_IDLE_TTL_SECONDS)
        await self.redis.sadd(self._user_index(user_id), sid)
        return sid

    async def get(self, sid: str) -> dict[str, Any] | None:
        raw = await self.redis.get(self._key(sid))
        if not raw:
            return None
        data = json.loads(raw)
        now = int(time.time())
        if now >= data["absolute_expiry"]:
            await self.destroy(sid)
            return None
        # sliding renewal (bounded by absolute expiry)
        data["last_activity_at"] = now
        ttl = min(self.settings.SESSION_IDLE_TTL_SECONDS, data["absolute_expiry"] - now)
        await self.redis.set(self._key(sid), json.dumps(data), ex=ttl)
        return data

    async def destroy(self, sid: str) -> None:
        raw = await self.redis.get(self._key(sid))
        if raw:
            user_id = json.loads(raw).get("user_id")
            if user_id:
                await self.redis.srem(self._user_index(user_id), sid)
        await self.redis.delete(self._key(sid))

    async def destroy_all_for_user(self, user_id: str) -> None:
        """Global logout — used on password change/reset, role change, disable."""
        sids = await self.redis.smembers(self._user_index(user_id))
        for sid in sids:
            await self.redis.delete(self._key(sid))
        await self.redis.delete(self._user_index(user_id))
