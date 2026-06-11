"""Sliding-window rate limiting + login lockout, backed by Redis db4 (security.md §8)."""

from __future__ import annotations

import time

from app.adapters.cache.base import get_cache_adapter
from app.core.errors import BizError
from app.settings import get_settings


class RateLimiter:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.redis = get_cache_adapter(self.settings).client(self.settings.CACHE_DB_RATELIMIT)

    async def hit(self, key: str, *, limit: int, window: int, code: str = "RATE_LIMIT_EXCEEDED") -> None:
        """Increment a fixed-window counter; raise BizError(code) when over limit."""
        now = int(time.time())
        bucket = f"rl:{key}:{now // window}"
        count = await self.redis.incr(bucket)
        if count == 1:
            await self.redis.expire(bucket, window)
        if count > limit:
            raise BizError(code, {"retry_after": window - (now % window)})

    async def record_login_failure(self, email: str) -> None:
        key = f"login_fail:{email.lower()}"
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, self.settings.LOGIN_LOCK_SECONDS)
        if count >= self.settings.LOGIN_LOCK_THRESHOLD:
            await self.redis.set(
                f"login_locked:{email.lower()}", "1", ex=self.settings.LOGIN_LOCK_SECONDS
            )

    async def assert_not_locked(self, email: str) -> None:
        if await self.redis.get(f"login_locked:{email.lower()}"):
            raise BizError("AUTH_ACCOUNT_LOCKED")

    async def clear_login_failures(self, email: str) -> None:
        await self.redis.delete(f"login_fail:{email.lower()}", f"login_locked:{email.lower()}")
