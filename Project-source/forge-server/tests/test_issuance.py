"""Integration tests for issuance (online/offline/revoke). Run: FORGE_INTEGRATION=1 pytest."""

import uuid

import pytest

from app.core import crypto
from app.core.errors import BizError
from app.licensing import forge_file
from app.licensing.keys import KeyManager
from app.schemas.license import IssueOfflineRequest, IssueOnlineRequest
from app.services.issuance import IssuanceService

pytestmark = pytest.mark.integration
CTX = {"ip": None, "user_agent": "pytest", "request_id": "test"}


async def test_issue_online(db, keys_ready, product_and_customer):
    p, c = product_and_customer
    req = IssueOnlineRequest(customer_id=str(c.id), product_id=str(p.id), term_preset="1y", seat_limit=3)
    lic = await IssuanceService(db).issue_online(req, actor_id=None, ctx=CTX)
    assert lic.mode == "online"
    assert uuid.UUID(lic.online_code)                       # a real UUID short code
    assert lic.offline_blob is None
    assert lic.seat_limit == 3 and lic.seat_used == 0
    assert lic.status == "issued"
    assert lic.active_until is not None                     # 1y -> bounded


async def test_issue_offline_signs_and_verifies(db, keys_ready, product_and_customer):
    p, c = product_and_customer
    req = IssueOfflineRequest(customer_id=str(c.id), product_id=str(p.id),
                              deployment_id="deadbeef"*8, term_preset="6m", features=["sso"])
    lic = await IssuanceService(db).issue_offline(req, actor_id=None, ctx=CTX)
    assert lic.mode == "offline" and lic.offline_blob
    assert lic.bound_fingerprint == "deadbeef" * 8
    # the signed blob verifies with the master public key
    master = await KeyManager(db).require_active("master")
    ok, payload = forge_file.parse_and_verify(lic.offline_blob, master.public_key.encode())
    assert ok is True
    assert payload["bound_fingerprint"] == "deadbeef" * 8
    assert payload["product"] == p.slug
    assert payload["binding"] == "hard"


async def test_offline_perpetual_99y(db, keys_ready, product_and_customer):
    p, c = product_and_customer
    req = IssueOfflineRequest(customer_id=str(c.id), product_id=str(p.id),
                              deployment_id="b"*64, term_preset="perpetual")
    lic = await IssuanceService(db).issue_offline(req, actor_id=None, ctx=CTX)
    assert lic.active_until is not None and lic.active_until.year >= lic.active_from.year + 90


async def test_offline_blob_tamper_detected(db, keys_ready, product_and_customer):
    p, c = product_and_customer
    req = IssueOfflineRequest(customer_id=str(c.id), product_id=str(p.id), deployment_id="c"*64, term_preset="1y")
    lic = await IssuanceService(db).issue_offline(req, actor_id=None, ctx=CTX)
    master = await KeyManager(db).require_active("master")
    tampered = lic.offline_blob[:-4] + ("AAAA" if lic.offline_blob[-4:] != "AAAA" else "BBBB")
    ok, _ = forge_file.parse_and_verify(tampered, master.public_key.encode())
    assert ok is False


async def test_revoke(db, keys_ready, product_and_customer):
    p, c = product_and_customer
    req = IssueOnlineRequest(customer_id=str(c.id), product_id=str(p.id), term_preset="1y")
    lic = await IssuanceService(db).issue_online(req, actor_id=None, ctx=CTX)
    revoked = await IssuanceService(db).revoke(str(lic.id), "test refund", actor_id=None, ctx=CTX)
    assert revoked.status == "revoked" and revoked.revoked_at is not None
    # idempotent
    again = await IssuanceService(db).revoke(str(lic.id), "x", actor_id=None, ctx=CTX)
    assert again.status == "revoked"


async def test_issue_inactive_product_rejected(db, keys_ready, product_and_customer):
    p, c = product_and_customer
    p.is_active = False
    await db.flush()
    req = IssueOnlineRequest(customer_id=str(c.id), product_id=str(p.id), term_preset="1y")
    with pytest.raises(BizError) as e:
        await IssuanceService(db).issue_online(req, actor_id=None, ctx=CTX)
    assert e.value.code == "ISSUE_PRODUCT_INACTIVE"


async def test_master_key_signs_consistently(db, keys_ready):
    """Same payload bytes -> verifiable signature (no nondeterministic signing surprises)."""
    master = await KeyManager(db).require_active("master")
    priv = KeyManager(db).decrypt_private(master)
    msg = b'{"a":1}'
    sig = crypto.sign_ed25519(priv, msg)
    assert crypto.verify_ed25519(master.public_key.encode(), msg, sig) is True
