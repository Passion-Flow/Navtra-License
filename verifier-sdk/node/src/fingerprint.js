// Hardware fingerprint — stable per-deployment id collected live, never stored.
// Linux /etc/machine-id · macOS IOPlatformUUID · Windows MachineGuid · fallback hostname+MAC.
import { createHash, randomBytes } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { execSync } from "node:child_process";
import { dirname } from "node:path";
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

// ── anti-clone identity (design 07) — additive; deploymentFingerprint() value unchanged ──

function inContainer() {
  if (process.env.KUBERNETES_SERVICE_HOST) return true;
  if (existsSync("/.dockerenv")) return true;
  try {
    const c = readFileSync("/proc/1/cgroup", "utf8");
    if (c.includes("docker") || c.includes("kubepods") || c.includes("containerd")) return true;
  } catch {}
  return false;
}

// Injected stable uid, authoritative ONLY in dev or inside a container/K8s (bare metal ignores
// it so a copier cannot spoof the bound id via an env var).
export function deploymentUid() {
  const uid = process.env.FORGE_DEPLOYMENT_UID;
  if (!uid) return null;
  if (process.env.FORGE_SDK_DEV || inContainer()) return uid;
  return null;
}

function readTrim(p) {
  try {
    const v = readFileSync(p, "utf8").trim();
    return v || null;
  } catch {
    return null;
  }
}

function machineIdRaw() {
  if (platform() === "linux") {
    return readTrim("/etc/machine-id") || readTrim("/var/lib/dbus/machine-id");
  }
  if (platform() === "darwin") {
    try {
      const out = execSync("ioreg -rd1 -c IOPlatformExpertDevice", { encoding: "utf8", timeout: 5000 });
      const m = out.match(/IOPlatformUUID"?\s*=\s*"([^"]+)"/);
      if (m) return m[1];
    } catch {}
  }
  return null;
}

const _hash = (v) => createHash("sha256").update(v, "utf8").digest("hex");

// Multi-signal vector (each value hashed); missing signals omitted, never fabricated.
export function collectSignals() {
  const mac = firstMac();
  const raw = {
    dmi_product_uuid: readTrim("/sys/class/dmi/id/product_uuid"),
    board_serial: readTrim("/sys/class/dmi/id/board_serial"),
    disk_serial: readTrim("/sys/class/dmi/id/product_serial"),
    cpu_sig: `${process.arch}|${platform()}`,
    machine_id: machineIdRaw(),
    mac: mac === "no-mac" ? null : mac,
  };
  const out = {};
  for (const [k, v] of Object.entries(raw)) if (v) out[k] = _hash(v);
  return out;
}

// First-activation random id persisted 0600; regenerated only when the file is gone
// (reinstall / fresh deploy = new identity).
export function ensureInstallId(path) {
  const existing = readTrim(path);
  if (existing && existing.length >= 16) return existing;
  const id = randomBytes(32).toString("hex");
  try {
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, id, { mode: 0o600 });
  } catch {}
  return id;
}
