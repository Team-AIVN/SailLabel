"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license.

Role-branched dashboard aggregation for Phase 7.

The public entry point is :func:`build_dashboard_summary`: it inspects the
caller's memberships (organization → workspace → project) and returns only the
widget slices the caller is entitled to see. The frontend chooses which cards
to render from the `roles` array it finds on the payload.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from django.db.models import Count, OuterRef, Q, Subquery
from django.utils import timezone

from fsm.state_choices import AnnotationStateChoices
from fsm.state_models import AnnotationState
from organizations.models import OrganizationMember
from projects.models import Project, ProjectMember
from settlement.models import ProjectPricing
from users.constants import OrganizationRole, ProjectRole
from workspaces.models import Workspace, WorkspaceMember

logger = logging.getLogger(__name__)


# Transition identifiers used by settlement + review flows.
_ACCEPT_TRANSITION = 'accept_annotation'
_REJECT_TRANSITION = 'reject_annotation'


# ---------------------------------------------------------------------------
# Role detection
# ---------------------------------------------------------------------------


def _effective_roles(user, organization) -> List[str]:
    """Collect every role the caller may act under in this organization.

    A single user can carry multiple roles simultaneously — e.g. a PM who also
    reviews on another project, or a super admin who is still a project
    manager on some projects. We return the union so the frontend can render
    every applicable widget block.
    """
    roles: List[str] = []
    if user.is_superuser:
        roles.append(OrganizationRole.SUPER_ADMIN)
    if organization is not None:
        om = (
            OrganizationMember.objects.filter(
                user=user, organization=organization, deleted_at__isnull=True
            )
            .only('role')
            .first()
        )
        if om and om.role == OrganizationRole.SUPER_ADMIN and OrganizationRole.SUPER_ADMIN not in roles:
            roles.append(OrganizationRole.SUPER_ADMIN)

    if organization is not None:
        has_ws_manager = WorkspaceMember.objects.filter(
            user=user,
            workspace__organization=organization,
            workspace__deleted_at__isnull=True,
            role=WorkspaceMember.Role.WORKSPACE_MANAGER,
            deleted_at__isnull=True,
        ).exists()
        if has_ws_manager:
            roles.append(WorkspaceMember.Role.WORKSPACE_MANAGER)

    project_roles = (
        ProjectMember.objects.filter(
            user=user,
            project__organization=organization,
            deleted_at__isnull=True,
            enabled=True,
        )
        .values_list('role', flat=True)
        .distinct()
    )
    for role in project_roles:
        if role not in roles:
            roles.append(role)

    return roles


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _today_range():
    """Return [start_of_today, start_of_tomorrow) in the active timezone."""
    now = timezone.localtime()
    start = timezone.make_aware(datetime.combine(now.date(), time.min), now.tzinfo)
    end = start + timedelta(days=1)
    return start, end


def _project_completion(project: Project) -> Dict[str, int]:
    """Cheap completion snapshot for one project using denormalized counts."""
    total = project.tasks.count()
    finished = project.tasks.filter(is_labeled=True).count()
    percent = int(round(finished / total * 100)) if total else 0
    return {
        'project_id': project.id,
        'title': project.title or '',
        'total': total,
        'finished': finished,
        'percent': percent,
    }


def _manager_projects_qs(user, organization):
    """Projects where the caller is a project manager (any org role escalates this set)."""
    base = Project.objects.filter(organization=organization)
    if user.is_superuser:
        return base
    om = (
        OrganizationMember.objects.filter(
            user=user, organization=organization, deleted_at__isnull=True
        )
        .only('role')
        .first()
    )
    if om and om.role == OrganizationRole.SUPER_ADMIN:
        return base

    managed_project_ids = list(
        ProjectMember.objects.filter(
            user=user,
            project__organization=organization,
            role=ProjectRole.PROJECT_MANAGER,
            deleted_at__isnull=True,
            enabled=True,
        ).values_list('project_id', flat=True)
    )
    # Workspace managers also see every project inside workspaces they manage.
    managed_workspace_ids = list(
        WorkspaceMember.objects.filter(
            user=user,
            workspace__organization=organization,
            role=WorkspaceMember.Role.WORKSPACE_MANAGER,
            deleted_at__isnull=True,
        ).values_list('workspace_id', flat=True)
    )
    return base.filter(
        Q(id__in=managed_project_ids) | Q(workspace_id__in=managed_workspace_ids)
    ).distinct()


# ---------------------------------------------------------------------------
# Widget builders
# ---------------------------------------------------------------------------


