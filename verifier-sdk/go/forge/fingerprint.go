package forge

import (
	"crypto/sha256"
	"encoding/hex"
	"net"
	"os"
	"os/exec"
	"regexp"
	"runtime"
	"strings"
)

// Hardware fingerprint — stable per-deployment id collected live, never stored.
// Linux /etc/machine-id · macOS IOPlatformUUID · Windows MachineGuid · fallback hostname+MAC.

func firstMAC() string {
	ifaces, _ := net.Interfaces()
	for _, i := range ifaces {
		if i.Flags&net.FlagLoopback == 0 && i.HardwareAddr.String() != "" {
			return i.HardwareAddr.String()
		}
	}
	return "no-mac"
}

func rawMachineID() string {
	// SECURITY: deployment-UID override only under FORGE_SDK_DEV; production must use real hardware.
	if os.Getenv("FORGE_SDK_DEV") != "" {
		if v := os.Getenv("FORGE_DEPLOYMENT_UID"); v != "" {
			return "override:" + v
		}
	}
	switch runtime.GOOS {
	case "linux":
		for _, p := range []string{"/etc/machine-id", "/var/lib/dbus/machine-id"} {
			if b, err := os.ReadFile(p); err == nil {
				if v := strings.TrimSpace(string(b)); v != "" {
					return "linux:" + v
				}
			}
		}
	case "darwin":
		if out, err := exec.Command("ioreg", "-rd1", "-c", "IOPlatformExpertDevice").Output(); err == nil {
			if m := regexp.MustCompile(`IOPlatformUUID"?\s*=\s*"([^"]+)"`).FindSubmatch(out); m != nil {
				return "macos:" + string(m[1])
			}
		}
	case "windows":
		if out, err := exec.Command("reg", "query",
			`HKLM\SOFTWARE\Microsoft\Cryptography`, "/v", "MachineGuid").Output(); err == nil {
			if m := regexp.MustCompile(`MachineGuid\s+REG_SZ\s+([0-9a-fA-F-]+)`).FindSubmatch(out); m != nil {
				return "windows:" + string(m[1])
			}
		}
	}
	host, _ := os.Hostname()
	return "fallback:" + host + ":" + firstMAC()
}

// DeploymentFingerprint returns the SHA-256 hex shown on the product activation page.
func DeploymentFingerprint() string {
	sum := sha256.Sum256([]byte(rawMachineID()))
	return hex.EncodeToString(sum[:])
}
