"""Tests for the Phase 8 observability surface.

Covers:
- In-process metrics registry (Counter/Gauge/Histogram + Prometheus text render).
- `/metrics/` exposition endpoint.
- `/health/` liveness stub and `/health/ready/` readiness probe branches.
- RequestMetricsMiddleware integration — requests produce the expected series.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.test import Client, override_settings
from django.urls import reverse

from label_studio.core.observability import Counter, Gauge, Histogram, render_latest
from label_studio.core.observability.health import ProbeResult, run_probes
from label_studio.core.observability.metrics import _Registry


# ---------- Registry primitives ---------------------------------------------


def test_counter_increments_and_renders_under_registry():
    reg = _Registry()
    c = reg.register(Counter('demo_requests_total', 'docs', ('method',)))
    c.inc(method='GET')
    c.inc(2, method='GET')
    c.inc(method='POST')

    with patch('label_studio.core.observability.metrics.REGISTRY', reg):
        output = render_latest()

    assert '# TYPE demo_requests_total counter' in output
    assert 'demo_requests_total{method="GET"} 3' in output
    assert 'demo_requests_total{method="POST"} 1' in output


def test_counter_rejects_negative_increment():
    c = Counter('demo_neg_total', 'docs')
    with pytest.raises(ValueError):
        c.inc(-1)


def test_counter_label_mismatch_raises():
    c = Counter('demo_labels_total', 'docs', ('a',))
    with pytest.raises(ValueError):
        c.inc(a='x', b='y')
    with pytest.raises(ValueError):
        c.inc()  # missing 'a'


def test_gauge_set_inc_dec():
    g = Gauge('demo_gauge', 'docs', ('dep',))
    g.set(5, dep='db')
    g.inc(2, dep='db')
    g.dec(1, dep='db')
    rendered = [s for s in g.collect()]
    assert (('demo_gauge', {'dep': 'db'}, 6.0)) in [tuple(s) for s in rendered]


def test_histogram_buckets_monotonic_and_sum_count():
    h = Histogram('demo_latency_seconds', 'docs', ('view',), buckets=(0.1, 0.5, 1.0))
    for value in (0.05, 0.2, 0.6, 2.0):
        h.observe(value, view='x')

    rows = list(h.collect())
    # Every row for view=x should carry the label.
    assert all(labels.get('view') == 'x' for _, labels, _ in rows)

    # Collect bucket counts keyed by `le`.
    buckets = {labels['le']: value for name, labels, value in rows if name == 'demo_latency_seconds_bucket'}
    assert buckets['0.1'] == 1
    assert buckets['0.5'] == 2
    assert buckets['1.0'] == 3
    assert buckets['+Inf'] == 4

    sums = {name: value for name, _, value in rows if name.endswith(('_sum', '_count'))}
    assert sums['demo_latency_seconds_count'] == 4
    assert sums['demo_latency_seconds_sum'] == pytest.approx(2.85)


def test_registry_rejects_conflicting_redeclaration():
    reg = _Registry()
    reg.register(Counter('demo_conflict_total', 'docs', ('a',)))
    with pytest.raises(ValueError):
        reg.register(Counter('demo_conflict_total', 'docs', ('a', 'b')))


def test_registry_is_idempotent_on_same_signature():
    reg = _Registry()
    first = reg.register(Counter('demo_idem_total', 'docs', ('a',)))
    again = reg.register(Counter('demo_idem_total', 'docs', ('a',)))
    assert first is again


# ---------- /metrics endpoint -----------------------------------------------


@pytest.mark.django_db
def test_metrics_endpoint_returns_prometheus_text():
    from label_studio.core.observability.instruments import HTTP_REQUESTS_TOTAL

    HTTP_REQUESTS_TOTAL.inc(view='fixture', method='GET', status_class='2xx')

    response = Client().get('/metrics/')
    assert response.status_code == 200
    assert response['Content-Type'].startswith('text/plain')
    body = response.content.decode()
    assert '# TYPE saillabel_http_requests_total counter' in body
    assert 'saillabel_http_requests_total' in body


# ---------- /health and /health/ready ---------------------------------------


@pytest.mark.django_db
def test_health_liveness_cheap_and_up():
    response = Client().get('/health/')
    assert response.status_code == 200
    assert response.json() == {'status': 'UP'}


@pytest.mark.django_db
def test_readiness_returns_503_when_any_probe_fails():
    def ok() -> ProbeResult:
        return ProbeResult('database', True)

    def bad() -> ProbeResult:
        return ProbeResult('redis', False, detail='ping failed')

    with patch('label_studio.core.observability.health.DEFAULT_PROBES', [ok, bad]):
        response = Client().get('/health/ready/')

    assert response.status_code == 503
    body = response.json()
    assert body['status'] == 'not_ready'
    assert body['checks']['database']['status'] == 'up'
    assert body['checks']['redis']['status'] == 'down'
    assert body['checks']['redis']['detail'] == 'ping failed'


@pytest.mark.django_db
def test_readiness_returns_200_when_all_green():
    def ok_db() -> ProbeResult:
        return ProbeResult('database', True)

    def ok_redis() -> ProbeResult:
        return ProbeResult('redis', True, detail='disabled')

    with patch('label_studio.core.observability.health.DEFAULT_PROBES', [ok_db, ok_redis]):
        response = Client().get('/health/ready/')

    assert response.status_code == 200
    assert response.json()['status'] == 'ready'


def test_run_probes_publishes_gauge():
    from label_studio.core.observability.instruments import READINESS_STATUS

    def ok() -> ProbeResult:
        return ProbeResult('gauge_dep_ok', True)

    def bad() -> ProbeResult:
        return ProbeResult('gauge_dep_bad', False)

    run_probes([ok, bad])
    values = {labels['dependency']: value for _, labels, value in READINESS_STATUS.collect()}
    assert values['gauge_dep_ok'] == 1.0
    assert values['gauge_dep_bad'] == 0.0


# ---------- Middleware ------------------------------------------------------


@pytest.mark.django_db
def test_request_middleware_records_histogram_and_counter():
    from label_studio.core.observability.instruments import (
        HTTP_REQUEST_DURATION_SECONDS,
        HTTP_REQUESTS_TOTAL,
    )

    before_count = sum(value for _, _, value in HTTP_REQUESTS_TOTAL.collect())

    # /version/ is an unauthenticated route that's always routed in OSS.
    response = Client().get('/version/')
    assert response.status_code == 200

    after_count = sum(value for _, _, value in HTTP_REQUESTS_TOTAL.collect())
    assert after_count > before_count

    # Histogram should have observed at least one sample since `before`.
    counts = [value for name, _, value in HTTP_REQUEST_DURATION_SECONDS.collect() if name.endswith('_count')]
    assert any(c > 0 for c in counts)


@pytest.mark.django_db
def test_request_middleware_skips_observability_paths():
    from label_studio.core.observability.instruments import HTTP_REQUESTS_TOTAL

    Client().get('/metrics/')
    labels = {frozenset(lbls.items()) for _, lbls, _ in HTTP_REQUESTS_TOTAL.collect()}
    # No label-set should have view starting with the metrics endpoint.
    assert not any('metrics' in dict(l).get('view', '') for l in labels)
