"""In-process metrics registry exposing Prometheus text format at /metrics/.

We intentionally avoid the ``prometheus_client`` dependency: the metric surface
we need (Counter/Histogram/Gauge with a handful of labels) is small enough to
implement without pulling in another package, and a single-process collector
matches the uWSGI deployment where each worker reports its own numbers. A Grafana
``sum by`` aggregation combines them at query time.
"""

from label_studio.core.observability.metrics import (
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    render_latest,
)

__all__ = ['REGISTRY', 'Counter', 'Gauge', 'Histogram', 'render_latest']
