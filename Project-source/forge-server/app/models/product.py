"""Product ORM model — a vendor product that licenses are issued for (A/B/C/D…)."""

from __future__ import annotations

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuthorMixin, Base, JSONType, TimestampMixin, UUIDMixin

ALGS = ("ed25519", "rsa2048", "rsa4096", "sm2")


class Product(UUIDMixin, TimestampMixin, AuthorMixin, Base):
    __tablename__ = "products"

    slug: Mapped[str] = mapped_column(String(64), nullable=False)            # e.g. DIFY_ENTERPRISE
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    features_template: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)
    quotas_template: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    default_alg: Mapped[str] = mapped_column(String(16), nullable=False, default="ed25519")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
