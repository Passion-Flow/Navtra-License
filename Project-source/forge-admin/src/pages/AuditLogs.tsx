import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { forge } from "@/api/forge";
import { useI18n } from "@/i18n/useI18n";
import { Badge, EmptyState, PageHeader, Pagination, Select, Table, Td, useFitRows } from "@/components/widgets";

const ACTIONS = ["", "login", "license.issue_online", "license.issue_offline", "license.activated",
  "license.revoke", "license.seat_exceeded", "crl.generate", "product.create", "customer.create"];

export default function AuditLogs() {
  const { t, tAction } = useI18n();
  const SIZE = useFitRows(56, 300);
  const [action, setAction] = useState("");
  const [result, setResult] = useState("");
  const [page, setPage] = useState(1);
  const qs = `?page=${page}&page_size=${SIZE}${action ? `&action=${action}` : ""}${result ? `&result=${result}` : ""}`;
  const { data, isLoading } = useQuery({ queryKey: ["audit", qs], queryFn: () => forge.listAudit(qs) });
  const rows = data?.data ?? [];
  const onFilter = (fn: (v: string) => void) => (v: string) => { setPage(1); fn(v); };

  return (
    <div>
      <PageHeader title={t("nav.audit")} subtitle={t("audit.subtitle")} />
      <div className="mb-4 flex gap-3">
        <div className="w-64"><Select label={t("audit.action")} value={action} onChange={onFilter(setAction)}
          options={ACTIONS.map((a) => ({ value: a, label: a ? tAction(a) : t("audit.all") }))} /></div>
        <div className="w-40"><Select label={t("audit.result")} value={result} onChange={onFilter(setResult)}
          options={[{ value: "", label: t("audit.all") }, { value: "success", label: t("audit.success") }, { value: "failure", label: t("audit.failure") }]} /></div>
      </div>
      {isLoading ? <EmptyState text={t("common.loading")} /> : rows.length === 0 ? <EmptyState text={t("audit.empty")} /> : (
        <Table head={[t("audit.time"), t("audit.actor"), t("audit.actionCol"), t("audit.resource"), t("audit.resultCol")]}
               cols={["20%", "20%", "22%", "24%", "14%"]}>
          {rows.map((a) => (
            <tr key={a.id}>
              <Td className="whitespace-nowrap text-xs">{a.timestamp.slice(0, 19).replace("T", " ")}</Td>
              <Td>{a.actor_name || a.actor_type}</Td>
              <Td>{tAction(a.action)}</Td>
              <Td className="text-xs">{a.resource_type ? `${a.resource_type}:${(a.resource_id || "").slice(0, 12)}` : "—"}</Td>
              <Td><Badge status={a.result === "success" ? "active" : "revoked"} label={t(`audit.${a.result}`)} /></Td>
            </tr>
          ))}
        </Table>
      )}
      <Pagination page={page} pageSize={SIZE} total={data?.total ?? 0} onPage={setPage} />
    </div>
  );
}
