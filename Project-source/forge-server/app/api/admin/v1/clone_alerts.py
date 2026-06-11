"""Clone-alert admin API — list & resolve "one license, multiple identities" alerts, and the
active online bindings behind a license (design 07-identity-anticlone §7)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_db_session
from app.core.errors import BizError
from app.models.binding import CloneAlert, FingerprintBinding
from app.models.license import License
from app.permissions.deps import require_perm
from app.permissions.registry import P

# prefix /admin-api/v1 is added at include time in main.py (matches the other admin routers)
router = APIRouter(tags=["clone-alerts"])


def _mask(v: str | None) -> str | None:
    if not v:
        return None
    return f"{v[:8]}…" if len(v) > 8 else v


def _alert_out(a: CloneAlert, license_public_id: str | None) -> dict:
    return {
        "id": str(a.id),
        "license_id": license_public_id,
        "detected_at": a.detected_at.isoformat() if a.detected_at else None,
        "alive_identities": a.alive_identities,
        "seat_limit": a.seat_limit,
        "sample": a.sample,
        "status": a.status,
    }


@router.get("/clone-alerts")
async def list_clone_alerts(status: str | None = None,
                            user: CurrentUser = Depends(require_perm(P.LICENSE_READ)),
                            db: AsyncSession = Depends(get_db_session)) -> dict:
    q = select(CloneAlert, License.license_id).join(License, License.id == CloneAlert.license_id)
    if status:
        q = q.where(CloneAlert.status == status)
    q = q.order_by(CloneAlert.detected_at.desc()).limit(200)
    rows = (await db.execute(q)).all()
    return {"data": [_alert_out(a, str(pub)) for a, pub in rows]}


@router.post("/clone-alerts/{alert_id}:resolve")
async def resolve_clone_alert(alert_id: str,
                              user: CurrentUser = Depends(require_perm(P.LICENSE_REVOKE)),
                              db: AsyncSession = Depends(get_db_session)) -> dict:
    alert = (await db.execute(
        select(CloneAlert).where(CloneAlert.id == uuid.UUID(alert_id))
    )).scalar_one_or_none()
    if not alert:
        raise BizError("RESOURCE_NOT_FOUND")
    alert.status = "resolved"
    await db.commit()
    return {"data": {"id": alert_id, "status": "resolved"}}


@router.get("/licenses/{license_id}/bindings")
async def list_bindings(license_id: str,
                        user: CurrentUser = Depends(require_perm(P.LICENSE_READ)),
                        db: AsyncSession = Depends(get_db_session)) -> dict:
    """Active online bindings (identities) behind a license — fingerprint / deployment uid /
    install id (masked) / heartbeat — so an operator can see who is using each seat."""
    rows = (await db.execute(
        select(FingerprintBinding).where(
            FingerprintBinding.license_id == uuid.UUID(license_id),
            FingerprintBinding.deleted_at.is_(None),
        ).order_by(FingerprintBinding.last_seen_at.desc())
    )).scalars().all()
    return {"data": [{
        "id": str(b.id),
        "fingerprint": _mask(b.fingerprint),
        "deployment_uid": b.deployment_uid,
        "install_id": _mask(b.install_id),
        "cluster_id": b.cluster_id,
        "status": b.status,
        "first_seen_at": b.first_seen_at.isoformat() if b.first_seen_at else None,
        "last_seen_at": b.last_seen_at.isoformat() if b.last_seen_at else None,
        "last_heartbeat_at": b.last_heartbeat_at.isoformat() if b.last_heartbeat_at else None,
    } for b in rows]}
