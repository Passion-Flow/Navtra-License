"""Online validation service (forge-edge). Activate / re-validate online licenses.

forge-edge holds NO master signing key. Leases are signed with the lower-stakes edge_lease
key (a compromised lease key can only forge leases for already-activated licenses, not mint
new licenses). Online security = phone-home + first-activation hardware bind + seat tracking
(anti-copy) + lease+grace (network resilience) + instant server-side revocation.
"""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import json
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.cache.base import get_cache_adapter
from app.core import crypto
from app.core.errors import BizError
from app.licensing import forge_file
from app.licensing.keys import KeyManager
from app.models.binding import FingerprintBinding, Lease
from app.models.revocation import Revocation
from app.repositories.license import LicenseRepository
from app.services.audit_service import AuditService
from app.settings import get_settings


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


class EdgeService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()
        self.licenses = LicenseRepository(db)
        self.keys = KeyManager(db)
        self.audit = AuditService(db)
        self.redis = get_cache_adapter(self.settings).client(self.settings.CACHE_DB_APP)
        self.lock_redis = get_cache_adapter(self.settings).client(self.settings.CACHE_DB_LOCK)

    async def _check_revoked(self, license_db_id) -> None:  # noqa: ANN001
        row = (await self.db.execute(
            select(Revocation).where(Revocation.license_id == license_db_id)
        )).scalar_one_or_none()
        if row:
            raise BizError("LICENSE_REVOKED")

    def _assert_valid_window(self, lic) -> None:  # noqa: ANN001
        # A soft-deleted license is treated as revoked: deleting a license in the admin must
        # immediately invalidate online leases (the next validate renewal locks), not merely
        # block fresh activations. Without this, a deleted-but-not-revoked license keeps
        # renewing leases until grace expiry — the product stays unlocked after deletion.
        if getattr(lic, "deleted_at", None) is not None:
            raise BizError("LICENSE_REVOKED")
        if lic.status == "revoked":
            raise BizError("LICENSE_REVOKED")
        if lic.active_until and _now() >= lic.active_until.astimezone(datetime.timezone.utc):
            raise BizError("LICENSE_EXPIRED")

    async def _mint_lease(self, lic, binding) -> dict:  # noqa: ANN001
        """Issue a signed lease token + opaque validation_token; cache hot state in Redis."""
        now = _now()
        expires = now + datetime.timedelta(seconds=self.settings.LEASE_TTL_SECONDS)
        grace = expires + datetime.timedelta(seconds=self.settings.LEASE_GRACE_SECONDS)
        validation_token = secrets.token_urlsafe(32)

        lease_payload = {
            "license_id": str(lic.license_id), "fingerprint": binding.fingerprint,
            "features": lic.features, "quotas": lic.quotas,
            "active_until": lic.active_until.astimezone(datetime.timezone.utc).isoformat() if lic.active_until else None,
            "lease_expires_at": expires.isoformat(), "grace_until": grace.isoformat(),
            "issued_at": now.isoformat(), "kind": "lease",
        }
        edge_key = await self.keys.require_active("edge_lease")
        sig = crypto.sign_ed25519(self.keys.decrypt_private(edge_key),
                                  forge_file.canonical_payload_bytes(lease_payload))
        lease_token = forge_file.build_forge_blob(lease_payload, sig)

        th = _sha(validation_token)
        self.db.add(Lease(license_id=lic.id, binding_id=binding.id, token_hash=th,
                          expires_at=expires, grace_until=grace))
        binding.last_seen_at = now
        binding.lease_expires_at = expires
        await self.redis.set(
            f"forge:lease:{th}",
            json.dumps({"license_db_id": str(lic.id), "binding_id": str(binding.id),
                        "fingerprint": binding.fingerprint}),
            ex=self.settings.LEASE_TTL_SECONDS + self.settings.LEASE_GRACE_SECONDS,
        )
        return {
            "validation_token": validation_token, "lease_token": lease_token,
            "lease": {"expires_at": expires.isoformat(), "grace_until": grace.isoformat()},
            "license": {"features": lic.features, "quotas": lic.quotas,
                        "active_until": lease_payload["active_until"]},
        }

    async def activate(self, online_code: str, fingerprint: str, cluster_id: str | None, ctx: dict) -> dict:
        lic = await self.licenses.get_by_online_code(online_code)
        if not lic or lic.mode != "online":
            raise BizError("RESOURCE_NOT_FOUND", {"resource": "online_code"})
        self._assert_valid_window(lic)
        await self._check_revoked(lic.id)

        # serialize seat accounting per license (anti-copy). FAIL-CLOSED: if the lock can't be
        # acquired (a concurrent activation holds it), retry briefly then REJECT — never proceed
        # un-serialized, or N concurrent activations would each read seat_used<limit and all insert.
        lock_key = f"forge:lock:seat:{lic.id}"
        got = None
        for _ in range(50):  # ~5s max
            got = await self.lock_redis.set(lock_key, "1", nx=True, ex=10)
            if got:
                break
            await asyncio.sleep(0.1)
        if not got:
            raise BizError("LICENSE_SEAT_LOCK_BUSY")
        try:
            existing = (await self.db.execute(
                select(FingerprintBinding).where(
                    FingerprintBinding.license_id == lic.id,
                    FingerprintBinding.fingerprint == fingerprint,
                    FingerprintBinding.deleted_at.is_(None))
            )).scalar_one_or_none()
            if existing is None:
                active_count = len((await self.db.execute(
                    select(FingerprintBinding).where(
                        FingerprintBinding.license_id == lic.id,
                        FingerprintBinding.status == "active",
                        FingerprintBinding.deleted_at.is_(None))
                )).scalars().all())
                if active_count >= lic.seat_limit:
                    self.audit.log(action="license.seat_exceeded", result="failure",
                                   resource_type="license", resource_id=str(lic.license_id),
                                   reason="LICENSE_SEAT_EXCEEDED",
                                   metadata={"attempted_fingerprint": fingerprint[:8] + "…"}, **ctx)
                    await self.db.commit()
                    raise BizError("LICENSE_SEAT_EXCEEDED")
                existing = FingerprintBinding(license_id=lic.id, fingerprint=fingerprint,
                                              cluster_id=cluster_id, status="active")
                self.db.add(existing)
                lic.seat_used += 1
                if lic.status == "issued":
                    lic.status = "active"
                    lic.activated_at = _now()
                await self.db.flush()
        finally:
            if got:
                await self.lock_redis.delete(lock_key)

        result = await self._mint_lease(lic, existing)
        self.audit.log(action="license.activated", result="success",
                       resource_type="license", resource_id=str(lic.license_id),
                       metadata={"fingerprint": fingerprint[:8] + "…", "cluster_id": cluster_id}, **ctx)
        await self.db.commit()
        return result

    async def validate(self, validation_token: str, fingerprint: str, ctx: dict) -> dict:
        th = _sha(validation_token)
        cached = await self.redis.get(f"forge:lease:{th}")
        lease_row = (await self.db.execute(
            select(Lease).where(Lease.token_hash == th, Lease.revoked.is_(False))
        )).scalar_one_or_none()
        if not cached and not lease_row:
            raise BizError("LICENSE_LEASE_EXPIRED")
        binding_id = json.loads(cached)["binding_id"] if cached else str(lease_row.binding_id)
        binding = (await self.db.execute(
            select(FingerprintBinding).where(FingerprintBinding.id == binding_id)
        )).scalar_one_or_none()
        if not binding or binding.fingerprint != fingerprint or binding.status != "active":
            raise BizError("LICENSE_BINDING_MISMATCH")
        # include_deleted: load even a soft-deleted license so _assert_valid_window can lock it
        # (LICENSE_REVOKED). Without include_deleted, get() returns None for deleted licenses and
        # the renewal would crash instead of cleanly locking the client.
        lic = await self.licenses.get(binding.license_id, include_deleted=True)
        if lic is None:
            raise BizError("LICENSE_REVOKED")
        self._assert_valid_window(lic)
        await self._check_revoked(lic.id)
        return await self._mint_lease(lic, binding)   # renew (rotates validation_token)
