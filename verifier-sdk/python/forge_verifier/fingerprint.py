"""Hardware fingerprint — a stable per-deployment id collected live from the host, never
stored (licensing.md): moving the DB / host changes it, defeating license copying.

Linux  /etc/machine-id · macOS IOPlatformUUID · Windows MachineGuid · fallback hostname+MAC.
Override with FORGE_DEPLOYMENT_UID for K8s / drift-prone infra (pin a stable uid).
"""

from __future__ import annotations

import hashlib
import os
import platform
import subprocess
import uuid


def _raw_machine_id() -> str:
    # SECURITY: the deployment-UID override is honored ONLY under FORGE_SDK_DEV. In production the
    # fingerprint must derive from real hardware (machine-id/UUID/MAC) so it changes on machine/DB
    # migration (anti-copy). An unconditional override would let a copier spoof the bound id.
    if os.environ.get("FORGE_SDK_DEV"):
        override = os.environ.get("FORGE_DEPLOYMENT_UID")
        if override:
            return f"override:{override}"

    system = platform.system()
    try:
        if system == "Linux":
            for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
                if os.path.isfile(path):
                    with open(path, encoding="utf-8") as fh:
                        if value := fh.read().strip():
                            return f"linux:{value}"
        elif system == "Darwin":
            out = subprocess.check_output(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"], text=True, timeout=5
            )
            for line in out.splitlines():
                if "IOPlatformUUID" in line:
                    return f"macos:{line.split('=')[-1].strip().strip(chr(34))}"
        elif system == "Windows":
            import winreg  # type: ignore

            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            return f"windows:{value}"
    except Exception:
        pass
    # fallback: hostname + MAC (uuid.getnode)
    return f"fallback:{platform.node()}:{uuid.getnode():012x}"


def deployment_fingerprint() -> str:
    """SHA-256 hex of the raw machine id — the value shown on the product activation page."""
    return hashlib.sha256(_raw_machine_id().encode("utf-8")).hexdigest()
