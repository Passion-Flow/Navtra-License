import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { forge, Product } from "@/api/forge";
import { ApiException } from "@/api/client";
import { useI18n } from "@/i18n/useI18n";
import { Avatar, Badge, EmptyState, Modal, PageHeader, Pagination, Primary, RowAction, Table, Td, useFitRows } from "@/components/widgets";
import { Alert, Button, TextField } from "@/components/ui";

export default function Products() {
  const { t, tError } = useI18n();
  const qc = useQueryClient();
  const SIZE = useFitRows();
  const [page, setPage] = useState(1);
  const { data, isLoading } = useQuery({ queryKey: ["products", page], queryFn: () => forge.listProducts(page, SIZE) });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ slug: "", name: "", description: "", features: "" });
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () => forge.createProduct({
      slug: form.slug, name: form.name, description: form.description || null,
      features_template: form.features.split(",").map((s) => s.trim()).filter(Boolean),
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["products"] }); setOpen(false); setForm({ slug: "", name: "", description: "", features: "" }); },
    onError: (e) => setError(e instanceof ApiException ? tError(e.error.code) : tError("SYSTEM_INTERNAL_ERROR")),
  });
  const del = useMutation({
    mutationFn: (id: string) => forge.deleteProduct(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["products"] }),
  });

  const rows = data?.data ?? [];
  return (
    <div>
      <PageHeader title={t("nav.products")} subtitle={t("products.subtitle")}
                  action={<Button onClick={() => { setError(null); setOpen(true); }}>{t("products.new")}</Button>} />
      {isLoading ? <EmptyState text={t("common.loading")} /> : rows.length === 0 ? <EmptyState text={t("products.empty")} /> : (
        <Table head={[t("products.name"), t("products.features"), t("products.active"), ""]}
               cols={["48%", "18%", "18%", "16%"]} align={["left", "left", "left", "right"]}>
          {rows.map((p: Product) => (
            <tr key={p.id}>
              <Td>
                <div className="flex items-center gap-3">
                  <Avatar name={p.name} />
                  <Primary title={p.name} sub={<span className="font-mono">{p.slug}</span>} />
                </div>
              </Td>
              <Td className="tnum">{p.features_template.length}</Td>
              <Td><Badge status={p.is_active ? "active" : "expired"} label={p.is_active ? t("common.yes") : t("common.no")} /></Td>
              <Td className="text-right"><RowAction danger onClick={() => del.mutate(p.id)}>{t("common.delete")}</RowAction></Td>
            </tr>
          ))}
        </Table>
      )}
      <Pagination page={page} pageSize={SIZE} total={data?.total ?? 0} onPage={setPage} />

      {open && (
        <Modal title={t("products.new")} onClose={() => setOpen(false)}>
          <div className="space-y-4">
            {error && <Alert>{error}</Alert>}
            <TextField label={t("products.slug")} value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} placeholder="DIFY_ENTERPRISE" />
            <TextField label={t("products.name")} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <TextField label={t("products.featuresCsv")} value={form.features} onChange={(e) => setForm({ ...form, features: e.target.value })} placeholder="sso, data_push" />
            <TextField label={t("products.description")} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="ghost" onClick={() => setOpen(false)}>{t("common.cancel")}</Button>
              <Button onClick={() => create.mutate()} disabled={!form.slug || !form.name || create.isPending}>{t("common.save")}</Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
