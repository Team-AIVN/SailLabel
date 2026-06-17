"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

import importlib

import pytest
from django.apps import apps as global_apps
from organizations.tests.factories import OrganizationFactory
from projects.models import Project
from projects.tests.factories import ProjectFactory
from workspaces.models import Workspace, WorkspaceMember

pytestmark = pytest.mark.django_db


def _run_backfill():
    module = importlib.import_module('projects.migrations.0036_backfill_project_workspace')
    module.forwards(global_apps, schema_editor=None)


def test_backfill_creates_default_workspace_per_organization():
    """Each organization gets its own 'Default' workspace after backfill."""
    org1 = OrganizationFactory()
    org2 = OrganizationFactory()

    # Ensure no pre-existing Default workspace for these fresh orgs.
    Workspace.all_objects.filter(organization__in=[org1, org2], title='Default').delete()

    _run_backfill()

    ws1 = Workspace.objects.get(organization=org1, title='Default')
    ws2 = Workspace.objects.get(organization=org2, title='Default')
    assert ws1.pk != ws2.pk
    assert ws1.created_by_id == org1.created_by_id
    assert ws2.created_by_id == org2.created_by_id


def test_backfill_assigns_null_projects_to_default_workspace():
    """Projects with workspace IS NULL are assigned to the org's Default workspace."""
    org = OrganizationFactory()
    Workspace.all_objects.filter(organization=org, title='Default').delete()

    unassigned_a = ProjectFactory(organization=org, title='orphan-a')
    unassigned_b = ProjectFactory(organization=org, title='orphan-b')
    # Ensure workspace is NULL pre-backfill (factory shouldn't set it, but be explicit).
    Project.objects.filter(pk__in=[unassigned_a.pk, unassigned_b.pk]).update(workspace=None)

    _run_backfill()

    default_ws = Workspace.objects.get(organization=org, title='Default')
    unassigned_a.refresh_from_db()
    unassigned_b.refresh_from_db()
    assert unassigned_a.workspace_id == default_ws.id
    assert unassigned_b.workspace_id == default_ws.id


def test_backfill_does_not_overwrite_existing_workspace_assignments():
    """Projects already assigned to a non-default workspace keep their assignment."""
    org = OrganizationFactory()
    Workspace.all_objects.filter(organization=org, title='Default').delete()

    other_workspace = Workspace.objects.create(
        organization=org,
        title='Pre-existing',
        created_by=org.created_by,
    )
    assigned_project = ProjectFactory(organization=org, title='already-placed')
    assigned_project.workspace = other_workspace
    assigned_project.save(update_fields=['workspace'])

    _run_backfill()

    assigned_project.refresh_from_db()
    assert assigned_project.workspace_id == other_workspace.id


def test_backfill_registers_owner_as_workspace_manager():
    """Org owner is added as workspace_manager when the Default workspace is created."""
    org = OrganizationFactory()
    Workspace.all_objects.filter(organization=org, title='Default').delete()

    _run_backfill()

    default_ws = Workspace.objects.get(organization=org, title='Default')
    membership = WorkspaceMember.objects.get(workspace=default_ws, user_id=org.created_by_id)
    assert membership.role == WorkspaceMember.Role.WORKSPACE_MANAGER


def test_backfill_is_idempotent():
    """Running the backfill twice does not create duplicate Default workspaces."""
    org = OrganizationFactory()
    Workspace.all_objects.filter(organization=org, title='Default').delete()

    _run_backfill()
    _run_backfill()

    assert Workspace.all_objects.filter(organization=org, title='Default').count() == 1