def _super_admin_widgets(user, organization) -> dict:
    """Org-wide counts + overall completion (not sensitive to ProjectMember)."""
    from tasks.models import Task

    if organization is None:
        return {
            'organization_count': 0,
            'workspace_count': 0,
            'user_count': 0,
            'project_count': 0,
            'completion': {'total': 0, 'finished': 0, 'percent': 0},
        }

    workspace_count = Workspace.objects.filter(
        organization=organization, deleted_at__isnull=True
    ).count()
    user_count = OrganizationMember.objects.filter(
        organization=organization, deleted_at__isnull=True
    ).count()
    projects = Project.objects.filter(organization=organization)
    project_count = projects.count()
    tasks = Task.objects.filter(project__organization=organization)
    total = tasks.count()
    finished = tasks.filter(is_labeled=True).count()
    percent = int(round(finished / total * 100)) if total else 0
    return {
        # OSS deploys have exactly one org per DB, but keep the shape flexible
        # so LSE multi-tenant dashboards can reuse the serializer later.
        'organization_count': 1,
        'workspace_count': workspace_count,
        'user_count': user_count,
        'project_count': project_count,
        'completion': {'total': total, 'finished': finished, 'percent': percent},
    }


def _workspace_manager_widgets(user, organization) -> dict:
    """Summary per workspace the caller manages."""
    ws_qs = WorkspaceMember.objects.filter(
        user=user,
        workspace__organization=organization,
        role=WorkspaceMember.Role.WORKSPACE_MANAGER,
        deleted_at__isnull=True,
        workspace__deleted_at__isnull=True,
    ).select_related('workspace')
    from tasks.models import Task

    workspaces: List[dict] = []
    for m in ws_qs:
        ws = m.workspace
        projects = Project.objects.filter(workspace=ws)
        workspace_tasks = Task.objects.filter(project__workspace=ws)
        total = workspace_tasks.count()
        finished = workspace_tasks.filter(is_labeled=True).count()
        workspaces.append({
            'workspace_id': ws.id,
            'title': ws.title,
            'project_count': projects.count(),
            'completion': {
                'total': total,
                'finished': finished,
                'percent': int(round(finished / total * 100)) if total else 0,
            },
        })
    return {'workspaces': workspaces}


