"""forge-edge public API schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

_strict = ConfigDict(strict=True, extra="forbid")


class ActivateRequest(BaseModel):
    model_config = _strict
    online_code: str = Field(min_length=8, max_length=64)
    fingerprint: str = Field(min_length=8, max_length=128)
    cluster_id: str | None = Field(default=None, max_length=128)


class ValidateRequest(BaseModel):
    model_config = _strict
    validation_token: str = Field(min_length=16, max_length=128)
    fingerprint: str = Field(min_length=8, max_length=128)
