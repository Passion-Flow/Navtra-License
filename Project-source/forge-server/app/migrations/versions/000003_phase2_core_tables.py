"""phase2 core tables: products, customers, signing_keys, licenses, bindings, leases, revocations, crl

Revision ID: 000003
Revises: 000002
Create Date: 2026-06-06
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "000003"
down_revision = "000002"
branch_labels = None
depends_on = None

_NOW = sa.text("CURRENT_TIMESTAMP")


def _base_cols() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=_NOW),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("updated_by", sa.Uuid(as_uuid=True), nullable=True),
    ]


def upgrade() -> None:
    is_pg = op.get_bind().dialect.name == "postgresql"

    op.create_table(
        "customers",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("contact_name", sa.String(128), nullable=True),
        sa.Column("contact_email", sa.String(320), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        *_base_cols(),
    )
    op.create_index("idx_customers_name", "customers", ["name"])

    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("features_template", sa.JSON, nullable=False),
        sa.Column("quotas_template", sa.JSON, nullable=False),
        sa.Column("default_alg", sa.String(16), nullable=False, server_default="ed25519"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        *_base_cols(),
        sa.CheckConstraint("default_alg IN ('ed25519','rsa2048','rsa4096','sm2')", name="ck_products_alg"),
    )
    if is_pg:
        op.create_index("uq_products_slug", "products", ["slug"], unique=True,
                        postgresql_where=sa.text("deleted_at IS NULL"))
    else:
        op.create_index("uq_products_slug", "products", ["slug"], unique=True)

    op.create_table(
        "signing_keys",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("key_id", sa.String(64), nullable=False),
        sa.Column("alg", sa.String(16), nullable=False, server_default="ed25519"),
        sa.Column("public_key", sa.Text, nullable=False),
        sa.Column("private_key_ciphertext", sa.Text, nullable=False),
        sa.Column("dek_wrapped", sa.Text, nullable=False),
        sa.Column("purpose", sa.String(16), nullable=False, server_default="master"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        *_base_cols(),
        sa.CheckConstraint("purpose IN ('master','edge_lease')", name="ck_signing_keys_purpose"),
        sa.UniqueConstraint("key_id", name="uq_signing_keys_key_id"),
    )

    op.create_table(
        "licenses",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("license_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("customer_id", sa.Uuid(as_uuid=True), sa.ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("product_id", sa.Uuid(as_uuid=True), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("signing_key_id", sa.Uuid(as_uuid=True), sa.ForeignKey("signing_keys.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("mode", sa.String(8), nullable=False),
        sa.Column("online_code", sa.String(64), nullable=True),
        sa.Column("offline_blob", sa.Text, nullable=True),
        sa.Column("term_preset", sa.String(16), nullable=False),
        sa.Column("active_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("subscription", sa.String(32), nullable=False, server_default="Enterprise"),
        sa.Column("quotas", sa.JSON, nullable=False),
        sa.Column("features", sa.JSON, nullable=False),
        sa.Column("scope", sa.String(24), nullable=False, server_default="customer_x_product"),
        sa.Column("binding", sa.String(8), nullable=False, server_default="hard"),
        sa.Column("bound_fingerprint", sa.String(128), nullable=True),
        sa.Column("cluster_id", sa.String(128), nullable=True),
        sa.Column("seat_limit", sa.Integer, nullable=False, server_default="1"),
        sa.Column("seat_used", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(12), nullable=False, server_default="issued"),
        sa.Column("alg", sa.String(16), nullable=False, server_default="ed25519"),
        sa.Column("issued_by", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False, server_default=_NOW),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(255), nullable=True),
        *_base_cols(),
        sa.CheckConstraint("mode IN ('online','offline')", name="ck_licenses_mode"),
        sa.CheckConstraint("term_preset IN ('1m','3m','6m','1y','3y','5y','perpetual')", name="ck_licenses_term"),
        sa.CheckConstraint("binding IN ('none','soft','hard')", name="ck_licenses_binding"),
        sa.CheckConstraint("status IN ('issued','active','expiring','expired','revoked','locked')", name="ck_licenses_status"),
        sa.CheckConstraint("seat_limit >= 1 AND seat_used >= 0", name="ck_licenses_seats"),
        sa.UniqueConstraint("license_id", name="uq_licenses_license_id"),
    )
    op.create_index("idx_licenses_customer_product", "licenses", ["customer_id", "product_id"])
    op.create_index("idx_licenses_status_active_until", "licenses", ["status", "active_until"])
    if is_pg:
        op.create_index("uq_licenses_online_code", "licenses", ["online_code"], unique=True,
                        postgresql_where=sa.text("online_code IS NOT NULL AND deleted_at IS NULL"))
    else:
        op.create_index("idx_licenses_online_code", "licenses", ["online_code"])

    op.create_table(
        "fingerprint_bindings",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("license_id", sa.Uuid(as_uuid=True), sa.ForeignKey("licenses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fingerprint", sa.String(128), nullable=False),
        sa.Column("cluster_id", sa.String(128), nullable=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="active"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=_NOW),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=_NOW),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        *_base_cols(),
        sa.CheckConstraint("status IN ('active','released','blocked')", name="ck_binding_status"),
    )
    op.create_index("idx_binding_license", "fingerprint_bindings", ["license_id"])
    if is_pg:
        op.create_index("uq_binding_license_fp", "fingerprint_bindings", ["license_id", "fingerprint"],
                        unique=True, postgresql_where=sa.text("deleted_at IS NULL"))
    else:
        op.create_index("uq_binding_license_fp", "fingerprint_bindings", ["license_id", "fingerprint"], unique=True)

    op.create_table(
        "leases",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("license_id", sa.Uuid(as_uuid=True), sa.ForeignKey("licenses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("binding_id", sa.Uuid(as_uuid=True), sa.ForeignKey("fingerprint_bindings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False, server_default=_NOW),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("grace_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean, nullable=False, server_default=sa.false()),
        *_base_cols(),
    )
    op.create_index("idx_leases_license", "leases", ["license_id"])
    op.create_index("idx_leases_expires", "leases", ["expires_at"])

    op.create_table(
        "revocations",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("license_id", sa.Uuid(as_uuid=True), sa.ForeignKey("licenses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=False, server_default=_NOW),
        sa.Column("crl_version", sa.Integer, nullable=True),
        *_base_cols(),
        sa.UniqueConstraint("license_id", name="uq_revocations_license"),
    )

    op.create_table(
        "crl_bundles",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("signed_blob", sa.Text, nullable=False),
        sa.Column("entry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=_NOW),
        *_base_cols(),
        sa.UniqueConstraint("version", name="uq_crl_version"),
    )


def downgrade() -> None:
    for tbl in ("crl_bundles", "revocations", "leases", "fingerprint_bindings",
                "licenses", "signing_keys", "products", "customers"):
        op.drop_table(tbl)
