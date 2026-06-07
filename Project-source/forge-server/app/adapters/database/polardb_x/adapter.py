"""PolarDB-X adapter — distributed, MySQL-protocol compatible; uses the aiomysql driver (async).
Reuses the MySQL adapter unchanged. (xinchuang.md §2)"""

from __future__ import annotations

from app.adapters.database.mysql.adapter import MySQLAdapter


class PolarDBXAdapter(MySQLAdapter):
    pass
