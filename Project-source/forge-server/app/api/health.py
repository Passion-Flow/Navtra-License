"""Liveness / readiness / health probes (observability.md)."""

from __future__ import annotations

from fastapi import APIRouter

from app.adapters.cache.base import get_cache_adapter
from app.db.session import get_engine
from app.settings import get_settings

router = APIRouter(tags=["health"])


@router.get("/livez")
async def livez() -> dict:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz() -> dict:
    settings = get_settings()
    checks = {"database": False, "cache": False}
    try:
        from sqlalchemy import text
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False
    checks["cache"] = await get_cache_adapter(settings).health_check()
    ready = all(checks.values())
    return {"status": "ok" if ready else "degraded", "checks": checks}


@router.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok", "service": "forge", "role": get_settings().APP_ROLE}
