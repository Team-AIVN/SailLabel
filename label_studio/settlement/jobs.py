"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

import logging
import time

from django.conf import settings

from core.redis import start_job_async_or_sync
from label_studio.core.observability.instruments import (
    SETTLEMENT_BATCH_DURATION_SECONDS,
    SETTLEMENT_BATCH_TOTAL,
)

from .services import compute_settlement

logger = logging.getLogger(__name__)


def run_settlement_batch(batch_id: int):
    """RQ entrypoint — delegates to `services.compute_settlement`.

    Keeping this a thin wrapper makes it trivial to unit-test the computation
    synchronously without standing up Redis / RQ. Timing and outcome are emitted
    as Prometheus metrics so Grafana panels (instructions.md §4) and alert
    rules can track batch health.
    """
    logger.info('run_settlement_batch starting for batch_id=%s', batch_id)
    started = time.monotonic()
    try:
        result = compute_settlement(batch_id)
    except Exception:
        SETTLEMENT_BATCH_TOTAL.inc(result='failure')
        SETTLEMENT_BATCH_DURATION_SECONDS.observe(time.monotonic() - started)
        raise
    SETTLEMENT_BATCH_TOTAL.inc(result='success')
    SETTLEMENT_BATCH_DURATION_SECONDS.observe(time.monotonic() - started)
    return result


def enqueue_settlement_batch(batch_id: int):
    """Enqueue `run_settlement_batch` onto the long-timeout queue.

    Settlement jobs read the full FSM audit for a project over a time window,
    which can be minutes for large projects — so we park them on `low` with
    `RQ_LONG_JOB_TIMEOUT`. In dev or when Redis is offline the job runs
    synchronously via `start_job_async_or_sync`.
    """
    return start_job_async_or_sync(
        run_settlement_batch,
        batch_id,
        queue_name='low',
        job_timeout=getattr(settings, 'RQ_LONG_JOB_TIMEOUT', 36000),
    )
