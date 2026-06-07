"""Cryptography core — field-level encryption (AES-256-GCM, KEK/DEK) + Ed25519 signing.

Security model (security.md §4, licensing.md):
  * L5 secrets (signing private keys, 2FA secrets) are stored encrypted with a per-record
    DEK; the DEK is wrapped by the KEK. The KEK lives ONLY in env/KMS
    (FORGE_FIELD_ENCRYPTION_KEY), never in code/repo/log.
  * The Ed25519 signing private key is decrypted into memory ONLY inside the forge-api
    process at sign time; it is never logged, never returned, never sent to forge-edge.
"""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import serialization


# ---------------------------------------------------------------------------
# KEK / DEK envelope encryption for L5 secrets
# ---------------------------------------------------------------------------
def _load_kek(kek_b64: str) -> bytes:
    if not kek_b64:
        raise RuntimeError("FORGE_FIELD_ENCRYPTION_KEY is required to handle L5 secrets")
    kek = base64.b64decode(kek_b64)
    if len(kek) != 32:
        raise RuntimeError("FORGE_FIELD_ENCRYPTION_KEY must be base64 of exactly 32 bytes")
    return kek


def encrypt_secret(plaintext: bytes, kek_b64: str) -> tuple[str, str]:
    """Encrypt an L5 secret. Returns (ciphertext_b64, wrapped_dek_b64).

    A fresh 256-bit DEK is generated per record, used to AES-256-GCM the plaintext,
    then itself AES-256-GCM-wrapped by the KEK. Nonces are prepended to ciphertexts.
    """
    kek = _load_kek(kek_b64)
    dek = AESGCM.generate_key(bit_length=256)
    data_nonce = os.urandom(12)
    ciphertext = AESGCM(dek).encrypt(data_nonce, plaintext, None)
    dek_nonce = os.urandom(12)
    wrapped = AESGCM(kek).encrypt(dek_nonce, dek, None)
    return (
        base64.b64encode(data_nonce + ciphertext).decode(),
        base64.b64encode(dek_nonce + wrapped).decode(),
    )


def decrypt_secret(ciphertext_b64: str, wrapped_dek_b64: str, kek_b64: str) -> bytes:
    kek = _load_kek(kek_b64)
    wrapped = base64.b64decode(wrapped_dek_b64)
    dek = AESGCM(kek).decrypt(wrapped[:12], wrapped[12:], None)
    blob = base64.b64decode(ciphertext_b64)
    return AESGCM(dek).decrypt(blob[:12], blob[12:], None)


# ---------------------------------------------------------------------------
# Ed25519 signing (master signing key + edge lease key)
# ---------------------------------------------------------------------------
def generate_ed25519() -> tuple[bytes, bytes]:
    """Generate a new Ed25519 keypair. Returns (private_pem, public_pem)."""
    priv = Ed25519PrivateKey.generate()
    private_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


def sign_ed25519(private_pem: bytes, message: bytes) -> bytes:
    priv = serialization.load_pem_private_key(private_pem, password=None)
    assert isinstance(priv, Ed25519PrivateKey)
    return priv.sign(message)


def verify_ed25519(public_pem: bytes, message: bytes, signature: bytes) -> bool:
    pub = serialization.load_pem_public_key(public_pem)
    assert isinstance(pub, Ed25519PublicKey)
    try:
        pub.verify(signature, message)
        return True
    except Exception:
        return False
