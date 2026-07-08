import i18next from "i18next";
import { forwardRef, useCallback, useMemo } from "react";
import { cn } from "../../utils/bem";
import { useDropdown } from "@humansignal/ui";
import "./Menu.prefix.css";
import { MenuContext } from "./MenuContext";
import { MenuItem } from "./MenuItem";

// Settings sidebar labels come from static page props (`.title`/`.menuItem`) in
// English. Map them to i18n keys and localize at render so both locales work.
const MENU_LABEL_KEYS = {
  General: "settings.general",
  Workers: "settings.workers",
  "Labeling Interface": "settings.labelingInterface",
  Annotation: "settings.annotation",
  Model: "settings.model",
  Predictions: "settings.predictions",
  "Cloud Storage": "settings.cloudStorage",
  Webhooks: "settings.webhooks",
  "Danger Zone": "settings.dangerZone",
};

const localizeMenuLabel = (label) => {
  const key = typeof label === "string" ? MENU_LABEL_KEYS[label] : null;
  return key && i18next.exists(key) ? i18next.t(key) : label;
};

export const Menu = forwardRef(
  ({ children, className, style, size, selectedKeys, closeDropdownOnItemClick, contextual }, ref) => {
    const dropdown = useDropdown();

    const selected = useMemo(() => {
      return new Set(selectedKeys ?? []);
    }, [selectedKeys]);

    const clickHandler = useCallback(
      (e) => {
        const elem = cn("main-menu").elem("item").closest(e.target);

        if (dropdown && elem && closeDropdownOnItemClick !== false) {
          dropdown.close();
        }
      },
      [dropdown],
    );

    const collapsed = useMemo(() => {
      return !!dropdown;
    }, [dropdown]);

    return (
      <MenuContext.Provider value={{ selected }}>
        <ul
          ref={ref}
          className={cn("main-menu").mod({ size, collapsed, contextual }).mix(className).toClassName()}
          style={style}
          onClick={clickHandler}
        >
          {children}
        </ul>
      </MenuContext.Provider>
    );
  },
);

Menu.Item = MenuItem;
Menu.Spacer = () => <li className={cn("main-menu").elem("spacer").toClassName()} />;
Menu.Divider = () => <li className={cn("main-menu").elem("divider").toClassName()} />;
Menu.Builder = (url, menuItems) => {
  return (menuItems ?? []).map((item, index) => {
    if (item === "SPACER") return <Menu.Spacer key={index} />;
    if (item === "DIVIDER") return <Menu.Divider key={index} />;

    let pageLabel;
    let pagePath;

    if (Array.isArray(item)) {
      [pagePath, pageLabel] = item;
    } else {
      const { menuItem, title, path } = item;
      pageLabel = title ?? menuItem;
      pagePath = path;
    }

    pageLabel = localizeMenuLabel(pageLabel);

    if (typeof pagePath === "function") {
      return (
        <Menu.Item key={index} onClick={pagePath}>
          {pageLabel}
        </Menu.Item>
      );
    }

    const location = `${url}${pagePath}`.replace(/([/]+)/g, "/");

    return (
      <Menu.Item key={index} to={location} exact>
        {pageLabel}
      </Menu.Item>
    );
  });
};

Menu.Group = ({ children, title, className, style }) => {
  return (
    <div className={cn("menu-group").mix(className).toClassName()} style={style}>
      <div className={cn("menu-group").elem("title").toClassName()}>{title}</div>
      <ul className={cn("menu-group").elem("list").toClassName()}>{children}</ul>
    </div>
  );
};
