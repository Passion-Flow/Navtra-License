"""Integration tests for forge-edge online validation (activate/seat/lease/revoke)."""

import pytest

from app.core.errors import BizError
from app.schemas.license import IssueOnlineRequest
from app.services.edge import EdgeService
from app.services.issuance import IssuanceService

pytestmark = pytest.mark.integration
CTX = {"ip": None, "user_agent": "pytest", "request_id": "test"}


async def _issue_online(db, p, c, seat_limit=2):
    req = IssueOnlineRequest(customer_id=str(p_c_id(c)), product_id=str(p_c_id(p)),
                             term_preset="1y", seat_limit=seat_limit)
    return await IssuanceService(db).issue_online(req, actor_id=None, ctx=CTX)


def p_c_id(obj):
    return obj.id


async def test_activate_binds_and_issues_lease(db, keys_ready, product_and_customer):
    p, c = product_and_customer
    lic = await _issue_online(db, p, c, seat_limit=2)
    edge = EdgeService(db)
    res = await edge.activate(lic.online_code, "fingerprintA", "clusterA", CTX)
    assert "validation_token" in res and "lease_token" in res
    assert res["lease"]["expires_at"] and res["lease"]["grace_until"]
    await db.refresh(lic)
    assert lic.seat_used == 1 and lic.status == "active"


async def test_same_fingerprint_reuses_seat(db, keys_ready, product_and_customer):
    p, c = product_and_customer
    lic = await _issue_online(db, p, c, seat_limit=2)
    edge = EdgeService(db)
    await edge.activate(lic.online_code, "fpSame", None, CTX)
    await edge.activate(lic.online_code, "fpSame", None, CTX)   # same host again
    await db.refresh(lic)
    assert lic.seat_used == 1                                   # not double-counted


async def test_seat_anti_copy(db, keys_ready, product_and_customer):
    p, c = product_and_customer
    lic = await _issue_online(db, p, c, seat_limit=2)
    edge = EdgeService(db)
    await edge.activate(lic.online_code, "fp1", None, CTX)
    await edge.activate(lic.online_code, "fp2", None, CTX)
    with pytest.raises(BizError) as e:                          # 3rd distinct host
        await edge.activate(lic.online_code, "fp3", None, CTX)
    assert e.value.code == "LICENSE_SEAT_EXCEEDED"


async def test_validate_renews_and_mismatch(db, keys_ready, product_and_customer):
    p, c = product_and_customer
    lic = await _issue_online(db, p, c, seat_limit=1)
    edge = EdgeService(db)
    res = await edge.activate(lic.online_code, "fpV", None, CTX)
    again = await edge.validate(res["validation_token"], "fpV", CTX)
    assert "lease_token" in again
    with pytest.raises(BizError) as e:
        await edge.validate(res["validation_token"], "WRONG-FP", CTX)
    assert e.value.code == "LICENSE_BINDING_MISMATCH"


async def test_revoked_blocks_activation(db, keys_ready, product_and_customer):
    p, c = product_and_customer
    lic = await _issue_online(db, p, c, seat_limit=2)
    await IssuanceService(db).revoke(str(lic.id), "test", actor_id=None, ctx=CTX)
    with pytest.raises(BizError) as e:
        await EdgeService(db).activate(lic.online_code, "fpR", None, CTX)
    assert e.value.code == "LICENSE_REVOKED"


async def test_unknown_code_rejected(db, keys_ready):
    with pytest.raises(BizError) as e:
        await EdgeService(db).activate("00000000-0000-0000-0000-000000000000", "fpX", None, CTX)
    assert e.value.code in ("RESOURCE_NOT_FOUND",)
