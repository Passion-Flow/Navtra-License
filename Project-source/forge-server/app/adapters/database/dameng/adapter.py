"""达梦 DM8 adapter — proprietary, Oracle-flavored; SYNC-only driver (dmPython).

There is no asyncio driver for 达梦, so this adapter is `is_async=False`: the session layer drives
it through the thread-affine SyncBridgeSession (validated against a sync driver — see
app/db/sync_bridge.py). Connection: `dm+dmPython://user:pass@host:port` using the official
`sqlalchemy-dm` dialect. The schema is the connecting user (Oracle-style); there is no separate
database in the URL.

VERIFIED (2026-06, real dm8 via qinchz/dm8-arm64, Python 3.14):
  - pip deps install on cp314: `dmPython>=2.5.32` + `sqlalchemy-dm-dialect>=2.0.0` (dialect name 'dm').
  - dmPython ALSO needs the 达梦 NATIVE CLIENT LIBS at runtime (libdmdpi.so + crypto). Without them
    connect fails `[-70089] Encryption module failed to load`. The Forge backend image, when built
    for DATABASE_TYPE=dameng, must bundle the DM client libs (~from the 达梦 distribution) and set
    LD_LIBRARY_PATH to them. With the libs present, the full chain
    DamengAdapter → dm dialect → dmPython → real dm8 (through SyncBridgeSession) works end-to-end.
"""

from __future__ import annotations

from sqlalchemy.engine import URL

from app.adapters.database.base import DatabaseAdapter


class DamengAdapter(DatabaseAdapter):
    is_async = False

    def dsn(self) -> URL:  # async path unused
        raise NotImplementedError("达梦 has no async driver; driven via SyncBridgeSession")

    def sync_dsn(self) -> URL:
        s = self.settings
        return URL.create(
            "dm+dmPython",
            username=s.DATABASE_USERNAME,
            password=s.DATABASE_PASSWORD,
            host=s.DATABASE_HOST,
            port=s.DATABASE_PORT,
        )

    def engine_kwargs(self) -> dict:
        s = self.settings
        return {
            "echo": s.DATABASE_ECHO,
            "pool_size": s.DATABASE_POOL_SIZE,
            "max_overflow": s.DATABASE_POOL_MAX_OVERFLOW,
            "pool_timeout": s.DATABASE_POOL_TIMEOUT,
            "pool_pre_ping": True,
        }

    def dialect_specific_sql(self, key: str) -> str:
        # 达梦 is Oracle-flavored — use DBMS_LOCK-style mutex semantics. Migration runs single-flow
        # in delivery; a table-row advisory lock is applied by the migrate CLI for non-PG/MySQL.
        return {
            "advisory_lock": "SELECT 1",
            "advisory_unlock": "SELECT 1",
        }[key]
