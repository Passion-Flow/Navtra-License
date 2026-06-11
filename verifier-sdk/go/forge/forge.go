package forge

import (
	"errors"
	"os"
	"path/filepath"
)

// ForgeVerifier — the high-level embeddable license check.
//
//	fv := forge.New("https://forge.navtra.ai")
//	fmt.Println("Deployment ID:", fv.Fingerprint)   // show on activation page
//	v := fv.VerifyOffline(pastedBlob, nil)           // offline .forge
//	v := fv.ActivateOnline(pastedCode, "")           // online short code
//	if !v.Unlocked() { show(v.Message("zh-CN")) }    // 需要激活许可证.
type ForgeVerifier struct {
	masterPub    []byte
	edgePub      []byte
	Fingerprint  string
	InstallID    string            // 反克隆：首激活随机 id（与指纹双锁）
	DeploymentID string            // 注入的容器/集群权威身份（裸机为空）
	Signals      map[string]string // 多信号向量
	online       *OnlineClient
}

// New builds a verifier; pass edgeURL="" for offline-only products.
func New(edgeURL string) *ForgeVerifier {
	return NewWithInstallPath(edgeURL, "")
}

// NewWithInstallPath lets the consumer pin where the install_id persists (e.g. a shared volume).
func NewWithInstallPath(edgeURL, installIDPath string) *ForgeVerifier {
	if installIDPath == "" {
		home, _ := os.UserHomeDir()
		installIDPath = filepath.Join(home, ".config", "forge", "install_id")
	}
	fv := &ForgeVerifier{
		masterPub:    MasterPublicPEM(),
		edgePub:      EdgeLeasePublicPEM(),
		Fingerprint:  DeploymentFingerprint(),
		InstallID:    EnsureInstallID(installIDPath),
		DeploymentID: DeploymentUID(),
		Signals:      CollectSignals(),
	}
	if edgeURL != "" {
		fv.online = NewOnlineClient(edgeURL, fv.edgePub)
	}
	return fv
}

func (fv *ForgeVerifier) VerifyOffline(blob string, revoked map[string]bool) Verdict {
	return VerifyOffline(blob, fv.masterPub, fv.Fingerprint, revoked)
}

// RevokedFromCRL verifies a signed CRL with the embedded master key and returns the revoked
// license_ids. An untrusted/invalid CRL is ignored (empty) — license expiry still guards.
func (fv *ForgeVerifier) RevokedFromCRL(crlBlob string) map[string]bool {
	out := map[string]bool{}
	valid, payload, err := ParseAndVerify(crlBlob, fv.masterPub)
	if err != nil || !valid || str(payload, "kind") != "crl" {
		return out
	}
	if list, ok := payload["revoked"].([]any); ok {
		for _, id := range list {
			if s, ok := id.(string); ok {
				out[s] = true
			}
		}
	}
	return out
}

func (fv *ForgeVerifier) ActivateOnline(onlineCode, clusterID string) (Verdict, error) {
	if fv.online == nil {
		return Verdict{}, errors.New("edgeURL not configured")
	}
	return fv.online.Activate(onlineCode, fv.Fingerprint, clusterID,
		fv.InstallID, fv.DeploymentID, fv.Signals), nil
}

func (fv *ForgeVerifier) Revalidate() (Verdict, error) {
	if fv.online == nil {
		return Verdict{}, errors.New("edgeURL not configured")
	}
	return fv.online.Revalidate(fv.Fingerprint, fv.InstallID), nil
}
