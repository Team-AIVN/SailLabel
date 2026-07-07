import { getRoot } from "mobx-state-tree";

// Current review status of the task (source of truth), shown as a single badge.
const STATUS = {
  NOT_SELECTED: { label: "미선정", bg: "#e4e7ec", fg: "#384250" },
  PENDING: { label: "대기", bg: "#fce7c3", fg: "#93500a" },
  ACCEPTED: { label: "승인", bg: "#cdefda", fg: "#12703a" },
  REJECTED: { label: "거절", bg: "#fbd5d5", fg: "#b42318" },
  FIXED_AND_ACCEPTED: { label: "수정+승인", bg: "#cdefda", fg: "#12703a" },
};

/**
 * Shows the task's current review status as one badge, plus a "더보기" link to the
 * review page where the full decision history (with comments) lives. The per-review
 * history is intentionally NOT dumped inline here.
 */
export const ReviewsCell = (cell) => {
  const { original: task, value } = cell;
  const reviews = Array.isArray(value) ? value : [];
  const status = task.review_status;

  if (!status && reviews.length === 0) return "";

  const projectId = getRoot(task)?.SDK?.projectId;
  const href = projectId ? `/projects/${projectId}/review?task=${task.id}` : null;
  const stop = (e) => e.stopPropagation();
  const meta = STATUS[status] ?? (reviews.length ? { label: status ?? "리뷰됨", bg: "#e4e7ec", fg: "#384250" } : null);

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, whiteSpace: "nowrap" }}>
      {meta ? (
        <span
          style={{
            fontSize: 11,
            fontWeight: 600,
            padding: "2px 10px",
            borderRadius: 999,
            background: meta.bg,
            color: meta.fg,
          }}
        >
          {meta.label}
        </span>
      ) : null}
      {reviews.length > 0 && href ? (
        <a href={href} onClick={stop} data-testid="dm-reviews-link" style={{ fontSize: 12 }}>
          더보기 ({reviews.length})
        </a>
      ) : null}
    </div>
  );
};
