"""Role predicates for LabelSea RBAC.

Predicates are unary (``user``) or binary (``user, obj``). django-rules composes them
via ``&``/``|`` — see ``projects/rules.py`` and ``workspaces/rules.py`` for the
concrete wiring onto named permissions.

Design notes:
- ``is_super_admin`` checks Django ``is_superuser`` first (escape hatch for the
  installation operator), then the app-level ``OrganizationMember.role`` row.
- Project predicates accept either a ``Project`` or a ``ProjectMember`` (anything
  with a ``project`` attribute) so callers can pass whichever they already loaded.
- Workspace manager is recognised as a project manager implicitly so that workspace
  managers retain control over projects inside their workspace.
- Worker = annotator ∪ reviewer (logical union, not a stored role).
"""

from __future__ import annotations

import rules

from users.constants import WORKER_ROLES, OrganizationRole, ProjectRole


def _resolve_project(obj):
    if obj is None:
        return None
    # ProjectMember, Annotation, Task — any object carrying `project`
    if hasattr(obj, 'project') and obj.project is not None:
        return obj.project
    return obj


def _resolve_workspace(obj):
    if obj is None:
        return None
    from workspaces.models import Workspace

    if isinstance(obj, Workspace):
        return obj
    # Project → its workspace (or any object exposing .project)
    project = _resolve_project(obj)
    if project is not None and getattr(project, 'workspace_id', None):
        return project.workspace
    return None


@rules.predicate
def is_authenticated_user(user):
    return bool(user and user.is_authenticated)


@rules.predicate
def is_super_admin(user):
    if not user or not user.is_authenticated:
        return False
    if getattr(user, 'is_superuser', False):
        return True
    org_id = getattr(user, 'active_organization_id', None)
    if not org_id:
        return False
    from organizations.models import Organization, OrganizationMember

    # The organization owner (creator) is the super admin for their organization.
    if Organization.objects.filter(id=org_id, created_by=user).exists():
        return True

    return OrganizationMember.objects.filter(
        user=user,
        organization_id=org_id,
        role=OrganizationRole.SUPER_ADMIN,
        deleted_at__isnull=True,
    ).exists()


@rules.predicate
def is_workspace_manager_of(user, obj):
    if not user or not user.is_authenticated:
        return False
    workspace = _resolve_workspace(obj)
    if workspace is None:
        return False
    if workspace.organization.created_by_id and workspace.organization.created_by_id == user.id:
        return True
    return workspace.members.filter(
        user=user,
        role='workspace_manager',
        deleted_at__isnull=True,
    ).exists()


def _has_project_role(user, obj, role):
    if not user or not user.is_authenticated:
        return False
    project = _resolve_project(obj)
    if project is None:
        return False
    return project.members.filter(
        user=user,
        role=role,
        deleted_at__isnull=True,
    ).exists()


@rules.predicate
def is_project_manager_of(user, obj):
    # Workspace manager supervises every project inside the workspace.
    if is_workspace_manager_of.test(user, obj):
        return True
    return _has_project_role(user, obj, ProjectRole.PROJECT_MANAGER)


@rules.predicate
def is_annotator_of(user, obj):
    return _has_project_role(user, obj, ProjectRole.ANNOTATOR)


@rules.predicate
def is_reviewer_of(user, obj):
    return _has_project_role(user, obj, ProjectRole.REVIEWER)


@rules.predicate
def is_worker_of(user, obj):
    if not user or not user.is_authenticated:
        return False
    project = _resolve_project(obj)
    if project is None:
        return False
    return project.members.filter(
        user=user,
        role__in=WORKER_ROLES,
        deleted_at__isnull=True,
    ).exists()


@rules.predicate
def is_project_member_of(user, obj):
    if not user or not user.is_authenticated:
        return False
    project = _resolve_project(obj)
    if project is None:
        return False
    return project.members.filter(user=user, deleted_at__isnull=True).exists()


def _manages_a_workspace(user):
    """Shared rule for creating projects/workspaces: super admins, and anyone who
    manages at least one workspace in their active organization. Unary (create has no
    target object), so a brand-new org is bootstrapped by its super admin, who can then
    delegate by making others workspace managers."""
    if not user or not user.is_authenticated:
        return False
    if is_super_admin.test(user):
        return True
    org_id = getattr(user, 'active_organization_id', None)
    if not org_id:
        return False
    from workspaces.models import WorkspaceMember

    return WorkspaceMember.objects.filter(
        user=user,
        workspace__organization_id=org_id,
        role='workspace_manager',
        deleted_at__isnull=True,
    ).exists()


@rules.predicate
def can_create_project(user):
    """Project creation is a management action (WM/SA) — see ``_manages_a_workspace``."""
    return _manages_a_workspace(user)


@rules.predicate
def can_create_workspace(user):
    """Workspace creation is a management action (WM/SA) — see ``_manages_a_workspace``."""
    return _manages_a_workspace(user)


@rules.predicate
def not_self_review(user, annotation):
    """Self-review prohibition — isolated from the full authorisation rule.

    ``tasks/api.py`` enforces this at the endpoint regardless of the caller's
    project role (OSS default allows any authenticated user to invoke the
    endpoint, so the self-review guard must stand independently).
    """
    if annotation is None:
        return False
    if not user or not user.is_authenticated:
        return False
    completed_by_id = getattr(annotation, 'completed_by_id', None)
    return not (completed_by_id and completed_by_id == user.id)


@rules.predicate
def can_review_annotation(user, annotation):
    """Full reviewer authorisation: self-review denied *and* role membership present.

    Use this where the caller needs a single yes/no (e.g. the ``/next-review/``
    queue filter). The accept/reject HTTP endpoints rely on ``not_self_review``
    on its own so they remain compatible with OSS role-less installations.
    """
    if not not_self_review.test(user, annotation):
        return False
    project = getattr(annotation, 'project', None) or getattr(getattr(annotation, 'task', None), 'project', None)
    if project is None:
        return False
    return is_reviewer_of.test(user, project) or is_project_manager_of.test(user, project)
