"""Redis adapter — per-logical-db async clients with connection pooling."""

from __future__ import annotations

from typing import Any

import redis.asyncio as aioredis

from app.adapters.cache.base import CacheAdapter


class RedisAdapter(CacheAdapter):
    def __init__(self, settings) -> None:  # noqa: ANN001
        super().__init__(settings)
        self._clients: dict[int, Any] = {}

    def client(self, db: int) -> Any:
        if db not in self._clients:
            s = self.settings
            self._clients[db] = aioredis.Redis(
                host=s.CACHE_HOST,
                port=s.CACHE_PORT,
                password=s.CACHE_PASSWORD or None,
                db=db,
                ssl=s.CACHE_USE_SSL,
                max_connections=s.CACHE_MAX_CONNECTIONS,
                decode_responses=True,
            )
        return self._clients[db]

    async def health_check(self) -> bool:
        try:
            return bool(await self.client(self.settings.CACHE_DB_APP).ping())
        except Exception:
            return False

    async def close(self) -> None:
        for c in self._clients.values():
            await c.aclose()
        self._clients.clear()
