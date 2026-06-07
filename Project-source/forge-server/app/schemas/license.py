"""License issuance + output schemas."""

from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict, Field

_strict = ConfigDict(strict=True, extra="forbid")
_TERM = r"^(1m|3m|6m|1y|3y|5y|perpetual)$"


class IssueOnlineRequest(BaseModel):
    model_config = _strict
    customer_id: str
    product_id: str
    term_preset: str = Field(pattern=_TERM)
    subscription: str = Field(default="Enterprise", max_length=32)
    quotas: dict = Field(default_factory=dict)
    features: list[str] = Field(default_factory=list)
    seat_limit: int = Field(default=1, ge=1, le=100000)


class IssueOfflineRequest(BaseModel):
    model_config = _strict
    customer_id: str
    product_id: str
    # hardware fingerprint = SHA-256 hex (64 lowercase). Enforced here AND in issue_offline
    # (defence in depth) so garbage can't be signed.
    deployment_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    term_preset: str = Field(pattern=_TERM)
    subscription: str = Field(default="Enterprise", max_length=32)
    quotas: dict = Field(default_factory=dict)
    features: list[str] = Field(default_factory=list)
    cluster_id: str | None = Field(default=None, max_length=128)


class IssueOnlineOut(BaseModel):
    license_id: str
    online_code: str
    active_from: datetime.datetime
    active_until: datetime.datetime | None
    seat_limit: int
    status: str


class IssueOfflineOut(BaseModel):
    license_id: str
    offline_blob: str
    bound_fingerprint: str
    active_from: datetime.datetime
    active_until: datetime.datetime | None
    status: str


class RevokeRequest(BaseModel):
    model_config = _strict
    reason: str = Field(default="", max_length=255)


class LicenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    license_id: str
    customer_id: str
    product_id: str
    mode: str
    term_preset: str
    subscription: str
    active_from: datetime.datetime
    active_until: datetime.datetime | None
    status: str
    binding: str
    seat_limit: int
    seat_used: int
    features: list
    quotas: dict
    issued_at: datetime.datetime
