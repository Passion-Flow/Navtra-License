"""user self-service avatar column

Revision ID: 000004
Revises: 000003
Create Date: 2026-06-08
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "000004"
down_revision = "000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar")
