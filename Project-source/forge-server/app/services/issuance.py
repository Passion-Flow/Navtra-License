"""License issuance service — online (short code) + offline (signed .forge) + revoke."""

from __future__ import annotations

import datetime
import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BizError

# A valid deployment ID is the SHA-256 hex hardware fingerprint emitted by the Verifier SDK
# (machine-id / IOPlatformUUID / MachineGuid → sha256 hexdigest): 64 lowercase hex chars.
_FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")
from app.licensing import forge_file, payload as payload_mod
from app.licensing.keys import KeyManager
from app.models.license import License
from app.models.revocation import Revocation
from app.repositories.license import (
    CustomerRepository, LicenseRepository, ProductRepository, RevocationRepository,
)
from app.services.audit_service import AuditService


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _uuid(value: str, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        raise BizError("VALIDATION_FAILED", {"field": field})


class IssuanceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.products = ProductRepository(db)
        self.customers = CustomerRepository(db)
        self.licenses = LicenseRepository(db)
        self.revocations = RevocationRepository(db)
        self.keys = KeyManager(db)
        self.audit = AuditService(db)

    async def _resolve(self, customer_id: str, product_id: str):
        customer = await self.customers.get(_uuid(customer_id, "customer_id"))
        product = await self.products.get(_uuid(product_id, "product_id"))
        if not customer or not product:
            raise BizError("RESOURCE_NOT_FOUND", {"resource": "customer_or_product"})
        if not product.is_active:
            raise BizError("ISSUE_PRODUCT_INACTIVE")
        return customer, product

    async def issue_online(self, req, *, actor_id: str | None, ctx: dict) -> License:
        customer, product = await self._resolve(req.customer_id, req.product_id)
        master = await self.keys.require_active("master")
        now = _now()
        lic = License(
            customer_id=customer.id, product_id=product.id, signing_key_id=master.id,
            mode="online", online_code=str(uuid.uuid4()),
            term_preset=req.term_preset, active_from=now,
            active_until=payload_mod.compute_active_until(req.term_preset, now, "online"),
            subscription=req.subscription, quotas=req.quotas, features=req.features,
            binding="hard", seat_limit=req.seat_limit, seat_used=0,
            status="issued", alg="ed25519", issued_by=_uuid(actor_id, "actor") if actor_id else None,
            issued_at=now,
        )
        self.db.add(lic)
        await self.db.flush()
        self.audit.log(action="license.issue_online", result="success", actor_id=actor_id,
                       resource_type="license", resource_id=str(lic.license_id),
                       metadata={"product": product.slug, "customer": customer.name,
                                 "seat_limit": req.seat_limit, "term": req.term_preset}, **ctx)
        await self.db.commit()
        return lic

    async def issue_offline(self, req, *, actor_id: str | None, ctx: dict) -> License:
        # The deployment ID must be a real SHA-256 hardware fingerprint, not an arbitrary
        # string — otherwise we'd sign a license bound to nothing meaningful.
        if not _FINGERPRINT_RE.match(req.deployment_id or ""):
            raise BizError("ISSUE_DEPLOYMENT_ID_INVALID")
        customer, product = await self._resolve(req.customer_id, req.product_id)
        master = await self.keys.require_active("master")
        now = _now()
        lic = License(
            customer_id=customer.id, product_id=product.id, signing_key_id=master.id,
            mode="offline", bound_fingerprint=req.deployment_id, cluster_id=req.cluster_id,
            term_preset=req.term_preset, active_from=now,
            active_until=payload_mod.compute_active_until(req.term_preset, now, "offline"),
            subscription=req.subscription, quotas=req.quotas, features=req.features,
            binding="hard", seat_limit=1, seat_used=1,
            status="active", alg="ed25519", issued_by=_uuid(actor_id, "actor") if actor_id else None,
            issued_at=now,
        )
        self.db.add(lic)
        await self.db.flush()  # populate id / license_id before signing
        # sign the canonical payload with the master private key -> compact .forge blob
        payload = payload_mod.build_payload(
            license_obj=lic, customer=customer, product=product, issuer_key_id=master.key_id
        )
        signature = self.keys.decrypt_private(master)
        from app.core import crypto
        sig = crypto.sign_ed25519(signature, forge_file.canonical_payload_bytes(payload))
        lic.offline_blob = forge_file.build_forge_blob(payload, sig)
        self.audit.log(action="license.issue_offline", result="success", actor_id=actor_id,
                       resource_type="license", resource_id=str(lic.license_id),
                       metadata={"product": product.slug, "customer": customer.name,
                                 "term": req.term_preset, "fingerprint": req.deployment_id[:8] + "…"}, **ctx)
        await self.db.commit()
        return lic

    async def revoke(self, license_db_id: str, reason: str, *, actor_id: str | None, ctx: dict) -> License:
        lic = await self.licenses.get(_uuid(license_db_id, "id"))
        if not lic:
            raise BizError("RESOURCE_NOT_FOUND", {"resource": "license"})
        if lic.status == "revoked":
            return lic
        lic.status = "revoked"
        lic.revoked_at = _now()
        lic.revoke_reason = reason
        if not await self.revocations.get_by_license(lic.id):
            # denormalize public id + mode so the CRL survives a later license hard-delete
            self.db.add(Revocation(license_id=lic.id, reason=reason,
                                   license_public_id=str(lic.license_id), mode=lic.mode))
        self.audit.log(action="license.revoke", result="success", actor_id=actor_id,
                       resource_type="license", resource_id=str(lic.license_id),
                       reason=reason or None, **ctx)
        await self.db.commit()
        return lic
