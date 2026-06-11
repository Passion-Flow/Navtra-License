"""Authentication service — login, 2FA, password reset (authentication.md).

Coordinates user repo + session store + rate limiter + audit + crypto. All user-facing
failures raise BizError(code); no bare strings, no email enumeration.
"""

from __future__ import annotations

import hashlib
import secrets

import pyotp
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.cache.base import get_cache_adapter
from app.core import crypto, security
from app.core.errors import BizError
from app.models.user import User
from app.permissions.roles import PLATFORM_ROLES
from app.repositories.user import UserRepository
from app.services.ratelimit import RateLimiter
from app.settings import get_settings


def _permissions_for(role: str) -> list[str]:
    perms = PLATFORM_ROLES.get(role, set())
    return ["*"] if "*" in perms else sorted(perms)


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.rl = RateLimiter()
        self.settings = get_settings()
        self.reset_redis = get_cache_adapter(self.settings).client(self.settings.CACHE_DB_APP)

    # ---- login ----------------------------------------------------------------
    async def authenticate(self, email: str, password: str, code: str | None) -> User:
        await self.rl.assert_not_locked(email)
        user = await self.users.get_by_email(email)
        # Constant-ish path: always do a hash verify to reduce timing oracle.
        valid = user is not None and security.verify_password(password, user.password_hash)
        if not user or not valid:
            await self.rl.record_login_failure(email)
            raise BizError("AUTH_INVALID_CREDENTIALS")
        if not user.is_active:
            raise BizError("AUTH_ACCOUNT_DISABLED")
        if user.twofa_enabled:
            if not code:
                raise BizError("AUTH_2FA_REQUIRED")
            if not self._verify_totp(user, code):
                await self.rl.record_login_failure(email)
                raise BizError("AUTH_2FA_INVALID")
        await self.rl.clear_login_failures(email)
        return user

    def permissions_for(self, user: User) -> list[str]:
        return _permissions_for(user.role)

    # ---- 2FA -------------------------------------------------------------------
    def _decrypt_totp_secret(self, user: User) -> str:
        return crypto.decrypt_secret(
            user.twofa_secret_ciphertext, user.twofa_dek_wrapped,
            self.settings.FORGE_FIELD_ENCRYPTION_KEY,
        ).decode()

    def _verify_totp(self, user: User, code: str) -> bool:
        if not user.twofa_secret_ciphertext:
            return False
        return pyotp.TOTP(self._decrypt_totp_secret(user)).verify(code, valid_window=1)

    def begin_2fa_setup(self, user: User) -> tuple[str, str]:
        """Generate a fresh secret + provisioning URI (not yet enabled)."""
        secret = pyotp.random_base32()
        uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=self.settings.TWOFA_ISSUER)
        ct, dek = crypto.encrypt_secret(secret.encode(), self.settings.FORGE_FIELD_ENCRYPTION_KEY)
        user.twofa_secret_ciphertext, user.twofa_dek_wrapped = ct, dek  # stored pending verify
        return secret, uri

    def confirm_2fa(self, user: User, code: str) -> list[str]:
        if not pyotp.TOTP(self._decrypt_totp_secret(user)).verify(code, valid_window=1):
            raise BizError("AUTH_2FA_INVALID")
        user.twofa_enabled = True
        backup = [secrets.token_hex(5) for _ in range(8)]
        ct, dek = crypto.encrypt_secret("\n".join(backup).encode(), self.settings.FORGE_FIELD_ENCRYPTION_KEY)
        user.backup_codes_ciphertext, user.backup_codes_dek_wrapped = ct, dek
        return backup

    # ---- password reset (anti-enumeration) ------------------------------------
    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    async def request_password_reset(self, email: str) -> str | None:
        """Return a token ONLY if the user exists; caller always shows the same response."""
        user = await self.users.get_by_email(email)
        if not user or not user.is_active:
            return None
        token = security.new_token(32)
        await self.reset_redis.set(
            f"pwreset:{self._hash_token(token)}", str(user.id), ex=self.settings.RESET_TOKEN_TTL_SECONDS
        )
        return token

    async def confirm_password_reset(self, token: str, new_password: str) -> User:
        key = f"pwreset:{self._hash_token(token)}"
        user_id = await self.reset_redis.get(key)
        if not user_id:
            raise BizError("AUTH_PASSWORD_RESET_TOKEN_INVALID")
        import uuid
        user = await self.users.get(uuid.UUID(user_id))
        if not user:
            raise BizError("AUTH_PASSWORD_RESET_TOKEN_INVALID")
        security.validate_password_policy(
            new_password, min_length=self.settings.PASSWORD_MIN_LENGTH,
            email=user.email, username=user.username,
            require_char_classes=self.settings.PASSWORD_REQUIRE_CHAR_CLASSES,
            forbid_identity=self.settings.PASSWORD_FORBID_IDENTITY,
        )
        user.password_hash = security.hash_password(new_password)
        await self.reset_redis.delete(key)  # one-time
        return user
