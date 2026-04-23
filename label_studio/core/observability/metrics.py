"""Minimal Prometheus-compatible metrics registry.

Output conforms to the `text exposition format
<https://prometheus.io/docs/instrumenting/exposition_formats/>`_ (v0.0.4). Only
the features we actively need are implemented:

- Counter — monotonically increasing float.
- Gauge — arbitrary float (set / inc / dec).
- Histogram — observations bucketed by ``le`` label, plus ``_sum`` and
  ``_count`` companion series.

Metrics are keyed by a stable ``(name, labelvalues)`` tuple. Concurrent mutation
is guarded by a per-metric lock; reads (render) walk a snapshot under the same
lock to avoid torn numbers.
"""

from __future__ import annotations

import math
import threading
from typing import Dict, Iterable, Mapping, Optional, Sequence, Tuple

_LabelKey = Tuple[Tuple[str, str], ...]


def _label_key(labelnames: Sequence[str], labelvalues: Mapping[str, str]) -> _LabelKey:
    return tuple(sorted((n, str(labelvalues[n])) for n in labelnames))


def _escape_label_value(value: str) -> str:
    return value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')


def _format_value(value: float) -> str:
    if math.isinf(value):
        return '+Inf' if value > 0 else '-Inf'
    if math.isnan(value):
        return 'NaN'
    if value == int(value) and abs(value) < 1e16:
        return repr(int(value))
    return repr(value)


def _format_le(bound: float) -> str:
    """Histogram bucket upper bounds are always rendered as floats (``1.0``, not
    ``1``) so dashboards that key on string label values stay compatible with
    ``prometheus_client``'s canonical output."""
    if math.isinf(bound):
        return '+Inf'
    if bound == int(bound):
        return f'{int(bound)}.0'
    return repr(bound)


class _MetricBase:
    kind = ''

    def __init__(self, name: str, documentation: str, labelnames: Sequence[str] = ()) -> None:
        self.name = name
        self.documentation = documentation
        self.labelnames = tuple(labelnames)
        self._lock = threading.Lock()

    def _validate_labels(self, labelvalues: Mapping[str, str]) -> None:
        missing = set(self.labelnames) - set(labelvalues)
        extra = set(labelvalues) - set(self.labelnames)
        if missing or extra:
            raise ValueError(
                f'Metric {self.name!r} label mismatch — expected {list(self.labelnames)}, got {sorted(labelvalues)}'
            )

    def collect(self) -> Iterable[Tuple[str, Dict[str, str], float]]:  # pragma: no cover - abstract
        raise NotImplementedError


