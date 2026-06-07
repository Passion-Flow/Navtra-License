// Offline verification + Verdict. fail-closed: any anomaly => locked.
import { readFileSync, writeFileSync, mkdirSync, renameSync } from "node:fs";
import { dirname } from "node:path";
import { parseAndVerify } from "./token.js";

function loadState(path) {
  try { return JSON.parse(readFileSync(path, "utf8")); } catch { return {}; }
}
function saveState(path, st) {
  // best-effort: a read-only FS can't be hardened, but never crash the product over it.
  try {
    const d = dirname(path); if (d) mkdirSync(d, { recursive: true });
    const tmp = path + ".tmp"; writeFileSync(tmp, JSON.stringify(st)); renameSync(tmp, path);
  } catch { /* ignore */ }
}

export const LOCK_MESSAGE = { "zh-CN": "需要激活许可证.", en: "License activation required." };
export const Status = {
  ACTIVE: "active", EXPIRING: "expiring", EXPIRED: "expired", REVOKED: "revoked",
  BINDING_MISMATCH: "binding_mismatch", INVALID_SIGNATURE: "invalid_signature", LOCKED: "locked",
};
const UNLOCKED = new Set([Status.ACTIVE, Status.EXPIRING]);

export class Verdict {
  constructor(status, reason = "", payload = {}) {
    this.status = status;
    this.reason = reason;
    this.payload = payload;
  }
  get unlocked() {
    return UNLOCKED.has(this.status);
  }
  message(lang = "zh-CN") {
    return this.unlocked ? "" : LOCK_MESSAGE[lang] || LOCK_MESSAGE.en;
  }
}

export function verifyOffline(blob, masterPublicPem, localFingerprint, opts = {}) {
  const now = opts.now || new Date();
  const revoked = opts.revokedLicenseIds; // Set<string> | undefined
  let valid, payload;
  try {
    ({ valid, payload } = parseAndVerify(blob, masterPublicPem));
  } catch {
    return new Verdict(Status.LOCKED, "malformed");
  }
  if (!valid) return new Verdict(Status.INVALID_SIGNATURE, "signature");

  // --- anti-rollback hardening (enabled when opts.statePath is a writable file the SDK owns) ---
  //   clock-rollback / CRL anti-rollback (opts.crlVersion) / CRL freshness (opts.maxCrlAgeDays).
  if (opts.statePath) {
    const st = loadState(opts.statePath);
    const skewMs = (opts.clockSkewMinutes ?? 10) * 60000;
    const wm = st.time_watermark ? new Date(st.time_watermark) : null;
    if (wm && now < new Date(wm.getTime() - skewMs)) return new Verdict(Status.LOCKED, "clock_rollback", payload);
    if (opts.crlVersion != null && st.crl_version != null && opts.crlVersion < st.crl_version)
      return new Verdict(Status.LOCKED, "crl_rollback", payload);
    if (opts.maxCrlAgeDays != null && opts.crlGeneratedAt) {
      const gen = new Date(opts.crlGeneratedAt);
      if ((now - gen) / 86400000 > opts.maxCrlAgeDays) return new Verdict(Status.LOCKED, "crl_stale", payload);
    }
    let newWm = now;
    for (const c of [wm, opts.crlGeneratedAt ? new Date(opts.crlGeneratedAt) : null]) if (c && c > newWm) newWm = c;
    st.time_watermark = newWm.toISOString();
    if (opts.crlVersion != null) st.crl_version = Math.max(opts.crlVersion, st.crl_version ?? opts.crlVersion);
    if (opts.crlGeneratedAt) st.crl_generated_at = opts.crlGeneratedAt;
    saveState(opts.statePath, st);
  }

  if ((payload.binding || "hard") === "hard" && payload.bound_fingerprint !== localFingerprint) {
    return new Verdict(Status.BINDING_MISMATCH, "fingerprint", payload);
  }
  if (revoked && revoked.has(payload.license_id)) return new Verdict(Status.REVOKED, "crl", payload);
  if (payload.active_until) {
    const until = new Date(payload.active_until);
    if (now >= until) return new Verdict(Status.EXPIRED, "expired", payload);
    if ((until - now) / 86400000 <= 30) return new Verdict(Status.EXPIRING, "expiring", payload);
  }
  return new Verdict(Status.ACTIVE, "ok", payload);
}
