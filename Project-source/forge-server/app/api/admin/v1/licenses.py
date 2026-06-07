"""Licenses admin API — issue (online/offline), list, get, revoke, delete."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, audit_ctx, get_db_session
from app.core.errors import BizError
from app.models.license import License
from app.permissions.deps import require_perm
from app.permissions.registry import P
from app.repositories.license import LicenseRepository
from app.schemas.license import (
    IssueOfflineOut, IssueOfflineRequest, IssueOnlineOut, IssueOnlineRequest, LicenseOut, RevokeRequest,
)
from app.services.issuance import IssuanceService

router = APIRouter(tags=["licenses"])


def _out(lic: License) -> LicenseOut:
    return LicenseOut(
        id=str(lic.id), license_id=str(lic.license_id), customer_id=str(lic.customer_id),
        product_id=str(lic.product_id), mode=lic.mode, term_preset=lic.term_preset,
        subscription=lic.subscription, active_from=lic.active_from, active_until=lic.active_until,
        status=lic.status, binding=lic.binding, seat_limit=lic.seat_limit, seat_used=lic.seat_used,
        features=lic.features, quotas=lic.quotas, issued_at=lic.issued_at,
    )


@router.post("/licenses:issue-online", status_code=201)
async def issue_online(body: IssueOnlineRequest, request: Request,
                       user: CurrentUser = Depends(require_perm(P.LICENSE_ISSUE)),
                       db: AsyncSession = Depends(get_db_session)) -> IssueOnlineOut:
    lic = await IssuanceService(db).issue_online(body, actor_id=user.user_id, ctx=audit_ctx(request))
    return IssueOnlineOut(license_id=str(lic.license_id), online_code=lic.online_code,
                          active_from=lic.active_from, active_until=lic.active_until,
                          seat_limit=lic.seat_limit, status=lic.status)


@router.post("/licenses:issue-offline", status_code=201)
async def issue_offline(body: IssueOfflineRequest, request: Request,
                        user: CurrentUser = Depends(require_perm(P.LICENSE_ISSUE)),
                        db: AsyncSession = Depends(get_db_session)) -> IssueOfflineOut:
    lic = await IssuanceService(db).issue_offline(body, actor_id=user.user_id, ctx=audit_ctx(request))
    return IssueOfflineOut(license_id=str(lic.license_id), offline_blob=lic.offline_blob,
                           bound_fingerprint=lic.bound_fingerprint, active_from=lic.active_from,
                           active_until=lic.active_until, status=lic.status)


@router.get("/licenses")
async def list_licenses(page: int = 1, page_size: int = 50,
                        user: CurrentUser = Depends(require_perm(P.LICENSE_READ)),
                        db: AsyncSession = Depends(get_db_session)) -> dict:
    repo = LicenseRepository(db)
    items = await repo.list(limit=min(page_size, 100), offset=(max(page, 1) - 1) * page_size)
    return {"data": [_out(x).model_dump(mode="json") for x in items], "total": await repo.count()}


@router.get("/licenses/{license_id}")
async def get_license(license_id: str, user: CurrentUser = Depends(require_perm(P.LICENSE_READ)),
                      db: AsyncSession = Depends(get_db_session)) -> LicenseOut:
    lic = await LicenseRepository(db).get(uuid.UUID(license_id))
    if not lic:
        raise BizError("RESOURCE_NOT_FOUND")
    return _out(lic)


@router.post("/licenses/{license_id}:revoke")
async def revoke_license(license_id: str, body: RevokeRequest, request: Request,
                         user: CurrentUser = Depends(require_perm(P.LICENSE_REVOKE)),
                         db: AsyncSession = Depends(get_db_session)) -> dict:
    lic = await IssuanceService(db).revoke(license_id, body.reason, actor_id=user.user_id,
                                           ctx=audit_ctx(request))
    return {"data": {"status": lic.status, "revoked_at": lic.revoked_at.isoformat() if lic.revoked_at else None},
            "request_id": request.state.request_id}


@router.delete("/licenses/{license_id}", status_code=200)
async def delete_license(license_id: str, request: Request,
                         user: CurrentUser = Depends(require_perm(P.LICENSE_DELETE)),
                         db: AsyncSession = Depends(get_db_session)) -> dict:
    from app.services.audit_service import AuditService
    repo = LicenseRepository(db)
    lic = await repo.get(uuid.UUID(license_id))
    if not lic:
        raise BizError("RESOURCE_NOT_FOUND")
    await repo.soft_delete(lic, actor_id=uuid.UUID(user.user_id))
    AuditService(db).log(action="license.delete", result="success", actor_id=user.user_id,
                         resource_type="license", resource_id=str(lic.license_id), **audit_ctx(request))
    await db.commit()
    return {"data": {"deleted": True}, "request_id": request.state.request_id}
