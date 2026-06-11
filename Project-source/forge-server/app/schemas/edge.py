"""forge-edge public API schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

_strict = ConfigDict(strict=True, extra="forbid")


# 反克隆身份字段（design 07）：全部 optional —— 旧 SDK 不发也能激活（向后兼容）。
class ActivateRequest(BaseModel):
    model_config = _strict
    online_code: str = Field(min_length=8, max_length=64)
    fingerprint: str = Field(min_length=8, max_length=128)
    cluster_id: str | None = Field(default=None, max_length=128)
    install_id: str | None = Field(default=None, max_length=64)
    signals: dict[str, str] | None = Field(default=None)
    deployment_uid: str | None = Field(default=None, max_length=128)


class ValidateRequest(BaseModel):
    model_config = _strict
    validation_token: str = Field(min_length=16, max_length=128)
    fingerprint: str = Field(min_length=8, max_length=128)
    install_id: str | None = Field(default=None, max_length=64)
