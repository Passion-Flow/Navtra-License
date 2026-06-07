package forge

import "errors"

// ForgeVerifier — the high-level embeddable license check.
//
//	fv := forge.New("https://forge.navtra.ai")
//	fmt.Println("Deployment ID:", fv.Fingerprint)   // show on activation page
//	v := fv.VerifyOffline(pastedBlob, nil)           // offline .forge
//	v := fv.ActivateOnline(pastedCode, "")           // online short code
//	if !v.Unlocked() { show(v.Message("zh-CN")) }    // 需要激活许可证.
type ForgeVerifier struct {
	masterPub   []byte
	edgePub     []byte
	Fingerprint string
	online      *OnlineClient
}

// New builds a verifier; pass edgeURL="" for offline-only products.
func New(edgeURL string) *ForgeVerifier {
	fv := &ForgeVerifier{
		masterPub:   MasterPublicPEM(),
		edgePub:     EdgeLeasePublicPEM(),
		Fingerprint: DeploymentFingerprint(),
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
	return fv.online.Activate(onlineCode, fv.Fingerprint, clusterID), nil
}

func (fv *ForgeVerifier) Revalidate() (Verdict, error) {
	if fv.online == nil {
		return Verdict{}, errors.New("edgeURL not configured")
	}
	return fv.online.Revalidate(fv.Fingerprint), nil
}
