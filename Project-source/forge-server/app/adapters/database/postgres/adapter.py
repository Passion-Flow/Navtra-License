"""PostgreSQL adapter (default provider) — asyncpg driver."""

from __future__ import annotations

from sqlalchemy.engine import URL

from app.adapters.database.base import DatabaseAdapter

# Advisory lock id for migration mutex (init-scripts.md: DB advisory lock).
MIGRATION_LOCK_ID = 0x46_4F_52_47_45  # "FORGE"


class PostgresAdapter(DatabaseAdapter):
    def dsn(self) -> URL:
        s = self.settings
        return URL.create(
            "postgresql+asyncpg",
            username=s.DATABASE_USERNAME,
            password=s.DATABASE_PASSWORD,
            host=s.DATABASE_HOST,
            port=s.DATABASE_PORT,
            database=s.DATABASE_NAME,
        )

    def engine_kwargs(self) -> dict:
        s = self.settings
        # asyncpg understands the libpq sslmode STRINGS (disable/allow/prefer/require/verify-ca/
        # verify-full). Passing the mode preserves "prefer" semantics (try SSL, fall back to
        # plaintext) — passing a bare True would make SSL mandatory and break non-TLS servers.
        mode = (s.DATABASE_SSL_MODE or "prefer").lower()
        connect_args = {} if mode in ("disable", "") else {"ssl": mode}
        return {
            "echo": s.DATABASE_ECHO,
            "pool_size": s.DATABASE_POOL_SIZE,
            "max_overflow": s.DATABASE_POOL_MAX_OVERFLOW,
            "pool_timeout": s.DATABASE_POOL_TIMEOUT,
            "pool_pre_ping": True,
            "connect_args": connect_args,
        }

    def dialect_specific_sql(self, key: str) -> str:
        return {
            "advisory_lock": f"SELECT pg_advisory_lock({MIGRATION_LOCK_ID})",
            "advisory_unlock": f"SELECT pg_advisory_unlock({MIGRATION_LOCK_ID})",
        }[key]
