"""Online client — phone-home to forge-edge. Lease + grace gives network resilience while
staying fail-closed: a cached lease keeps the product running until grace_until; past that
(or on revoke) the verdict is locked.
"""

from __future__ import annotations

import datetime
import json
import urllib.error
import urllib.request

from forge_verifier import _token
from forge_verifier.verifier import ACTIVE, LOCKED, REVOKED, Verdict


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _parse_dt(value: str | None) -> datetime.datetime | None:
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


class OnlineClient:
    """Talks to forge-edge. Verifies the returned lease_token with the embedded edge_lease
    public key, so a lease can be trusted during the offline grace window."""

    def __init__(self, edge_base_url: str, edge_lease_public_pem: bytes, timeout: float = 8.0) -> None:
        self.base = edge_base_url.rstrip("/")
        self.edge_pub = edge_lease_public_pem
        self.timeout = timeout
        self._last_lease: dict | None = None       # cached verified lease payload
        self._validation_token: str | None = None

    def _post(self, path: str, body: dict) -> tuple[int, dict]:
        req = urllib.request.Request(
            self.base + path, data=json.dumps(body).encode(), method="POST",
            headers={"Content-Type": "application/json"},
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(req, timeout=self.timeout) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or "{}")

    def _accept(self, resp: dict) -> Verdict:
        """Verify the signed lease_token with the embedded edge key, then cache it."""
        valid, lease = _token.parse_and_verify(resp["lease_token"], self.edge_pub)
        if not valid:
            return Verdict(LOCKED, "lease_signature")
        self._last_lease = lease
        self._validation_token = resp.get("validation_token")
        return Verdict(ACTIVE, "online", lease)

    def activate(self, online_code: str, fingerprint: str, cluster_id: str | None = None) -> Verdict:
        status, resp = self._post("/edge/v1/activate",
                                  {"online_code": online_code, "fingerprint": fingerprint,
                                   "cluster_id": cluster_id})
        if status == 200:
            return self._accept(resp)
        if resp.get("code") == "LICENSE_REVOKED":
            return Verdict(REVOKED, "revoked")
        return Verdict(LOCKED, resp.get("code", "activate_failed"))

    def revalidate(self, fingerprint: str) -> Verdict:
        """Renew the lease; if the network is down, fall back to grace on the cached lease."""
        if not self._validation_token:
            return Verdict(LOCKED, "not_activated")
        status, resp = self._post("/edge/v1/validate",
                                  {"validation_token": self._validation_token, "fingerprint": fingerprint})
        if status == 200:
            return self._accept(resp)
        if resp.get("code") == "LICENSE_REVOKED":
            return Verdict(REVOKED, "revoked")
        # network/edge error -> tolerate within the signed grace window (fail-closed after)
        if self._last_lease:
            grace = _parse_dt(self._last_lease.get("grace_until"))
            if grace and _now() < grace:
                return Verdict(ACTIVE, "grace", self._last_lease)
        return Verdict(LOCKED, resp.get("code", "lease_expired"))
