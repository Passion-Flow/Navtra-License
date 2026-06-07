"""KingbaseES (人大金仓) V9 adapter — PostgreSQL-compatible kernel.

KingbaseES's official driver is `ksycopg2` (a sync psycopg2 fork). Because its kernel is
PG-compatible at the wire level, Forge connects via asyncpg (async) and the PG dialect, run in
Oracle/PG compatibility mode on the Kingbase side. Caveat (xinchuang.md §2): version-banner
parsing differs from upstream PG — validate against the customer's Kingbase build; if asyncpg
cannot connect, fall back to the sync-session bridge with ksycopg2.
"""

from __future__ import annotations

from app.adapters.database.postgres.adapter import PostgresAdapter


class KingbaseAdapter(PostgresAdapter):
    pass
