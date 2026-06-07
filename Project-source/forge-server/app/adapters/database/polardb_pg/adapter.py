"""PolarDB-PostgreSQL adapter — 100% PostgreSQL-compatible (Alibaba shared-storage PG fork);
uses the same asyncpg driver as the postgres provider. (xinchuang.md §2)"""

from __future__ import annotations

from app.adapters.database.postgres.adapter import PostgresAdapter


class PolarDBPGAdapter(PostgresAdapter):
    """PolarDB-PG speaks the PostgreSQL wire protocol — behaviour identical at the driver layer."""
