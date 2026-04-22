import { useAtom } from "jotai";
import { useTranslation } from "react-i18next";
import { Dropdown } from "@humansignal/ui";
import { Menu } from "../Menu/Menu";
import { cn } from "../../utils/bem";
import { localeAtom, SUPPORTED_LOCALES, type SupportedLocale } from "../../i18n/atoms";

const LABEL_KEY: Record<SupportedLocale, string> = {
  en: "locale.english",
  ko: "locale.korean",
};

const SHORT_LABEL: Record<SupportedLocale, string> = {
  en: "EN",
  ko: "KO",
};

export const LocaleSwitcher = () => {
  const { t } = useTranslation();
  const [locale, setLocale] = useAtom(localeAtom);
  const menuClass = cn("menu-header");

  return (
    <div className={menuClass.elem("locale").toClassName()}>
      <div className={menuClass.elem("locale-button").toClassName()}>
        <Dropdown.Trigger
          align="right"
          content={
            <Menu size="medium" selectedKeys={[locale]}>
              {SUPPORTED_LOCALES.map((code) => (
                <Menu.Item
                  key={code}
                  onClick={() => setLocale(code)}
                  active={code === locale}
                  label={t(LABEL_KEY[code])}
                />
              ))}
            </Menu>
          }
        >
          <div
            role="button"
            tabIndex={0}
            aria-label={t("locale.label")}
            title={t("locale.label")}
            data-testid="locale-switcher"
          >
            {SHORT_LABEL[locale]}
          </div>
        </Dropdown.Trigger>
      </div>
    </div>
  );
};
