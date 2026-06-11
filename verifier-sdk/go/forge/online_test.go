package forge

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

// edge stub returning a fixed status + JSON body for /edge/v1/validate.
func stubEdge(t *testing.T, status int, body map[string]any) *OnlineClient {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(status)
		_ = json.NewEncoder(w).Encode(body)
	}))
	t.Cleanup(srv.Close)
	c := NewOnlineClient(srv.URL, nil)
	c.token = "vtok" // pretend already activated
	return c
}

func withGrace(c *OnlineClient, until time.Time) {
	c.lastLease = map[string]any{"grace_until": until.UTC().Format(time.RFC3339)}
}

// Fix B: a DEFINITIVE authority rejection must lock NOW, even inside the grace window.

func TestRevalidate_RevokedLocksDespiteGrace(t *testing.T) {
	c := stubEdge(t, 403, map[string]any{"code": "LICENSE_REVOKED"})
	withGrace(c, time.Now().Add(24*time.Hour)) // plenty of grace left
	v := c.Revalidate("fp", "")
	if v.Status != StatusRevoked {
		t.Fatalf("revoked must lock now (no grace), got %s/%s", v.Status, v.Reason)
	}
}

func TestRevalidate_DefinitiveCodeLocksDespiteGrace(t *testing.T) {
	for _, code := range []string{"LICENSE_EXPIRED", "LICENSE_BINDING_MISMATCH", "LICENSE_LEASE_EXPIRED", "RESOURCE_NOT_FOUND"} {
		c := stubEdge(t, 409, map[string]any{"code": code})
		withGrace(c, time.Now().Add(24*time.Hour))
		v := c.Revalidate("fp", "")
		if v.Unlocked() {
			t.Fatalf("%s must lock now (no grace), got %s/%s", code, v.Status, v.Reason)
		}
	}
}

// Non-authoritative outcomes (5xx / network) ride the grace window.

func TestRevalidate_ServerErrorRidesGrace(t *testing.T) {
	c := stubEdge(t, 500, map[string]any{"code": "SYSTEM_INTERNAL_ERROR"})
	withGrace(c, time.Now().Add(1*time.Hour))
	v := c.Revalidate("fp", "")
	if v.Status != StatusActive || v.Reason != "grace" {
		t.Fatalf("5xx within grace must ride grace, got %s/%s", v.Status, v.Reason)
	}
}

func TestRevalidate_NetworkErrorRidesGrace(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) {}))
	url := srv.URL
	srv.Close() // now unreachable → connection error
	c := NewOnlineClient(url, nil)
	c.token = "vtok"
	withGrace(c, time.Now().Add(1*time.Hour))
	v := c.Revalidate("fp", "")
	if v.Status != StatusActive || v.Reason != "grace" {
		t.Fatalf("network error within grace must ride grace, got %s/%s", v.Status, v.Reason)
	}
}

func TestRevalidate_NetworkErrorPastGraceLocks(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) {}))
	url := srv.URL
	srv.Close()
	c := NewOnlineClient(url, nil)
	c.token = "vtok"
	withGrace(c, time.Now().Add(-1*time.Hour)) // grace already expired
	v := c.Revalidate("fp", "")
	if v.Unlocked() {
		t.Fatalf("network error past grace must lock, got %s/%s", v.Status, v.Reason)
	}
}

func TestRevalidate_NotActivatedLocks(t *testing.T) {
	c := NewOnlineClient("http://127.0.0.1:1", nil) // never called
	v := c.Revalidate("fp", "")
	if v.Status != StatusLocked || v.Reason != "not_activated" {
		t.Fatalf("no token must lock not_activated, got %s/%s", v.Status, v.Reason)
	}
}
