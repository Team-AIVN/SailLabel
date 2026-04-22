import { atom } from "jotai";

export const SUPPORTED_LOCALES = ["en", "ko"] as const;
export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number];

export const LOCALE_STORAGE_KEY = "labelstudio:locale";

const detectInitialLocale = (): SupportedLocale => {
  if (typeof window === "undefined") return "en";
  const stored = window.localStorage?.getItem(LOCALE_STORAGE_KEY);
  if (stored && (SUPPORTED_LOCALES as readonly string[]).includes(stored)) {
    return stored as SupportedLocale;
  }
  const browser = (window.navigator?.language ?? "en").slice(0, 2).toLowerCase();
  return (SUPPORTED_LOCALES as readonly string[]).includes(browser) ? (browser as SupportedLocale) : "en";
};

const baseLocaleAtom = atom<SupportedLocale>(detectInitialLocale());

export const localeAtom = atom<SupportedLocale, [SupportedLocale], void>(
  (get) => get(baseLocaleAtom),
  (_get, set, next) => {
    set(baseLocaleAtom, next);
    if (typeof window !== "undefined") {
      try {
        window.localStorage?.setItem(LOCALE_STORAGE_KEY, next);
      } catch {
        // localStorage may be unavailable (e.g. private mode); ignore.
      }
    }
  },
);
