#!/bin/sh
# Forge DB hardening — runs ONCE at first PostgreSQL init (official postgres image runs every
# *.sh / *.sql in /docker-entrypoint-initdb.d). A shell script (not plain .sql) so it can read
# EDGE_DATABASE_PASSWORD from the environment: the operator sets that ONE secret in .env and it is
# used both to create the role here AND for forge-edge to connect — no value to keep in sync by hand.
#
# Creates a RESTRICTED edge role: the public forge-edge connects as this account. It is NOT the DB
# owner and cannot alter the schema; the master KEK is also withheld from edge, so even broad SELECT
# can't recover the master private key (that KEK isolation is the load-bearing protection). Because
# the app tables don't exist yet at init time, ALTER DEFAULT PRIVILEGES is used so the grants apply
# automatically to the tables forge_app (the migrator) creates later.
set -e

EDGE_PW="${EDGE_DATABASE_PASSWORD:-CHANGE_ME_EDGE_DB_PASSWORD}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'forge_edge') THEN
    CREATE ROLE forge_edge LOGIN PASSWORD '${EDGE_PW}';
  END IF;
END \$\$;

GRANT CONNECT ON DATABASE "${POSTGRES_DB}" TO forge_edge;
GRANT USAGE ON SCHEMA public TO forge_edge;

ALTER DEFAULT PRIVILEGES FOR ROLE "${POSTGRES_USER}" IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE ON TABLES TO forge_edge;
ALTER DEFAULT PRIVILEGES FOR ROLE "${POSTGRES_USER}" IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO forge_edge;

-- existing tables (none on a fresh init) — no-op, keeps re-runs idempotent.
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO forge_edge;
SQL
