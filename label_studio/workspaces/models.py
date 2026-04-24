"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

import logging
import os
import uuid

from core.utils.common import load_func
from core.utils.db import has_column_cached
from django.conf import settings
from django.core.validators import MaxLengthValidator, MinLengthValidator
from django.db import models, transaction
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)

WorkspaceMixin = load_func(settings.WORKSPACE_MIXIN)

WORKSPACE_TITLE_MIN_LEN = 3
WORKSPACE_TITLE_MAX_LEN = 256


class WorkspaceManager(models.Manager):
    """Unfiltered manager — returns every row including soft-deleted."""


class WorkspaceVisibleManager(WorkspaceManager):
    """Default manager that hides soft-deleted workspaces (deleted_at IS NULL)."""

    def get_queryset(self):
        qs = super().get_queryset()
        # Avoid referencing columns that might not exist during early migrations
        if has_column_cached(self.model._meta.db_table, 'deleted_at'):
            return qs.filter(deleted_at__isnull=True)
        return qs


class Workspace(WorkspaceMixin, models.Model):
    """Tenancy layer between Organization and Project.

    FSM integration (FsmHistoryStateModel + state choices + transitions) is intentionally
    deferred to Phase 4 when the full state machine for the annotation workflow is designed.
    """

    objects = WorkspaceVisibleManager()
    all_objects = WorkspaceManager()

    title = models.CharField(
        _('title'),
        max_length=WORKSPACE_TITLE_MAX_LEN,
        help_text=f'Workspace title. {WORKSPACE_TITLE_MIN_LEN}..{WORKSPACE_TITLE_MAX_LEN} chars.',
        validators=[
            MinLengthValidator(WORKSPACE_TITLE_MIN_LEN),
            MaxLengthValidator(WORKSPACE_TITLE_MAX_LEN),
        ],
    )
    description = models.TextField(_('description'), blank=True, default='')

    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='workspaces',
        help_text='Organization that owns the workspace',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='workspaces_created',
        verbose_name=_('created_by'),
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    deleted_at = models.DateTimeField(
        _('deleted at'),
        default=None,
        null=True,
        blank=True,
        db_index=True,
        help_text='If NULL, the workspace is not considered deleted.',
    )
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='workspaces_deleted',
        verbose_name=_('deleted by'),
    )

    class Meta:
        db_table = 'workspace'
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'title'],
                condition=models.Q(deleted_at__isnull=True),
                name='uniq_workspace_title_per_org',
            ),
        ]
        indexes = [
            models.Index(fields=['organization', '-created_at']),
            models.Index(fields=['organization', 'deleted_at']),
        ]

    def __str__(self):
        return f'{self.title} (org={self.organization_id})'

    def soft_delete(self, user=None):
        with transaction.atomic():
            self.deleted_at = timezone.now()
            self.deleted_by = user
            self.save(update_fields=['deleted_at', 'deleted_by', 'updated_at'])

    def has_permission(self, user):
        # Delegate to mixin, which sets request.user.workspace for activity logging.
        return super().has_permission(user)


class WorkspaceMember(models.Model):
    class Role(models.TextChoices):
        WORKSPACE_MANAGER = 'workspace_manager', _('Workspace Manager')
        MEMBER = 'member', _('Member')

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='workspace_memberships',
        help_text='User ID',
    )
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name='members',
        help_text='Workspace ID',
    )
    role = models.CharField(
        _('role'),
        max_length=32,
        choices=Role.choices,
        default=Role.MEMBER,
    )

    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    deleted_at = models.DateTimeField(
        _('deleted at'),
        default=None,
        null=True,
        blank=True,
        db_index=True,
        help_text='If NULL, the membership is not considered deleted.',
    )

    class Meta:
        db_table = 'workspace_member'
        constraints = [
            models.UniqueConstraint(fields=['user', 'workspace'], name='uniq_workspace_member'),
        ]


def _workspace_upload_path(instance, filename):
    workspace = str(instance.workspace_id)
    workspace_dir = os.path.join(settings.MEDIA_ROOT, 'workspace-upload', workspace)
    os.makedirs(workspace_dir, exist_ok=True)
    return 'workspace-upload/' + workspace + '/' + str(uuid.uuid4())[0:8] + '-' + filename


class WorkspaceFileUpload(models.Model):
    """File uploaded at the workspace scope.

    These files are the workspace's default import pool. They are stored independently from
    :class:`data_import.models.FileUpload` (which is project-scoped) so that the existing
    per-project import pipeline is untouched. Phase 3 storage work will introduce the
    mechanism that promotes these files into project tasks.
    """

    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name='file_uploads',
        help_text='Workspace that owns the file',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='workspace_file_uploads',
        help_text='User that uploaded the file',
    )
    file = models.FileField(upload_to=_workspace_upload_path)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)

    class Meta:
        db_table = 'workspace_file_upload'
        indexes = [models.Index(fields=['workspace', '-created_at'])]

    @cached_property
    def file_name(self):
        return os.path.basename(self.file.name)

    @property
    def size(self):
        try:
            return self.file.size
        except (ValueError, OSError):
            return None

    @property
    def url(self):
        try:
            return self.file.url
        except ValueError:
            return None

    def has_permission(self, user):
        return self.workspace.has_permission(user)
