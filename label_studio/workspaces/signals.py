"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver
from projects.models import Project

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Project)
def materialize_task_pool_on_project(sender, instance, **kwargs):
    """Seed a project's tasks from its selected Task Pool once it is published.

    Fires for any project save but returns immediately unless the project has a work
    pool, is published, and has no tasks yet — so it runs exactly once at setup and
    does not disturb non-pool projects.
    """
    if not instance.task_pool_id or instance.is_draft:
        return
    if instance.tasks.exists():
        return
    try:
        from .taskpools import materialize_pool_to_project

        materialize_pool_to_project(instance)
    except Exception:
        logger.exception('Failed to materialize task pool for project %s', instance.pk)


def _blob_segment(name, fallback):
    """Make one path segment of a blob name out of a user-typed title.

    Azure accepts Unicode blob names, so Korean titles survive as-is. Only the
    characters that would either fork the path (`/`, `\\`) or trip Azure's naming
    rules (trailing dot/space, blank) are rewritten.
    """
    segment = (name or '').replace('\\', '_').replace('/', '_')
    segment = ' '.join(segment.split())  # collapse whitespace runs, strip the ends
    segment = segment.strip('. ')
    return segment or str(fallback)


def azure_export_prefix(project):
    """`export/<workspace title>/<project title>` — where a project's results land.

    Annotations are written under this prefix as `<task id>.json` (see
    ``ExportStorageLink.get_key`` with ``FUTURE_SAVE_TASK_TO_STORAGE``). Task ids are
    globally unique, so two same-titled projects sharing a folder cannot clobber each
    other's files. The prefix is resolved once, when the storage is attached: renaming
    a workspace or project afterwards leaves already-attached storages pointing at the
    old folder (re-run ``scripts/prod_setup_export_storage.py`` to re-derive them).
    """
    workspace = project.workspace
    return 'export/{}/{}'.format(
        _blob_segment(workspace.title, workspace.pk),
        _blob_segment(project.title, project.pk),
    )


@receiver(post_save, sender=Project)
def attach_azure_export_storage(sender, instance, created, **kwargs):
    """Auto-attach an Azure export storage to new workspace projects.

    When the deployment has default Azure credentials (AZURE_BLOB_ACCOUNT_NAME/KEY and
    AZURE_BLOB_DEFAULT_CONTAINER), every submitted annotation is then pushed to
    `export/<workspace>/<project>/` automatically (see export_annotation_to_azure_storages),
    and the storage's Sync bulk-pushes everything when work is done. No-op when the
    env is not configured, so setups without Azure are unaffected.
    """
    if not created or not instance.workspace_id:
        return
    try:
        from core.utils.params import get_env
        from io_storages.azure_blob.models import AzureBlobExportStorage

        container = get_env('AZURE_BLOB_DEFAULT_CONTAINER')
        if not (container and get_env('AZURE_BLOB_ACCOUNT_NAME') and get_env('AZURE_BLOB_ACCOUNT_KEY')):
            return
        if instance.io_storages_azureblobexportstorages.exists():
            return
        prefix = azure_export_prefix(instance)
        AzureBlobExportStorage.objects.create(
            project=instance,
            title='결과 자동 저장 (Azure)',
            container=container,
            prefix=prefix,
        )
        logger.info('Attached azure export storage to project %s (%s)', instance.pk, prefix)
    except Exception:
        logger.exception('Failed to attach azure export storage to project %s', instance.pk)
