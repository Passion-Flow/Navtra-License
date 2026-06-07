"""CRL admin API — generate + download the signed revocation list."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, audit_ctx, get_db_session
from app.core.errors import BizError
from app.permissions.deps import require_perm
from app.permissions.registry import P
from app.services.crl import CrlService

router = APIRouter(tags=["crl"])


@router.post("/crl:generate")
async def generate(request: Request, user: CurrentUser = Depends(require_perm(P.CRL_GENERATE)),
                   db: AsyncSession = Depends(get_db_session)) -> dict:
    bundle = await CrlService(db).generate(actor_id=user.user_id, ctx=audit_ctx(request))
    return {"data": {"version": bundle.version, "entry_count": bundle.entry_count,
                     "signed_blob": bundle.signed_blob}, "request_id": request.state.request_id}


@router.get("/crl/latest")
async def latest(user: CurrentUser = Depends(require_perm(P.LICENSE_READ)),
                 db: AsyncSession = Depends(get_db_session)) -> dict:
    blob = await CrlService(db).get_latest_blob()
    if not blob:
        raise BizError("RESOURCE_NOT_FOUND", {"resource": "crl"})
    return {"data": {"signed_blob": blob}}
