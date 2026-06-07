"""Current-operator endpoints — /me, /me/permissions."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, get_db_session
from app.core import security
from app.core.errors import BizError
from app.repositories.user import UserRepository
from app.schemas.auth import MeOut, PasswordChange, ProfileUpdate

router = APIRouter(tags=["me"])


def _me_out(db_user, permissions: list[str]) -> MeOut:
    return MeOut(id=str(db_user.id), email=db_user.email, username=db_user.username,
                 role=db_user.role, avatar=db_user.avatar, twofa_enabled=db_user.twofa_enabled,
                 permissions=permissions)


@router.get("/me")
async def me(user: CurrentUser = Depends(get_current_user),
             db: AsyncSession = Depends(get_db_session)) -> MeOut:
    db_user = await UserRepository(db).get(uuid.UUID(user.user_id))
    if not db_user:
        raise BizError("AUTH_REQUIRED")
    return _me_out(db_user, user.permissions)


@router.patch("/me/profile")
async def update_my_profile(body: ProfileUpdate, user: CurrentUser = Depends(get_current_user),
                            db: AsyncSession = Depends(get_db_session)) -> MeOut:
    """Self-service: any member edits their own username / email / avatar."""
    repo = UserRepository(db)
    db_user = await repo.get(uuid.UUID(user.user_id))
    if not db_user:
        raise BizError("AUTH_REQUIRED")
    sent = body.model_fields_set
    if "email" in sent and body.email is not None:
        email = body.email.lower()
        existing = await repo.get_by_email(email, include_deleted=True)
        if existing and str(existing.id) != user.user_id:
            raise BizError("RESOURCE_CONFLICT", {"field": "email"})
        db_user.email = email
    if "username" in sent and body.username is not None:
        db_user.username = body.username
    if "avatar" in sent:
        db_user.avatar = body.avatar or None   # empty string clears the avatar
    await db.commit()
    return _me_out(db_user, user.permissions)


@router.post("/me/password")
async def change_my_password(body: PasswordChange, user: CurrentUser = Depends(get_current_user),
                             db: AsyncSession = Depends(get_db_session)) -> dict:
    """Self-service password change — must prove the current password first."""
    db_user = await UserRepository(db).get(uuid.UUID(user.user_id))
    if not db_user:
        raise BizError("AUTH_REQUIRED")
    if not security.verify_password(body.current_password, db_user.password_hash):
        raise BizError("AUTH_INVALID_CREDENTIALS")
    db_user.password_hash = security.hash_password(body.new_password)
    await db.commit()
    return {"data": {"ok": True}}


@router.get("/me/permissions")
async def my_permissions(user: CurrentUser = Depends(get_current_user)) -> dict:
    return {"data": {"permissions": user.permissions, "role": user.role}}
