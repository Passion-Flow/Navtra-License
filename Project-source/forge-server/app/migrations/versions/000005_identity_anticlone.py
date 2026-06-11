"""device identity / anti-clone: binding signals+install_id+deployment_uid+heartbeat, clone_alerts

Revision ID: 000005
Revises: 000004
Create Date: 2026-06-12

All additive & nullable — existing single-fingerprint bindings keep working (validate tolerates
null install_id/signals; next activate backfills). design 07-identity-anticlone.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

revision = "000005"
down_revision = "000004"
branch_labels = None
depends_on = None

_JSON = JSONB().with_variant(JSON(), "mysql", "oracle")


def upgrade() -> None:
    op.add_column("fingerprint_bindings", sa.Column("install_id", sa.String(64), nullable=True))
    op.add_column("fingerprint_bindings", sa.Column("signals", _JSON, nullable=True))
    op.add_column("fingerprint_bindings", sa.Column("deployment_uid", sa.String(128), nullable=True))
    op.add_column("fingerprint_bindings", sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "clone_alerts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("license_id", sa.Uuid(), sa.ForeignKey("licenses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("alive_identities", sa.Integer(), nullable=False),
        sa.Column("seat_limit", sa.Integer(), nullable=False),
        sa.Column("sample", _JSON, nullable=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
    )
    op.create_index("ix_clone_alerts_license", "clone_alerts", ["license_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_clone_alerts_license", table_name="clone_alerts")
    op.drop_table("clone_alerts")
    op.drop_column("fingerprint_bindings", "last_heartbeat_at")
    op.drop_column("fingerprint_bindings", "deployment_uid")
    op.drop_column("fingerprint_bindings", "signals")
    op.drop_column("fingerprint_bindings", "install_id")
