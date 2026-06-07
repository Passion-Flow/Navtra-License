"""Database adapter interface — business code is dialect-neutral; each provider
implements this (HARD RULE: 03-Services, all 4 providers postgres/mysql/oracle/tidb).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine

from app.settings import AppSettings


class DatabaseAdapter(ABC):
    """Assembles an AsyncEngine from field-ized settings; exposes dialect-specific SQL.

    `is_async` is True for providers with an asyncio driver (asyncpg/aiomysql). Providers whose
    only driver is synchronous (达梦 dmPython, KingbaseES ksycopg2) set is_async=False and
    implement `create_sync_engine()`; the session layer then drives them through the thread-affine
    SyncBridgeSession so the async core stays untouched. (xinchuang.md §2)
    """

    is_async: bool = True

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    @abstractmethod
    def dsn(self) -> URL:
        """SQLAlchemy async URL built with URL.create (safely escapes special chars in
        credentials — e.g. '@'/'!' in passwords — which a hand-built f-string would break)."""

    @abstractmethod
    def engine_kwargs(self) -> dict:
        ...

    def dialect_specific_sql(self, key: str) -> str:
        """Hook for dialect-specific snippets (e.g. advisory lock). Default = generic."""
        return _GENERIC_SQL[key]

    def create_engine(self) -> AsyncEngine:
        from sqlalchemy.ext.asyncio import create_async_engine
        return create_async_engine(self.dsn(), **self.engine_kwargs())

    def sync_dsn(self) -> URL:
        """Synchronous SQLAlchemy URL — only sync-driver providers (is_async=False) override this."""
        raise NotImplementedError(f"{type(self).__name__} has no synchronous driver")

    def create_sync_engine(self):
        """Build a synchronous Engine for sync-only drivers; driven via SyncBridgeSession."""
        from sqlalchemy import create_engine as _create_sync
        kw = {k: v for k, v in self.engine_kwargs().items() if k != "connect_args"}
        return _create_sync(self.sync_dsn(), **kw)


_GENERIC_SQL: dict[str, str] = {}


def get_database_adapter(settings: AppSettings) -> DatabaseAdapter:
    from app.adapters.database.dameng.adapter import DamengAdapter
    from app.adapters.database.kingbase.adapter import KingbaseAdapter
    from app.adapters.database.mysql.adapter import MySQLAdapter
    from app.adapters.database.oceanbase.adapter import OceanBaseAdapter
    from app.adapters.database.opengauss.adapter import OpenGaussAdapter
    from app.adapters.database.oracle.adapter import OracleAdapter
    from app.adapters.database.polardb_pg.adapter import PolarDBPGAdapter
    from app.adapters.database.polardb_x.adapter import PolarDBXAdapter
    from app.adapters.database.postgres.adapter import PostgresAdapter
    from app.adapters.database.tidb.adapter import TiDBAdapter

    return {
        "postgres": PostgresAdapter,
        "mysql": MySQLAdapter,
        "oracle": OracleAdapter,
        "tidb": TiDBAdapter,
        # 信创 (domestic) databases — PG-family via asyncpg, MySQL-family via aiomysql:
        "opengauss": OpenGaussAdapter,
        "kingbase": KingbaseAdapter,
        "polardb-pg": PolarDBPGAdapter,
        "oceanbase": OceanBaseAdapter,
        "polardb-x": PolarDBXAdapter,
        # sync-only proprietary driver → driven via SyncBridgeSession (is_async=False):
        "dameng": DamengAdapter,
    }[settings.DATABASE_TYPE](settings)
