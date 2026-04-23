"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from decimal import Decimal

from organizations.models import OrganizationMember
from organizations.tests.factories import OrganizationFactory
from projects.models import ProjectMember
from projects.tests.factories import ProjectFactory
from rest_framework.test import APITestCase
from settlement.models import Currency, ProjectPricing
from users.constants import OrganizationRole, ProjectRole
from users.tests.factories import UserFactory
from workspaces.models import WorkspaceMember
from workspaces.tests.factories import WorkspaceFactory


def _join_org(user, org, role=OrganizationRole.MEMBER):
    user.active_organization = org
    user.save(update_fields=['active_organization'])
    OrganizationMember.objects.update_or_create(
        user=user, organization=org, defaults={'role': role}
    )


class DashboardSummaryAPITests(APITestCase):
    """Role-scoped payload: every role branch only surfaces for entitled users."""

    url = '/api/dashboard/summary/'

    def setUp(self):
        self.organization = OrganizationFactory()
        self.owner = self.organization.created_by
        self.owner.active_organization = self.organization
        self.owner.save(update_fields=['active_organization'])

    def test_unauthenticated_denied(self):
        response = self.client.get(self.url)
        assert response.status_code in (401, 403)

    def test_plain_member_sees_no_role_branches(self):
        user = UserFactory()
        _join_org(user, self.organization)
        self.client.force_authenticate(user=user)

        response = self.client.get(self.url)
        assert response.status_code == 200
        body = response.json()
        assert body['organization_id'] == self.organization.id
        assert body['roles'] == []
        assert body['summary'] == {}

    def test_super_admin_role_populates_overview(self):
        admin = UserFactory()
        _join_org(admin, self.organization, role=OrganizationRole.SUPER_ADMIN)
        # Add a workspace and project so the counts aren't all zero.
        WorkspaceFactory(organization=self.organization, title='W1')
        ProjectFactory(organization=self.organization, created_by=admin)

        self.client.force_authenticate(user=admin)
        response = self.client.get(self.url)
        assert response.status_code == 200
        body = response.json()
        assert OrganizationRole.SUPER_ADMIN in body['roles']
        sa = body['summary']['super_admin']
        assert sa['workspace_count'] >= 1
        assert sa['project_count'] >= 1
        assert sa['user_count'] >= 1
        assert 'completion' in sa

    def test_workspace_manager_lists_managed_workspaces(self):
        manager = UserFactory()
        _join_org(manager, self.organization)
        workspace = WorkspaceFactory(organization=self.organization, title='Ops')
        WorkspaceMember.objects.create(
            user=manager, workspace=workspace, role=WorkspaceMember.Role.WORKSPACE_MANAGER
        )

        self.client.force_authenticate(user=manager)
        response = self.client.get(self.url)
        assert response.status_code == 200
        body = response.json()
        assert WorkspaceMember.Role.WORKSPACE_MANAGER in body['roles']
        wm = body['summary']['workspace_manager']
        titles = {w['title'] for w in wm['workspaces']}
        assert 'Ops' in titles

    def test_project_manager_lists_managed_projects_with_settlement_estimate(self):
        manager = UserFactory()
        _join_org(manager, self.organization)
        project = ProjectFactory(organization=self.organization, created_by=manager)
        ProjectMember.objects.create(
            user=manager, project=project, role=ProjectRole.PROJECT_MANAGER, enabled=True
        )
        ProjectPricing.objects.create(
            project=project,
            label_price=Decimal('100'),
            review_price=Decimal('50'),
            currency=Currency.KRW,
        )

        self.client.force_authenticate(user=manager)
        response = self.client.get(self.url)
        assert response.status_code == 200
        body = response.json()
        assert ProjectRole.PROJECT_MANAGER in body['roles']
        pm = body['summary']['project_manager']
        project_ids = [p['project_id'] for p in pm['projects']]
        assert project.id in project_ids
        target = next(p for p in pm['projects'] if p['project_id'] == project.id)
        # No annotations yet ⇒ estimate payload renders but totals are zero.
        assert target['estimated_settlement'] is not None
        assert target['estimated_settlement']['currency'] == Currency.KRW
        assert Decimal(target['estimated_settlement']['total_amount']) == Decimal('0')

    def test_project_manager_without_pricing_returns_null_estimate(self):
        manager = UserFactory()
        _join_org(manager, self.organization)
        project = ProjectFactory(organization=self.organization, created_by=manager)
        ProjectMember.objects.create(
            user=manager, project=project, role=ProjectRole.PROJECT_MANAGER, enabled=True
        )

        self.client.force_authenticate(user=manager)
        response = self.client.get(self.url)
        body = response.json()
        pm = body['summary']['project_manager']
        target = next(p for p in pm['projects'] if p['project_id'] == project.id)
        assert target['estimated_settlement'] is None

    def test_annotator_branch_renders_zero_counts_without_state_data(self):
        worker = UserFactory()
        _join_org(worker, self.organization)
        project = ProjectFactory(organization=self.organization, created_by=self.owner)
        ProjectMember.objects.create(
            user=worker, project=project, role=ProjectRole.ANNOTATOR, enabled=True
        )

        self.client.force_authenticate(user=worker)
        response = self.client.get(self.url)
        body = response.json()
        assert ProjectRole.ANNOTATOR in body['roles']
        ann = body['summary']['annotator']
        assert ann['today_assigned'] == 0
        assert ann['rejected_open'] == 0
        assert ann['deadlines'] == []

    def test_reviewer_branch_renders_empty_queue_initially(self):
        reviewer = UserFactory()
        _join_org(reviewer, self.organization)
        project = ProjectFactory(organization=self.organization, created_by=self.owner)
        ProjectMember.objects.create(
            user=reviewer, project=project, role=ProjectRole.REVIEWER, enabled=True
        )

        self.client.force_authenticate(user=reviewer)
        response = self.client.get(self.url)
        body = response.json()
        assert ProjectRole.REVIEWER in body['roles']
        rv = body['summary']['reviewer']
        assert rv['pending_review'] == 0
        assert rv['recent_decisions'] == []

    def test_multi_role_user_gets_union_payload(self):
        """A PM who also reviews on a different project sees both branches."""
        user = UserFactory()
        _join_org(user, self.organization)
        p_mgr = ProjectFactory(organization=self.organization, created_by=user)
        p_rev = ProjectFactory(organization=self.organization, created_by=self.owner)
        ProjectMember.objects.create(
            user=user, project=p_mgr, role=ProjectRole.PROJECT_MANAGER, enabled=True
        )
        ProjectMember.objects.create(
            user=user, project=p_rev, role=ProjectRole.REVIEWER, enabled=True
        )

        self.client.force_authenticate(user=user)
        body = self.client.get(self.url).json()
        assert ProjectRole.PROJECT_MANAGER in body['roles']
        assert ProjectRole.REVIEWER in body['roles']
        assert 'project_manager' in body['summary']
        assert 'reviewer' in body['summary']
