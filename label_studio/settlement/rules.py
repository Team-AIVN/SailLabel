"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

import rules
from core.permissions import make_perm


def _project_from_obj(obj):
    """Accept either a Project instance or anything with a `.project` attribute.

    Settlement objects (SettlementBatch, ProjectPricing) all hang off a Project,
    so the predicate can normalise here and check org/workspace membership once.
    """
    if obj is None:
        return None
    if hasattr(obj, 'project') and obj.project is not None:
        return obj.project
    return obj


@rules.predicate
def is_settlement_manager(user, obj):
    """True if `user` may create/edit/run settlement batches for `obj`'s project.

    Org owner → workspace manager → project creator form the allowlist. Regular
    workspace members do not get settlement-mutation rights because payouts touch
    money.
    """
    project = _project_from_obj(obj)
    if project is None or not user or not user.is_authenticated:
        return False
    organization = getattr(project, 'organization', None)
    if organization is not None and organization.created_by_id == user.id:
        return True
    workspace = getattr(project, 'workspace', None)
    if workspace is not None:
        if workspace.members.filter(
            user=user, role='workspace_manager', deleted_at__isnull=True
        ).exists():
            return True
    if project.created_by_id == user.id:
        return True
    return False


@rules.predicate
def is_settlement_viewer(user, obj):
    """True if `user` may view pricing / batch history.

    Any authenticated user in the same organization as the project is allowed —
    payroll visibility is intentionally broader than mutation rights so team
    members can audit their own payouts.
    """
    project = _project_from_obj(obj)
    if project is None or not user or not user.is_authenticated:
        return False
    organization = getattr(project, 'organization', None)
    if organization is None:
        return False
    active = getattr(user, 'active_organization_id', None)
    return active == organization.id or organization.created_by_id == user.id


make_perm('settlement.view', is_settlement_viewer, overwrite=True)
make_perm('settlement.change', is_settlement_manager, overwrite=True)
make_perm('settlement.delete', is_settlement_manager, overwrite=True)
make_perm('settlement.run_batch', is_settlement_manager, overwrite=True)
make_perm('settlement.set_pricing', is_settlement_manager, overwrite=True)
