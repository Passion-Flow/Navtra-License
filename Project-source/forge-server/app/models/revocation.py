"""Revocation + signed CRL bundle ORM models.

Online licenses are revoked server-side (instant). Offline licenses can't phone home, so
revoked offline licenses are published in a signed CRL the product imports.
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuthorMixin, Base, TimestampMixin, UUIDMixin


class Revocation(UUIDMixin, TimestampMixin, AuthorMixin, Base):
    __tablename__ = "revocations"

    # FK is SET NULL (not RESTRICT): the license row may be HARD-deleted, but the revocation must
    # survive so its license_id stays in the CRL — offline clients keep rejecting it (no bypass).
    license_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("licenses.id", ondelete="SET NULL"), unique=True, nullable=True
    )
    # denormalized at revoke time so the CRL needs no License row (survives license hard-delete).
    license_public_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mode: Mapped[str | None] = mapped_column(String(12), nullable=True)   # online / offline
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    revoked_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    crl_version: Mapped[int | None] = mapped_column(Integer, nullable=True)  # set when included in a CRL


class CrlBundle(UUIDMixin, TimestampMixin, AuthorMixin, Base):
    __tablename__ = "crl_bundles"

    version: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    signed_blob: Mapped[str] = mapped_column(Text, nullable=False)   # base64 signed CRL (JSON + signature)
    entry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
