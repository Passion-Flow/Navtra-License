"""Unit tests for the crypto core — no DB/Redis needed."""

import base64
import os

import pytest

from app.core import crypto


def _kek() -> str:
    return base64.b64encode(os.urandom(32)).decode()


def test_kek_dek_roundtrip():
    kek = _kek()
    secret = b"this-is-a-signing-private-key"
    ct, wrapped = crypto.encrypt_secret(secret, kek)
    assert ct != base64.b64encode(secret).decode()  # actually encrypted
    assert crypto.decrypt_secret(ct, wrapped, kek) == secret


def test_decrypt_with_wrong_kek_fails():
    ct, wrapped = crypto.encrypt_secret(b"x", _kek())
    with pytest.raises(Exception):
        crypto.decrypt_secret(ct, wrapped, _kek())  # different KEK


def test_kek_must_be_32_bytes():
    with pytest.raises(RuntimeError):
        crypto.encrypt_secret(b"x", base64.b64encode(os.urandom(16)).decode())


def test_ed25519_sign_verify_and_tamper():
    priv, pub = crypto.generate_ed25519()
    msg = b'{"license_id":"abc","exp":"2027"}'
    sig = crypto.sign_ed25519(priv, msg)
    assert crypto.verify_ed25519(pub, msg, sig) is True
    # tampering the payload invalidates the signature
    assert crypto.verify_ed25519(pub, msg + b"!", sig) is False
    # a different keypair cannot verify
    _, other_pub = crypto.generate_ed25519()
    assert crypto.verify_ed25519(other_pub, msg, sig) is False
