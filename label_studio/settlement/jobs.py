"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

import logging

from django.conf import settings

from core.redis import start_job_async_or_sync

from .services import compute_settlement

logger = logging.getLogger(__name__)


def run_settlement_batch(batch_id: int):
    """RQ entrypoint — delegates to `services.compute_settlement`.

    Keeping this a thin wrapper makes it trivial to unit-test the computation
    synchronously without standing up Redis / RQ.
    """
    logger.info('run_settlement_batch starting for batch_id=%s', batch_id)
    return compute_settlement(batch_id)


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
