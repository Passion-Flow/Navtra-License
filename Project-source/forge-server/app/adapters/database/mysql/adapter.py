"""MySQL adapter (8.4) — aiomysql driver. Forces READ COMMITTED (InnoDB default is RR)."""

from __future__ import annotations

from sqlalchemy.engine import URL

from app.adapters.database.base import DatabaseAdapter


class MySQLAdapter(DatabaseAdapter):
    def dsn(self) -> URL:
        s = self.settings
        return URL.create(
            "mysql+aiomysql",
            username=s.DATABASE_USERNAME,
            password=s.DATABASE_PASSWORD,
            host=s.DATABASE_HOST,
            port=s.DATABASE_PORT,
            database=s.DATABASE_NAME,
            query={"charset": "utf8mb4"},
        )

    def engine_kwargs(self) -> dict:
        s = self.settings
        return {
            "echo": s.DATABASE_ECHO,
            "pool_size": s.DATABASE_POOL_SIZE,
            "max_overflow": s.DATABASE_POOL_MAX_OVERFLOW,
            "pool_timeout": s.DATABASE_POOL_TIMEOUT,
            "pool_pre_ping": True,
            "isolation_level": "READ COMMITTED",
        }

    def dialect_specific_sql(self, key: str) -> str:
        return {
            "advisory_lock": "SELECT GET_LOCK('forge_migration', 60)",
            "advisory_unlock": "SELECT RELEASE_LOCK('forge_migration')",
        }[key]
