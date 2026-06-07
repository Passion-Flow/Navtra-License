"""openGauss adapter — PostgreSQL-derived (PG 9.2-era kernel), connects via the asyncpg driver.

⚠️ AUTH (verified 2026-06 against opengauss/opengauss:5.0.0): openGauss defaults to its own
`sha256` password scheme (password_encryption_type=2), which is NOT standard SCRAM-SHA-256, so
asyncpg fails with "unsupported SASL Authentication methods". To use Forge's async path the
openGauss app account must use a driver-compatible scheme — set on the DB side:

    SET password_encryption_type = 1;            -- MD5 (asyncpg-compatible)
    CREATE USER forge_app WITH PASSWORD '...';    -- now stored as MD5
    -- pg_hba: host forge_main forge_app 0.0.0.0/0 md5

If the customer's openGauss policy mandates sha256 and MD5 is disallowed, fall back to the
openGauss psycopg2 fork via the sync-session bridge (xinchuang.md §2 — same path as KingbaseES /
达梦). The SQL/dialect itself is PG-compatible; only the auth handshake differs.
"""

from __future__ import annotations

from app.adapters.database.postgres.adapter import PostgresAdapter


class OpenGaussAdapter(PostgresAdapter):
    pass
