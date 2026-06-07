"""Forge Verifier SDK (Python) — embed in a consumer product to verify Forge licenses.

    from forge_verifier import ForgeVerifier
    fv = ForgeVerifier(edge_url="https://forge.navtra.ai")
    print("Deployment ID:", fv.fingerprint)          # show on the activation page
    v = fv.verify_offline(pasted_blob)                # offline .forge
    v = fv.activate_online(pasted_code)               # online short code
    if not v.unlocked:
        show(v.message("zh-CN"))                      # 需要激活许可证.
"""

from __future__ import annotations

from forge_verifier import keys
from forge_verifier.fingerprint import deployment_fingerprint
from forge_verifier.online import OnlineClient
from forge_verifier.verifier import Verdict, verify_offline

__all__ = ["ForgeVerifier", "Verdict", "verify_offline", "OnlineClient", "deployment_fingerprint"]


class ForgeVerifier:
    def __init__(self, edge_url: str | None = None) -> None:
        self.master_pub = keys.master_public_pem()
        self.edge_pub = keys.edge_lease_public_pem()
        self.fingerprint = deployment_fingerprint()
        self.online = OnlineClient(edge_url, self.edge_pub) if edge_url else None

    def verify_offline(self, blob: str, revoked_license_ids: set[str] | None = None) -> Verdict:
        return verify_offline(blob, self.master_pub, self.fingerprint,
                              revoked_license_ids=revoked_license_ids)

    def revoked_from_crl(self, crl_blob: str) -> set[str]:
        """Verify a signed CRL with the embedded master key; return the revoked license_ids.
        An untrusted/invalid CRL is ignored (empty set) — license expiry still guards."""
        from forge_verifier._token import parse_and_verify
        try:
            valid, payload = parse_and_verify(crl_blob, self.master_pub)
        except Exception:
            return set()
        if not valid or payload.get("kind") != "crl":
            return set()
        return set(payload.get("revoked", []))

    def activate_online(self, online_code: str, cluster_id: str | None = None) -> Verdict:
        if not self.online:
            raise RuntimeError("edge_url not configured")
        return self.online.activate(online_code, self.fingerprint, cluster_id)

    def revalidate(self) -> Verdict:
        if not self.online:
            raise RuntimeError("edge_url not configured")
        return self.online.revalidate(self.fingerprint)
