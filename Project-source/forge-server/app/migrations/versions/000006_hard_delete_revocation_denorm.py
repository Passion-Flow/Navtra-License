"""hard-delete support: denormalize public id+mode into revocations, FK RESTRICT -> SET NULL

Revision ID: 000006
Revises: 000005
Create Date: 2026-06-12

Licenses become HARD-deletable (bindings/leases/clone_alerts cascade). A revocation must outlive
its license so the CRL keeps listing it (offline clients keep rejecting it) — so we denormalize the
public license_id + mode onto the revocation and switch its FK to ON DELETE SET NULL.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "000006"
down_revision = "000005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("revocations", sa.Column("license_public_id", sa.String(64), nullable=True))
    op.add_column("revocations", sa.Column("mode", sa.String(12), nullable=True))
    # backfill from the still-present license rows
    op.execute("""
        UPDATE revocations r
           SET license_public_id = l.license_id::text,
               mode = l.mode
          FROM licenses l
         WHERE l.id = r.license_id
    """)
    # FK RESTRICT -> SET NULL, and allow license_id to be null
    op.alter_column("revocations", "license_id", existing_type=sa.Uuid(), nullable=True)
    op.drop_constraint("revocations_license_id_fkey", "revocations", type_="foreignkey")
    op.create_foreign_key("revocations_license_id_fkey", "revocations", "licenses",
                          ["license_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("revocations_license_id_fkey", "revocations", type_="foreignkey")
    op.create_foreign_key("revocations_license_id_fkey", "revocations", "licenses",
                          ["license_id"], ["id"], ondelete="RESTRICT")
    op.alter_column("revocations", "license_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_column("revocations", "mode")
    op.drop_column("revocations", "license_public_id")
