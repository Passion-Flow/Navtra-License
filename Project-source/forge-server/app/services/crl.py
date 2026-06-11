"""CRL service — signed certificate revocation list for OFFLINE licenses.

Offline licenses can't phone home, so a revoked offline license is published in a CRL signed
with the master key. The product imports the CRL, verifies it with the embedded master public
key, and treats listed license_ids as revoked. (Online revocation is enforced live at the edge.)
"""

from __future__ import annotations

import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.licensing import forge_file
from app.licensing.keys import KeyManager
from app.models.license import License
from app.models.revocation import CrlBundle, Revocation
from app.services.audit_service import AuditService


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class CrlService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.keys = KeyManager(db)
        self.audit = AuditService(db)

    async def _latest_bundle(self) -> CrlBundle | None:
        return (await self.db.execute(
            select(CrlBundle).where(CrlBundle.deleted_at.is_(None)).order_by(CrlBundle.version.desc())
        )).scalars().first()

    async def get_latest_blob(self) -> str | None:
        bundle = await self._latest_bundle()
        return bundle.signed_blob if bundle else None

    async def generate(self, *, actor_id: str | None, ctx: dict) -> CrlBundle:
        # all revoked OFFLINE licenses (by public license_id)
        rows = (await self.db.execute(
            select(License.license_id).join(Revocation, Revocation.license_id == License.id)
            .where(License.mode == "offline")
        )).scalars().all()
        revoked_ids = sorted(str(x) for x in rows)

        latest = await self._latest_bundle()
        version = (latest.version + 1) if latest else 1
        now = _now()
        payload = {"kind": "crl", "version": version, "generated_at": now.isoformat(),
                   "revoked": revoked_ids, "alg": "ed25519"}
        sig, master = await self.keys.sign("master", forge_file.canonical_payload_bytes(payload))
        blob = forge_file.build_forge_blob(payload, sig)

        bundle = CrlBundle(version=version, signed_blob=blob, entry_count=len(revoked_ids))
        self.db.add(bundle)
        # stamp the version onto revocations that are now published
        for rev in (await self.db.execute(
            select(Revocation).join(License, Revocation.license_id == License.id)
            .where(License.mode == "offline", Revocation.crl_version.is_(None))
        )).scalars().all():
            rev.crl_version = version
        self.audit.log(action="crl.generate", result="success", actor_id=actor_id,
                       resource_type="crl", resource_id=str(version),
                       metadata={"entry_count": len(revoked_ids)}, **ctx)
        await self.db.commit()
        return bundle
