"""audit_log create table (append-only)

Revision ID: 000002
Revises: 000001
Create Date: 2026-06-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "000002"
down_revision = "000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("actor_type", sa.String(12), nullable=False),
        sa.Column("actor_id", sa.String(128), nullable=True),
        sa.Column("actor_name", sa.String(255), nullable=True),
        sa.Column("action", sa.String(48), nullable=False),
        sa.Column("resource_type", sa.String(32), nullable=True),
        sa.Column("resource_id", sa.String(128), nullable=True),
        sa.Column("result", sa.String(8), nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("metadata", sa.JSON, nullable=False),
        sa.CheckConstraint("actor_type IN ('user','system','api_key','cli')", name="ck_audit_actor_type"),
        sa.CheckConstraint("result IN ('success','failure')", name="ck_audit_result"),
    )
    op.create_index("idx_audit_timestamp", "audit_log", ["timestamp"])
    op.create_index("idx_audit_actor", "audit_log", ["actor_id", "timestamp"])
    op.create_index("idx_audit_resource", "audit_log", ["resource_type", "resource_id", "timestamp"])


def downgrade() -> None:
    op.drop_index("idx_audit_resource", table_name="audit_log")
    op.drop_index("idx_audit_actor", table_name="audit_log")
    op.drop_index("idx_audit_timestamp", table_name="audit_log")
    op.drop_table("audit_log")
