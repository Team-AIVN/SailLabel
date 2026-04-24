import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { cn } from "../../../utils/bem";
import "./Settlement.prefix.css";

const CURRENCIES = ["KRW", "USD", "EUR", "JPY"];

export const SettlementPage = ({ show, pricing, setPricing, error }) => {
  const { t } = useTranslation();
  const rootClass = useMemo(() => cn("project-settlement"), []);

  if (!show) return null;

  const update = (field, value) => setPricing((prev) => ({ ...prev, [field]: value }));

  return (
    <div className={rootClass.toClassName()}>
      <div className={rootClass.elem("note").toClassName()}>{t("createProject.settlement.note")}</div>

      <div className={rootClass.elem("grid").toClassName()}>
        <label className={rootClass.elem("field").toClassName()}>
          <span>{t("createProject.settlement.currencyLabel")}</span>
          <select
            value={pricing.currency ?? "USD"}
            onChange={(event) => update("currency", event.target.value)}
          >
            {CURRENCIES.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </select>
        </label>

        <label className={rootClass.elem("field").toClassName()}>
          <span>{t("createProject.settlement.labelPriceLabel")}</span>
          <input
            type="number"
            min="0"
            step="0.01"
            value={pricing.label_price ?? ""}
            onChange={(event) => update("label_price", event.target.value)}
          />
          <small>{t("createProject.settlement.priceHint")}</small>
        </label>

        <label className={rootClass.elem("field").toClassName()}>
          <span>{t("createProject.settlement.reviewPriceLabel")}</span>
          <input
            type="number"
            min="0"
            step="0.01"
            value={pricing.review_price ?? ""}
            onChange={(event) => update("review_price", event.target.value)}
          />
          <small>{t("createProject.settlement.priceHint")}</small>
        </label>
      </div>

      {error && <div className={rootClass.elem("error").toClassName()}>{error}</div>}
    </div>
  );
};
