import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Spinner } from "../../components/Spinner/Spinner";
import { useAPI } from "../../providers/ApiProvider";
import { useParams } from "../../providers/RoutesProvider";
import { cn } from "../../utils/bem";
import "./Review.prefix.css";

const REVIEW_STATUSES = ["NOT_SELECTED", "PENDING", "ACCEPTED", "REJECTED", "FIXED_AND_ACCEPTED"];

const listOf = (response) => {
  if (!response) return [];
  if (Array.isArray(response)) return response;
  if (Array.isArray(response.results)) return response.results;
  return [];
};

const userLabel = (user) => {
  if (!user) return "—";
  const name = [user.first_name, user.last_name].filter(Boolean).join(" ").trim();
  return name || user.email || user.username || `User ${user.id}`;
};

export const ReviewPage = () => {
  const { t } = useTranslation();
  const api = useAPI();
  const routeParams = useParams();
  const root = useMemo(() => cn("review-page"), []);

  // Resolve the project id reliably: the routing context's params may be empty on a
  // direct/deep-link load, so fall back to parsing it from the URL path.
  const id = useMemo(
    () => routeParams.id ?? window.location.pathname.match(/\/projects\/(\d+)/)?.[1] ?? null,
    [routeParams.id],
  );

  const [tasks, setTasks] = useState([]);
  const [progress, setProgress] = useState(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  // Optional ?task=<id> deep-link from the Data Manager "Reviews" column focuses one task.
  const taskFilter = useMemo(() => new URLSearchParams(window.location.search).get("task") ?? "", []);

  const loadProgress = useCallback(async () => {
    if (!id) return;
    const res = await api.callApi("reviewProgress", { params: { pk: id } });
    setProgress(res && !res.error ? res : null);
  }, [api, id]);

  const loadTasks = useCallback(async () => {
    if (!id) return;
    const params = { pk: id };
    if (statusFilter) params.review_status = statusFilter;
    if (taskFilter) params.task = taskFilter;
    const res = await api.callApi("reviewTasks", { params });
    setTasks(listOf(res));
  }, [api, id, statusFilter, taskFilter]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      await Promise.all([loadProgress(), loadTasks()]);
      setLoading(false);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  if (loading && !progress) {
    return (
      <div className={root.elem("loading").toClassName()}>
        <Spinner size={48} />
      </div>
    );
  }

  const statusLabel = (s) => t(`review.status.${s}`, s.replace(/_/g, " ").toLowerCase());

  return (
    <div className={root.toClassName()}>
      <header className={root.elem("header").toClassName()}>
        <h1>{t("review.title", "Review")}</h1>
        {progress && (
          <div className={root.elem("stats").toClassName()}>
            <div className={root.elem("stat").toClassName()}>
              <span className={root.elem("stat-value").toClassName()}>{progress.annotation_progress}%</span>
              <span className={root.elem("stat-label").toClassName()}>
                {t("review.annotationProgress", "Annotation progress")}
              </span>
            </div>
            <div className={root.elem("stat").toClassName()}>
              <span className={root.elem("stat-value").toClassName()}>{progress.review_progress}%</span>
              <span className={root.elem("stat-label").toClassName()}>
                {t("review.reviewProgress", "Review progress")}
              </span>
            </div>
            <div className={root.elem("stat").toClassName()}>
              <span className={root.elem("stat-value").toClassName()}>
                {progress.review_completed}/{progress.review_selected}
              </span>
              <span className={root.elem("stat-label").toClassName()}>{t("review.reviewed", "Reviewed")}</span>
            </div>
          </div>
        )}
      </header>

      <div className={root.elem("toolbar").toClassName()}>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">{t("review.allStatuses", "All review statuses")}</option>
          {REVIEW_STATUSES.map((s) => (
            <option key={s} value={s}>
              {statusLabel(s)}
            </option>
          ))}
        </select>
      </div>

      <table className={root.elem("table").toClassName()}>
        <thead>
          <tr>
            <th>{t("review.col.taskId", "Task ID")}</th>
            <th>{t("review.col.version", "Version")}</th>
            <th>{t("review.col.annotator", "Annotator")}</th>
            <th>{t("review.col.reviewStatus", "Review status")}</th>
            <th>{t("review.col.reviewer", "Reviewer")}</th>
          </tr>
        </thead>
        <tbody>
          {tasks.map((row) => (
            <tr key={row.task_id}>
              <td>
                <a href={`/projects/${id}/data?task=${row.task_id}`}>{row.task_id}</a>
              </td>
              <td>{row.annotation_version ?? "—"}</td>
              <td>{userLabel(row.annotator)}</td>
              <td>
                <span className={root.elem("badge").mod({ status: row.review_status }).toClassName()}>
                  {statusLabel(row.review_status)}
                </span>
              </td>
              <td>{userLabel(row.reviewer)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {tasks.length === 0 && <p className={root.elem("muted").toClassName()}>{t("review.empty", "No tasks.")}</p>}
    </div>
  );
};

ReviewPage.title = "Review";
ReviewPage.path = "/review";
ReviewPage.exact = true;
