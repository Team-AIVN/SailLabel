import i18next from "i18next";
import { getRoot } from "mobx-state-tree";

// Current review status of the task (source of truth), shown as a single badge.
// Colors use theme vars (subtle tint bg + strong content text) so the pill adapts to
// light/dark mode. Labels are resolved via i18n at render time (module-load i18n is
// unreliable) with a Korean fallback.
const NEUTRAL = { bg: "var(--color-neutral-emphasis-subtle)", fg: "var(--color-neutral-content)" };
const POSITIVE = { bg: "var(--color-positive-emphasis-subtle)", fg: "var(--color-positive-content)" };
const NEGATIVE = { bg: "var(--color-negative-emphasis-subtle)", fg: "var(--color-negative-content)" };
const WARNING = { bg: "var(--color-warning-emphasis-subtle)", fg: "var(--color-warning-content)" };
const STATUS = {
  NOT_SELECTED: { fallback: "미선정", ...NEUTRAL },
  PENDING: { fallback: "대기", ...WARNING },
  ACCEPTED: { fallback: "승인", ...POSITIVE },
  REJECTED: { fallback: "거절", ...NEGATIVE },
  FIXED_AND_ACCEPTED: { fallback: "수정+승인", ...POSITIVE },
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
  const meta = STATUS[status] ?? (reviews.length ? { fallback: status ?? "리뷰됨", ...NEUTRAL } : null);
  const label = meta ? i18next.t(`dm.reviewStatus.${status}`, meta.fallback) : "";

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
          {label}
        </span>
      ) : null}
      {reviews.length > 0 && href ? (
        <a href={href} onClick={stop} data-testid="dm-reviews-link" style={{ fontSize: 12 }}>
          {i18next.t("dm.activityLog", "이력")} ({reviews.length})
        </a>
      ) : null}
    </div>
  );
};
