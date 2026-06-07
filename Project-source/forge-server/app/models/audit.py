"""Audit log ORM model — append-only (HARD RULE: audit-log.md).

No deleted_at, no updated_at: rows are immutable once written. Business code only ever
INSERTs via AuditService; the forge_app DB role is granted INSERT only on this table.
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import uuid7
from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    actor_type: Mapped[str] = mapped_column(String(12), nullable=False)   # user/system/api_key/cli
    actor_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    actor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(48), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    result: Mapped[str] = mapped_column(String(8), nullable=False)        # success/failure
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)  # error code on failure
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # JSONB on postgres; JSON on mysql/oracle/tidb (portable across the 4 providers).
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB().with_variant(JSON(), "mysql", "oracle"), nullable=False, default=dict
    )
