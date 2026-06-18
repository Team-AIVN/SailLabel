"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver
from projects.models import Project

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Project)
def materialize_work_pool_on_project(sender, instance, **kwargs):
    """Seed a project's tasks from its selected Work Pool once it is published.

    Fires for any project save but returns immediately unless the project has a work
    pool, is published, and has no tasks yet — so it runs exactly once at setup and
    does not disturb non-pool projects.
    """
    if not instance.work_pool_id or instance.is_draft:
        return
    if instance.tasks.exists():
        return
    try:
        from .workpools import materialize_pool_to_project

        materialize_pool_to_project(instance)
    except Exception:
        logger.exception('Failed to materialize work pool for project %s', instance.pk)
