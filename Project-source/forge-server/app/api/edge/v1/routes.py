"""forge-edge public validation API (/edge/v1). NO master key; hardened; strict rate limits.

This is the only Forge surface a consumer product reaches over the public internet.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import audit_ctx, get_db_session
from app.licensing.keys import KeyManager
from app.schemas.edge import ActivateRequest, ValidateRequest
from app.services.edge import EdgeService
from app.services.ratelimit import RateLimiter

router = APIRouter(prefix="/edge/v1", tags=["edge"])


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/activate")
async def activate(body: ActivateRequest, request: Request,
                   db: AsyncSession = Depends(get_db_session)) -> dict:
    rl = RateLimiter()
    await rl.hit(f"edge_act_ip:{_ip(request)}", limit=20, window=60)
    await rl.hit(f"edge_act_code:{body.online_code}", limit=10, window=60)
    return await EdgeService(db).activate(body.online_code, body.fingerprint, body.cluster_id, audit_ctx(request))


@router.post("/validate")
async def validate(body: ValidateRequest, request: Request,
                   db: AsyncSession = Depends(get_db_session)) -> dict:
    await RateLimiter().hit(f"edge_val:{body.validation_token[:16]}", limit=60, window=60)
    return await EdgeService(db).validate(body.validation_token, body.fingerprint, audit_ctx(request))


@router.get("/crl")
async def crl(db: AsyncSession = Depends(get_db_session)) -> dict:
    """Latest signed CRL for products to fetch (online-reachable products auto-pull it)."""
    from app.services.crl import CrlService
    blob = await CrlService(db).get_latest_blob()
    return {"data": {"signed_blob": blob}}


@router.get("/public-key")
async def public_key(db: AsyncSession = Depends(get_db_session)) -> dict:
    """Public keys consumers embed: master verifies offline .forge, edge_lease verifies leases."""
    km = KeyManager(db)
    master = await km.require_active("master")
    edge = await km.require_active("edge_lease")
    return {"data": {
        "master": {"key_id": master.key_id, "alg": master.alg, "public_key": master.public_key},
        "edge_lease": {"key_id": edge.key_id, "alg": edge.alg, "public_key": edge.public_key},
    }}
