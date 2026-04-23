"""Thin helper wrappers around ``AuditLog.record()``.

Goal: give API views a single-line call per event with consistent metadata
shape, without leaking audit details into the call sites. Each helper swallows
actor/organization lookup and converts model instances to serialisable
metadata (ids + human-readable labels).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from audit.models import AuditAction, AuditLog

logger = logging.getLogger(__name__)


def _safe_record(**kwargs) -> None:
    """Wrap ``AuditLog.record`` in an exception guard.

    Audit writes happen inside the request transaction by design (§4), but the
    *only* acceptable failure mode for an audit helper is to log and move on —
    otherwise a transient write error would corrupt an unrelated user action.
    The transaction rollback still covers the data-integrity case; this guard
    is for infrastructure-level issues (broken JSON, connection blip).
    """
    try:
        AuditLog.record(**kwargs)
    except Exception:
        logger.exception('AuditLog.record failed for %s', kwargs.get('action'))


def record_project_event(
    *,
    action: str,
    actor: Any,
    project: Any,
    metadata: Optional[dict] = None,
) -> None:
    payload = {
        'title': getattr(project, 'title', ''),
        'workspace_id': getattr(project, 'workspace_id', None),
    }
    if metadata:
        payload.update(metadata)
    organization = getattr(project, 'organization', None)
    _safe_record(
        action=action,
        actor=actor,
        organization=organization,
        target=project,
        metadata=payload,
    )


def record_workspace_event(
    *,
    action: str,
    actor: Any,
    workspace: Any,
    metadata: Optional[dict] = None,
) -> None:
    payload = {'title': getattr(workspace, 'title', '')}
    if metadata:
        payload.update(metadata)
    organization = getattr(workspace, 'organization', None)
    _safe_record(
        action=action,
        actor=actor,
        organization=organization,
        target=workspace,
        metadata=payload,
    )


def record_role_change(
    *,
    action: str,
    actor: Any,
    subject: Any,
    scope: str,
    scope_id: Optional[int],
    role: Optional[str],
    previous_role: Optional[str] = None,
    organization: Any = None,
) -> None:
    """Record a role grant/revoke/change against a membership row.

    ``subject`` is the ``*Member`` instance (OrganizationMember, WorkspaceMember,
    ProjectMember). ``scope`` identifies which layer ("organization" | "workspace"
    | "project"); ``scope_id`` is the FK on that side. Role names are stored as
    strings so the metadata remains stable if role enums evolve.
    """
    payload = {
        'scope': scope,
        'scope_id': scope_id,
        'user_id': getattr(subject, 'user_id', None),
        'role': role,
    }
    if previous_role is not None:
        payload['previous_role'] = previous_role
    _safe_record(
        action=action,
        actor=actor,
        organization=organization,
        target=subject,
        metadata=payload,
    )


def record_data_export(
    *,
    actor: Any,
    project: Any,
    metadata: Optional[dict] = None,
) -> None:
    payload = {
        'project_id': getattr(project, 'id', None),
        'project_title': getattr(project, 'title', ''),
    }
    if metadata:
        payload.update(metadata)
    organization = getattr(project, 'organization', None)
    _safe_record(
        action=AuditAction.DATA_EXPORTED,
        actor=actor,
        organization=organization,
        target=project,
        metadata=payload,
    )
