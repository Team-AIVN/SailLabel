import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./locales/en.json";
import ko from "./locales/ko.json";
import { LOCALE_STORAGE_KEY, SUPPORTED_LOCALES, type SupportedLocale } from "./atoms";

const detectLocale = (): SupportedLocale => {
  if (typeof window === "undefined") return "en";
  const stored = window.localStorage?.getItem(LOCALE_STORAGE_KEY);
  if (stored && (SUPPORTED_LOCALES as readonly string[]).includes(stored)) {
    return stored as SupportedLocale;
  }
  const browser = (window.navigator?.language ?? "en").slice(0, 2).toLowerCase();
  return (SUPPORTED_LOCALES as readonly string[]).includes(browser) ? (browser as SupportedLocale) : "en";
};

if (!i18n.isInitialized) {
  i18n
    .use(initReactI18next)
    .init({
      resources: {
        en: { translation: en },
        ko: { translation: ko },
      },
      lng: detectLocale(),
      fallbackLng: "en",
      supportedLngs: SUPPORTED_LOCALES as unknown as string[],
      interpolation: { escapeValue: false },
      returnNull: false,
      returnEmptyString: false,
      react: {
        useSuspense: false,
        bindI18n: "languageChanged loaded",
      },
      initImmediate: false,
    });
}

if (typeof document !== "undefined") {
  document.documentElement.lang = i18n.language;
}

export default i18n;
