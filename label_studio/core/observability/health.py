"""Readiness probe helpers.

Liveness (``/health/``) keeps the cheap legacy behavior — process is up. Readiness
(``/health/ready/``) fans out to each dependency we actually need in-request to
avoid sending traffic to a pod that can't serve it.

The probe is used by:
- Kubernetes / uWSGI readiness checks (returns 503 when any dep is down).
- The ``saillabel_readiness_status`` gauge exposed on ``/metrics/`` so Grafana
  can chart availability per dependency.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, List

from django.conf import settings
from django.db import connections

from label_studio.core.observability.instruments import READINESS_STATUS

logger = logging.getLogger(__name__)


@dataclass
class ProbeResult:
    name: str
    ready: bool
    detail: str = ''

    def to_dict(self) -> dict:
        payload = {'status': 'up' if self.ready else 'down'}
        if self.detail:
            payload['detail'] = self.detail
        return payload


def _check_database() -> ProbeResult:
    try:
        conn = connections['default']
        conn.ensure_connection()
        with conn.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        return ProbeResult('database', True)
    except Exception as exc:
        logger.warning('Readiness: database check failed: %s', exc)
        return ProbeResult('database', False, detail=str(exc)[:200])


def _check_redis() -> ProbeResult:
    # Redis is optional in OSS deployments. If the feature is disabled we report
    # ready so a single-process dev setup isn't flagged unhealthy.
    if not getattr(settings, 'REDIS_ENABLED', False):
        return ProbeResult('redis', True, detail='disabled')

    # Lazy import — core.redis instantiates a client at import time, and we want
    # settings to be fully loaded before that happens in tests.
    from core.redis import redis_healthcheck

    ok = redis_healthcheck()
    return ProbeResult('redis', bool(ok), detail='' if ok else 'ping failed')


def _check_rq() -> ProbeResult:
    # RQ workers are optional in OSS. When Redis is disabled jobs run inline via
    # start_job_async_or_sync, so a missing worker is not a readiness failure.
    if not getattr(settings, 'REDIS_ENABLED', False):
        return ProbeResult('rq', True, detail='inline')

    try:
        import django_rq
        from rq import Worker

        conn = django_rq.get_connection()
        workers = Worker.all(connection=conn)
        if workers:
            return ProbeResult('rq', True, detail=f'{len(workers)} worker(s)')
        return ProbeResult('rq', False, detail='no workers registered')
    except Exception as exc:
        logger.warning('Readiness: rq check failed: %s', exc)
        return ProbeResult('rq', False, detail=str(exc)[:200])


DEFAULT_PROBES: List[Callable[[], ProbeResult]] = [
    _check_database,
    _check_redis,
    _check_rq,
]


def run_probes(probes: List[Callable[[], ProbeResult]] | None = None) -> List[ProbeResult]:
    """Run each probe, publish its outcome to Prometheus, and return results."""
    results: List[ProbeResult] = []
    for probe in probes or DEFAULT_PROBES:
        try:
            result = probe()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning('Readiness probe %s raised: %s', probe.__name__, exc, exc_info=True)
            result = ProbeResult(getattr(probe, '__name__', 'unknown'), False, detail=str(exc)[:200])
        results.append(result)
        try:
            READINESS_STATUS.set(1.0 if result.ready else 0.0, dependency=result.name)
        except Exception:
            logger.debug('Failed to record readiness gauge for %s', result.name, exc_info=True)
    return results
