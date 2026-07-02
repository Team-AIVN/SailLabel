"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

import pytest
from django.db import IntegrityError
from django.utils import timezone
from organizations.tests.factories import OrganizationFactory
from workspaces.models import Workspace, WorkspaceMember

from .factories import WorkspaceFactory, WorkspaceMemberFactory

pytestmark = pytest.mark.django_db


def test_visible_manager_hides_soft_deleted_rows():
    """Default `objects` manager excludes soft-deleted workspaces; `all_objects` returns them."""
    org = OrganizationFactory()
    active = WorkspaceFactory(organization=org, title='active')
    deleted = WorkspaceFactory(organization=org, title='archived')
    deleted.soft_delete(user=org.created_by)

    visible_titles = set(Workspace.objects.values_list('title', flat=True))
    all_titles = set(Workspace.all_objects.values_list('title', flat=True))

    assert 'active' in visible_titles
    assert 'archived' not in visible_titles
    assert {'active', 'archived'} <= all_titles
    assert active.pk in set(Workspace.objects.values_list('pk', flat=True))


def test_soft_delete_sets_deleted_at_and_deleted_by():
    """soft_delete populates deleted_at + deleted_by and leaves the row in the DB."""
    org = OrganizationFactory()
    workspace = WorkspaceFactory(organization=org)
    user = org.created_by

    workspace.soft_delete(user=user)
    workspace.refresh_from_db()

    assert workspace.deleted_at is not None
    assert workspace.deleted_by_id == user.id
    # Row still exists in the DB via the unfiltered manager.
    assert Workspace.all_objects.filter(pk=workspace.pk).exists()


def test_partial_unique_constraint_scoped_to_organization():
    """Two workspaces with the same title are allowed across different organizations."""
    org1 = OrganizationFactory()
    org2 = OrganizationFactory()
    WorkspaceFactory(organization=org1, title='shared')
    WorkspaceFactory(organization=org2, title='shared')  # should not raise

    assert Workspace.objects.filter(title='shared').count() == 2


def test_partial_unique_constraint_blocks_duplicate_active_titles():
    """Same (organization, title) cannot coexist as two active rows."""
    org = OrganizationFactory()
    WorkspaceFactory(organization=org, title='duplicate')

    with pytest.raises(IntegrityError):
        # Bypass factory defaults; write directly to trigger DB constraint.
        Workspace.objects.create(
            organization=org,
            title='duplicate',
            created_by=org.created_by,
        )


def test_partial_unique_constraint_allows_reuse_after_soft_delete():
    """A soft-deleted workspace's title can be reused because uniqueness is partial (deleted_at IS NULL)."""
    org = OrganizationFactory()
    original = WorkspaceFactory(organization=org, title='reusable')
    original.soft_delete(user=org.created_by)

    # New workspace with the same title should not collide with the soft-deleted one.
    reused = Workspace.objects.create(
        organization=org,
        title='reusable',
        created_by=org.created_by,
    )
    assert reused.pk != original.pk
    assert Workspace.all_objects.filter(organization=org, title='reusable').count() == 2


def test_workspace_member_unique_constraint():
    """A user cannot have two membership rows in the same workspace."""
    org = OrganizationFactory()
    workspace = WorkspaceFactory(organization=org)
    WorkspaceMemberFactory(workspace=workspace, user=org.created_by)

    with pytest.raises(IntegrityError):
        WorkspaceMember.objects.create(
            user=org.created_by,
            workspace=workspace,
            role=WorkspaceMember.Role.WORKSPACE_MANAGER,
        )


def test_workspace_member_role_defaults_to_member():
    """WorkspaceMember.role defaults to MEMBER when not explicitly set."""
    org = OrganizationFactory()
    workspace = WorkspaceFactory(organization=org)
    member = WorkspaceMember.objects.create(user=org.created_by, workspace=workspace)

    assert member.role == WorkspaceMember.Role.MEMBER


def test_workspace_member_soft_delete_field():
    """WorkspaceMember.deleted_at supports soft delete pattern."""
    org = OrganizationFactory()
    workspace = WorkspaceFactory(organization=org)
    member = WorkspaceMemberFactory(workspace=workspace, user=org.created_by)

    member.deleted_at = timezone.now()
    member.save(update_fields=['deleted_at', 'updated_at'])
    member.refresh_from_db()

    assert member.deleted_at is not None
