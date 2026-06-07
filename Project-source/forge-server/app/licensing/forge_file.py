"""`.forge` offline license — compact self-contained signed token (JWS-like).

Format (v1):   <base64url(payload.json)>.<base64url(ed25519_signature)>

- payload.json is the canonical UTF-8 JSON of the business fields (the SIGNED bytes);
  it already carries `alg` and `issuer` (= signing key_id), so no separate metadata is
  needed — the verifier selects the embedded public key by `issuer`/`alg`.
- The signature is a detached Ed25519 signature over the exact payload bytes.

The Verifier SDKs (python/node/go) re-implement `parse_and_verify` identically: split on
".", base64url-decode the payload, verify the signature with the EMBEDDED public key, then
check business fields (expiry / hardware binding / CRL). Any byte change → signature fails.
This is compact (~hundreds of chars), matching the reference offline blob.
"""

from __future__ import annotations

import base64
import json

FORMAT = "forge-v1"


def _b64u_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64u_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def canonical_payload_bytes(payload: dict) -> bytes:
    """Deterministic encoding so the signed bytes are stable across signer + verifier."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def build_forge_blob(payload: dict, signature: bytes) -> str:
    return f"{_b64u_encode(canonical_payload_bytes(payload))}.{_b64u_encode(signature)}"


def parse_and_verify(blob: str, public_pem: bytes) -> tuple[bool, dict]:
    """Return (signature_valid, payload). Raises ValueError on malformed input."""
    from app.core import crypto

    parts = blob.strip().split(".")
    if len(parts) != 2:
        raise ValueError("malformed .forge token")
    payload_bytes = _b64u_decode(parts[0])
    signature = _b64u_decode(parts[1])
    payload = json.loads(payload_bytes)
    valid = crypto.verify_ed25519(public_pem, payload_bytes, signature)
    return valid, payload
