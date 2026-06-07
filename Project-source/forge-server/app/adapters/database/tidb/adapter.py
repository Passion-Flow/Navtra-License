"""TiDB adapter — MySQL wire-compatible; app uses the aiomysql driver against TiDB :4000."""

from __future__ import annotations

from app.adapters.database.mysql.adapter import MySQLAdapter


class TiDBAdapter(MySQLAdapter):
    """TiDB speaks the MySQL protocol; behaviour identical at the driver layer.

    Kept as a distinct provider so DATABASE_TYPE=tidb is explicit and so TiDB-specific
    tuning (e.g. optimistic txn, no GET_LOCK on older versions) can diverge here.
    """
