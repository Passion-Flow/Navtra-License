// Forge Verifier SDK (Node). Embed in a consumer product to verify Forge licenses.
//   import { ForgeVerifier } from "@forge/verifier";
//   const fv = new ForgeVerifier({ edgeUrl: "https://forge.navtra.ai" });
//   console.log("Deployment ID:", fv.fingerprint);     // show on activation page
//   const v = fv.verifyOffline(pastedBlob);            // offline .forge
//   const v2 = await fv.activateOnline(pastedCode);    // online short code
//   if (!v.unlocked) show(v.message("zh-CN"));         // 需要激活许可证.
import { homedir } from "node:os";
import { join } from "node:path";
import { collectSignals, deploymentFingerprint, deploymentUid, ensureInstallId } from "./fingerprint.js";
import { edgeLeasePublicPem, masterPublicPem } from "./keys.js";
import { OnlineClient } from "./online.js";
import { parseAndVerify } from "./token.js";
import { Verdict, Status, verifyOffline } from "./verifier.js";

export { Verdict, Status, verifyOffline, OnlineClient, deploymentFingerprint };

export class ForgeVerifier {
  constructor({ edgeUrl, installIdPath } = {}) {
    this.masterPub = masterPublicPem();
    this.edgePub = edgeLeasePublicPem();
    this.fingerprint = deploymentFingerprint();
    // 反克隆身份（design 07）：注入 UID（容器/集群权威）、多信号向量、首激活随机 install_id。
    this.deploymentUid = deploymentUid();
    this.signals = collectSignals();
    this.installId = ensureInstallId(installIdPath || join(homedir(), ".config", "forge", "install_id"));
    this.online = edgeUrl ? new OnlineClient(edgeUrl, this.edgePub) : null;
  }
  verifyOffline(blob, revokedLicenseIds) {
    return verifyOffline(blob, this.masterPub, this.fingerprint, { revokedLicenseIds });
  }
  // Verify a signed CRL with the embedded master key; return a Set of revoked license_ids.
  revokedFromCrl(crlBlob) {
    try {
      const { valid, payload } = parseAndVerify(crlBlob, this.masterPub);
      if (!valid || payload.kind !== "crl") return new Set();
      return new Set(payload.revoked || []);
    } catch {
      return new Set();
    }
  }
  activateOnline(onlineCode, clusterId = null) {
    if (!this.online) throw new Error("edgeUrl not configured");
    return this.online.activate(onlineCode, this.fingerprint, clusterId, {
      installId: this.installId, signals: this.signals, deploymentUid: this.deploymentUid,
    });
  }
  revalidate() {
    if (!this.online) throw new Error("edgeUrl not configured");
    return this.online.revalidate(this.fingerprint, { installId: this.installId });
  }
}
