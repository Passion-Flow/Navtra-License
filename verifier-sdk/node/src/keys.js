// Embedded vendor public keys. In a real product these are shipped as constants; for
// development the vendor bakes embedded_keys.json via `forge keys export-public`.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

function load() {
  // SECURITY: honor the env key-override ONLY under FORGE_SDK_DEV (tests). In a shipped product it
  // is ignored, so an attacker can't swap in their own public key to verify a self-signed license.
  if (process.env.FORGE_SDK_DEV && process.env.FORGE_EMBEDDED_KEYS) return JSON.parse(process.env.FORGE_EMBEDDED_KEYS);
  const p = join(dirname(fileURLToPath(import.meta.url)), "embedded_keys.json");
  return JSON.parse(readFileSync(p, "utf8"));
}

export const masterPublicPem = () => load().master.public_key;
export const edgeLeasePublicPem = () => load().edge_lease.public_key;
