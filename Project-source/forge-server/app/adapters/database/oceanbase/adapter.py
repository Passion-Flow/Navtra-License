"""OceanBase CE adapter — MySQL-protocol compatible; uses the aiomysql driver (async).

OceanBase 4.x in MySQL tenant mode is wire/SQL compatible with MySQL 8, so Forge reuses the
MySQL adapter unchanged. (xinchuang.md §2 — strongest open-source 信创 option: async-ready,
official Docker, arm64.)"""

from __future__ import annotations

from app.adapters.database.mysql.adapter import MySQLAdapter


class OceanBaseAdapter(MySQLAdapter):
    def dialect_specific_sql(self, key: str) -> str:
        # OceanBase supports MySQL GET_LOCK/RELEASE_LOCK named locks.
        return super().dialect_specific_sql(key)
