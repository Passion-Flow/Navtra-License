// Router with URL path-style i18n (/<lang>/...). Root `/` detects the browser language and
// redirects to /<lang>/ (i18n.md §4.5). Authenticated pages live under AppLayout (sidebar).
// Vendor-internal tool: no self-service registration, no forgot-password.
import { ReactNode } from "react";
import { Navigate, Route, Routes, useParams } from "react-router-dom";
import { AuthProvider } from "@/auth/AuthContext";
import { ThemeProvider } from "@/theme/ThemeProvider";
import { RequireAuth } from "@/auth/RequireAuth";
import { AppLayout } from "@/components/AppLayout";
import { langToUrlSeg, SUPPORTED_LANGS, urlSegToLang } from "@/i18n";
import Login from "@/pages/Login";
import TwoFASetup from "@/pages/TwoFASetup";
import Dashboard from "@/pages/Dashboard";
import Products from "@/pages/Products";
import Customers from "@/pages/Customers";
import Users from "@/pages/Users";
import Profile from "@/pages/Profile";
import Issue from "@/pages/Issue";
import Licenses from "@/pages/Licenses";
import AuditLogs from "@/pages/AuditLogs";
import Settings from "@/pages/Settings";

function detectLang(): string {
  const nav = navigator.language?.toLowerCase() ?? "";
  const match = SUPPORTED_LANGS.find((l) => nav.startsWith(l.toLowerCase().slice(0, 2)));
  return langToUrlSeg(match ?? "zh-CN");
}

function LangGate({ children }: { children: ReactNode }) {
  const { lang } = useParams();
  const normalized = langToUrlSeg(urlSegToLang(lang));
  if (lang !== normalized) return <Navigate to={`/${normalized}`} replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<Navigate to={`/${detectLang()}/login`} replace />} />
          <Route
            path="/:lang/*"
            element={
              <LangGate>
                <Routes>
                  <Route path="login" element={<Login />} />
                  <Route element={<RequireAuth><AppLayout /></RequireAuth>}>
                    <Route path="dashboard" element={<Dashboard />} />
                    <Route path="account/profile" element={<Profile />} />
                    <Route path="account/2fa" element={<TwoFASetup />} />
                    <Route path="products" element={<Products />} />
                    <Route path="customers" element={<Customers />} />
                    <Route path="users" element={<Users />} />
                    <Route path="issue" element={<Issue />} />
                    <Route path="licenses" element={<Licenses />} />
                    <Route path="audit-logs" element={<AuditLogs />} />
                    <Route path="settings" element={<Settings />} />
                  </Route>
                  <Route path="*" element={<Navigate to="login" replace />} />
                </Routes>
              </LangGate>
            }
          />
        </Routes>
      </AuthProvider>
    </ThemeProvider>
  );
}
