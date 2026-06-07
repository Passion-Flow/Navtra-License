"""Online seat / hardware binding + lease ORM models.

FingerprintBinding tracks every distinct hardware fingerprint that activated an online
license (seat anti-copy). Lease is persisted for audit; the hot lease state lives in Redis.
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuthorMixin, Base, TimestampMixin, UUIDMixin

BINDING_STATUSES = ("active", "released", "blocked")


class FingerprintBinding(UUIDMixin, TimestampMixin, AuthorMixin, Base):
    __tablename__ = "fingerprint_bindings"

    license_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("licenses.id", ondelete="CASCADE"))
    fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    cluster_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="active")
    first_seen_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    lease_expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Lease(UUIDMixin, TimestampMixin, AuthorMixin, Base):
    __tablename__ = "leases"

    license_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("licenses.id", ondelete="CASCADE"))
    binding_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fingerprint_bindings.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)        # sha256 of validation_token
    issued_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    grace_until: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
