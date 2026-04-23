"""Request-level Prometheus metrics middleware.

Place early enough that the timer captures view work but after auth middleware
so ``request.resolver_match`` is populated. Records:

- ``saillabel_http_request_duration_seconds`` histogram (view, method, status_class)
- ``saillabel_http_requests_total`` counter (view, method, status_class)

Skips its own observability URLs so scraping Prometheus doesn't self-pollute
dashboards with `/metrics/` traffic.
"""

from __future__ import annotations

import logging
import time

from django.utils.deprecation import MiddlewareMixin

from label_studio.core.observability.instruments import (
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
)

logger = logging.getLogger(__name__)

_EXCLUDED_PATH_PREFIXES = ('/metrics', '/health', '/static/', '/__debug__/')


def _resolve_view_label(request) -> str:
    match = getattr(request, 'resolver_match', None)
    if match is None:
        return 'unmatched'
    if match.url_name:
        return (match.namespace + ':' + match.url_name) if match.namespace else match.url_name
    # Fall back to view callable's dotted name for unnamed routes (OpenAPI docs).
    func = match.func
    module = getattr(func, '__module__', '')
    name = getattr(func, '__qualname__', getattr(func, '__name__', 'anonymous'))
    return f'{module}.{name}' if module else name


def _status_class(status_code: int) -> str:
    if 200 <= status_code < 300:
        return '2xx'
    if 300 <= status_code < 400:
        return '3xx'
    if 400 <= status_code < 500:
        return '4xx'
    if 500 <= status_code < 600:
        return '5xx'
    return 'other'


class RequestMetricsMiddleware(MiddlewareMixin):
    """Time each request and observe the result into Prometheus instruments."""

    def process_request(self, request):
        request._metrics_started_at = time.monotonic()

    def process_response(self, request, response):
        started = getattr(request, '_metrics_started_at', None)
        if started is None:
            return response

        path = request.path or ''
        if any(path.startswith(prefix) for prefix in _EXCLUDED_PATH_PREFIXES):
            return response

        duration = max(0.0, time.monotonic() - started)
        status_class = _status_class(getattr(response, 'status_code', 0) or 0)
        view = _resolve_view_label(request)
        method = request.method or 'UNKNOWN'

        try:
            HTTP_REQUEST_DURATION_SECONDS.observe(
                duration, view=view, method=method, status_class=status_class
            )
            HTTP_REQUESTS_TOTAL.inc(view=view, method=method, status_class=status_class)
        except Exception:
            logger.debug('Failed to record request metrics', exc_info=True)

        return response
