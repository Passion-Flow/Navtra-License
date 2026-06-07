// Compact signed-token codec — MUST match forge-server app/licensing/forge_file.py.
// Format: <base64url(canonical_payload_json)>.<base64url(ed25519_signature)>
import { createPublicKey, verify } from "node:crypto";

export function b64uDecode(s) {
  return Buffer.from(s, "base64url");
}

// Verify the detached Ed25519 signature over the EXACT payload bytes with the embedded key.
export function parseAndVerify(blob, publicPem) {
  const parts = String(blob).trim().split(".");
  if (parts.length !== 2) throw new Error("malformed token");
  const payloadBytes = b64uDecode(parts[0]);
  const signature = b64uDecode(parts[1]);
  const payload = JSON.parse(payloadBytes.toString("utf8"));
  const key = createPublicKey(publicPem);
  // Ed25519: algorithm arg must be null
  const valid = verify(null, payloadBytes, key, signature);
  return { valid, payload };
}
