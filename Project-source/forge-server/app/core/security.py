"""Password hashing (argon2id), secure tokens, password policy, fingerprint compare."""

from __future__ import annotations

import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.errors import BizError

_hasher = PasswordHasher()  # argon2id defaults (memory/time cost are sane for server use)

_WEAK = {"password", "123456", "12345678", "qwerty", "admin", "forge", "letmein"}


def hash_password(plaintext: str) -> str:
    return _hasher.hash(plaintext)


def verify_password(plaintext: str, stored_hash: str) -> bool:
    try:
        return _hasher.verify(stored_hash, plaintext)
    except (VerifyMismatchError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(stored_hash)
    except InvalidHashError:
        return True


def validate_password_policy(
    password: str,
    *,
    min_length: int,
    email: str,
    username: str,
    require_char_classes: int = 3,
    forbid_identity: bool = True,
) -> None:
    """Raise AUTH_PASSWORD_WEAK if the password violates policy (authentication.md).

    `require_char_classes` and `forbid_identity` are tunable so a vendor-internal product
    (e.g. Forge, b2b §11.1) can relax the policy — e.g. allow a password equal to the email.
    """
    if len(password) < min_length:
        raise BizError("AUTH_PASSWORD_WEAK", {"reason": "min_length", "min_length": min_length})
    classes = sum(
        bool(any(c in group for c in password))
        for group in ("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz",
                      "0123456789", "!@#$%^&*()-_=+[]{};:,.<>?/|")
    )
    if classes < require_char_classes:
        raise BizError("AUTH_PASSWORD_WEAK", {"reason": "char_classes"})
    low = password.lower()
    if low in _WEAK:
        raise BizError("AUTH_PASSWORD_WEAK", {"reason": "too_common"})
    if forbid_identity and (low == (username or "").lower() or low == (email or "").lower()):
        raise BizError("AUTH_PASSWORD_WEAK", {"reason": "equals_identity"})


def new_token(nbytes: int = 32) -> str:
    """URL-safe one-time token (>= 32 bytes entropy) for password reset / API keys."""
    return secrets.token_urlsafe(nbytes)


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)
