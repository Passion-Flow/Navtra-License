import { ReactNode } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useI18n } from "@/i18n/useI18n";
import { useAuth } from "@/auth/AuthContext";
import { LangSwitcher } from "./LangSwitcher";
import { ThemeSwitcher } from "./ThemeSwitcher";
import { Logo } from "./Logo";
import { Dropdown, DropdownItem } from "./Dropdown";
import {
  IconAudit, IconChevron, IconCustomer, IconDashboard, IconIssue, IconLicense,
  IconLogout, IconProduct, IconRevoked, IconSettings, IconUser,
} from "./icons";

const NAV: { key: string; to: string; perm?: string; icon: (p: { size?: number }) => ReactNode }[] = [
  { key: "dashboard", to: "dashboard", icon: IconDashboard },
  { key: "products", to: "products", perm: "platform.product.read", icon: IconProduct },
  { key: "customers", to: "customers", perm: "platform.customer.read", icon: IconCustomer },
  { key: "issue", to: "issue", perm: "platform.license.issue", icon: IconIssue },
  { key: "licenses", to: "licenses", perm: "platform.license.read", icon: IconLicense },
  { key: "security", to: "security", perm: "platform.license.read", icon: IconRevoked },
  { key: "audit", to: "audit-logs", perm: "platform.audit.read", icon: IconAudit },
  { key: "users", to: "users", perm: "platform.user.read", icon: IconUser },
  { key: "settings", to: "settings", perm: "system.key.read", icon: IconSettings },
];

export function AppLayout() {
  const { t, lang } = useI18n();
  const { user, logout, has } = useAuth();
  const navigate = useNavigate();
  const seg = lang === "en" ? "en" : "zh";
  const initial = (user?.username || "?").charAt(0).toUpperCase();

  async function onLogout() {
    await logout();
    navigate(`/${seg}/login`);
  }

  return (
    // fixed shell: sidebar + header stay; only the content area scrolls
    <div className="flex h-screen overflow-hidden">
      <aside className="flex w-60 shrink-0 flex-col border-r border-zinc-200 bg-white dark:border-zinc-800 dark:bg-[#0e0e10]">
        <div className="px-5 py-5">
          <Logo size={26} />
        </div>
        <nav className="flex-1 space-y-0.5 overflow-y-auto px-3">
          {NAV.filter((n) => !n.perm || has(n.perm)).map((n) => {
            const Icon = n.icon;
            return (
              <NavLink
                key={n.key}
                to={`/${seg}/${n.to}`}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-lg px-3 py-2 text-[13px] font-medium transition-colors ${
                    isActive
                      ? "bg-brand/10 text-brand dark:bg-brand/15 dark:text-brand"
                      : "text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-900 dark:hover:text-zinc-100"
                  }`
                }
              >
                <Icon size={17} />
                {t(`nav.${n.key}`)}
              </NavLink>
            );
          })}
        </nav>

        {/* user profile pinned to the sidebar bottom (menu opens upward) */}
        <div className="border-t border-zinc-200 p-3 dark:border-zinc-800">
          <Dropdown
            align="left"
            width="w-[13rem]"
            placement="up"
            triggerClassName="flex w-full items-center gap-3 rounded-md px-2 py-2 text-left hover:bg-zinc-50 dark:hover:bg-zinc-900"
            trigger={
              <>
                {user?.avatar ? (
                  <img src={user.avatar} alt={user.username} className="h-8 w-8 shrink-0 rounded-full object-cover" />
                ) : (
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-zinc-900 text-xs font-semibold text-white dark:bg-white dark:text-zinc-900">
                    {initial}
                  </span>
                )}
                <span className="min-w-0 flex-1 leading-tight">
                  <span className="block truncate text-[13px] font-medium text-zinc-800 dark:text-zinc-100">{user?.username}</span>
                  <span className="block truncate text-xs text-zinc-400 dark:text-zinc-500">
                    {user?.role ? t(`users.role_${user.role}`) : ""}
                  </span>
                </span>
                <IconChevron size={14} {...{ className: "shrink-0 text-zinc-400" }} />
              </>
            }
          >
            {(close) => (
              <>
                <DropdownItem icon={<IconUser size={16} />} onSelect={() => { close(); navigate(`/${seg}/account/profile`); }}>
                  {t("nav.profile")}
                </DropdownItem>
                <DropdownItem icon={<IconLogout size={16} />} onSelect={() => { close(); void onLogout(); }}>
                  {t("common.logout")}
                </DropdownItem>
              </>
            )}
          </Dropdown>
        </div>
      </aside>

      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex shrink-0 items-center justify-end gap-2.5 border-b border-zinc-200 bg-white/70 px-6 py-2.5 backdrop-blur dark:border-zinc-800 dark:bg-[#0b0b0c]/70">
          <LangSwitcher />
          <ThemeSwitcher />
        </header>
        <main className="flex-1 overflow-hidden p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
