import { Dropdown, DropdownItem } from "./Dropdown";
import { Theme, useTheme } from "@/theme/ThemeProvider";
import { useI18n } from "@/i18n/useI18n";

function SunIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M19 5l-1.5 1.5M6.5 17.5L5 19" />
    </svg>
  );
}
function MoonIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.8A9 9 0 1111.2 3 7 7 0 0021 12.8z" />
    </svg>
  );
}
function SystemIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="12" rx="2" /><path d="M8 20h8M12 16v4" />
    </svg>
  );
}

const ICONS: Record<Theme, JSX.Element> = { light: <SunIcon />, dark: <MoonIcon />, system: <SystemIcon /> };

export function ThemeSwitcher() {
  const { theme, setTheme } = useTheme();
  const { t } = useI18n();
  const order: Theme[] = ["light", "dark", "system"];
  return (
    <Dropdown align="right" width="w-44" trigger={<span className="text-zinc-500 dark:text-zinc-300">{ICONS[theme]}</span>}>
      {(close) =>
        order.map((opt) => (
          <DropdownItem
            key={opt}
            icon={<span className="text-zinc-500 dark:text-zinc-300">{ICONS[opt]}</span>}
            selected={theme === opt}
            onSelect={() => {
              setTheme(opt);
              close();
            }}
          >
            {t(`theme.${opt}`)}
          </DropdownItem>
        ))
      }
    </Dropdown>
  );
}
