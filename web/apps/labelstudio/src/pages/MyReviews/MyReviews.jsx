import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useUpdatePageTitle } from "@humansignal/core";
import { Spinner } from "../../components/Spinner/Spinner";
import { useAPI } from "../../providers/ApiProvider";
import { cn } from "../../utils/bem";
import "./MyReviews.prefix.css";

const parseList = (response) => {
  if (!response) return [];
  if (Array.isArray(response)) return response;
  if (Array.isArray(response.results)) return response.results;
  return [];
};

const STATE_OPTIONS = ["ALL", "ACCEPTED", "REJECTED"];

const formatTimestamp = (iso, locale) => {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString(locale);
  } catch {
    return iso;
  }
};

export const MyReviewsPage = () => {
  const { t, i18n } = useTranslation();
  const api = useAPI();

  const [rows, setRows] = useState([]);
  const [networkState, setNetworkState] = useState("loading");
  const [stateFilter, setStateFilter] = useState("ALL");

  useUpdatePageTitle(t("myReviews.pageTitle"));

  const fetchReviews = useCallback(async () => {
    setNetworkState("loading");
    const params = stateFilter !== "ALL" ? { state: stateFilter } : {};
    const response = await api.callApi("currentUserReviews", { params });
    setRows(parseList(response));
    setNetworkState("loaded");
  }, [api, stateFilter]);

  useEffect(() => {
    fetchReviews();
  }, [fetchReviews]);

  const root = useMemo(() => cn("my-reviews-page"), []);
  const isEmpty = networkState === "loaded" && rows.length === 0;

  return (
    <div className={root.toClassName()}>
      <div className={root.elem("toolbar").toClassName()}>
        <label className={root.elem("filter").toClassName()}>
          <span>{t("myReviews.filter.state")}</span>
          <select value={stateFilter} onChange={(event) => setStateFilter(event.target.value)}>
            {STATE_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {t(`myReviews.states.${option.toLowerCase()}`)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {networkState === "loading" ? (
        <div className={root.elem("loading").toClassName()}>
          <Spinner size={48} />
        </div>
      ) : isEmpty ? (
        <div className={root.elem("empty").toClassName()}>
          <div>
            <div className={root.elem("empty-title").toClassName()}>{t("myReviews.empty.title")}</div>
            <div className={root.elem("empty-description").toClassName()}>{t("myReviews.empty.description")}</div>
          </div>
        </div>
      ) : (
        <div className={root.elem("table-wrapper").toClassName()}>
          <table className={root.elem("table").toClassName()}>
            <thead>
              <tr>
                <th>{t("myReviews.columns.task")}</th>
                <th>{t("myReviews.columns.project")}</th>
                <th>{t("myReviews.columns.annotation")}</th>
                <th>{t("myReviews.columns.transition")}</th>
                <th>{t("myReviews.columns.state")}</th>
                <th>{t("myReviews.columns.comment")}</th>
                <th>{t("myReviews.columns.reviewedAt")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>
                    <a href={`/projects/${row.project_id}/data?task=${row.task_id}`}>
                      #{row.task_id}
                    </a>
                  </td>
                  <td>#{row.project_id}</td>
                  <td>#{row.annotation_id}</td>
                  <td>{t(`myReviews.transitions.${row.transition_name}`, { defaultValue: row.transition_name })}</td>
                  <td>
                    <span
                      className={root.elem("state-badge").mod({ value: row.state?.toLowerCase() }).toClassName()}
                    >
                      {t(`myReviews.states.${row.state?.toLowerCase()}`, { defaultValue: row.state })}
                    </span>
                  </td>
                  <td className={root.elem("comment").toClassName()}>{row.comment || ""}</td>
                  <td>{formatTimestamp(row.created_at, i18n.language)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

MyReviewsPage.title = "My Reviews";
MyReviewsPage.path = "/reviews";
MyReviewsPage.exact = true;
