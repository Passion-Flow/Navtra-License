"""Signing key ORM model — keypairs. private key stored AES-256-GCM encrypted (L5).

purpose=master: offline `.forge` signing (forge-api only, never on the public edge).
purpose=edge_lease: short-lived online lease signing (forge-edge); lower stakes than master.
"""

from __future__ import annotations

import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuthorMixin, Base, TimestampMixin, UUIDMixin

PURPOSES = ("master", "edge_lease")


class SigningKey(UUIDMixin, TimestampMixin, AuthorMixin, Base):
    __tablename__ = "signing_keys"

    key_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)  # e.g. ed25519-<short>
    alg: Mapped[str] = mapped_column(String(16), nullable=False, default="ed25519")
    public_key: Mapped[str] = mapped_column(Text, nullable=False)                 # PEM, exportable
    private_key_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)      # AES-256-GCM
    dek_wrapped: Mapped[str] = mapped_column(Text, nullable=False)                 # KEK-wrapped DEK
    purpose: Mapped[str] = mapped_column(String(16), nullable=False, default="master")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    rotated_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
