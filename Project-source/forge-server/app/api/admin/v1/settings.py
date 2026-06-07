"""Settings admin API — signing keys (public material only; private keys never leave api)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_db_session
from app.core.errors import BizError
from app.models.signing_key import SigningKey
from app.permissions.deps import require_perm
from app.permissions.registry import P

router = APIRouter(prefix="/signing-keys", tags=["settings"])


@router.get("")
async def list_keys(user: CurrentUser = Depends(require_perm(P.KEY_READ)),
                    db: AsyncSession = Depends(get_db_session)) -> dict:
    rows = (await db.execute(
        select(SigningKey).where(SigningKey.deleted_at.is_(None)).order_by(SigningKey.created_at.desc())
    )).scalars().all()
    # NEVER return private_key_ciphertext / dek_wrapped.
    return {"data": [{"id": str(k.id), "key_id": k.key_id, "alg": k.alg, "purpose": k.purpose,
                      "is_active": k.is_active, "created_at": k.created_at.isoformat()} for k in rows]}


@router.get("/{key_id}:export-public")
async def export_public(key_id: str, user: CurrentUser = Depends(require_perm(P.KEY_READ)),
                        db: AsyncSession = Depends(get_db_session)) -> dict:
    """Return the PUBLIC key (PEM) to embed into a consumer product's Verifier SDK."""
    k = (await db.execute(select(SigningKey).where(SigningKey.key_id == key_id))).scalar_one_or_none()
    if not k:
        raise BizError("KEY_NOT_FOUND")
    return {"data": {"key_id": k.key_id, "alg": k.alg, "purpose": k.purpose, "public_key": k.public_key}}
