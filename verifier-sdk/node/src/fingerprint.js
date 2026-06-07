// Hardware fingerprint — stable per-deployment id collected live, never stored.
// Linux /etc/machine-id · macOS IOPlatformUUID · Windows MachineGuid · fallback hostname+MAC.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { execSync } from "node:child_process";
import { hostname, networkInterfaces, platform } from "node:os";

function firstMac() {
  for (const ifaces of Object.values(networkInterfaces())) {
    for (const i of ifaces || []) {
      if (!i.internal && i.mac && i.mac !== "00:00:00:00:00:00") return i.mac;
    }
  }
  return "no-mac";
}

function rawMachineId() {
  // SECURITY: deployment-UID override only under FORGE_SDK_DEV; production must use real hardware.
  if (process.env.FORGE_SDK_DEV && process.env.FORGE_DEPLOYMENT_UID) return `override:${process.env.FORGE_DEPLOYMENT_UID}`;
  try {
    if (platform() === "linux") {
      for (const p of ["/etc/machine-id", "/var/lib/dbus/machine-id"]) {
        try {
          const v = readFileSync(p, "utf8").trim();
          if (v) return `linux:${v}`;
        } catch {}
      }
    } else if (platform() === "darwin") {
      const out = execSync("ioreg -rd1 -c IOPlatformExpertDevice", { encoding: "utf8", timeout: 5000 });
      const m = out.match(/IOPlatformUUID"?\s*=\s*"([^"]+)"/);
      if (m) return `macos:${m[1]}`;
    } else if (platform() === "win32") {
      const out = execSync(
        'reg query "HKLM\\SOFTWARE\\Microsoft\\Cryptography" /v MachineGuid',
        { encoding: "utf8", timeout: 5000 },
      );
      const m = out.match(/MachineGuid\s+REG_SZ\s+([0-9a-fA-F-]+)/);
      if (m) return `windows:${m[1]}`;
    }
  } catch {}
  return `fallback:${hostname()}:${firstMac()}`;
}

export function deploymentFingerprint() {
  return createHash("sha256").update(rawMachineId(), "utf8").digest("hex");
}
