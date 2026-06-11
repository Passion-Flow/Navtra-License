"""Audit service — the ONLY way to write the append-only audit log (audit-log.md).

Business operation + audit write share the caller's transaction (database.md §11):
the caller commits both together. Sensitive values are masked before entering metadata.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog

_SENSITIVE = {"password", "token", "secret", "private_key", "validation_token", "kek"}


def _mask_metadata(metadata: dict) -> dict:
    out = {}
    for k, v in (metadata or {}).items():
        if k.lower() in _SENSITIVE and isinstance(v, str):
            out[k] = f"{v[:4]}****{v[-4:]}" if len(v) > 8 else "****"
        else:
            out[k] = v
    return out


class AuditService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def log(
        self,
        *,
        action: str,
        result: str,
        actor_type: str = "user",
        actor_id: str | None = None,
        actor_name: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        reason: str | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
        metadata: dict | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            action=action,
            result=result,
            actor_type=actor_type,
            actor_id=actor_id,
            actor_name=actor_name,
            resource_type=resource_type,
            resource_id=resource_id,
            reason=reason,
            ip=ip,
            user_agent=user_agent,
            request_id=request_id,
            metadata_=_mask_metadata(metadata or {}),
        )
        self.db.add(entry)
        return entry
