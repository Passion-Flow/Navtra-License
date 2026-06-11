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
from app.models.binding import CloneAlert, FingerprintBinding, Lease
from app.models.revocation import Revocation
from app.repositories.license import LicenseRepository
from app.services.audit_service import AuditService
from app.settings import get_settings


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


_FUZZY_MIN = 2  # 信号向量命中 ≥ 此数 → 判为同机硬件漂移（换盘/换网卡），复用既有 binding 不新占 seat


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

    async def _active_bindings(self, license_db_id) -> list:  # noqa: ANN001
        return list((await self.db.execute(
            select(FingerprintBinding).where(
                FingerprintBinding.license_id == license_db_id,
                FingerprintBinding.status == "active",
                FingerprintBinding.deleted_at.is_(None))
        )).scalars().all())

    def _match_binding(self, bindings, fingerprint, deployment_uid, signals):  # noqa: ANN001
        """身份匹配（design 07）：deployment_uid 优先（容器/集群权威身份）；否则指纹精确；
        都不中再用多信号模糊匹配（同机换盘/换网卡漂移）→ 复用既有 binding，不新占 seat。"""
        if deployment_uid:
            for b in bindings:
                if b.deployment_uid == deployment_uid:
                    return b
            return None
        for b in bindings:
            if b.deployment_uid is None and b.fingerprint == fingerprint:
                return b
        if signals:
            for b in bindings:
                if b.deployment_uid is None and b.signals:
                    overlap = sum(1 for k, v in signals.items() if b.signals.get(k) == v)
                    if overlap >= _FUZZY_MIN:
                        return b
        return None

    async def activate(self, online_code: str, fingerprint: str, cluster_id: str | None, ctx: dict,
                       *, install_id: str | None = None, signals: dict | None = None,
                       deployment_uid: str | None = None) -> dict:
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
            bindings = await self._active_bindings(lic.id)
            existing = self._match_binding(bindings, fingerprint, deployment_uid, signals)
            if existing is not None:
                # install_id 双锁：激活介质被复制到"重新生成了不同 install_id"的装机 → 拒（反克隆）。
                # 旧绑定 install_id 为 null（升级前）则容忍并回填；旧 SDK 不发 install_id 也容忍。
                if existing.install_id and install_id and existing.install_id != install_id:
                    self.audit.log(action="license.install_id_mismatch", result="failure",
                                   resource_type="license", resource_id=str(lic.license_id),
                                   reason="INSTALL_ID_MISMATCH", **ctx)
                    await self.db.commit()
                    raise BizError("LICENSE_BINDING_MISMATCH")
                existing.install_id = existing.install_id or install_id
                existing.signals = signals or existing.signals
                existing.deployment_uid = deployment_uid or existing.deployment_uid
                existing.fingerprint = fingerprint
                existing.last_heartbeat_at = _now()
            else:
                active_count = len(bindings)
                if active_count >= lic.seat_limit:
                    # 超 seat 的新身份 = 疑似克隆/共享 → 告警 + 拒新（决策：告警+超seat拒新）
                    self.db.add(CloneAlert(
                        license_id=lic.id, alive_identities=active_count + 1,
                        seat_limit=lic.seat_limit,
                        sample={"attempted_fingerprint": fingerprint[:12],
                                "deployment_uid": deployment_uid, "ip": ctx.get("ip")}))
                    self.audit.log(action="license.seat_exceeded", result="failure",
                                   resource_type="license", resource_id=str(lic.license_id),
                                   reason="LICENSE_SEAT_EXCEEDED",
                                   metadata={"attempted_fingerprint": fingerprint[:8] + "…"}, **ctx)
                    await self.db.commit()
                    raise BizError("LICENSE_SEAT_EXCEEDED")
                existing = FingerprintBinding(
                    license_id=lic.id, fingerprint=fingerprint, cluster_id=cluster_id,
                    status="active", install_id=install_id, signals=signals,
                    deployment_uid=deployment_uid, last_heartbeat_at=_now())
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
                       metadata={"fingerprint": fingerprint[:8] + "…", "cluster_id": cluster_id,
                                 "deployment_uid": deployment_uid}, **ctx)
        await self.db.commit()
        return result

    async def validate(self, validation_token: str, fingerprint: str, ctx: dict,
                       *, install_id: str | None = None) -> dict:
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
        if not binding or binding.status != "active":
            raise BizError("LICENSE_BINDING_MISMATCH")
        # 身份校验：硬件绑定要求指纹相等（防拷贝）；deployment_uid 绑定（容器/集群）不钉硬件指纹
        # ——多 pod 指纹各异，validation_token 的持有即身份证明。
        if binding.deployment_uid is None and binding.fingerprint != fingerprint:
            raise BizError("LICENSE_BINDING_MISMATCH")
        # install_id 双锁：lease+token 被复制到 install_id 不同的装机 → 拒（旧绑定/旧 SDK 容忍 null）
        if binding.install_id and install_id and binding.install_id != install_id:
            raise BizError("LICENSE_BINDING_MISMATCH")
        binding.last_heartbeat_at = _now()
        # include_deleted: load even a soft-deleted license so _assert_valid_window can lock it
        # (LICENSE_REVOKED). Without include_deleted, get() returns None for deleted licenses and
        # the renewal would crash instead of cleanly locking the client.
        lic = await self.licenses.get(binding.license_id, include_deleted=True)
        if lic is None:
            raise BizError("LICENSE_REVOKED")
        self._assert_valid_window(lic)
        await self._check_revoked(lic.id)
        return await self._mint_lease(lic, binding)   # renew (rotates validation_token)
