#!/usr/bin/env node
// forge-verify CLI: `forge-verify fingerprint` | `forge-verify offline <blob|file>`
import { readFileSync } from "node:fs";
import { ForgeVerifier, deploymentFingerprint } from "./index.js";

const args = process.argv.slice(2);
if (!args[0] || args[0] === "-h" || args[0] === "--help") {
  console.log("forge-verify fingerprint | forge-verify offline <blob|file>");
  process.exit(0);
}
if (args[0] === "fingerprint") {
  console.log(deploymentFingerprint());
  process.exit(0);
}
if (args[0] === "offline" && args[1]) {
  let blob = args[1];
  try { blob = readFileSync(blob, "utf8").trim(); } catch {}
  const v = new ForgeVerifier().verifyOffline(blob);
  console.log(`status = ${v.status}  reason = ${v.reason}`);
  if (v.payload?.product) console.log(`product = ${v.payload.product}  until = ${v.payload.active_until}`);
  if (!v.unlocked) console.log(v.message("zh-CN"));
  process.exit(v.unlocked ? 0 : 1);
}
console.log("forge-verify fingerprint | forge-verify offline <blob|file>");
process.exit(2);
