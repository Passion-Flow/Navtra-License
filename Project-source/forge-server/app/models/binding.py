"""Online seat / hardware binding + lease ORM models.

FingerprintBinding tracks every distinct hardware fingerprint that activated an online
license (seat anti-copy). Lease is persisted for audit; the hot lease state lives in Redis.
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuthorMixin, Base, JSONType, TimestampMixin, UUIDMixin

BINDING_STATUSES = ("active", "released", "blocked", "dead")


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
    # ── 反克隆身份升级（design 07）：全部 nullable，旧绑定容忍 null（按旧单指纹逻辑放行）──
    install_id: Mapped[str | None] = mapped_column(String(64), nullable=True)        # 首激活随机 id（与指纹双锁）
    signals: Mapped[dict | None] = mapped_column(JSONType, nullable=True)            # 多信号向量 {signal: sha256}
    deployment_uid: Mapped[str | None] = mapped_column(String(128), nullable=True)   # 容器/集群注入的权威身份
    last_heartbeat_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CloneAlert(UUIDMixin, TimestampMixin, AuthorMixin, Base):
    """同一 License 出现超 seat 的不同在线身份 → 克隆/共享告警（design 07 §4.2）。"""

    __tablename__ = "clone_alerts"

    license_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("licenses.id", ondelete="CASCADE"))
    detected_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    alive_identities: Mapped[int] = mapped_column(Integer, nullable=False)
    seat_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    sample: Mapped[dict | None] = mapped_column(JSONType, nullable=True)             # 指纹摘要+ip 抽样
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="open")  # open/ack/resolved


class Lease(UUIDMixin, TimestampMixin, AuthorMixin, Base):
    __tablename__ = "leases"

    license_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("licenses.id", ondelete="CASCADE"))
    binding_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fingerprint_bindings.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)        # sha256 of validation_token
    issued_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    grace_until: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
