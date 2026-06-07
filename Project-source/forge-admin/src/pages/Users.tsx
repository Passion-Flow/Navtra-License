import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { forge, OperatorUser } from "@/api/forge";
import { ApiException } from "@/api/client";
import { useI18n } from "@/i18n/useI18n";
import { Avatar, Badge, EmptyState, Modal, PageHeader, Pagination, Primary, RowAction, Select, Table, Td, useFitRows } from "@/components/widgets";
import { Alert, Button, TextField } from "@/components/ui";

const ROLES = ["super_admin", "admin", "auditor"];

export default function Users() {
  const { t, tError } = useI18n();
  const qc = useQueryClient();
  const SIZE = useFitRows();
  const [page, setPage] = useState(1);
  const { data, isLoading } = useQuery({ queryKey: ["users", page], queryFn: () => forge.listUsers(page, SIZE) });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ email: "", username: "", role: "admin" });
  const [error, setError] = useState<string | null>(null);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["users"] });
  const onErr = (e: unknown) => setError(e instanceof ApiException ? tError(e.error.code) : tError("SYSTEM_INTERNAL_ERROR"));

  const create = useMutation({
    mutationFn: () => forge.createUser({ email: form.email, username: form.username, role: form.role }),
    onSuccess: () => { invalidate(); setOpen(false); setForm({ email: "", username: "", role: "admin" }); },
    onError: onErr,
  });
  const toggle = useMutation({
    mutationFn: (u: OperatorUser) => forge.updateUser(u.id, { is_active: !u.is_active }),
    onSuccess: invalidate, onError: onErr,
  });
  const reset = useMutation({
    mutationFn: (id: string) => forge.resetUserPassword(id),  // defaults to email (§11.1)
    onSuccess: invalidate, onError: onErr,
  });
  const del = useMutation({
    mutationFn: (id: string) => forge.deleteUser(id),
    onSuccess: invalidate, onError: onErr,
  });

  const rows = data?.data ?? [];
  return (
    <div>
      <PageHeader title={t("nav.users")} subtitle={t("users.subtitle")}
                  action={<Button onClick={() => { setError(null); setOpen(true); }}>{t("users.new")}</Button>} />
      {error && !open && <div className="mb-3"><Alert>{error}</Alert></div>}
      {isLoading ? <EmptyState text={t("common.loading")} /> : rows.length === 0 ? <EmptyState text={t("users.empty")} /> : (
        <Table head={[t("users.operator"), t("users.role"), t("users.status"), ""]}
               cols={["40%", "20%", "16%", "24%"]} align={["left", "left", "left", "right"]}>
          {rows.map((u: OperatorUser) => (
            <tr key={u.id}>
              <Td>
                <div className="flex items-center gap-3">
                  <Avatar name={u.username} />
                  <Primary title={u.username} sub={u.email} />
                </div>
              </Td>
              <Td><Badge status={u.role === "super_admin" ? "active" : u.role === "auditor" ? "pending" : "online"} label={t(`users.role_${u.role}`)} /></Td>
              <Td><Badge status={u.is_active ? "active" : "revoked"} label={u.is_active ? t("users.active") : t("users.disabled")} /></Td>
              <Td className="text-right">
                <div className="inline-flex gap-3">
                  <RowAction onClick={() => toggle.mutate(u)}>{u.is_active ? t("users.disable") : t("users.enable")}</RowAction>
                  <RowAction onClick={() => reset.mutate(u.id)}>{t("users.reset")}</RowAction>
                  <RowAction danger onClick={() => del.mutate(u.id)}>{t("common.delete")}</RowAction>
                </div>
              </Td>
            </tr>
          ))}
        </Table>
      )}
      <Pagination page={page} pageSize={SIZE} total={data?.total ?? 0} onPage={setPage} />
      {open && (
        <Modal title={t("users.new")} onClose={() => setOpen(false)}>
          <div className="space-y-4">
            {error && <Alert>{error}</Alert>}
            <TextField label={t("users.email")} type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            <TextField label={t("users.username")} value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
            <Select label={t("users.role")} value={form.role} onChange={(v) => setForm({ ...form, role: v })}
                    options={ROLES.map((r) => ({ value: r, label: t(`users.role_${r}`) }))} />
            <p className="text-[12px] text-zinc-500">{t("users.pwhint")}</p>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="ghost" onClick={() => setOpen(false)}>{t("common.cancel")}</Button>
              <Button onClick={() => create.mutate()} disabled={!form.email || !form.username || create.isPending}>{t("common.save")}</Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
