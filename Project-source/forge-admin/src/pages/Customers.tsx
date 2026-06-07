import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { forge, Customer } from "@/api/forge";
import { ApiException } from "@/api/client";
import { useI18n } from "@/i18n/useI18n";
import { Avatar, EmptyState, Modal, PageHeader, Pagination, Primary, RowAction, Table, Td, useFitRows } from "@/components/widgets";
import { Alert, Button, TextField } from "@/components/ui";

export default function Customers() {
  const { t, tError } = useI18n();
  const qc = useQueryClient();
  const SIZE = useFitRows();
  const [page, setPage] = useState(1);
  const { data, isLoading } = useQuery({ queryKey: ["customers", page], queryFn: () => forge.listCustomers(page, SIZE) });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", contact_name: "", contact_email: "", notes: "" });
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () => forge.createCustomer({
      name: form.name, contact_name: form.contact_name || null,
      contact_email: form.contact_email || null, notes: form.notes || null,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["customers"] }); setOpen(false); setForm({ name: "", contact_name: "", contact_email: "", notes: "" }); },
    onError: (e) => setError(e instanceof ApiException ? tError(e.error.code) : tError("SYSTEM_INTERNAL_ERROR")),
  });
  const del = useMutation({
    mutationFn: (id: string) => forge.deleteCustomer(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["customers"] }),
  });

  const rows = data?.data ?? [];
  return (
    <div>
      <PageHeader title={t("nav.customers")} subtitle={t("customers.subtitle")}
                  action={<Button onClick={() => { setError(null); setOpen(true); }}>{t("customers.new")}</Button>} />
      {isLoading ? <EmptyState text={t("common.loading")} /> : rows.length === 0 ? <EmptyState text={t("customers.empty")} /> : (
        <Table head={[t("customers.name"), t("customers.contact"), ""]}
               cols={["52%", "34%", "14%"]} align={["left", "left", "right"]}>
          {rows.map((c: Customer) => (
            <tr key={c.id}>
              <Td>
                <div className="flex items-center gap-3">
                  <Avatar name={c.name} />
                  <Primary title={c.name} sub={c.contact_email || undefined} />
                </div>
              </Td>
              <Td>{c.contact_name || "—"}</Td>
              <Td className="text-right"><RowAction danger onClick={() => del.mutate(c.id)}>{t("common.delete")}</RowAction></Td>
            </tr>
          ))}
        </Table>
      )}
      <Pagination page={page} pageSize={SIZE} total={data?.total ?? 0} onPage={setPage} />
      {open && (
        <Modal title={t("customers.new")} onClose={() => setOpen(false)}>
          <div className="space-y-4">
            {error && <Alert>{error}</Alert>}
            <TextField label={t("customers.name")} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <TextField label={t("customers.contact")} value={form.contact_name} onChange={(e) => setForm({ ...form, contact_name: e.target.value })} />
            <TextField label={t("customers.email")} type="email" value={form.contact_email} onChange={(e) => setForm({ ...form, contact_email: e.target.value })} />
            <TextField label={t("customers.notes")} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="ghost" onClick={() => setOpen(false)}>{t("common.cancel")}</Button>
              <Button onClick={() => create.mutate()} disabled={!form.name || create.isPending}>{t("common.save")}</Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
