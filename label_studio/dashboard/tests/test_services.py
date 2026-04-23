"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from django.test import TestCase
from organizations.models import OrganizationMember
from organizations.tests.factories import OrganizationFactory
from projects.models import ProjectMember
from projects.tests.factories import ProjectFactory
from users.constants import OrganizationRole, ProjectRole
from users.tests.factories import UserFactory
from workspaces.models import WorkspaceMember
from workspaces.tests.factories import WorkspaceFactory

from dashboard.services import _effective_roles, build_dashboard_summary


class EffectiveRolesTests(TestCase):
    """Union-of-roles — a single user can carry multiple role flags at once."""

    def setUp(self):
        self.organization = OrganizationFactory()

    def test_plain_member_returns_empty_role_set(self):
        user = UserFactory()
        OrganizationMember.objects.create(user=user, organization=self.organization)
        assert _effective_roles(user, self.organization) == []

    def test_super_admin_org_member(self):
        user = UserFactory()
        OrganizationMember.objects.create(
            user=user, organization=self.organization, role=OrganizationRole.SUPER_ADMIN
        )
        assert OrganizationRole.SUPER_ADMIN in _effective_roles(user, self.organization)

    def test_is_superuser_promotes_to_super_admin(self):
        user = UserFactory(is_superuser=True)
        OrganizationMember.objects.create(user=user, organization=self.organization)
        assert OrganizationRole.SUPER_ADMIN in _effective_roles(user, self.organization)

    def test_workspace_manager_and_project_reviewer_coexist(self):
        user = UserFactory()
        OrganizationMember.objects.create(user=user, organization=self.organization)
        workspace = WorkspaceFactory(organization=self.organization)
        WorkspaceMember.objects.create(
            user=user, workspace=workspace, role=WorkspaceMember.Role.WORKSPACE_MANAGER
        )
        project = ProjectFactory(organization=self.organization, created_by=user)
        ProjectMember.objects.create(
            user=user, project=project, role=ProjectRole.REVIEWER, enabled=True
        )
        roles = _effective_roles(user, self.organization)
        assert WorkspaceMember.Role.WORKSPACE_MANAGER in roles
        assert ProjectRole.REVIEWER in roles


class BuildDashboardSummaryTests(TestCase):
    """Top-level payload shape: roles array, summary dict, generated_at."""

    def setUp(self):
        self.organization = OrganizationFactory()
        self.owner = self.organization.created_by

    def test_payload_has_required_keys(self):
        user = UserFactory()
        OrganizationMember.objects.create(user=user, organization=self.organization)
        payload = build_dashboard_summary(user, self.organization)
        assert set(payload.keys()) == {'roles', 'organization_id', 'summary', 'generated_at'}

    def test_no_organization_yields_empty_roles(self):
        user = UserFactory()
        payload = build_dashboard_summary(user, None)
        assert payload['organization_id'] is None
        assert payload['roles'] == []
        assert payload['summary'] == {}

    def test_super_admin_branch_populated(self):
        user = UserFactory()
        OrganizationMember.objects.create(
            user=user, organization=self.organization, role=OrganizationRole.SUPER_ADMIN
        )
        payload = build_dashboard_summary(user, self.organization)
        assert 'super_admin' in payload['summary']
        assert 'completion' in payload['summary']['super_admin']
