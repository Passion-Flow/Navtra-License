// Minimal URL-driven i18n. Language comes from the URL `/:lang/...` (i18n.md §4.5),
// never from cookie/localStorage. Backend returns CODES; the frontend translates (§4.6.2).
import zhCN from "./locales/zh-CN.json";
import en from "./locales/en.json";

export const SUPPORTED_LANGS = ["zh-CN", "en"] as const;
export type Lang = (typeof SUPPORTED_LANGS)[number];
export const DEFAULT_LANG: Lang = "zh-CN";

const DICTS: Record<Lang, Record<string, unknown>> = { "zh-CN": zhCN, en };

// URL uses short segments zh|en; map to full locale codes.
export function urlSegToLang(seg: string | undefined): Lang {
  if (seg === "en") return "en";
  if (seg === "zh" || seg === "zh-CN") return "zh-CN";
  return DEFAULT_LANG;
}
export function langToUrlSeg(lang: Lang): string {
  return lang === "en" ? "en" : "zh";
}

function lookup(dict: Record<string, unknown>, key: string): string | undefined {
  return key.split(".").reduce<unknown>((acc, k) => (acc as Record<string, unknown>)?.[k], dict) as
    | string
    | undefined;
}

export function translate(lang: Lang, key: string): string {
  return lookup(DICTS[lang], key) ?? lookup(DICTS[DEFAULT_LANG], key) ?? key;
}

// Map a backend error envelope code to a localized message (§4.6.2).
export function translateError(lang: Lang, code: string): string {
  return translate(lang, `errors.${code}`) || translate(lang, "errors.SYSTEM_INTERNAL_ERROR");
}

// Audit action codes contain dots (e.g. "license.issue_online"), so look them up directly
// from the `actions` map rather than via the dot-splitting translate() (§4.6.2).
export function translateAction(lang: Lang, code: string): string {
  const get = (l: Lang) => (DICTS[l] as { actions?: Record<string, string> }).actions?.[code];
  return get(lang) ?? get(DEFAULT_LANG) ?? code;
}
