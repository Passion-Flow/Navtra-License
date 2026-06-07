"""Admin auth API — login / logout / me / password reset / 2FA (authentication.md)."""

from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, get_db_session
from app.repositories.user import UserRepository
from app.schemas.auth import LoginRequest, MeOut, TwoFASetupOut, TwoFAVerify
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.services.ratelimit import RateLimiter
from app.services.session_service import SessionService
from app.settings import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, sid: str) -> None:
    s = get_settings()
    response.set_cookie(
        key=s.SESSION_COOKIE_NAME, value=sid, httponly=True, secure=s.SESSION_COOKIE_SECURE,
        samesite=s.SESSION_COOKIE_SAMESITE, max_age=s.SESSION_ABSOLUTE_TTL_SECONDS, path="/",
    )


@router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response,
                db: AsyncSession = Depends(get_db_session)) -> MeOut:
    auth = AuthService(db)
    audit = AuditService(db)
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")
    await RateLimiter().hit(f"login_ip:{ip}", limit=get_settings().LOGIN_MAX_PER_IP_PER_MIN,
                            window=60, code="RATE_LIMIT_LOGIN_BLOCKED")
    try:
        user = await auth.authenticate(body.email, body.password, body.code)
    except Exception as exc:
        audit.log(action="login", result="failure", actor_type="user", actor_name=body.email,
                  reason=getattr(exc, "code", "AUTH_INVALID_CREDENTIALS"), ip=ip, user_agent=ua,
                  request_id=request.state.request_id)
        await db.commit()
        raise
    user.last_login_at = datetime.datetime.now(datetime.timezone.utc)
    perms = auth.permissions_for(user)
    sid = await SessionService().create(user_id=str(user.id), role=user.role, ip=ip or "", ua=ua,
                                        twofa_verified=user.twofa_enabled, permissions=perms)
    audit.log(action="login", result="success", actor_id=str(user.id), actor_name=user.username,
              ip=ip, user_agent=ua, request_id=request.state.request_id)
    await db.commit()
    _set_session_cookie(response, sid)
    return MeOut(id=str(user.id), email=user.email, username=user.username, role=user.role,
                 twofa_enabled=user.twofa_enabled, permissions=perms)


@router.post("/logout")
async def logout(request: Request, response: Response,
                 user: CurrentUser = Depends(get_current_user)) -> dict:
    sid = request.cookies.get(get_settings().SESSION_COOKIE_NAME)
    if sid:
        await SessionService().destroy(sid)
    response.delete_cookie(get_settings().SESSION_COOKIE_NAME, path="/")
    return {"data": {"ok": True}, "request_id": request.state.request_id}


# NOTE: no unauthenticated "forgot password" flow — Forge is vendor-internal (~5 operators).
# Operators change their own password under Account Security (authenticated, Phase 3), and the
# super admin sets/resets operator passwords in user management. AuthService still carries the
# password-policy + reset-token primitives those features will reuse.


@router.post("/2fa:setup")
async def twofa_setup(request: Request, user: CurrentUser = Depends(get_current_user),
                      db: AsyncSession = Depends(get_db_session)) -> TwoFASetupOut:
    repo = UserRepository(db)
    import uuid
    db_user = await repo.get(uuid.UUID(user.user_id))
    secret, uri = AuthService(db).begin_2fa_setup(db_user)
    await db.commit()
    return TwoFASetupOut(secret=secret, provisioning_uri=uri)


@router.post("/2fa:verify")
async def twofa_verify(body: TwoFAVerify, request: Request,
                       user: CurrentUser = Depends(get_current_user),
                       db: AsyncSession = Depends(get_db_session)) -> dict:
    import uuid
    repo = UserRepository(db)
    db_user = await repo.get(uuid.UUID(user.user_id))
    backup = AuthService(db).confirm_2fa(db_user, body.code)
    AuditService(db).log(action="2fa_enable", result="success", actor_id=user.user_id,
                         actor_name=db_user.username, request_id=request.state.request_id)
    await db.commit()
    return {"data": {"backup_codes": backup}, "request_id": request.state.request_id}
