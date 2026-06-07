"""Engine + session factory, assembled via the active database adapter.

Async-driver providers (asyncpg/aiomysql) use the AsyncEngine/AsyncSession path unchanged.
Sync-only providers (是 is_async=False — 达梦/Kingbase) are driven through the thread-affine
SyncBridgeSession over a synchronous Engine, so the verified async core is never modified.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker

from app.adapters.database.base import DatabaseAdapter, get_database_adapter
from app.db.sync_bridge import SyncBridgeSession
from app.settings import get_settings

_adapter: DatabaseAdapter | None = None
_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None
_sync_engine: Any = None
_sync_sessionmaker: Any = None


def _adapter_inst() -> DatabaseAdapter:
    global _adapter
    if _adapter is None:
        _adapter = get_database_adapter(get_settings())
    return _adapter


def get_engine() -> AsyncEngine:
    global _engine, _sessionmaker
    if _engine is None:
        _engine = _adapter_inst().create_engine()
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _sessionmaker is None:
        get_engine()
    assert _sessionmaker is not None
    return _sessionmaker


def _get_sync_sessionmaker():
    global _sync_engine, _sync_sessionmaker
    if _sync_sessionmaker is None:
        _sync_engine = _adapter_inst().create_sync_engine()
        _sync_sessionmaker = sessionmaker(_sync_engine, expire_on_commit=False)
    return _sync_sessionmaker


async def get_db_session() -> AsyncIterator[Any]:
    """FastAPI dependency: one session per request. Async providers yield AsyncSession;
    sync-only providers yield a SyncBridgeSession with the same async API surface."""
    if _adapter_inst().is_async:
        async with get_sessionmaker()() as session:
            yield session
    else:
        async with SyncBridgeSession(_get_sync_sessionmaker()) as session:
            yield session


def reset_engine() -> None:
    """Clear cached engines/sessionmakers (test support). No-op cost in production."""
    global _adapter, _engine, _sessionmaker, _sync_engine, _sync_sessionmaker
    _adapter = None
    _engine = None
    _sessionmaker = None
    _sync_engine = None
    _sync_sessionmaker = None
