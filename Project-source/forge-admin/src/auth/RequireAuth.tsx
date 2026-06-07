import { ReactNode } from "react";
import { Navigate, useParams } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { useI18n } from "@/i18n/useI18n";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const { lang } = useParams();
  const { t } = useI18n();
  if (loading) return <div className="p-8 text-zinc-500">{t("common.loading")}</div>;
  if (!user) return <Navigate to={`/${lang ?? "zh"}/login`} replace />;
  return <>{children}</>;
}