class Counter(_MetricBase):
    """Monotonic counter. Callers should name instances with the ``_total`` suffix
    per Prometheus naming conventions — this class emits series at ``self.name``
    verbatim."""

    kind = 'counter'

    def __init__(self, name: str, documentation: str, labelnames: Sequence[str] = ()) -> None:
        super().__init__(name, documentation, labelnames)
        self._values: Dict[_LabelKey, float] = {}

    def inc(self, amount: float = 1.0, **labels: str) -> None:
        if amount < 0:
            raise ValueError('Counter increment must be non-negative')
        self._validate_labels(labels)
        key = _label_key(self.labelnames, labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + float(amount)

    def collect(self) -> Iterable[Tuple[str, Dict[str, str], float]]:
        with self._lock:
            items = list(self._values.items())
        for key, value in items:
            yield self.name, dict(key), value


class Gauge(_MetricBase):
    kind = 'gauge'

    def __init__(self, name: str, documentation: str, labelnames: Sequence[str] = ()) -> None:
        super().__init__(name, documentation, labelnames)
        self._values: Dict[_LabelKey, float] = {}

    def set(self, value: float, **labels: str) -> None:
        self._validate_labels(labels)
        key = _label_key(self.labelnames, labels)
        with self._lock:
            self._values[key] = float(value)

    def inc(self, amount: float = 1.0, **labels: str) -> None:
        self._validate_labels(labels)
        key = _label_key(self.labelnames, labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + float(amount)

    def dec(self, amount: float = 1.0, **labels: str) -> None:
        self.inc(-amount, **labels)

    def collect(self) -> Iterable[Tuple[str, Dict[str, str], float]]:
        with self._lock:
            items = list(self._values.items())
        for key, value in items:
            yield self.name, dict(key), value


# Same bucket layout as prometheus_client.DEFAULT_BUCKETS so dashboards/alerts
# tuned for default Prometheus SDKs continue to work unchanged.
DEFAULT_HISTOGRAM_BUCKETS = (
    0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, float('inf'),
)


class Histogram(_MetricBase):
    kind = 'histogram'

    def __init__(
        self,
        name: str,
        documentation: str,
        labelnames: Sequence[str] = (),
        buckets: Sequence[float] = DEFAULT_HISTOGRAM_BUCKETS,
    ) -> None:
        super().__init__(name, documentation, labelnames)
        bounds = list(buckets)
        if not bounds:
            raise ValueError('Histogram needs at least one bucket')
        if bounds[-1] != float('inf'):
            bounds.append(float('inf'))
        self._bounds = tuple(bounds)
        self._buckets: Dict[_LabelKey, list[float]] = {}
        self._sum: Dict[_LabelKey, float] = {}
        self._count: Dict[_LabelKey, float] = {}

    def observe(self, value: float, **labels: str) -> None:
        self._validate_labels(labels)
        key = _label_key(self.labelnames, labels)
        with self._lock:
            counts = self._buckets.get(key)
            if counts is None:
                counts = [0.0] * len(self._bounds)
                self._buckets[key] = counts
            for idx, bound in enumerate(self._bounds):
                if value <= bound:
                    counts[idx] += 1.0
            self._sum[key] = self._sum.get(key, 0.0) + float(value)
            self._count[key] = self._count.get(key, 0.0) + 1.0

    def collect(self) -> Iterable[Tuple[str, Dict[str, str], float]]:
        with self._lock:
            keys = list(self._buckets.keys())
            buckets = {k: list(v) for k, v in self._buckets.items()}
            sums = dict(self._sum)
            counts = dict(self._count)
        for key in keys:
            labels = dict(key)
            for idx, bound in enumerate(self._bounds):
                bucket_labels = dict(labels, le=_format_le(bound))
                yield self.name + '_bucket', bucket_labels, buckets[key][idx]
            yield self.name + '_sum', labels, sums[key]
            yield self.name + '_count', labels, counts[key]


class _Registry:
    def __init__(self) -> None:
        self._metrics: Dict[str, _MetricBase] = {}
        self._lock = threading.Lock()

    def register(self, metric: _MetricBase) -> _MetricBase:
        with self._lock:
            existing = self._metrics.get(metric.name)
            if existing is not None:
                if type(existing) is type(metric) and existing.labelnames == metric.labelnames:
                    # Idempotent re-registration under autoreload / twin imports.
                    return existing
                raise ValueError(f'Metric {metric.name!r} already registered with a different signature')
            self._metrics[metric.name] = metric
            return metric

    def unregister(self, name: str) -> None:
        with self._lock:
            self._metrics.pop(name, None)

    def get(self, name: str) -> Optional[_MetricBase]:
        return self._metrics.get(name)

    def snapshot(self) -> list[_MetricBase]:
        with self._lock:
            return list(self._metrics.values())


REGISTRY = _Registry()


def render_latest() -> str:
    """Return the Prometheus text-format snapshot for REGISTRY."""
    lines: list[str] = []
    for metric in REGISTRY.snapshot():
        lines.append(f'# HELP {metric.name} {metric.documentation}')
        lines.append(f'# TYPE {metric.name} {metric.kind}')
        for series_name, labels, value in metric.collect():
            if labels:
                label_str = ','.join(f'{k}="{_escape_label_value(v)}"' for k, v in sorted(labels.items()))
                lines.append(f'{series_name}{{{label_str}}} {_format_value(value)}')
            else:
                lines.append(f'{series_name} {_format_value(value)}')
    lines.append('')
    return '\n'.join(lines)
