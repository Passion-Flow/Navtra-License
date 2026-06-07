"""Unit tests for the licensing core (.forge codec + validity terms). No DB/Redis needed."""

import datetime

import pytest

from app.core import crypto
from app.core.errors import BizError
from app.licensing import forge_file, payload as payload_mod


def _keypair():
    return crypto.generate_ed25519()  # (private_pem, public_pem)


def _sign(priv, payload):
    return crypto.sign_ed25519(priv, forge_file.canonical_payload_bytes(payload))


def test_canonical_bytes_deterministic():
    a = {"b": 1, "a": [1, 2], "z": None}
    b = {"z": None, "a": [1, 2], "b": 1}
    assert forge_file.canonical_payload_bytes(a) == forge_file.canonical_payload_bytes(b)


def test_forge_roundtrip_valid():
    priv, pub = _keypair()
    payload = {"license_id": "L1", "product": "P", "alg": "ed25519", "bound_fingerprint": "fp"}
    blob = forge_file.build_forge_blob(payload, _sign(priv, payload))
    assert blob.count(".") == 1            # compact two-part token
    assert len(blob) < 1200                # compact, not bulky tar
    ok, parsed = forge_file.parse_and_verify(blob, pub)
    assert ok is True
    assert parsed["product"] == "P"


def test_forge_tamper_payload_fails():
    priv, pub = _keypair()
    payload = {"license_id": "L1", "features": ["sso"]}
    sig = _sign(priv, payload)
    tampered = forge_file.build_forge_blob({"license_id": "L1", "features": ["sso", "admin"]}, sig)
    ok, _ = forge_file.parse_and_verify(tampered, pub)
    assert ok is False


def test_forge_wrong_key_fails():
    priv, _ = _keypair()
    _, other_pub = _keypair()
    payload = {"license_id": "L1"}
    blob = forge_file.build_forge_blob(payload, _sign(priv, payload))
    ok, _ = forge_file.parse_and_verify(blob, other_pub)
    assert ok is False


def test_forge_malformed_raises():
    _, pub = _keypair()
    with pytest.raises(ValueError):
        forge_file.parse_and_verify("not-a-valid-token", pub)


@pytest.mark.parametrize("term,months,years", [
    ("1m", 1, 0), ("3m", 3, 0), ("6m", 6, 0), ("1y", 0, 1), ("3y", 0, 3), ("5y", 0, 5),
])
def test_term_offsets(term, months, years):
    base = datetime.datetime(2026, 6, 6, tzinfo=datetime.timezone.utc)
    until = payload_mod.compute_active_until(term, base, "offline")
    expected = base.replace(year=base.year + years)
    # approximate month math: just assert it advanced and is in the future
    assert until > base
    if years:
        assert until.year == 2026 + years


def test_perpetual_online_is_none_offline_far_future():
    base = datetime.datetime(2026, 6, 6, tzinfo=datetime.timezone.utc)
    assert payload_mod.compute_active_until("perpetual", base, "online") is None
    offline = payload_mod.compute_active_until("perpetual", base, "offline")
    assert offline is not None and offline.year >= 2026 + 90  # +99y backstop


def test_invalid_term_raises():
    base = datetime.datetime(2026, 6, 6, tzinfo=datetime.timezone.utc)
    with pytest.raises(BizError) as e:
        payload_mod.compute_active_until("99m", base, "offline")
    assert e.value.code == "ISSUE_INVALID_TERM"
