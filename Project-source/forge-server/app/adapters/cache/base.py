"""Cache adapter interface — Redis is the only provider, but the adapter layer keeps
business code free of the concrete SDK (standalone / sentinel / cluster topologies).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.settings import AppSettings


class CacheAdapter(ABC):
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    @abstractmethod
    def client(self, db: int) -> Any:
        """Return an async redis client bound to a logical db (app/session/lock/...)."""

    @abstractmethod
    async def health_check(self) -> bool:
        ...


def get_cache_adapter(settings: AppSettings) -> CacheAdapter:
    from app.adapters.cache.redis.adapter import RedisAdapter
    from app.adapters.cache.valkey.adapter import ValkeyAdapter

    return {"redis": RedisAdapter, "valkey": ValkeyAdapter}[settings.CACHE_TYPE](settings)
