"""Resolve a user's effective (canonical) role for a project or workspace.

Returns the single highest-privilege role string the user holds for the given
object, or ``None`` when they have no access. Built on the predicates in
``users.rules`` and exposed to the frontend (via serializers) as
``current_user_role`` so the UI can gate menus, routes and controls per role.

The backend still enforces access independently through API permissions — this
module only *describes* the role for display/UX; it does not grant anything.
"""

from __future__ import annotations

from users.rules import (
    is_annotator_of,
    is_project_manager_of,
    is_project_member_of,
    is_reviewer_of,
    is_super_admin,
    is_workspace_manager_of,
)

# Canonical role strings shared with the frontend.
ROLE_SUPER_ADMIN = 'super_admin'
ROLE_WORKSPACE_MANAGER = 'workspace_manager'
ROLE_PROJECT_MANAGER = 'project_manager'
ROLE_REVIEWER = 'reviewer'
ROLE_ANNOTATOR = 'annotator'
ROLE_MEMBER = 'member'


def resolve_project_role(user, project):
    """Highest-privilege role the user holds in ``project`` (or ``None``)."""
    if project is None or not user or not user.is_authenticated:
        return None
    if is_super_admin.test(user):
        return ROLE_SUPER_ADMIN
    if is_workspace_manager_of.test(user, project):
        return ROLE_WORKSPACE_MANAGER
    # is_project_manager_of also matches workspace managers, but those already
    # returned above — so reaching here means an explicit project_manager row.
    if is_project_manager_of.test(user, project):
        return ROLE_PROJECT_MANAGER
    if is_reviewer_of.test(user, project):
        return ROLE_REVIEWER
    if is_annotator_of.test(user, project):
        return ROLE_ANNOTATOR
    if is_project_member_of.test(user, project):
        return ROLE_MEMBER
    return None


def resolve_workspace_role(user, workspace):
    """Highest-privilege role the user holds in ``workspace`` (or ``None``).

    A project manager of any project inside the workspace gets view-only
    (``project_manager``) access; a plain workspace member (``member``) may see
    only the workspace header per the permission spec.
    """
    if workspace is None or not user or not user.is_authenticated:
        return None
    if is_super_admin.test(user):
        return ROLE_SUPER_ADMIN
    if is_workspace_manager_of.test(user, workspace):
        return ROLE_WORKSPACE_MANAGER

    from projects.models import Project
    from users.constants import ProjectRole

    manages_project = Project.objects.filter(
        workspace=workspace,
        members__user=user,
        members__role=ProjectRole.PROJECT_MANAGER,
        members__deleted_at__isnull=True,
    ).exists()
    if manages_project:
        return ROLE_PROJECT_MANAGER

    if workspace.members.filter(user=user, deleted_at__isnull=True).exists():
        return ROLE_MEMBER
    return None
