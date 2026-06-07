package forge

import (
	"bytes"
	"encoding/json"
	"net/http"
	"time"
)

// OnlineClient phones home to forge-edge; lease + grace gives network resilience.
type OnlineClient struct {
	base     string
	edgePub  []byte
	client   *http.Client
	lastLease map[string]any
	token     string
}

func NewOnlineClient(edgeBaseURL string, edgeLeasePublicPEM []byte) *OnlineClient {
	return &OnlineClient{
		base:    trimSlash(edgeBaseURL),
		edgePub: edgeLeasePublicPEM,
		client:  &http.Client{Timeout: 8 * time.Second},
	}
}

func trimSlash(s string) string {
	for len(s) > 0 && s[len(s)-1] == '/' {
		s = s[:len(s)-1]
	}
	return s
}

func (c *OnlineClient) post(path string, body map[string]any) (int, map[string]any, error) {
	b, _ := json.Marshal(body)
	resp, err := c.client.Post(c.base+path, "application/json", bytes.NewReader(b))
	if err != nil {
		return 0, nil, err
	}
	defer resp.Body.Close()
	var out map[string]any
	json.NewDecoder(resp.Body).Decode(&out)
	return resp.StatusCode, out, nil
}

func (c *OnlineClient) accept(resp map[string]any) Verdict {
	lt, _ := resp["lease_token"].(string)
	valid, lease, err := ParseAndVerify(lt, c.edgePub)
	if err != nil || !valid {
		return Verdict{StatusLocked, "lease_signature", nil}
	}
	c.lastLease = lease
	c.token, _ = resp["validation_token"].(string)
	return Verdict{StatusActive, "online", lease}
}

func (c *OnlineClient) Activate(onlineCode, fingerprint, clusterID string) Verdict {
	status, body, err := c.post("/edge/v1/activate",
		map[string]any{"online_code": onlineCode, "fingerprint": fingerprint, "cluster_id": clusterID})
	if err != nil {
		return Verdict{StatusLocked, "network", nil}
	}
	if status == 200 {
		return c.accept(body)
	}
	if str(body, "code") == "LICENSE_REVOKED" {
		return Verdict{StatusRevoked, "revoked", nil}
	}
	reason := str(body, "code")
	if reason == "" {
		reason = "activate_failed"
	}
	return Verdict{StatusLocked, reason, nil}
}

func (c *OnlineClient) Revalidate(fingerprint string) Verdict {
	if c.token == "" {
		return Verdict{StatusLocked, "not_activated", nil}
	}
	status, body, err := c.post("/edge/v1/validate",
		map[string]any{"validation_token": c.token, "fingerprint": fingerprint})
	if err == nil && status == 200 {
		return c.accept(body)
	}
	if err == nil && str(body, "code") == "LICENSE_REVOKED" {
		return Verdict{StatusRevoked, "revoked", nil}
	}
	// network/edge error -> tolerate within the signed grace window
	if c.lastLease != nil {
		if g := str(c.lastLease, "grace_until"); g != "" {
			if t, perr := time.Parse(time.RFC3339, g); perr == nil && time.Now().UTC().Before(t) {
				return Verdict{StatusActive, "grace", c.lastLease}
			}
		}
	}
	return Verdict{StatusLocked, "lease_expired", nil}
}
