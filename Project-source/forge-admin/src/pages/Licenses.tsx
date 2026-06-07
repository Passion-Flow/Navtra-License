import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { forge, License } from "@/api/forge";
import { useI18n } from "@/i18n/useI18n";
import { Badge, EmptyState, PageHeader, Pagination, RowAction, Table, Td, useFitRows } from "@/components/widgets";
import { useAuth } from "@/auth/AuthContext";

function mask(id: string) {
  return id.length > 8 ? `${id.slice(0, 4)}****${id.slice(-4)}` : id;
}

export default function Licenses() {
  const { t } = useI18n();
  const { has } = useAuth();
  const qc = useQueryClient();
  const SIZE = useFitRows();
  const [page, setPage] = useState(1);
  const { data, isLoading } = useQuery({ queryKey: ["licenses", page], queryFn: () => forge.listLicenses(page, SIZE) });
  const { data: products } = useQuery({ queryKey: ["products", "all"], queryFn: () => forge.listProducts(1, 1000) });
  const { data: customers } = useQuery({ queryKey: ["customers", "all"], queryFn: () => forge.listCustomers(1, 1000) });

  const pMap = new Map(products?.data.map((p) => [p.id, p.slug]));
  const cMap = new Map(customers?.data.map((c) => [c.id, c.name]));

  const revoke = useMutation({
    mutationFn: (id: string) => forge.revokeLicense(id, "revoked from console"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["licenses"] }),
  });
  const del = useMutation({
    mutationFn: (id: string) => forge.deleteLicense(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["licenses"] }),
  });

  const rows = data?.data ?? [];
  const canRevoke = has("platform.license.revoke");
  const canDelete = has("platform.license.delete");

  return (
    <div>
      <PageHeader title={t("nav.licenses")} subtitle={t("licenses.subtitle")} />
      {isLoading ? <EmptyState text={t("common.loading")} /> : rows.length === 0 ? <EmptyState text={t("licenses.empty")} /> : (
        <Table
          head={[t("licenses.id"), t("licenses.customer"), t("licenses.product"), t("licenses.mode"), t("licenses.term"), t("licenses.status"), t("licenses.seats"), t("licenses.until"), ""]}
          cols={["11%", "18%", "15%", "8%", "9%", "11%", "7%", "11%", "10%"]}
          align={["left", "left", "left", "left", "left", "left", "left", "left", "right"]}
        >
          {rows.map((l: License) => (
            <tr key={l.id}>
              <Td className="font-mono text-xs">{mask(l.license_id)}</Td>
              <Td>{cMap.get(l.customer_id) || "—"}</Td>
              <Td className="font-mono text-xs">{pMap.get(l.product_id) || "—"}</Td>
              <Td>{t(`issue.${l.mode}`)}</Td>
              <Td>{t(`issue.term_${l.term_preset}`)}</Td>
              <Td><Badge status={l.status} label={t(`status.${l.status}`)} /></Td>
              <Td>{l.mode === "online" ? `${l.seat_used}/${l.seat_limit}` : "—"}</Td>
              <Td className="text-xs">{l.active_until ? l.active_until.slice(0, 10) : t("issue.term_perpetual")}</Td>
              <Td className="whitespace-nowrap text-right">
                {canRevoke && l.status !== "revoked" && (
                  <RowAction onClick={() => revoke.mutate(l.id)}>{t("licenses.revoke")}</RowAction>
                )}
                {canDelete && <RowAction danger onClick={() => del.mutate(l.id)}>{t("common.delete")}</RowAction>}
              </Td>
            </tr>
          ))}
        </Table>
      )}
      <Pagination page={page} pageSize={SIZE} total={data?.total ?? 0} onPage={setPage} />
    </div>
  );
}
