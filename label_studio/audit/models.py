"""Append-only audit log.

Design: every row is immutable. Use ``AuditLog.record(...)`` — no update() or delete()
should be called on this table from application code. The database enforces nothing;
discipline is by convention plus tests. Emissions happen synchronously inside the
request transaction so an audit-write failure rolls back the originating action.
"""

from __future__ import annotations

from typing import Any, Optional

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class AuditAction(models.TextChoices):
    ROLE_GRANTED = 'role.granted', _('Role granted')
    ROLE_REVOKED = 'role.revoked', _('Role revoked')
    ROLE_CHANGED = 'role.changed', _('Role changed')
    PROJECT_CREATED = 'project.created', _('Project created')
    PROJECT_UPDATED = 'project.updated', _('Project updated')
    PROJECT_DELETED = 'project.deleted', _('Project deleted')
    WORKSPACE_CREATED = 'workspace.created', _('Workspace created')
    WORKSPACE_UPDATED = 'workspace.updated', _('Workspace updated')
    WORKSPACE_DELETED = 'workspace.deleted', _('Workspace deleted')
    DATA_EXPORTED = 'data.exported', _('Data exported')


class AuditLog(models.Model):
    """Immutable record of a security-relevant event."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        help_text='User who performed the action. NULL for system actors.',
    )
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        help_text='Organization the action occurred within.',
    )

    action = models.CharField(
        max_length=64,
        choices=AuditAction.choices,
        db_index=True,
        help_text='Dotted event name (e.g. role.granted).',
    )

    target_type = models.CharField(
        max_length=64,
        blank=True,
        default='',
        help_text="Target model label (e.g. 'projects.project'). Free-form string, not an FK.",
    )
    target_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text='Primary key of the target row.',
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text='Event-specific payload (before/after diff, role name, export format, etc.).',
    )

    class Meta:
        db_table = 'audit_log'
        indexes = [
            models.Index(fields=['organization', '-created_at']),
            models.Index(fields=['action', '-created_at']),
            models.Index(fields=['target_type', 'target_id']),
        ]

    def __str__(self):
        return f'{self.action} by {self.actor_id} at {self.created_at}'

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise RuntimeError('AuditLog rows are immutable — update is not permitted.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError('AuditLog rows are immutable — delete is not permitted.')

    @classmethod
    def record(
        cls,
        *,
        action: str,
        actor: Optional[Any] = None,
        organization: Optional[Any] = None,
        target: Optional[Any] = None,
        metadata: Optional[dict] = None,
    ) -> 'AuditLog':
        target_type = ''
        target_id = None
        if target is not None:
            meta = target._meta
            target_type = f'{meta.app_label}.{meta.model_name}'
            target_id = getattr(target, 'pk', None)
        return cls.objects.create(
            action=action,
            actor=actor,
            organization=organization,
            target_type=target_type,
            target_id=target_id,
            metadata=metadata or {},
        )
