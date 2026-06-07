"""Auth API schemas — Pydantic v2 strict (data-validation.md). No dict/Any inputs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field

_strict = ConfigDict(strict=True, extra="forbid")


class LoginRequest(BaseModel):
    model_config = _strict
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    code: str | None = Field(default=None, max_length=8)  # 2FA TOTP


class MeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    username: str
    role: str
    avatar: str | None = None
    twofa_enabled: bool
    permissions: list[str]


class ProfileUpdate(BaseModel):
    """Self-service profile edit — any subset of one's own username / email / avatar."""
    model_config = _strict
    username: str | None = Field(default=None, min_length=1, max_length=64)
    email: EmailStr | None = None
    # a small image data URI (data:image/...;base64,...) or an https URL; <= ~512 KB encoded.
    avatar: str | None = Field(default=None, max_length=700_000)


class PasswordChange(BaseModel):
    """Self-service password change — must prove the current password."""
    model_config = _strict
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


class TwoFAVerify(BaseModel):
    model_config = _strict
    code: str = Field(min_length=6, max_length=8)


class TwoFASetupOut(BaseModel):
    secret: str
    provisioning_uri: str
