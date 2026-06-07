"""Oracle adapter (23ai) — python-oracledb async. NOTE: no official arm64 image."""

from __future__ import annotations

from sqlalchemy.engine import URL

from app.adapters.database.base import DatabaseAdapter


class OracleAdapter(DatabaseAdapter):
    def dsn(self) -> URL:
        s = self.settings
        # oracledb async uses service name via the DSN host:port/?service_name form.
        return URL.create(
            "oracle+oracledb",
            username=s.DATABASE_USERNAME,
            password=s.DATABASE_PASSWORD,
            host=s.DATABASE_HOST,
            port=s.DATABASE_PORT,
            query={"service_name": s.DATABASE_ORACLE_SERVICE_NAME},
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
        # Oracle uses DBMS_LOCK for advisory locks; migration mutex is acquired via a
        # dedicated single-row lock table to stay portable across editions.
        return {
            "advisory_lock": "SELECT id FROM forge_migration_lock FOR UPDATE",
            "advisory_unlock": "COMMIT",
        }[key]
