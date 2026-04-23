"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

import rules
from core.permissions import make_perm


@rules.predicate
def is_workspace_manager(user, workspace):
    if workspace is None or not user or not user.is_authenticated:
        return False
    # Organization owner implicitly manages every workspace in their org.
    if workspace.organization.created_by_id and workspace.organization.created_by_id == user.id:
        return True
    return workspace.members.filter(
        user=user,
        role='workspace_manager',
        deleted_at__isnull=True,
    ).exists()


@rules.predicate
def is_workspace_member(user, workspace):
    if workspace is None or not user or not user.is_authenticated:
        return False
    if workspace.organization.created_by_id and workspace.organization.created_by_id == user.id:
        return True
    return workspace.members.filter(user=user, deleted_at__isnull=True).exists()


# Override the default is_authenticated predicate for destructive/invite actions —
# only workspace managers (or org owners) may mutate the workspace or invite members.
make_perm('workspaces.change', is_workspace_manager, overwrite=True)
make_perm('workspaces.delete', is_workspace_manager, overwrite=True)
make_perm('workspaces.invite', is_workspace_manager, overwrite=True)
