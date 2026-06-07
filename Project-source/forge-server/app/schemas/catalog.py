"""Product + Customer API schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field

_strict = ConfigDict(strict=True, extra="forbid")
_orm = ConfigDict(from_attributes=True)


class ProductCreate(BaseModel):
    model_config = _strict
    slug: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_\-]+$")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    features_template: list[str] = Field(default_factory=list)
    quotas_template: dict = Field(default_factory=dict)
    default_alg: str = Field(default="ed25519", pattern=r"^(ed25519|rsa2048|rsa4096|sm2)$")


class ProductUpdate(BaseModel):
    model_config = _strict
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    features_template: list[str] | None = None
    quotas_template: dict | None = None
    is_active: bool | None = None


class ProductOut(BaseModel):
    model_config = _orm
    id: str
    slug: str
    name: str
    description: str | None
    features_template: list
    quotas_template: dict
    default_alg: str
    is_active: bool


class CustomerCreate(BaseModel):
    model_config = _strict
    name: str = Field(min_length=1, max_length=255)
    contact_name: str | None = Field(default=None, max_length=128)
    contact_email: EmailStr | None = None
    notes: str | None = Field(default=None, max_length=4000)


class CustomerUpdate(BaseModel):
    model_config = _strict
    name: str | None = Field(default=None, min_length=1, max_length=255)
    contact_name: str | None = Field(default=None, max_length=128)
    contact_email: EmailStr | None = None
    notes: str | None = Field(default=None, max_length=4000)


class CustomerOut(BaseModel):
    model_config = _orm
    id: str
    name: str
    contact_name: str | None
    contact_email: str | None
    notes: str | None
