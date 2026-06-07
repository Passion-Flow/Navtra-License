"""Operator (user) management API schemas — Super Admin manages Admin / Auditor operators."""

from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import ROLES

_strict = ConfigDict(strict=True, extra="forbid")

_ROLE_RE = "^(" + "|".join(ROLES) + ")$"


class UserCreate(BaseModel):
    model_config = _strict
    email: EmailStr
    username: str = Field(min_length=1, max_length=64)
    role: str = Field(pattern=_ROLE_RE)
    # vendor-internal convention (§11.1): if omitted, the initial password defaults to the email.
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdate(BaseModel):
    model_config = _strict
    username: str | None = Field(default=None, min_length=1, max_length=64)
    role: str | None = Field(default=None, pattern=_ROLE_RE)
    is_active: bool | None = None


class PasswordResetIn(BaseModel):
    model_config = _strict
    # if omitted, resets to the operator's email (§11.1 convention).
    new_password: str | None = Field(default=None, min_length=8, max_length=128)


class UserOut(BaseModel):
    id: str
    email: str
    username: str
    role: str
    is_active: bool
    twofa_enabled: bool
    last_login_at: datetime.datetime | None = None
    created_at: datetime.datetime | None = None
