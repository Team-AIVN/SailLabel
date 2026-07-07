import { format, isValid } from "date-fns";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Spinner } from "../../components/Spinner/Spinner";
import { useAPI } from "../../providers/ApiProvider";
import { useParams } from "../../providers/RoutesProvider";
import { cn } from "../../utils/bem";
import { ProjectRoleGuard } from "../../components/RoleGuard/RoleGuard";
import "./Review.prefix.css";

const REVIEW_STATUSES = ["NOT_SELECTED", "PENDING", "ACCEPTED", "REJECTED", "FIXED_AND_ACCEPTED"];
// Each review decision maps to the badge status used for its pill color/label.
const DECISION_STATUS = { ACCEPT: "ACCEPTED", REJECT: "REJECTED", FIX_AND_ACCEPT: "FIXED_AND_ACCEPTED" };
const fmtTime = (value) => {
  const date = new Date(value);
  return isValid(date) ? format(date, "MM/dd HH:mm") : "";
};

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

const FIX_COMMENT_PREFIX = "[Fix + Accept]";

const prettyJSON = (raw) => {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
};

// Parse a "[Fix + Accept]\nOriginal: ...\nUpdated: ..." auto-comment into before/after.
const parseFixComment = (text) => {
  if (typeof text !== "string" || !text.startsWith(FIX_COMMENT_PREFIX)) return null;
  const original = text.match(/Original:\s*(.*)/)?.[1]?.trim();
  const updated = text.match(/Updated:\s*([\s\S]*)$/)?.[1]?.trim();
  if (original === undefined || updated === undefined) return null;
  return { original: prettyJSON(original), updated: prettyJSON(updated) };
};

const signLines = (block, sign) =>
  block
    .split("\n")
    .map((line) => `${sign} ${line}`)
    .join("\n");

const ReviewPageInner = () => {
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

  // Render a review comment; a "[Fix + Accept]" auto-comment becomes a code-diff block.
  const renderCommentBody = (text) => {
    const fix = parseFixComment(text);
    if (!fix) return text;
    return (
      <div className={root.elem("diff").toClassName()}>
        <div className={root.elem("diff-title").toClassName()}>Fix + Accept</div>
        <pre className={root.elem("diff-line").mod({ kind: "del" }).toClassName()}>{signLines(fix.original, "-")}</pre>
        <pre className={root.elem("diff-line").mod({ kind: "add" }).toClassName()}>{signLines(fix.updated, "+")}</pre>
      </div>
    );
  };

  // Flatten every task's reviews into one row per decision, newest first.
  const reviewRows = tasks
    .flatMap((task) => (task.reviews ?? []).map((r) => ({ ...r, task_id: task.task_id, annotator: task.annotator })))
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

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
            <th>{t("review.col.annotator", "Labeler")}</th>
            <th>{t("review.col.decision", "Decision")}</th>
            <th>{t("review.col.reviewer", "Reviewer")}</th>
            <th>{t("review.col.comments", "Comment")}</th>
            <th>{t("review.col.time", "Time")}</th>
          </tr>
        </thead>
        <tbody>
          {reviewRows.map((r) => (
            <tr key={r.id}>
              <td>
                <a href={`/projects/${id}/data?task=${r.task_id}`}>{r.task_id}</a>
              </td>
              <td>{r.annotation_version ?? "—"}</td>
              <td>{userLabel(r.annotator)}</td>
              <td>
                <span className={root.elem("badge").mod({ status: DECISION_STATUS[r.decision] }).toClassName()}>
                  {statusLabel(DECISION_STATUS[r.decision] ?? r.decision)}
                </span>
              </td>
              <td>{userLabel(r.reviewer)}</td>
              <td>{r.comment ? renderCommentBody(r.comment) : "—"}</td>
              <td className={root.elem("muted").toClassName()}>{fmtTime(r.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {reviewRows.length === 0 && <p className={root.elem("muted").toClassName()}>{t("review.empty", "No reviews.")}</p>}
    </div>
  );
};

// Reviewers (and project managers / workspace managers / super admins) only.
// Labelers and unassigned members are redirected to the project data view.
export const ReviewPage = () => (
  <ProjectRoleGuard check={(perms) => perms.canReview}>
    <ReviewPageInner />
  </ProjectRoleGuard>
);

ReviewPage.title = "Review";
ReviewPage.path = "/review";
ReviewPage.exact = true;
