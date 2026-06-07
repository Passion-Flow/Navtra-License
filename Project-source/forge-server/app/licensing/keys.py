"""Signing key management — master (offline .forge) + edge_lease (online leases).

The master Ed25519 private key signs offline licenses and lives ONLY in forge-api. The
edge_lease key signs short-lived online leases (lower stakes). Private keys are stored
AES-256-GCM encrypted (KEK from env); they are decrypted into memory only at sign time.
"""

from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.core.errors import BizError
from app.models.signing_key import SigningKey
from app.settings import get_settings


class KeyManager:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._settings = get_settings()

    def _kek_for(self, purpose: str) -> str:
        """Per-purpose KEK so a breached forge-edge (which only has FORGE_EDGE_KEK) cannot decrypt
        the master private key. master/2fa -> master KEK; edge_lease -> edge KEK (dev falls back)."""
        if purpose == "edge_lease":
            return self._settings.FORGE_EDGE_KEK or self._settings.FORGE_FIELD_ENCRYPTION_KEY
        return self._settings.FORGE_FIELD_ENCRYPTION_KEY

    @staticmethod
    def _key_id(alg: str, public_pem: bytes) -> str:
        return f"{alg}-{hashlib.sha256(public_pem).hexdigest()[:12]}"

    async def get_active(self, purpose: str) -> SigningKey | None:
        stmt = (
            select(SigningKey)
            .where(SigningKey.purpose == purpose, SigningKey.is_active.is_(True),
                   SigningKey.deleted_at.is_(None))
            .order_by(SigningKey.created_at.desc())
        )
        return (await self.db.execute(stmt)).scalars().first()

    async def require_active(self, purpose: str) -> SigningKey:
        key = await self.get_active(purpose)
        if not key:
            raise BizError("KEY_NOT_FOUND", {"purpose": purpose})
        return key

    async def ensure_keys(self) -> dict[str, str]:
        """Idempotently create the master + edge_lease Ed25519 keys. Returns key_ids."""
        out: dict[str, str] = {}
        for purpose in ("master", "edge_lease"):
            existing = await self.get_active(purpose)
            if existing:
                out[purpose] = existing.key_id
                continue
            private_pem, public_pem = crypto.generate_ed25519()
            ct, dek = crypto.encrypt_secret(private_pem, self._kek_for(purpose))
            key = SigningKey(
                key_id=self._key_id("ed25519", public_pem),
                alg="ed25519",
                public_key=public_pem.decode(),
                private_key_ciphertext=ct,
                dek_wrapped=dek,
                purpose=purpose,
                is_active=True,
            )
            self.db.add(key)
            out[purpose] = key.key_id
        return out

    def decrypt_private(self, key: SigningKey) -> bytes:
        return crypto.decrypt_secret(key.private_key_ciphertext, key.dek_wrapped, self._kek_for(key.purpose))

    async def sign(self, purpose: str, message: bytes) -> tuple[bytes, SigningKey]:
        key = await self.require_active(purpose)
        return crypto.sign_ed25519(self.decrypt_private(key), message), key
