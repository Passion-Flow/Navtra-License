"""Operator (user) management admin API — Super Admin creates/updates/disables Admin & Auditor
operators. Mutations that change role / disable / reset password globally log the target out
(SessionService.destroy_all_for_user) so revoked privileges take effect immediately."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, audit_ctx, get_db_session
from app.core import security
from app.core.errors import BizError
from app.models.user import User
from app.permissions.deps import require_perm
from app.permissions.registry import P
from app.repositories.user import UserRepository
from app.schemas.user import PasswordResetIn, UserCreate, UserOut, UserUpdate
from app.services.audit_service import AuditService
from app.services.session_service import SessionService

router = APIRouter(prefix="/users", tags=["users"])


def _out(u: User) -> UserOut:
    return UserOut(id=str(u.id), email=u.email, username=u.username, role=u.role,
                   is_active=u.is_active, twofa_enabled=u.twofa_enabled,
                   last_login_at=u.last_login_at, created_at=u.created_at)


async def _active_super_admins(db: AsyncSession) -> int:
    stmt = select(func.count()).select_from(User).where(
        User.role == "super_admin", User.is_active.is_(True), User.deleted_at.is_(None))
    return (await db.execute(stmt)).scalar_one()


@router.get("")
async def list_users(page: int = 1, page_size: int = 50,
                     user: CurrentUser = Depends(require_perm(P.USER_READ)),
                     db: AsyncSession = Depends(get_db_session)) -> dict:
    repo = UserRepository(db)
    items = await repo.list(limit=min(page_size, 100), offset=(max(page, 1) - 1) * page_size,
                            order_by=User.created_at.desc())
    return {"data": [_out(u).model_dump(mode="json") for u in items], "total": await repo.count()}


@router.post("", status_code=201)
async def create_user(body: UserCreate, request: Request,
                      user: CurrentUser = Depends(require_perm(P.USER_WRITE)),
                      db: AsyncSession = Depends(get_db_session)) -> UserOut:
    repo = UserRepository(db)
    email = body.email.lower()
    if await repo.get_by_email(email, include_deleted=True):
        raise BizError("RESOURCE_CONFLICT", {"field": "email"})
    # §11.1 vendor convention: default the initial password to the email when not supplied.
    pw = body.password or email
    u = User(email=email, username=body.username, role=body.role, is_active=True,
             password_hash=security.hash_password(pw), created_by=uuid.UUID(user.user_id))
    repo.add(u)
    await db.flush()
    AuditService(db).log(action="user.create", result="success", actor_id=user.user_id,
                         resource_type="user", resource_id=email,
                         metadata={"role": body.role}, **audit_ctx(request))
    await db.commit()
    return _out(u)


@router.patch("/{user_id}")
async def update_user(user_id: str, body: UserUpdate, request: Request,
                      user: CurrentUser = Depends(require_perm(P.USER_WRITE)),
                      db: AsyncSession = Depends(get_db_session)) -> UserOut:
    repo = UserRepository(db)
    u = await repo.get(uuid.UUID(user_id))
    if not u:
        raise BizError("RESOURCE_NOT_FOUND")

    is_self = str(u.id) == user.user_id
    demoting = body.role is not None and body.role != "super_admin" and u.role == "super_admin"
    disabling = body.is_active is False and u.is_active

    # lockout protection: never disable/demote yourself, never remove the last active super-admin.
    if is_self and (disabling or demoting):
        raise BizError("USER_SELF_LOCKOUT")
    if (disabling or demoting) and u.role == "super_admin" and await _active_super_admins(db) <= 1:
        raise BizError("USER_LAST_SUPER_ADMIN")

    role_changed = body.role is not None and body.role != u.role
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(u, field, value)
    u.updated_by = uuid.UUID(user.user_id)
    AuditService(db).log(action="user.update", result="success", actor_id=user.user_id,
                         resource_type="user", resource_id=u.email,
                         metadata={"role": u.role, "is_active": u.is_active}, **audit_ctx(request))
    await db.commit()
    # revoked privileges / disable take effect immediately: kill the target's sessions.
    if role_changed or disabling:
        await SessionService().destroy_all_for_user(str(u.id))
    return _out(u)


@router.post("/{user_id}/reset-password", status_code=200)
async def reset_password(user_id: str, body: PasswordResetIn, request: Request,
                         user: CurrentUser = Depends(require_perm(P.USER_WRITE)),
                         db: AsyncSession = Depends(get_db_session)) -> dict:
    repo = UserRepository(db)
    u = await repo.get(uuid.UUID(user_id))
    if not u:
        raise BizError("RESOURCE_NOT_FOUND")
    u.password_hash = security.hash_password(body.new_password or u.email)
    u.updated_by = uuid.UUID(user.user_id)
    AuditService(db).log(action="user.reset_password", result="success", actor_id=user.user_id,
                         resource_type="user", resource_id=u.email, **audit_ctx(request))
    await db.commit()
    await SessionService().destroy_all_for_user(str(u.id))   # force re-login with the new password
    return {"data": {"reset": True}, "request_id": request.state.request_id}


@router.delete("/{user_id}", status_code=200)
async def delete_user(user_id: str, request: Request,
                      user: CurrentUser = Depends(require_perm(P.USER_DELETE)),
                      db: AsyncSession = Depends(get_db_session)) -> dict:
    repo = UserRepository(db)
    u = await repo.get(uuid.UUID(user_id))
    if not u:
        raise BizError("RESOURCE_NOT_FOUND")
    if str(u.id) == user.user_id:
        raise BizError("USER_SELF_LOCKOUT")
    if u.role == "super_admin" and await _active_super_admins(db) <= 1:
        raise BizError("USER_LAST_SUPER_ADMIN")
    await repo.soft_delete(u, actor_id=uuid.UUID(user.user_id))
    AuditService(db).log(action="user.delete", result="success", actor_id=user.user_id,
                         resource_type="user", resource_id=u.email, **audit_ctx(request))
    await db.commit()
    await SessionService().destroy_all_for_user(str(u.id))
    return {"data": {"deleted": True}, "request_id": request.state.request_id}
