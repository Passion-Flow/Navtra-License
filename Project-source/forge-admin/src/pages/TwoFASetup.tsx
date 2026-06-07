import { useState } from "react";
import { api, ApiException } from "@/api/client";
import { Alert, Button, TextField } from "@/components/ui";
import { Card, PageHeader } from "@/components/widgets";
import { useI18n } from "@/i18n/useI18n";

interface SetupOut { secret: string; provisioning_uri: string }

export default function TwoFASetup() {
  const { t, tError } = useI18n();
  const [setup, setSetup] = useState<SetupOut | null>(null);
  const [code, setCode] = useState("");
  const [backup, setBackup] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function begin() {
    setError(null);
    try {
      setSetup(await api.post<SetupOut>("/auth/2fa:setup"));
    } catch (err) {
      setError(err instanceof ApiException ? tError(err.error.code) : tError("SYSTEM_INTERNAL_ERROR"));
    }
  }

  async function verify(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const res = await api.post<{ data: { backup_codes: string[] } }>("/auth/2fa:verify", { code });
      setBackup(res.data.backup_codes);
    } catch (err) {
      setError(err instanceof ApiException ? tError(err.error.code) : tError("SYSTEM_INTERNAL_ERROR"));
    }
  }

  return (
    <div className="max-w-xl">
      <PageHeader title={t("twofa.title")} subtitle={t("twofa.subtitle")} />
      <Card className="space-y-4 p-6">
        {error && <Alert>{error}</Alert>}
        {!setup && <Button onClick={begin}>{t("twofa.enable")}</Button>}
        {setup && !backup && (
          <form onSubmit={verify} className="space-y-4">
            <p className="text-sm text-zinc-600 dark:text-zinc-400">{t("twofa.setupHint")}</p>
            <div className="break-all rounded-md bg-zinc-100 p-3 font-mono text-sm text-zinc-700 dark:bg-zinc-800/60 dark:text-zinc-300">
              {t("twofa.secret")}: {setup.secret}
            </div>
            <TextField label={t("twofa.code")} inputMode="numeric" value={code}
                       onChange={(e) => setCode(e.target.value)} required />
            <Button type="submit">{t("common.submit")}</Button>
          </form>
        )}
        {backup && (
          <div className="space-y-2">
            <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{t("twofa.backupTitle")}</p>
            <ul className="grid grid-cols-2 gap-2 rounded-md bg-zinc-100 p-3 font-mono text-sm text-zinc-700 dark:bg-zinc-800/60 dark:text-zinc-300">
              {backup.map((c) => <li key={c}>{c}</li>)}
            </ul>
          </div>
        )}
      </Card>
    </div>
  );
}