def _project_manager_widgets(user, organization) -> dict:
    """Per-managed-project: completion + worker progress + estimated settlement."""
    projects = list(_manager_projects_qs(user, organization).select_related('pricing'))
    project_ids = [p.id for p in projects]

    # Worker progress — per-user ACCEPTED counts for each managed project.
    accepted_rows = (
        AnnotationState.objects.filter(
            project_id__in=project_ids,
            state=AnnotationStateChoices.ACCEPTED,
            transition_name=_ACCEPT_TRANSITION,
            completed_by_id__isnull=False,
        )
        .values('project_id', 'completed_by_id')
        .annotate(total=Count('id'))
    )
    by_project: Dict[int, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for row in accepted_rows:
        by_project[row['project_id']][row['completed_by_id']] = row['total']

    # Review counts for settlement estimate.
    review_rows = (
        AnnotationState.objects.filter(
            project_id__in=project_ids,
            transition_name__in=[_ACCEPT_TRANSITION, _REJECT_TRANSITION],
            triggered_by__isnull=False,
        )
        .values('project_id')
        .annotate(total=Count('id'))
    )
    reviews_by_project: Dict[int, int] = {r['project_id']: r['total'] for r in review_rows}
    accepted_by_project: Dict[int, int] = {
        pid: sum(users.values()) for pid, users in by_project.items()
    }

    project_blocks: List[dict] = []
    for project in projects:
        completion = _project_completion(project)
        worker_map = by_project.get(project.id, {})
        worker_progress = [
            {'user_id': uid, 'accepted': count}
            for uid, count in sorted(
                worker_map.items(), key=lambda kv: kv[1], reverse=True
            )
        ]
        pricing: Optional[ProjectPricing] = getattr(project, 'pricing', None)
        if pricing is not None:
            label_amount = Decimal(pricing.label_price) * Decimal(
                accepted_by_project.get(project.id, 0)
            )
            review_amount = Decimal(pricing.review_price) * Decimal(
                reviews_by_project.get(project.id, 0)
            )
            total = label_amount + review_amount
            estimated = {
                'currency': pricing.currency,
                'label_amount': str(label_amount),
                'review_amount': str(review_amount),
                'total_amount': str(total),
                'accepted_count': accepted_by_project.get(project.id, 0),
                'review_count': reviews_by_project.get(project.id, 0),
            }
        else:
            estimated = None
        project_blocks.append({
            **completion,
            'type': project.type,
            'worker_progress': worker_progress,
            'estimated_settlement': estimated,
        })
    return {'projects': project_blocks}


def _annotator_widgets(user, organization) -> dict:
    """Assigned tasks today + rejected tasks waiting for rework + deadline list."""
    if organization is None:
        return {
            'today_assigned': 0,
            'rejected_open': 0,
            'rejected_tasks': [],
            'deadlines': [],
        }
    start, end = _today_range()
    # Projects the caller is an annotator on.
    project_ids = list(
        ProjectMember.objects.filter(
            user=user,
            project__organization=organization,
            role=ProjectRole.ANNOTATOR,
            deleted_at__isnull=True,
            enabled=True,
        ).values_list('project_id', flat=True)
    )

    today_assigned = 0
    rejected_open = 0
    rejected_tasks: List[dict] = []
    if project_ids:
        # Today's ASSIGNED transitions for the caller.
        today_assigned = AnnotationState.objects.filter(
            project_id__in=project_ids,
            state=AnnotationStateChoices.ASSIGNED,
            completed_by_id=user.id,
            created_at__gte=start,
            created_at__lt=end,
        ).count()

        # "Latest state per annotation" without DISTINCT ON — compatible with
        # SQLite (CI) and Postgres alike. Keep only rows whose id matches the
        # max id for that annotation, then filter to REJECTED terminals owned
        # by the caller.
        latest_id_subq = (
            AnnotationState.objects.filter(annotation_id=OuterRef('annotation_id'))
            .order_by('-id')
            .values('id')[:1]
        )
        rejected_qs = (
            AnnotationState.objects.filter(
                project_id__in=project_ids,
                state=AnnotationStateChoices.REJECTED,
                completed_by_id=user.id,
                id=Subquery(latest_id_subq),
            )
            .order_by('-id')
            .values('annotation_id', 'task_id', 'project_id', 'created_at')
        )
        rejected_list = list(rejected_qs[:25])
        rejected_open = len(rejected_list)
        rejected_tasks = [
            {
                'annotation_id': r['annotation_id'],
                'task_id': r['task_id'],
                'project_id': r['project_id'],
                'rejected_at': r['created_at'].isoformat(),
            }
            for r in rejected_list
        ]

    return {
        'today_assigned': today_assigned,
        'rejected_open': rejected_open,
        'rejected_tasks': rejected_tasks,
        # Project-level deadlines are not yet modeled in the Project schema —
        # surface an empty list so the widget renders gracefully. Phase 9 adds
        # the field.
        'deadlines': [],
    }


def _reviewer_widgets(user, organization) -> dict:
    """Pending review queue + the caller's most recent accept/reject decisions."""
    if organization is None:
        return {'pending_review': 0, 'recent_decisions': []}
    project_ids = list(
        ProjectMember.objects.filter(
            user=user,
            project__organization=organization,
            role=ProjectRole.REVIEWER,
            deleted_at__isnull=True,
            enabled=True,
        ).values_list('project_id', flat=True)
    )
    if not project_ids:
        return {'pending_review': 0, 'recent_decisions': []}

    # Latest-state-per-annotation = WILL_REVIEWED across all review projects.
    # UUID7 ordering (-id) means the largest id per annotation_id is the newest.
    latest_id_subq = (
        AnnotationState.objects.filter(annotation_id=OuterRef('annotation_id'))
        .order_by('-id')
        .values('id')[:1]
    )
    pending_review = AnnotationState.objects.filter(
        project_id__in=project_ids,
        state=AnnotationStateChoices.WILL_REVIEWED,
        id=Subquery(latest_id_subq),
    ).count()

    recent_qs = (
        AnnotationState.objects.filter(
            project_id__in=project_ids,
            transition_name__in=[_ACCEPT_TRANSITION, _REJECT_TRANSITION],
            triggered_by_id=user.id,
        )
        .order_by('-id')
        .values('annotation_id', 'project_id', 'state', 'created_at', 'transition_name')[:20]
    )
    recent_decisions = [
        {
            'annotation_id': r['annotation_id'],
            'project_id': r['project_id'],
            'state': r['state'],
            'transition': r['transition_name'],
            'reviewed_at': r['created_at'].isoformat(),
        }
        for r in recent_qs
    ]
    return {'pending_review': pending_review, 'recent_decisions': recent_decisions}


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


def build_dashboard_summary(user, organization) -> dict:
    """Return the role-scoped dashboard payload for `user` in `organization`."""
    roles = _effective_roles(user, organization)
    summary: Dict[str, dict] = {}
    if OrganizationRole.SUPER_ADMIN in roles:
        summary['super_admin'] = _super_admin_widgets(user, organization)
    if WorkspaceMember.Role.WORKSPACE_MANAGER in roles:
        summary['workspace_manager'] = _workspace_manager_widgets(user, organization)
    if ProjectRole.PROJECT_MANAGER in roles:
        summary['project_manager'] = _project_manager_widgets(user, organization)
    if ProjectRole.ANNOTATOR in roles:
        summary['annotator'] = _annotator_widgets(user, organization)
    if ProjectRole.REVIEWER in roles:
        summary['reviewer'] = _reviewer_widgets(user, organization)
    return {
        'roles': roles,
        'organization_id': organization.id if organization is not None else None,
        'summary': summary,
        'generated_at': timezone.now().isoformat(),
    }
