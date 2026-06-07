import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { forge } from "@/api/forge";
import { ApiException } from "@/api/client";
import { useI18n } from "@/i18n/useI18n";
import { Card, CopyBox, PageHeader, Select } from "@/components/widgets";
import { Alert, Button, TextField } from "@/components/ui";

const TERMS = ["1m", "3m", "6m", "1y", "3y", "5y", "perpetual"];

// The copied text is a fixed delivery format sent to the customer (English labels,
// independent of UI language): code + validity range (start ~ end 23:59:59).
const pad = (n: number) => String(n).padStart(2, "0");
function nowStamp() {
  const d = new Date();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}
function validityRange(until: string | null) {
  const end = until ? `${until.slice(0, 10)} 23:59:59` : "Perpetual";
  return `${nowStamp()} ～ ${end}`;
}
function onlineCopyText(code: string, until: string | null) {
  return `Online Code:\n\n${code}\n\nValidity Period：${validityRange(until)}`;
}
function offlineCopyText(id: string, blob: string, until: string | null) {
  return `ID: ${id}\n\nOffline Code:\n\n${blob}\n\nValidity Period：${validityRange(until)}`;
}

// A valid deployment ID is the SHA-256 hex fingerprint emitted by the Verifier SDK (64 hex chars).
const FP_RE = /^[0-9a-f]{64}$/;

export default function Issue() {
  const { t, tError } = useI18n();
  const { data: products } = useQuery({ queryKey: ["products", "all"], queryFn: () => forge.listProducts(1, 1000) });
  const { data: customers } = useQuery({ queryKey: ["customers", "all"], queryFn: () => forge.listCustomers(1, 1000) });
  const [mode, setMode] = useState<"online" | "offline">("online");
  const [f, setF] = useState({ customer_id: "", product_id: "", term_preset: "1y", subscription: "Enterprise", seat_limit: "1", deployment_id: "", features: "" });
  const [result, setResult] = useState<{ kind: "online" | "offline"; value: string; until: string | null } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const set = (k: string, v: string) => setF({ ...f, [k]: v });

  async function generate() {
    setBusy(true); setError(null); setResult(null);
    const base = {
      customer_id: f.customer_id, product_id: f.product_id, term_preset: f.term_preset,
      subscription: f.subscription, features: f.features.split(",").map((s) => s.trim()).filter(Boolean),
    };
    try {
      if (mode === "online") {
        const r = await forge.issueOnline({ ...base, seat_limit: Number(f.seat_limit) || 1 });
        setResult({ kind: "online", value: onlineCopyText(r.online_code, r.active_until), until: r.active_until });
      } else {
        const r = await forge.issueOffline({ ...base, deployment_id: f.deployment_id });
        setResult({ kind: "offline", value: offlineCopyText(f.deployment_id, r.offline_blob, r.active_until), until: r.active_until });
      }
    } catch (e) {
      setError(e instanceof ApiException ? tError(e.error.code) : tError("SYSTEM_INTERNAL_ERROR"));
    } finally { setBusy(false); }
  }

  const depInvalid = mode === "offline" && f.deployment_id !== "" && !FP_RE.test(f.deployment_id.trim());
  const canSubmit = f.customer_id && f.product_id && (mode === "online" || FP_RE.test(f.deployment_id.trim()));

  return (
    <div>
      <PageHeader title={t("nav.issue")} subtitle={t("issue.subtitle")} />
      <Card className="p-6">
        <div className="mb-5 inline-flex rounded-lg bg-zinc-100 p-1 dark:bg-zinc-800">
          {(["online", "offline"] as const).map((m) => (
            <button key={m} onClick={() => { setMode(m); setResult(null); }}
              className={`rounded-md px-5 py-1.5 text-sm font-medium transition-colors ${mode === m ? "bg-white text-zinc-900 shadow-sm dark:bg-zinc-700 dark:text-white" : "text-zinc-500 hover:text-zinc-700 dark:text-zinc-400"}`}>
              {t(`issue.${m}`)}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Select label={t("issue.customer")} value={f.customer_id} onChange={(v) => set("customer_id", v)}
            placeholder="—" options={(customers?.data ?? []).map((c) => ({ value: c.id, label: c.name }))} />
          <Select label={t("issue.product")} value={f.product_id} onChange={(v) => set("product_id", v)}
            placeholder="—" options={(products?.data ?? []).map((p) => ({ value: p.id, label: `${p.name} (${p.slug})` }))} />
          <Select label={t("issue.term")} value={f.term_preset} onChange={(v) => set("term_preset", v)}
            options={TERMS.map((tm) => ({ value: tm, label: t(`issue.term_${tm}`) }))} />
          <TextField label={t("issue.subscription")} value={f.subscription} onChange={(e) => set("subscription", e.target.value)} />
          {mode === "online" && (
            <TextField label={t("issue.seat")} type="number" min={1} value={f.seat_limit} onChange={(e) => set("seat_limit", e.target.value)} />
          )}
          {mode === "offline" && (
            <TextField label={t("issue.deploymentId")} value={f.deployment_id} onChange={(e) => set("deployment_id", e.target.value)}
              placeholder={t("issue.deploymentIdHint")} error={depInvalid ? t("issue.deploymentIdInvalid") : undefined} />
          )}
          <TextField label={t("issue.featuresCsv")} value={f.features} onChange={(e) => set("features", e.target.value)} placeholder="sso, data_push" />
        </div>

        {error && <div className="mt-4"><Alert>{error}</Alert></div>}
        <div className="mt-5">
          <Button onClick={generate} disabled={!canSubmit || busy}>{busy ? t("common.loading") : t("issue.generate")}</Button>
        </div>

        {result && (
          <div className="mt-6 space-y-2 border-t border-zinc-200 pt-5 dark:border-zinc-800">
            <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
              {result.kind === "online" ? t("issue.onlineCode") : t("issue.offlineBlob")}
            </p>
            <CopyBox value={result.value} />
            <p className="text-xs text-zinc-400">{t("issue.copyHint")}</p>
          </div>
        )}
      </Card>
    </div>
  );
}
