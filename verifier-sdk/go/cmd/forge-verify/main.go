// forge-verify CLI: `forge-verify fingerprint` | `forge-verify offline <blob|file>`
package main

import (
	"fmt"
	"os"

	"github.com/navtra/forge-verifier/forge"
)

func main() {
	args := os.Args[1:]
	if len(args) == 0 || args[0] == "-h" || args[0] == "--help" {
		fmt.Println("forge-verify fingerprint | forge-verify offline <blob|file>")
		return
	}
	switch args[0] {
	case "fingerprint":
		fmt.Println(forge.DeploymentFingerprint())
	case "offline":
		if len(args) < 2 {
			fmt.Println("usage: forge-verify offline <blob|file>")
			os.Exit(2)
		}
		blob := args[1]
		if b, err := os.ReadFile(blob); err == nil {
			blob = string(b)
		}
		v := forge.New("").VerifyOffline(blob, nil)
		fmt.Printf("status = %s  reason = %s\n", v.Status, v.Reason)
		if p, ok := v.Payload["product"]; ok {
			fmt.Printf("product = %v  until = %v\n", p, v.Payload["active_until"])
		}
		if !v.Unlocked() {
			fmt.Println(v.Message("zh-CN"))
			os.Exit(1)
		}
	default:
		fmt.Println("forge-verify fingerprint | forge-verify offline <blob|file>")
		os.Exit(2)
	}
}
