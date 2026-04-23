import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Typography, useToast } from "@humansignal/ui";
import { useUpdatePageTitle, createTitleFromSegments } from "@humansignal/core";
import { Spinner } from "../../../components/Spinner/Spinner";
import { confirm, modal } from "../../../components/Modal/Modal";
import { useAPI } from "../../../providers/ApiProvider";
import { useProject } from "../../../providers/ProjectProvider";
import { cn } from "../../../utils/bem";
import "./SettlementSettings.prefix.css";

const CURRENCIES = ["KRW", "USD", "EUR", "JPY"];
const STATUS_KEYS = {
  PENDING: "pending",
  RUNNING: "running",
  COMPLETED: "completed",
  FAILED: "failed",
};

const parseList = (response) => {
  if (!response) return [];
  if (Array.isArray(response)) return response;
  if (Array.isArray(response.results)) return response.results;
  return [];
};

const formatTimestamp = (iso, locale) => {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString(locale);
  } catch {
    return iso;
  }
};

const formatAmount = (amount, currency, locale) => {
  if (amount === null || amount === undefined || amount === "") return "—";
  const num = typeof amount === "number" ? amount : Number.parseFloat(amount);
  if (Number.isNaN(num)) return String(amount);
  try {
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency: currency || "USD",
      currencyDisplay: "code",
    }).format(num);
  } catch {
    return `${num} ${currency ?? ""}`.trim();
  }
};

const startOfLastMonth = () => {
  const now = new Date();
  const d = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  return d.toISOString().slice(0, 10);
};

const endOfLastMonth = () => {
  const now = new Date();
  const d = new Date(now.getFullYear(), now.getMonth(), 0);
  return d.toISOString().slice(0, 10);
};

const downloadBlob = (blob, filename) => {
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
};

const filenameFromHeaders = (headers, fallback) => {
  const disposition = headers?.get?.("content-disposition") || "";
  const match = disposition.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
  return match?.[1] ? decodeURIComponent(match[1]) : fallback;
};

