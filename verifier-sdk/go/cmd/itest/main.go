// Integration test (dev only): drives the live Forge stack to prove the Go SDK matches.
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/cookiejar"
	"os"

	"github.com/navtra/forge-verifier/forge"
)

const edge = "http://forge-edge:8081"
const admin = "http://forge-api:8080/admin-api/v1"

var client *http.Client

func call(base, method, path string, body any) map[string]any {
	var r io.Reader
	if body != nil {
		b, _ := json.Marshal(body)
		r = bytes.NewReader(b)
	}
	req, _ := http.NewRequest(method, base+path, r)
	req.Header.Set("Content-Type", "application/json")
	resp, err := client.Do(req)
	if err != nil {
		return map[string]any{"_err": err.Error()}
	}
	defer resp.Body.Close()
	var out map[string]any
	json.NewDecoder(resp.Body).Decode(&out)
	return out
}

func main() {
	jar, _ := cookiejar.New(nil)
	client = &http.Client{Jar: jar}

	pk := call(edge, "GET", "/edge/v1/public-key", nil)
	data, _ := json.Marshal(pk["data"])
	os.Setenv("FORGE_SDK_DEV", "1") // allow the test key/fingerprint overrides (gated in release)
	os.Setenv("FORGE_EMBEDDED_KEYS", string(data))

	fv := forge.New(edge)
	fmt.Println("本机部署指纹:", fv.Fingerprint[:24], "...")

	call(admin, "POST", "/auth/login", map[string]any{"email": "forge@navtra.ai", "password": "forge@navtra.ai", "code": nil})
	pid := call(admin, "GET", "/products", nil)["data"].([]any)[0].(map[string]any)["id"]
	cid := call(admin, "GET", "/customers", nil)["data"].([]any)[0].(map[string]any)["id"]

	fmt.Println("\n=== 离线轨 ===")
	off := call(admin, "POST", "/licenses:issue-offline",
		map[string]any{"customer_id": cid, "product_id": pid, "deployment_id": fv.Fingerprint, "term_preset": "1y"})
	blob := off["offline_blob"].(string)
	v := fv.VerifyOffline(blob, nil)
	fmt.Printf("  SDK 验签(本机绑定) -> %s  (product=%v)\n", v.Status, v.Payload["product"])
	bad := blob[:len(blob)-6] + "AAAAAA"
	fmt.Printf("  SDK 验签(篡改签名) -> %s\n", fv.VerifyOffline(bad, nil).Status)
	off2 := call(admin, "POST", "/licenses:issue-offline",
		map[string]any{"customer_id": cid, "product_id": pid, "deployment_id": "some-other-host-fingerprint", "term_preset": "1y"})
	v2 := fv.VerifyOffline(off2["offline_blob"].(string), nil)
	fmt.Printf("  SDK 验签(绑定别的机器) -> %s   锁定提示: '%s'\n", v2.Status, v2.Message("zh-CN"))

	fmt.Println("\n=== 在线轨 ===")
	on := call(admin, "POST", "/licenses:issue-online",
		map[string]any{"customer_id": cid, "product_id": pid, "term_preset": "1y", "seat_limit": 1})
	va, _ := fv.ActivateOnline(on["online_code"].(string), "")
	fmt.Printf("  SDK 在线激活 -> %s\n", va.Status)
	vr, _ := fv.Revalidate()
	fmt.Printf("  SDK 续租 -> %s\n", vr.Status)
}
