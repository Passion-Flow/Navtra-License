// Online client — phone-home to forge-edge; lease + grace for network resilience.
import { parseAndVerify } from "./token.js";
import { Status, Verdict } from "./verifier.js";

export class OnlineClient {
  constructor(edgeBaseUrl, edgeLeasePublicPem, timeoutMs = 8000) {
    this.base = edgeBaseUrl.replace(/\/$/, "");
    this.edgePub = edgeLeasePublicPem;
    this.timeoutMs = timeoutMs;
    this._lastLease = null;
    this._validationToken = null;
  }

  async _post(path, body) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), this.timeoutMs);
    try {
      const res = await fetch(this.base + path, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body), signal: ctrl.signal,
      });
      return { status: res.status, body: await res.json().catch(() => ({})) };
    } finally {
      clearTimeout(t);
    }
  }

  _accept(resp) {
    const { valid, payload } = parseAndVerify(resp.lease_token, this.edgePub);
    if (!valid) return new Verdict(Status.LOCKED, "lease_signature");
    this._lastLease = payload;
    this._validationToken = resp.validation_token;
    return new Verdict(Status.ACTIVE, "online", payload);
  }

  async activate(onlineCode, fingerprint, clusterId = null, { installId, signals, deploymentUid } = {}) {
    const reqBody = { online_code: onlineCode, fingerprint, cluster_id: clusterId };
    // 反克隆身份字段（design 07）：仅在有值时附带；新 edge 先行部署，旧 edge 收不到也不影响。
    if (installId) reqBody.install_id = installId;
    if (signals && Object.keys(signals).length) reqBody.signals = signals;
    if (deploymentUid) reqBody.deployment_uid = deploymentUid;
    let r;
    try {
      r = await this._post("/edge/v1/activate", reqBody);
    } catch {
      return new Verdict(Status.LOCKED, "network");
    }
    if (r.status === 200) return this._accept(r.body);
    if (r.body?.code === "LICENSE_REVOKED") return new Verdict(Status.REVOKED, "revoked");
    return new Verdict(Status.LOCKED, r.body?.code || "activate_failed");
  }

  async revalidate(fingerprint, { installId } = {}) {
    if (!this._validationToken) return new Verdict(Status.LOCKED, "not_activated");
    const reqBody = { validation_token: this._validationToken, fingerprint };
    if (installId) reqBody.install_id = installId;
    let r;
    try {
      r = await this._post("/edge/v1/validate", reqBody);
    } catch {
      r = null;
    }
    if (r && r.status === 200) return this._accept(r.body);
    if (r && r.body?.code === "LICENSE_REVOKED") return new Verdict(Status.REVOKED, "revoked");
    // network/edge error -> tolerate within the signed grace window
    if (this._lastLease?.grace_until && new Date() < new Date(this._lastLease.grace_until)) {
      return new Verdict(Status.ACTIVE, "grace", this._lastLease);
    }
    return new Verdict(Status.LOCKED, r?.body?.code || "lease_expired");
  }
}
