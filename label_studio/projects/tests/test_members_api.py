"""Tests for /api/projects/<pk>/members/ (role management)."""

from organizations.models import OrganizationMember
from organizations.tests.factories import OrganizationFactory
from projects.models import ProjectMember
from projects.tests.factories import ProjectFactory
from rest_framework.test import APITestCase
from users.constants import OrganizationRole, ProjectRole
from users.tests.factories import UserFactory


def _join_org(user, org, role=OrganizationRole.MEMBER):
    user.active_organization = org
    user.save(update_fields=['active_organization'])
    OrganizationMember.objects.update_or_create(
        user=user, organization=org, defaults={'role': role}
    )


class ProjectMemberAPITests(APITestCase):
    def setUp(self):
        self.organization = OrganizationFactory()
        self.owner = self.organization.created_by
        # Seed the org owner as a super_admin so they can manage project members
        # without needing a workspace or explicit project_manager row. Mirrors
        # what the onboarding flow should eventually set up.
        _join_org(self.owner, self.organization, role=OrganizationRole.SUPER_ADMIN)
        self.project = ProjectFactory(organization=self.organization)

        self.outsider = UserFactory()
        _join_org(self.outsider, self.organization)

    def test_org_owner_can_add_project_member(self):
        self.client.force_authenticate(user=self.owner)
        resp = self.client.post(
            f'/api/projects/{self.project.id}/members/',
            {'user': self.outsider.id, 'role': ProjectRole.REVIEWER},
            format='json',
        )
        assert resp.status_code == 201, resp.content
        body = resp.json()
        assert body['role'] == ProjectRole.REVIEWER
        assert body['user'] == self.outsider.id

        member = ProjectMember.objects.get(user=self.outsider, project=self.project)
        assert member.role == ProjectRole.REVIEWER
        assert member.deleted_at is None

    def test_non_manager_forbidden_to_add(self):
        _join_org(self.outsider, self.organization)
        self.client.force_authenticate(user=self.outsider)
        resp = self.client.post(
            f'/api/projects/{self.project.id}/members/',
            {'user': self.outsider.id, 'role': ProjectRole.ANNOTATOR},
            format='json',
        )
        assert resp.status_code == 403, resp.content

    def test_super_admin_can_change_role(self):
        admin = UserFactory()
        _join_org(admin, self.organization, role=OrganizationRole.SUPER_ADMIN)
        member = ProjectMember.objects.create(
            user=self.outsider, project=self.project, role=ProjectRole.ANNOTATOR
        )

        self.client.force_authenticate(user=admin)
        resp = self.client.patch(
            f'/api/projects/{self.project.id}/members/{member.id}/',
            {'role': ProjectRole.REVIEWER},
            format='json',
        )
        assert resp.status_code == 200, resp.content
        member.refresh_from_db()
        assert member.role == ProjectRole.REVIEWER

    def test_delete_soft_deletes_member(self):
        self.client.force_authenticate(user=self.owner)
        member = ProjectMember.objects.create(
            user=self.outsider, project=self.project, role=ProjectRole.ANNOTATOR
        )

        resp = self.client.delete(f'/api/projects/{self.project.id}/members/{member.id}/')
        assert resp.status_code == 204, resp.content

        member.refresh_from_db()
        assert member.deleted_at is not None
        assert member.enabled is False

    def test_cross_org_project_not_accessible(self):
        other_org = OrganizationFactory()
        other_project = ProjectFactory(organization=other_org)

        self.client.force_authenticate(user=self.outsider)
        resp = self.client.get(f'/api/projects/{other_project.id}/members/')
        # 403 (project in another org, active_organization guard) or 404 if queryset filter hits first.
        assert resp.status_code in (403, 404), resp.content


class OrganizationMemberPatchTests(APITestCase):
    def setUp(self):
        self.organization = OrganizationFactory()
        self.owner = self.organization.created_by
        _join_org(self.owner, self.organization, role=OrganizationRole.SUPER_ADMIN)
        self.outsider = UserFactory()
        _join_org(self.outsider, self.organization)

    def test_super_admin_can_promote_member(self):
        self.client.force_authenticate(user=self.owner)
        resp = self.client.patch(
            f'/api/organizations/{self.organization.id}/memberships/{self.outsider.id}',
            {'role': OrganizationRole.SUPER_ADMIN},
            format='json',
        )
        assert resp.status_code == 200, resp.content
        membership = OrganizationMember.objects.get(user=self.outsider, organization=self.organization)
        assert membership.role == OrganizationRole.SUPER_ADMIN

    def test_non_super_admin_cannot_promote(self):
        self.client.force_authenticate(user=self.outsider)
        resp = self.client.patch(
            f'/api/organizations/{self.organization.id}/memberships/{self.outsider.id}',
            {'role': OrganizationRole.SUPER_ADMIN},
            format='json',
        )
        assert resp.status_code == 403, resp.content

    def test_last_super_admin_cannot_demote_self(self):
        self.client.force_authenticate(user=self.owner)
        resp = self.client.patch(
            f'/api/organizations/{self.organization.id}/memberships/{self.owner.id}',
            {'role': OrganizationRole.MEMBER},
            format='json',
        )
        assert resp.status_code == 400, resp.content
