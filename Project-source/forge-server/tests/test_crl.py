"""Integration tests for CRL (offline strong revocation)."""

import pytest

from app.licensing import forge_file
from app.licensing.keys import KeyManager
from app.schemas.license import IssueOfflineRequest
from app.services.crl import CrlService
from app.services.issuance import IssuanceService

pytestmark = pytest.mark.integration
CTX = {"ip": None, "user_agent": "pytest", "request_id": "test"}


async def test_crl_contains_revoked_offline_and_is_signed(db, keys_ready, product_and_customer):
    p, c = product_and_customer
    req = IssueOfflineRequest(customer_id=str(c.id), product_id=str(p.id), deployment_id="a"*64, term_preset="1y")
    lic = await IssuanceService(db).issue_offline(req, actor_id=None, ctx=CTX)
    await IssuanceService(db).revoke(str(lic.id), "refund", actor_id=None, ctx=CTX)

    bundle = await CrlService(db).generate(actor_id=None, ctx=CTX)
    assert bundle.version >= 1 and bundle.entry_count >= 1

    master = await KeyManager(db).require_active("master")
    ok, payload = forge_file.parse_and_verify(bundle.signed_blob, master.public_key.encode())
    assert ok is True
    assert payload["kind"] == "crl"
    assert str(lic.license_id) in payload["revoked"]


async def test_crl_version_increments(db, keys_ready, product_and_customer):
    svc = CrlService(db)
    v1 = await svc.generate(actor_id=None, ctx=CTX)
    v2 = await svc.generate(actor_id=None, ctx=CTX)
    assert v2.version == v1.version + 1


async def test_tampered_crl_fails_verification(db, keys_ready, product_and_customer):
    bundle = await CrlService(db).generate(actor_id=None, ctx=CTX)
    master = await KeyManager(db).require_active("master")
    tampered = bundle.signed_blob[:-4] + ("AAAA" if bundle.signed_blob[-4:] != "AAAA" else "BBBB")
    ok, _ = forge_file.parse_and_verify(tampered, master.public_key.encode())
    assert ok is False
