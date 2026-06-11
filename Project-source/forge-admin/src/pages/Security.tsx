// 反克隆安全页（design 07）：同一 License 出现超 seat 的不同在线身份 → 克隆/共享告警列表 +
// 点开看该 License 当前在线绑定（指纹/部署UID/install_id 脱敏 + 心跳）。
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { forge, type CloneAlert } from "@/api/forge";
import { useI18n } from "@/i18n/useI18n";
import { Badge, EmptyState, PageHeader, Select, Table, Td } from "@/components/widgets";
import { Button } from "@/components/ui";

function Bindings({ licenseId }: { licenseId: string }) {
  const { t } = useI18n();
  const { data, isLoading } = useQuery({
    queryKey: ["bindings", licenseId],
    queryFn: () => forge.listBindings(licenseId),
  });
  const rows = data?.data ?? [];
  if (isLoading) return <div className="px-4 py-3 text-xs text-zinc-400">{t("common.loading")}</div>;
  if (rows.length === 0) return <div className="px-4 py-3 text-xs text-zinc-400">{t("security.noBindings")}</div>;
  return (
    <div className="bg-zinc-50 px-4 py-3 dark:bg-zinc-900/40">
      <Table head={[t("security.identity"), t("security.deploymentUid"), t("security.installId"),
                    t("security.bindingStatus"), t("security.lastSeen")]}
             cols={["24%", "26%", "20%", "14%", "16%"]}>
        {rows.map((b) => (
          <tr key={b.id}>
            <Td className="font-mono text-xs">{b.fingerprint || "—"}</Td>
            <Td className="font-mono text-xs">{b.deployment_uid || "—"}</Td>
            <Td className="font-mono text-xs">{b.install_id || "—"}</Td>
            <Td><Badge status={b.status === "active" ? "active" : "revoked"} label={b.status} /></Td>
            <Td className="whitespace-nowrap text-xs">{(b.last_seen_at || "").slice(0, 19).replace("T", " ") || "—"}</Td>
          </tr>
        ))}
      </Table>
    </div>
  );
}

export default function Security() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [status, setStatus] = useState("open");
  const [open, setOpen] = useState<string | null>(null);
  const { data, isLoading } = useQuery({
    queryKey: ["clone-alerts", status],
    queryFn: () => forge.listCloneAlerts(status),
    refetchInterval: 15_000,
  });
  const resolve = useMutation({
    mutationFn: (id: string) => forge.resolveCloneAlert(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["clone-alerts"] }),
  });
  const rows: CloneAlert[] = data?.data ?? [];

  return (
    <div>
      <PageHeader title={t("nav.security")} subtitle={t("security.subtitle")} />
      <div className="mb-4 w-48">
        <Select label={t("security.status")} value={status} onChange={setStatus}
          options={[{ value: "open", label: t("security.open") },
                    { value: "resolved", label: t("security.resolved") },
                    { value: "", label: t("security.all") }]} />
      </div>
      {isLoading ? <EmptyState text={t("common.loading")} />
        : rows.length === 0 ? <EmptyState text={t("security.empty")} /> : (
        <Table head={[t("security.detected"), t("security.license"), t("security.identities"),
                      t("security.statusCol"), ""]}
               cols={["20%", "26%", "18%", "14%", "22%"]}>
          {rows.map((a) => (
            <>
              <tr key={a.id}>
                <Td className="whitespace-nowrap text-xs">{(a.detected_at || "").slice(0, 19).replace("T", " ")}</Td>
                <Td className="font-mono text-xs">{a.license_id?.slice(0, 18)}…</Td>
                <Td><span className="font-semibold text-amber-600">{a.alive_identities}</span> / {a.seat_limit}</Td>
                <Td><Badge status={a.status === "open" ? "revoked" : "active"} label={t(`security.${a.status}`)} /></Td>
                <Td>
                  <div className="flex gap-2">
                    <Button variant="ghost" onClick={() => setOpen(open === a.id ? null : a.license_id)}>
                      {t("security.viewBindings")}
                    </Button>
                    {a.status === "open" && (
                      <Button variant="ghost" onClick={() => resolve.mutate(a.id)} disabled={resolve.isPending}>
                        {t("security.resolve")}
                      </Button>
                    )}
                  </div>
                </Td>
              </tr>
              {open === a.license_id && (
                <tr key={`${a.id}-b`}>
                  <td colSpan={5} className="p-0"><Bindings licenseId={a.license_id} /></td>
                </tr>
              )}
            </>
          ))}
        </Table>
      )}
    </div>
  );
}
