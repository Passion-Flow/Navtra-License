"""Celery application — the `worker` and `scheduler` (beat) container roles load this module
(`celery -A app.worker ...`). Broker + result backend live on the same Redis as the app cache,
on dedicated logical DBs (CACHE_DB_BROKER / CACHE_DB_RESULT).

Tasks do not duplicate business logic: each opens a normal DB session through the active database
adapter and calls the very same async services the API uses, so the verified core stays the one
source of truth. Async work is bridged to Celery's sync worker via a fresh event loop per task.
"""

from __future__ import annotations

import asyncio
import datetime
import os
from collections.abc import Awaitable, Callable
from typing import Any

from celery import Celery

from app.settings import get_settings


def _redis_url(db: int) -> str:
    s = get_settings()
    scheme = "rediss" if s.CACHE_USE_SSL else "redis"
    auth = f":{s.CACHE_PASSWORD}@" if s.CACHE_PASSWORD else ""
    return f"{scheme}://{auth}{s.CACHE_HOST}:{s.CACHE_PORT}/{db}"


_s = get_settings()

# Periodic cadences (seconds) — overridable via env without touching settings.py.
_CRL_REFRESH_SECONDS = float(os.getenv("CRL_REFRESH_SECONDS", "21600"))   # 6h
_LICENSE_SWEEP_SECONDS = float(os.getenv("LICENSE_SWEEP_SECONDS", "3600"))  # 1h

celery = Celery(
    "forge",
    broker=_redis_url(_s.CACHE_DB_BROKER),
    backend=_redis_url(_s.CACHE_DB_RESULT),
)
celery.conf.update(
    task_default_queue="default",
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    result_expires=3600,
    timezone=os.getenv("TZ", "UTC"),
    beat_schedule={
        # Republish the signed CRL so new revocations propagate to edge / offline validators.
        "refresh-crl": {"task": "forge.refresh_crl", "schedule": _CRL_REFRESH_SECONDS},
        # Flip licenses past their active_until into the terminal "expired" status (dashboard truth).
        "sweep-expired-licenses": {"task": "forge.sweep_expired_licenses", "schedule": _LICENSE_SWEEP_SECONDS},
    },
)


async def _with_session(fn: Callable[[Any], Awaitable[Any]]) -> Any:
    """Run one async unit of work against a single DB session.

    Each Celery task runs under its own ``asyncio.run`` event loop, so we must NOT reuse the app's
    cached engine (its asyncpg pool is bound to whichever loop created it — reuse across loops raises
    "attached to a different loop"). Instead build a dedicated engine for this task and dispose it
    afterwards. Periodic tasks are infrequent, so the per-run engine cost is negligible.
    """
    from app.adapters.database.base import get_database_adapter

    adapter = get_database_adapter(get_settings())
    if adapter.is_async:
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        engine = adapter.create_engine()
        try:
            sm = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
            async with sm() as session:
                return await fn(session)
        finally:
            await engine.dispose()
    else:
        from sqlalchemy.orm import sessionmaker

        from app.db.sync_bridge import SyncBridgeSession

        engine = adapter.create_sync_engine()
        try:
            async with SyncBridgeSession(sessionmaker(engine, expire_on_commit=False)) as session:
                return await fn(session)
        finally:
            engine.dispose()


@celery.task(name="forge.refresh_crl")
def refresh_crl() -> int | None:
    """Regenerate + sign the CRL bundle (no-op-cheap when nothing changed; version still bumps)."""

    async def _do(session: Any) -> int | None:
        from app.services.crl import CrlService

        bundle = await CrlService(session).generate(
            actor_id=None, ctx={"actor_type": "system", "actor_name": "scheduler"}
        )
        return getattr(bundle, "version", None)

    return asyncio.run(_with_session(_do))


@celery.task(name="forge.sweep_expired_licenses")
def sweep_expired_licenses() -> int:
    """Mark licenses whose active_until has passed as expired. Returns the number flipped."""

    async def _do(session: Any) -> int:
        from sqlalchemy import update

        from app.models.license import License

        now = datetime.datetime.now(datetime.timezone.utc)
        res = await session.execute(
            update(License)
            .where(
                License.active_until.is_not(None),
                License.active_until < now,
                License.status.notin_(("expired", "revoked", "locked")),
            )
            .values(status="expired")
        )
        await session.commit()
        return int(getattr(res, "rowcount", 0) or 0)

    return asyncio.run(_with_session(_do))
