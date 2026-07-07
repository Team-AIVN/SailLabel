import { format, isValid } from "date-fns";
import { getRoot } from "mobx-state-tree";

const DECISION_LABEL = {
  ACCEPT: "Accepted",
  REJECT: "Rejected",
  FIX_AND_ACCEPT: "Fixed & accepted",
};

const fmtDate = (value) => {
  const date = new Date(value);
  return isValid(date) ? format(date, "MMM dd, HH:mm") : "";
};

/**
 * Renders the task's reviews as links: a "View reviews" link to the project's review
 * page (focused on this task) plus one link per review version so every version is
 * reachable. Value is the raw `reviews` array from the task serializer.
 */
export const ReviewsCell = (cell) => {
  const { original: task, value } = cell;
  const reviews = Array.isArray(value) ? value : [];

  if (reviews.length === 0) return "";

  const projectId = getRoot(task)?.SDK?.projectId;
  const taskId = task.id;
  const href = projectId ? `/projects/${projectId}/review?task=${taskId}` : "#";
  const stop = (e) => e.stopPropagation();

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 3, whiteSpace: "normal", minWidth: 180 }}>
      <a href={href} onClick={stop} data-testid="dm-reviews-link">
        View reviews ({reviews.length})
      </a>
      {reviews.map((review) => {
        const label = DECISION_LABEL[review.decision] ?? review.decision;
        const isReject = review.decision === "REJECT";
        return (
          <div key={review.id} style={{ fontSize: 12, lineHeight: 1.4 }} title={fmtDate(review.created_at)}>
            <span
              style={{
                fontWeight: 600,
                color: isReject ? "var(--color-negative-content, #c0392b)" : "var(--color-neutral-content-subtler)",
              }}
            >
              v{review.annotation_version ?? review.stage} · {label}
            </span>
            {review.comment ? (
              <div style={{ color: "var(--color-neutral-content)", fontStyle: "italic" }}>“{review.comment}”</div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
};
