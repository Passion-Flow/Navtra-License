"""Thread-affine async→sync session bridge for sync-only DB drivers (达梦 dmPython,
KingbaseES ksycopg2). xinchuang.md §2.

A SQLAlchemy Session and its DBAPI connection are NOT safe to touch from multiple threads, so
each request's bridge owns a single-worker thread and runs EVERY operation on it. SELECT results
are fully buffered (`Result.freeze()`) on the worker thread before crossing back, so the caller
can iterate them on the event-loop thread without touching the connection. Async-driver providers
(asyncpg/aiomysql) never enter this path — the verified async core is unchanged.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any


class _Rowcount:
    """Returned for DML execute() so callers can read .rowcount without a live cursor."""

    def __init__(self, rowcount: int) -> None:
        self.rowcount = rowcount


class SyncBridgeSession:
    """Exposes the AsyncSession subset Forge's repositories use (execute/add/add_all/commit/
    flush/rollback/refresh/get/delete/close) over a synchronous Session on a dedicated thread."""

    def __init__(self, sync_sessionmaker: Any) -> None:
        self._sm = sync_sessionmaker
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="forge-syncdb")
        self._session: Any = None

    async def _run(self, fn, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, lambda: fn(*args, **kwargs))

    async def __aenter__(self) -> "SyncBridgeSession":
        self._session = await self._run(self._sm)
        return self

    async def __aexit__(self, *exc) -> None:
        try:
            if self._session is not None:
                await self._run(self._session.close)
        finally:
            self._executor.shutdown(wait=True)

    # --- query --------------------------------------------------------------
    async def execute(self, statement, *args, **kwargs):
        def _do():
            res = self._session.execute(statement, *args, **kwargs)
            # ORM ChunkedIteratorResult has no `returns_rows` attr (it returns rows); Core
            # CursorResult sets it False for INSERT/UPDATE/DELETE.
            if getattr(res, "returns_rows", True):
                return ("rows", res.freeze())
            return ("dml", res.rowcount)
        kind, payload = await self._run(_do)
        return payload() if kind == "rows" else _Rowcount(payload)

    async def get(self, *args, **kwargs):
        return await self._run(self._session.get, *args, **kwargs)

    async def scalar(self, statement, *args, **kwargs):
        return await self._run(lambda: self._session.scalar(statement, *args, **kwargs))

    # --- unit of work (in-memory add runs on the worker thread for affinity) -
    def add(self, obj) -> None:
        self._executor.submit(self._session.add, obj).result()

    def add_all(self, objs) -> None:
        self._executor.submit(self._session.add_all, list(objs)).result()

    async def delete(self, obj) -> None:
        await self._run(self._session.delete, obj)

    async def flush(self, *args, **kwargs) -> None:
        await self._run(self._session.flush, *args, **kwargs)

    async def commit(self) -> None:
        await self._run(self._session.commit)

    async def rollback(self) -> None:
        await self._run(self._session.rollback)

    async def refresh(self, obj, *args, **kwargs) -> None:
        await self._run(self._session.refresh, obj, *args, **kwargs)

    async def close(self) -> None:
        if self._session is not None:
            await self._run(self._session.close)
