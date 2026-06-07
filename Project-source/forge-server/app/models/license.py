"""License ORM model (core). online (short code, phone-home) vs offline (signed .forge)."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import uuid7
from app.db.base import AuthorMixin, Base, JSONType, TimestampMixin, UUIDMixin

MODES = ("online", "offline")
TERM_PRESETS = ("1m", "3m", "6m", "1y", "3y", "5y", "perpetual")
SCOPES = ("customer_x_product", "customer_bundle", "instance")
BINDINGS = ("none", "soft", "hard")
STATUSES = ("issued", "active", "expiring", "expired", "revoked", "locked")


class License(UUIDMixin, TimestampMixin, AuthorMixin, Base):
    __tablename__ = "licenses"

    license_id: Mapped[uuid.UUID] = mapped_column(default=uuid7, unique=True)  # masked display id
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"))
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    signing_key_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("signing_keys.id", ondelete="RESTRICT"))

    mode: Mapped[str] = mapped_column(String(8), nullable=False)
    online_code: Mapped[str | None] = mapped_column(String(64), nullable=True)   # online: UUID token
    offline_blob: Mapped[str | None] = mapped_column(Text, nullable=True)        # offline: .forge base64

    term_preset: Mapped[str] = mapped_column(String(16), nullable=False)
    active_from: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    active_until: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    subscription: Mapped[str] = mapped_column(String(32), nullable=False, default="Enterprise")
    quotas: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    features: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)

    scope: Mapped[str] = mapped_column(String(24), nullable=False, default="customer_x_product")
    binding: Mapped[str] = mapped_column(String(8), nullable=False, default="hard")
    bound_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cluster_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    seat_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    seat_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    status: Mapped[str] = mapped_column(String(12), nullable=False, default="issued")
    alg: Mapped[str] = mapped_column(String(16), nullable=False, default="ed25519")
    issued_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    issued_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    activated_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
