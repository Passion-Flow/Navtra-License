"""Valkey adapter — BSD-3-licensed, Redis-protocol-compatible drop-in (Linux Foundation fork).

Offered for SSPL-averse customers (some SOE/government procurement blanket-bans SSPL, which is
in Redis 8's tri-license). The redis-py async client speaks to Valkey unchanged, so this reuses
the Redis adapter verbatim. (xinchuang.md §6)"""

from __future__ import annotations

from app.adapters.cache.redis.adapter import RedisAdapter


class ValkeyAdapter(RedisAdapter):
    """Valkey is Redis-wire-compatible — identical client behaviour."""
