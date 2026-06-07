import { useCallback } from "react";
import { useNavigate, useParams, useLocation } from "react-router-dom";
import { DEFAULT_LANG, Lang, langToUrlSeg, SUPPORTED_LANGS, translate, translateAction, translateError, urlSegToLang } from "./index";

export function useI18n() {
  const { lang: seg } = useParams();
  const lang: Lang = urlSegToLang(seg);
  const navigate = useNavigate();
  const location = useLocation();

  const t = useCallback((key: string) => translate(lang, key), [lang]);
  const tError = useCallback((code: string) => translateError(lang, code), [lang]);
  const tAction = useCallback((code: string) => translateAction(lang, code), [lang]);

  // Switching language rewrites the URL prefix (bookmarkable; URL is source of truth).
  const switchLang = useCallback(
    (next: Lang) => {
      const parts = location.pathname.split("/");
      parts[1] = langToUrlSeg(next);
      navigate(parts.join("/") + location.search);
    },
    [location, navigate],
  );

  return { lang, t, tError, tAction, switchLang, langs: SUPPORTED_LANGS, defaultLang: DEFAULT_LANG };
}
