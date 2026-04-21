import { useEffect } from "react";
import { useAtomValue } from "jotai";
import i18n from "./index";
import { localeAtom } from "./atoms";

export const LocaleSync = () => {
  const locale = useAtomValue(localeAtom);

  useEffect(() => {
    if (i18n.language !== locale) {
      i18n.changeLanguage(locale);
    }
    if (typeof document !== "undefined") {
      document.documentElement.lang = locale;
    }
  }, [locale]);

  return null;
};
