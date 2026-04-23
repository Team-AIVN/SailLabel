"""Shared metric instruments for SailLabel.

Declared once and imported from middleware / job entry points so every worker
registers the same series with consistent labels. Suffixes follow Prometheus
conventions (``_total``, ``_seconds``).

Aligned with instructions.md §4 (NFR observability) and
``deploy/grafana/saillabel-overview.json``.
"""

from label_studio.core.observability.metrics import REGISTRY, Counter, Gauge, Histogram


# ---- HTTP request latency / error rate -------------------------------------

HTTP_REQUEST_DURATION_SECONDS = REGISTRY.register(
    Histogram(
        'saillabel_http_request_duration_seconds',
        'HTTP request latency in seconds, labeled by view, method, and status class.',
        labelnames=('view', 'method', 'status_class'),
    )
)

HTTP_REQUESTS_TOTAL = REGISTRY.register(
    Counter(
        'saillabel_http_requests_total',
        'Count of HTTP responses labeled by view, method, and status code family (2xx/3xx/4xx/5xx).',
        labelnames=('view', 'method', 'status_class'),
    )
)


# ---- io_storages sync ------------------------------------------------------

STORAGE_SYNC_TOTAL = REGISTRY.register(
    Counter(
        'saillabel_storage_sync_total',
        'Count of io_storages sync jobs labeled by backend class name and outcome (success|failure).',
        labelnames=('backend', 'result'),
    )
)

STORAGE_SYNC_DURATION_SECONDS = REGISTRY.register(
    Histogram(
        'saillabel_storage_sync_duration_seconds',
        'Duration of a single io_storages sync job (scan_and_create_links), by backend.',
        labelnames=('backend',),
    )
)


# ---- Settlement batches ----------------------------------------------------

SETTLEMENT_BATCH_TOTAL = REGISTRY.register(
    Counter(
        'saillabel_settlement_batch_total',
        'Count of settlement batches executed, by outcome (success|failure).',
        labelnames=('result',),
    )
)

SETTLEMENT_BATCH_DURATION_SECONDS = REGISTRY.register(
    Histogram(
        'saillabel_settlement_batch_duration_seconds',
        'Duration of run_settlement_batch from enqueue-to-finish, in seconds.',
        labelnames=(),
        # Settlement jobs are bursty and can span minutes; widen the upper tail.
        buckets=(0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0, 1800.0, float('inf')),
    )
)


# ---- Readiness / health ----------------------------------------------------

READINESS_STATUS = REGISTRY.register(
    Gauge(
        'saillabel_readiness_status',
        'Last observed readiness probe status per dependency (1=ready, 0=unhealthy).',
        labelnames=('dependency',),
    )
)
