import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiException } from "@/api/client";
import { Alert, Button, TextField } from "@/components/ui";
import { LangSwitcher } from "@/components/LangSwitcher";
import { ThemeSwitcher } from "@/components/ThemeSwitcher";
import { Logo } from "@/components/Logo";
import { useI18n } from "@/i18n/useI18n";
import { useAuth } from "@/auth/AuthContext";
import { langToUrlSeg } from "@/i18n";

export default function Login() {
  const { t, tError, lang } = useI18n();
  const { refresh } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [need2fa, setNeed2fa] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const canSubmit =
    email.trim() !== "" && password.trim() !== "" && (!need2fa || code.trim() !== "");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    try {
      await api.post("/auth/login", { email, password, code: code || null });
      await refresh();
      navigate(`/${langToUrlSeg(lang)}/dashboard`);
    } catch (err) {
      if (err instanceof ApiException) {
        if (err.error.code === "AUTH_2FA_REQUIRED") {
          setNeed2fa(true);
          setError(tError("AUTH_2FA_REQUIRED"));
        } else {
          setError(tError(err.error.code));
        }
      } else {
        setError(tError("SYSTEM_INTERNAL_ERROR"));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center px-4">
      <div className="absolute right-6 top-5 flex items-center gap-2.5">
        <LangSwitcher />
        <ThemeSwitcher />
      </div>

      <div className="w-full max-w-[22rem]">
        <div className="mb-6 flex items-center">
          <Logo size={30} />
        </div>
        <div className="rounded-xl border border-zinc-200 bg-white p-7 dark:border-zinc-800 dark:bg-[#131315]">
          <h1 className="text-xl font-semibold tracking-tight text-zinc-900 dark:text-white">{t("login.title")}</h1>
          <p className="mt-1.5 text-sm text-zinc-500 dark:text-zinc-400">{t("login.welcome")}</p>
          <form onSubmit={submit} className="mt-6 space-y-4">
            {error && <Alert>{error}</Alert>}
            <TextField label={t("login.email")} type="email" autoComplete="username"
                       value={email} onChange={(e) => setEmail(e.target.value)}
                       placeholder={t("login.emailPlaceholder")} />
            <TextField label={t("login.password")} type="password" autoComplete="current-password"
                       value={password} onChange={(e) => setPassword(e.target.value)}
                       placeholder={t("login.passwordPlaceholder")} />
            {need2fa && (
              <TextField label={t("login.code")} inputMode="numeric" value={code}
                         onChange={(e) => setCode(e.target.value)} placeholder={t("login.codeHint")} />
            )}
            <Button type="submit" disabled={busy || !canSubmit} className="w-full">
              {busy ? t("common.loading") : t("login.submit")}
            </Button>
          </form>
        </div>
        <p className="mt-5 text-center text-xs text-zinc-400 dark:text-zinc-600">Forge · License Authority</p>
      </div>
    </div>
  );
}
