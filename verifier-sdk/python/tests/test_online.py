"""Fix B: revalidate must distinguish a DEFINITIVE authority rejection (lock now, no grace)
from a NON-authoritative outcome (network / 5xx → ride the signed grace window)."""

import datetime
import urllib.error

import pytest

from forge_verifier.online import OnlineClient


def _client(post_impl, grace_delta_hours=None):
    c = OnlineClient("http://edge.invalid", b"")
    c._validation_token = "vtok"  # pretend already activated
    c._post = post_impl  # type: ignore[assignment]
    if grace_delta_hours is not None:
        until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=grace_delta_hours)
        c._last_lease = {"grace_until": until.isoformat()}
    return c


def _resp(status, code):
    def post(_path, _body):
        return status, ({"code": code} if code else {})
    return post


def _raises_urlerror(_path, _body):
    raise urllib.error.URLError("connection refused")


def test_revoked_locks_despite_grace():
    c = _client(_resp(403, "LICENSE_REVOKED"), grace_delta_hours=24)
    v = c.revalidate("fp")
    assert v.status == "revoked" and not v.unlocked


@pytest.mark.parametrize("code", [
    "LICENSE_EXPIRED", "LICENSE_BINDING_MISMATCH", "LICENSE_LEASE_EXPIRED", "RESOURCE_NOT_FOUND",
])
def test_definitive_code_locks_despite_grace(code):
    c = _client(_resp(409, code), grace_delta_hours=24)
    v = c.revalidate("fp")
    assert not v.unlocked, f"{code} must lock now, got {v.status}"


def test_server_error_rides_grace():
    c = _client(_resp(500, "SYSTEM_INTERNAL_ERROR"), grace_delta_hours=1)
    v = c.revalidate("fp")
    assert v.unlocked and v.reason == "grace"


def test_network_error_within_grace_rides_grace():
    c = _client(_raises_urlerror, grace_delta_hours=1)
    v = c.revalidate("fp")
    assert v.unlocked and v.reason == "grace"


def test_network_error_past_grace_locks():
    c = _client(_raises_urlerror, grace_delta_hours=-1)
    v = c.revalidate("fp")
    assert not v.unlocked


def test_not_activated_locks():
    c = OnlineClient("http://edge.invalid", b"")
    v = c.revalidate("fp")
    assert v.status == "locked" and v.reason == "not_activated"
