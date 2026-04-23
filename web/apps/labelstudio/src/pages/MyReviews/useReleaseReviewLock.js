import { useEffect, useRef } from "react";

const buildReleaseUrl = (annotationId) => {
  const hostname = window.APP_SETTINGS?.hostname ?? "";
  return `${hostname}/api/annotations/${annotationId}/release-lock/`;
};

const getCsrfToken = () => {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
};

const fireBeacon = (annotationId) => {
  if (!annotationId) return;
  const url = buildReleaseUrl(annotationId);
  const csrf = getCsrfToken();
  const payload = csrf
    ? new Blob([JSON.stringify({ csrfmiddlewaretoken: csrf })], { type: "application/json" })
    : new Blob();
  try {
    const sent = navigator.sendBeacon?.(url, payload);
    if (sent) return;
  } catch {
    // fall through to sync fallback
  }
  if (typeof fetch === "function") {
    fetch(url, {
      method: "POST",
      credentials: "include",
      keepalive: true,
      headers: csrf ? { "X-CSRFToken": csrf } : undefined,
    }).catch(() => {});
  }
};

export const useReleaseReviewLock = (annotationIdRef) => {
  const ref = useRef(annotationIdRef);
  ref.current = annotationIdRef;

  useEffect(() => {
    const handler = () => fireBeacon(ref.current);
    window.addEventListener("pagehide", handler);
    return () => window.removeEventListener("pagehide", handler);
  }, []);
};

export const releaseReviewLock = fireBeacon;
