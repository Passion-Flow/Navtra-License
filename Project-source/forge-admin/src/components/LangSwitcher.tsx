// Language switcher — custom dropdown (i18n.md §4.6.1: dropdown, never a toggle; §4.6.3:
// wrap native controls). Lists all supported languages; selecting rewrites the URL prefix.
import { Dropdown, DropdownItem } from "./Dropdown";
import { useI18n } from "@/i18n/useI18n";
import { Lang } from "@/i18n";

const LABELS: Record<Lang, string> = { "zh-CN": "简体中文", en: "English (United States)" };

function GlobeIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a14 14 0 010 18M12 3a14 14 0 000 18" />
    </svg>
  );
}

export function LangSwitcher() {
  const { lang, langs, switchLang } = useI18n();
  return (
    <Dropdown
      align="right"
      width="w-52"
      trigger={
        <>
          <GlobeIcon />
          <span>{LABELS[lang]}</span>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" /></svg>
        </>
      }
    >
      {(close) =>
        langs.map((l) => (
          <DropdownItem
            key={l}
            selected={lang === l}
            onSelect={() => {
              switchLang(l);
              close();
            }}
          >
            {LABELS[l]}
          </DropdownItem>
        ))
      }
    </Dropdown>
  );
}
