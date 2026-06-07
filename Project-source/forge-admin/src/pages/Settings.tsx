import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { forge } from "@/api/forge";
import { useI18n } from "@/i18n/useI18n";
import { Badge, Card, CopyBox, EmptyState, PageHeader, RowAction, Table, Td } from "@/components/widgets";
import { Button } from "@/components/ui";

export default function Settings() {
  const { t } = useI18n();
  const { data, isLoading } = useQuery({ queryKey: ["keys"], queryFn: forge.listKeys });
  const [pub, setPub] = useState<string | null>(null);
  const exportPub = useMutation({
    mutationFn: (keyId: string) => forge.exportPublic(keyId),
    onSuccess: (r) => setPub(r.data.public_key),
  });
  const crl = useMutation({ mutationFn: () => forge.generateCrl() });

  return (
    <div className="space-y-8">
      <PageHeader title={t("nav.settings")} subtitle={t("settings.subtitle")} />

      <section>
        <h2 className="mb-3 text-sm font-semibold text-zinc-800 dark:text-zinc-100">{t("settings.keys")}</h2>
        {isLoading ? <EmptyState text={t("common.loading")} /> : (
          <Table
            head={[t("settings.keyId"), t("settings.purpose"), t("settings.alg"), t("settings.activeCol"), ""]}
            cols={["36%", "20%", "16%", "14%", "14%"]}
            align={["left", "left", "left", "left", "right"]}
          >
            {(data?.data ?? []).map((k) => (
              <tr key={k.id}>
                <Td className="font-mono text-xs">{k.key_id}</Td>
                <Td>{k.purpose}</Td>
                <Td>{k.alg}</Td>
                <Td><Badge status={k.is_active ? "active" : "expired"} label={k.is_active ? t("common.yes") : t("common.no")} /></Td>
                <Td className="text-right"><RowAction onClick={() => exportPub.mutate(k.key_id)}>{t("settings.exportPublic")}</RowAction></Td>
              </tr>
            ))}
          </Table>
        )}
        <p className="mt-2 text-xs text-zinc-400 dark:text-zinc-500">{t("settings.privateNote")}</p>
        {pub && (
          <div className="mt-4">
            <p className="mb-1.5 text-[13px] font-medium text-zinc-600 dark:text-zinc-400">{t("settings.publicKey")}</p>
            <CopyBox value={pub} />
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold text-zinc-800 dark:text-zinc-100">{t("settings.crl")}</h2>
        <Card className="p-6">
          <p className="mb-4 text-sm text-zinc-500 dark:text-zinc-400">{t("settings.crlNote")}</p>
          <Button onClick={() => crl.mutate()} disabled={crl.isPending}>{t("settings.generateCrl")}</Button>
          {crl.data && (
            <p className="mt-3 text-sm text-emerald-600 dark:text-emerald-400">
              {t("settings.crlDone")} v{crl.data.data.version} · {crl.data.data.entry_count} {t("settings.entries")}
            </p>
          )}
        </Card>
      </section>
    </div>
  );
}
