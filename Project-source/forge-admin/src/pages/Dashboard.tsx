import { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { forge } from "@/api/forge";
import { useI18n } from "@/i18n/useI18n";
import { Card, PageHeader } from "@/components/widgets";
import { IconCheck, IconClock, IconLicense, IconRevoked } from "@/components/icons";

const DOT: Record<string, string> = {
  active: "bg-emerald-500", issued: "bg-sky-500", expiring: "bg-amber-500",
  expired: "bg-zinc-400", revoked: "bg-red-500",
};

function Kpi({ icon, chip, label, value, sub }: {
  icon: ReactNode; chip: string; label: string; value: ReactNode; sub?: string;
}) {
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between">
        <span className="text-[13px] text-zinc-500 dark:text-zinc-400">{label}</span>
        <span className={`flex h-9 w-9 items-center justify-center rounded-lg ${chip}`}>{icon}</span>
      </div>
      <div className="mt-3 text-[28px] font-semibold leading-none tracking-tight text-zinc-900 tnum dark:text-zinc-50">{value}</div>
      {sub && <div className="mt-2 text-xs text-zinc-400 tnum dark:text-zinc-500">{sub}</div>}
    </Card>
  );
}

export default function Dashboard() {
  const { t, tAction } = useI18n();
  const { data: lic } = useQuery({ queryKey: ["licenses", "all"], queryFn: () => forge.listLicenses(1, 1000) });
  const { data: prod } = useQuery({ queryKey: ["products", "all"], queryFn: () => forge.listProducts(1, 1000) });
  const { data: cust } = useQuery({ queryKey: ["customers", "all"], queryFn: () => forge.listCustomers(1, 1000) });
  const { data: audit } = useQuery({ queryKey: ["audit", "recent"], queryFn: () => forge.listAudit("?page_size=7") });

  const rows = lic?.data ?? [];
  const total = lic?.total ?? rows.length;
  const by = (s: string) => rows.filter((l) => l.status === s).length;
  const online = rows.filter((l) => l.mode === "online").length;
  const offline = rows.filter((l) => l.mode === "offline").length;
  const statuses = ["active", "issued", "expiring", "expired", "revoked"];
  const statusTotal = Math.max(rows.length, 1);
  const denom = Math.max(rows.length, 1);
  const pct = (n: number) => `${Math.round((n / denom) * 100)}%`;

  return (
    <div>
      <PageHeader title={t("nav.dashboard")} subtitle={t("dash.subtitle")} />

      <div className="space-y-5">
      {/* KPI cards — semantic icon anchors (colour matches the status dots, not decorative) */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Kpi label={t("dash.totalLicenses")} value={total}
             sub={`${t("dash.online")} ${online} · ${t("dash.offline")} ${offline}`}
             icon={<IconLicense size={18} />} chip="bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400" />
        <Kpi label={t("dash.active")} value={by("active") + by("issued")}
             sub={pct(by("active") + by("issued")) + " " + t("dash.ofTotal")}
             icon={<IconCheck size={18} />} chip="bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400" />
        <Kpi label={t("dash.expiring")} value={by("expiring")} sub={t("dash.within30")}
             icon={<IconClock size={18} />} chip="bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400" />
        <Kpi label={t("dash.revoked")} value={by("revoked")}
             sub={pct(by("revoked")) + " " + t("dash.ofTotal")}
             icon={<IconRevoked size={18} />} chip="bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-400" />
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        {/* distribution */}
        <Card className="p-5 lg:col-span-1">
          <h2 className="text-[13px] font-semibold text-zinc-700 dark:text-zinc-200">{t("dash.distribution")}</h2>
          <div className="mt-4 mb-4 flex h-1.5 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
            {statuses.map((s) => by(s) > 0 && <div key={s} className={DOT[s]} style={{ width: `${(by(s) / statusTotal) * 100}%` }} />)}
          </div>
          <ul className="space-y-2">
            {statuses.map((s) => (
              <li key={s} className="flex items-center justify-between text-[13px]">
                <span className="flex items-center gap-2 text-zinc-600 dark:text-zinc-400">
                  <span className={`h-1.5 w-1.5 rounded-full ${DOT[s]}`} />{t(`status.${s}`)}
                </span>
                <span className="font-medium text-zinc-900 tnum dark:text-zinc-100">{by(s)}</span>
              </li>
            ))}
          </ul>
          <div className="mt-5 grid grid-cols-2 gap-x-6 gap-y-3 border-t border-zinc-100 pt-4 text-[13px] dark:border-zinc-800">
            {[[t("dash.online"), online], [t("dash.offline"), offline], [t("nav.products"), prod?.data.length ?? 0], [t("nav.customers"), cust?.data.length ?? 0]].map(([l, v]) => (
              <div key={l as string} className="flex items-center justify-between">
                <span className="text-zinc-500 dark:text-zinc-400">{l}</span>
                <span className="font-medium text-zinc-900 tnum dark:text-zinc-100">{v}</span>
              </div>
            ))}
          </div>
        </Card>

        {/* recent activity */}
        <Card className="p-5 lg:col-span-2">
          <h2 className="text-[13px] font-semibold text-zinc-700 dark:text-zinc-200">{t("dash.recent")}</h2>
          <ul className="mt-2 divide-y divide-zinc-100 dark:divide-zinc-800/70">
            {(audit?.data ?? []).map((a) => (
              <li key={a.id} className="flex items-center justify-between py-2.5 text-[13px]">
                <span className="flex items-center gap-3 truncate">
                  <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${a.result === "success" ? "bg-emerald-500" : "bg-red-500"}`} />
                  <span className="text-zinc-700 dark:text-zinc-300">{tAction(a.action)}</span>
                  <span className="truncate text-zinc-400 dark:text-zinc-500">{a.actor_name || a.actor_type}</span>
                </span>
                <span className="shrink-0 text-zinc-400 tnum dark:text-zinc-600">{a.timestamp.slice(5, 16).replace("T", " ")}</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>
      </div>
    </div>
  );
}