export const SettlementSettings = () => {
  const { t, i18n } = useTranslation();
  const { project } = useProject();
  const api = useAPI();
  const toast = useToast();
  const root = useMemo(() => cn("settlement-settings"), []);

  useUpdatePageTitle(createTitleFromSegments([project?.title, t("settlement.title")]));

  const [pricing, setPricing] = useState(null);
  const [pricingLoading, setPricingLoading] = useState(true);
  const [pricingSaving, setPricingSaving] = useState(false);
  const [currency, setCurrency] = useState("USD");
  const [labelPrice, setLabelPrice] = useState("");
  const [reviewPrice, setReviewPrice] = useState("");

  const [batches, setBatches] = useState([]);
  const [batchesLoading, setBatchesLoading] = useState(true);
  const [batchRunning, setBatchRunning] = useState(false);
  const [periodStart, setPeriodStart] = useState(startOfLastMonth);
  const [periodEnd, setPeriodEnd] = useState(endOfLastMonth);
  const [downloading, setDownloading] = useState(null);

  const projectId = project?.id;

  const loadPricing = useCallback(async () => {
    if (!projectId) return;
    setPricingLoading(true);
    const response = await api.callApi("projectPricing", {
      params: { pk: projectId },
      suppressError: true,
    });
    setPricingLoading(false);
    if (!response || response.error) {
      setPricing(null);
      return;
    }
    setPricing(response);
    setCurrency(response.currency || "USD");
    setLabelPrice(response.label_price ?? "");
    setReviewPrice(response.review_price ?? "");
  }, [api, projectId]);

  const loadBatches = useCallback(async () => {
    if (!projectId) return;
    setBatchesLoading(true);
    const response = await api.callApi("projectSettlements", {
      params: { pk: projectId },
      suppressError: true,
    });
    setBatchesLoading(false);
    setBatches(parseList(response));
  }, [api, projectId]);

  useEffect(() => {
    loadPricing();
  }, [loadPricing]);

  useEffect(() => {
    loadBatches();
  }, [loadBatches]);

  const handleSavePricing = useCallback(async () => {
    const label = labelPrice === "" ? null : Number.parseFloat(labelPrice);
    const review = reviewPrice === "" ? null : Number.parseFloat(reviewPrice);
    if (label === null || Number.isNaN(label) || label < 0) {
      toast.show({ message: t("settlement.form.invalidAmount"), type: "error" });
      return;
    }
    if (review === null || Number.isNaN(review) || review < 0) {
      toast.show({ message: t("settlement.form.invalidAmount"), type: "error" });
      return;
    }
    setPricingSaving(true);
    const response = await api.callApi("updateProjectPricing", {
      params: { pk: projectId },
      body: {
        currency,
        label_price: label,
        review_price: review,
      },
    });
    setPricingSaving(false);
    if (!response || response.error) {
      toast.show({ message: t("settlement.pricing.saveError"), type: "error" });
      return;
    }
    setPricing(response);
    setLabelPrice(response.label_price ?? "");
    setReviewPrice(response.review_price ?? "");
    toast.show({ message: t("settlement.pricing.saved") });
  }, [labelPrice, reviewPrice, currency, api, projectId, t, toast]);

  const handleRunBatch = useCallback(async () => {
    if (!periodStart || !periodEnd) {
      toast.show({ message: t("settlement.form.required"), type: "error" });
      return;
    }
    if (new Date(periodEnd) <= new Date(periodStart)) {
      toast.show({ message: t("settlement.form.invalidPeriod"), type: "error" });
      return;
    }
    setBatchRunning(true);
    const response = await api.callApi("createProjectSettlement", {
      params: { pk: projectId },
      body: { period_start: periodStart, period_end: periodEnd },
    });
    setBatchRunning(false);
    if (!response || response.error) {
      toast.show({ message: t("settlement.batches.runError"), type: "error" });
      return;
    }
    toast.show({ message: t("settlement.batches.runSuccess") });
    loadBatches();
  }, [api, projectId, periodStart, periodEnd, t, toast, loadBatches]);

  const handleDelete = useCallback(
    (batch) => {
      confirm({
        title: t("settlement.batches.actions.delete"),
        body: t("settlement.batches.deleteConfirm"),
        buttonLook: "negative",
        onOk: async () => {
          const response = await api.callApi("deleteSettlement", {
            params: { pk: batch.id },
            suppressError: true,
          });
          if (response && response.error) {
            toast.show({ message: t("settlement.batches.deleteError"), type: "error" });
            return;
          }
          loadBatches();
        },
      });
    },
    [api, t, toast, loadBatches],
  );

  const handleDownload = useCallback(
    async (batch, reportFormat) => {
      setDownloading(`${batch.id}:${reportFormat}`);
      try {
        const response = await api.callApi("settlementReportRaw", {
          params: { pk: batch.id, report_format: reportFormat },
        });
        if (!response || !response.ok) {
          toast.show({ message: t("settlement.batches.runError"), type: "error" });
          return;
        }
        const blob = await response.blob();
        const fallback = `settlement-${batch.id}.${reportFormat}`;
        downloadBlob(blob, filenameFromHeaders(response.headers, fallback));
      } finally {
        setDownloading(null);
      }
    },
    [api, t, toast],
  );

  const handleViewDetail = useCallback(
    async (batch) => {
      const response = await api.callApi("settlementDetail", {
        params: { pk: batch.id },
        suppressError: true,
      });
      if (!response || response.error) {
        toast.show({ message: t("settlement.batches.runError"), type: "error" });
        return;
      }
      const items = parseList(response.items);
      modal({
        title: t("settlement.detail.heading"),
        width: 720,
        body: (
          <div className={root.elem("detail").toClassName()}>
            <dl className={root.elem("detail-meta").toClassName()}>
              <div>
                <dt>{t("settlement.batches.columns.period")}</dt>
                <dd>
                  {response.period_start} → {response.period_end}
                </dd>
              </div>
              <div>
                <dt>{t("settlement.batches.columns.status")}</dt>
                <dd>{t(`settlement.batches.status.${STATUS_KEYS[response.status] ?? "pending"}`)}</dd>
              </div>
              <div>
                <dt>{t("settlement.detail.total")}</dt>
                <dd>{formatAmount(response.total_amount, response.currency, i18n.language)}</dd>
              </div>
              <div>
                <dt>{t("settlement.batches.columns.createdAt")}</dt>
                <dd>{formatTimestamp(response.created_at, i18n.language)}</dd>
              </div>
            </dl>
            <Typography variant="title" size="small" className="mb-tight">
              {t("settlement.detail.itemsHeading")}
            </Typography>
            {items.length === 0 ? (
              <div className={root.elem("empty").toClassName()}>{t("settlement.detail.noItems")}</div>
            ) : (
              <div className={root.elem("table-wrapper").toClassName()}>
                <table className={root.elem("table").toClassName()}>
                  <thead>
                    <tr>
                      <th>{t("settlement.detail.user")}</th>
                      <th>{t("settlement.detail.annotations")}</th>
                      <th>{t("settlement.detail.reviews")}</th>
                      <th>{t("settlement.detail.subtotal")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item) => {
                      const user = item.user_detail || {};
                      const userLabel = user.email || user.username || user.first_name || `#${item.user}`;
                      return (
                        <tr key={item.id ?? item.user}>
                          <td>{userLabel}</td>
                          <td>
                            {item.accepted_count ?? 0}
                            {item.label_amount != null && (
                              <span className="text-neutral-content-subtler">
                                {" "}
                                ({formatAmount(item.label_amount, item.currency ?? response.currency, i18n.language)})
                              </span>
                            )}
                          </td>
                          <td>
                            {item.review_count ?? 0}
                            {item.review_amount != null && (
                              <span className="text-neutral-content-subtler">
                                {" "}
                                ({formatAmount(item.review_amount, item.currency ?? response.currency, i18n.language)})
                              </span>
                            )}
                          </td>
                          <td>{formatAmount(item.amount, item.currency ?? response.currency, i18n.language)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ),
      });
    },
    [api, i18n.language, root, t, toast],
  );

  if (!projectId) {
    return (
      <div style={{ display: "flex", justifyContent: "center", marginTop: 32 }}>
        <Spinner size={32} />
      </div>
    );
  }

  return (
    <div className={root.toClassName()}>
      <Typography variant="headline" size="medium" className="mb-tighter">
        {t("settlement.title")}
      </Typography>
      <Typography variant="body" size="medium" className="text-neutral-content-subtler !mb-base">
        {t("settlement.description")}
      </Typography>

      <div className={root.elem("section").toClassName()}>
        <div className={cn("settings-wrapper").toClassName()}>
          <h3 className={root.elem("heading").toClassName()}>{t("settlement.pricing.heading")}</h3>
          {pricingLoading ? (
            <Spinner size={24} />
          ) : (
            <>
              <div className={root.elem("pricing-grid").toClassName()}>
                <label className={root.elem("field").toClassName()}>
                  <span>{t("settlement.pricing.currency")}</span>
                  <select value={currency} onChange={(event) => setCurrency(event.target.value)}>
                    {CURRENCIES.map((code) => (
                      <option key={code} value={code}>
                        {code}
                      </option>
                    ))}
                  </select>
                </label>

                <label className={root.elem("field").toClassName()}>
                  <span>{t("settlement.pricing.annotationRate")}</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={labelPrice}
                    onChange={(event) => setLabelPrice(event.target.value)}
                  />
                  <small className="text-neutral-content-subtler">{t("settlement.pricing.annotationRateHint")}</small>
                </label>

                <label className={root.elem("field").toClassName()}>
                  <span>{t("settlement.pricing.reviewRate")}</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={reviewPrice}
                    onChange={(event) => setReviewPrice(event.target.value)}
                  />
                  <small className="text-neutral-content-subtler">{t("settlement.pricing.reviewRateHint")}</small>
                </label>
              </div>

              <div className={root.elem("actions").toClassName()}>
                <Button variant="primary" onClick={handleSavePricing} waiting={pricingSaving}>
                  {t("settlement.pricing.save")}
                </Button>
              </div>

              <div className={root.elem("status").toClassName()}>
                {pricing?.updated_at
                  ? t("settlement.pricing.lastUpdated", {
                      timestamp: formatTimestamp(pricing.updated_at, i18n.language),
                    })
                  : t("settlement.pricing.notSet")}
              </div>
            </>
          )}
        </div>
      </div>

      <div className={root.elem("section").toClassName()}>
        <div className={cn("settings-wrapper").toClassName()}>
          <h3 className={root.elem("heading").toClassName()}>{t("settlement.batches.heading")}</h3>

          <div className={root.elem("batch-form").toClassName()}>
            <label className={root.elem("field").toClassName()}>
              <span>{t("settlement.batches.periodStart")}</span>
              <input type="date" value={periodStart} onChange={(event) => setPeriodStart(event.target.value)} />
            </label>
            <label className={root.elem("field").toClassName()}>
              <span>{t("settlement.batches.periodEnd")}</span>
              <input type="date" value={periodEnd} onChange={(event) => setPeriodEnd(event.target.value)} />
            </label>
            <Button variant="primary" onClick={handleRunBatch} waiting={batchRunning}>
              {t("settlement.batches.submit")}
            </Button>
          </div>

          <div style={{ marginTop: 24 }}>
            {batchesLoading ? (
              <Spinner size={24} />
            ) : batches.length === 0 ? (
              <div className={root.elem("empty").toClassName()}>{t("settlement.batches.empty")}</div>
            ) : (
              <div className={root.elem("table-wrapper").toClassName()}>
                <table className={root.elem("table").toClassName()}>
                  <thead>
                    <tr>
                      <th>{t("settlement.batches.columns.period")}</th>
                      <th>{t("settlement.batches.columns.status")}</th>
                      <th>{t("settlement.batches.columns.total")}</th>
                      <th>{t("settlement.batches.columns.items")}</th>
                      <th>{t("settlement.batches.columns.createdAt")}</th>
                      <th>{t("settlement.batches.columns.actions")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {batches.map((batch) => {
                      const statusKey = STATUS_KEYS[batch.status] ?? "pending";
                      const completed = batch.status === "COMPLETED";
                      const downloadingCsv = downloading === `${batch.id}:csv`;
                      const downloadingPdf = downloading === `${batch.id}:pdf`;
                      const annotations = batch.accepted_annotation_count ?? 0;
                      const reviews = batch.review_count ?? 0;
                      return (
                        <tr key={batch.id}>
                          <td>
                            {batch.period_start} → {batch.period_end}
                          </td>
                          <td>
                            <span
                              className={root.elem("status-badge").mod({ value: statusKey }).toClassName()}
                            >
                              {t(`settlement.batches.status.${statusKey}`)}
                            </span>
                          </td>
                          <td>{formatAmount(batch.total_amount, batch.currency, i18n.language)}</td>
                          <td>
                            {annotations} / {reviews}
                          </td>
                          <td>{formatTimestamp(batch.created_at, i18n.language)}</td>
                          <td>
                            <div className={root.elem("row-actions").toClassName()}>
                              <Button size="small" variant="neutral" look="outlined" onClick={() => handleViewDetail(batch)}>
                                {t("settlement.batches.actions.view")}
                              </Button>
                              <Button
                                size="small"
                                variant="neutral"
                                look="outlined"
                                disabled={!completed}
                                waiting={downloadingCsv}
                                onClick={() => handleDownload(batch, "csv")}
                              >
                                {t("settlement.batches.actions.downloadCsv")}
                              </Button>
                              <Button
                                size="small"
                                variant="neutral"
                                look="outlined"
                                disabled={!completed}
                                waiting={downloadingPdf}
                                onClick={() => handleDownload(batch, "pdf")}
                              >
                                {t("settlement.batches.actions.downloadPdf")}
                              </Button>
                              <Button
                                size="small"
                                variant="negative"
                                look="outlined"
                                onClick={() => handleDelete(batch)}
                              >
                                {t("settlement.batches.actions.delete")}
                              </Button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

SettlementSettings.title = "Settlement";
SettlementSettings.path = "/settlement";
