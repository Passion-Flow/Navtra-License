"""Audit logs admin API — read-only, filterable (Super Admin / Auditor only)."""

from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_db_session
from app.models.audit import AuditLog
from app.permissions.deps import require_perm
from app.permissions.registry import P

router = APIRouter(prefix="/audit-logs", tags=["audit"])


def _row(a: AuditLog) -> dict:
    return {
        "id": str(a.id), "timestamp": a.timestamp.isoformat(),
        "actor_type": a.actor_type, "actor_name": a.actor_name, "actor_id": a.actor_id,
        "action": a.action, "resource_type": a.resource_type, "resource_id": a.resource_id,
        "result": a.result, "reason": a.reason, "ip": a.ip, "request_id": a.request_id,
        "metadata": a.metadata_,
    }


@router.get("")
async def list_audit_logs(
    page: int = 1, page_size: int = 50,
    action: str | None = None, resource_type: str | None = None, result: str | None = None,
    date_from: datetime.datetime | None = None, date_to: datetime.datetime | None = None,
    user: CurrentUser = Depends(require_perm(P.AUDIT_READ)),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    filters = []
    if action:
        filters.append(AuditLog.action == action)
    if resource_type:
        filters.append(AuditLog.resource_type == resource_type)
    if result:
        filters.append(AuditLog.result == result)
    if date_from:
        filters.append(AuditLog.timestamp >= date_from)
    if date_to:
        filters.append(AuditLog.timestamp <= date_to)

    stmt = (select(AuditLog).where(*filters).order_by(AuditLog.timestamp.desc())
            .limit(min(page_size, 200)).offset((max(page, 1) - 1) * page_size))
    rows = (await db.execute(stmt)).scalars().all()
    total = (await db.execute(select(func.count()).select_from(AuditLog).where(*filters))).scalar_one()
    return {"data": [_row(a) for a in rows], "total": int(total)}
