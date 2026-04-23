"""Tests for /api/current-user/whoami extended fields.

BaseWhoAmIUserSerializer exposes organization_role and is_super_admin so the
frontend can gate role-dependent UI without a second request.
"""

from organizations.models import OrganizationMember
from organizations.tests.factories import OrganizationFactory
from rest_framework.test import APITestCase
from users.constants import OrganizationRole
from users.tests.factories import UserFactory


def _join_org(user, org, role=OrganizationRole.MEMBER):
    user.active_organization = org
    user.save(update_fields=['active_organization'])
    m, _ = OrganizationMember.objects.get_or_create(user=user, organization=org)
    if m.role != role:
        m.role = role
        m.save(update_fields=['role'])


class WhoAmIRoleFieldsTests(APITestCase):
    def setUp(self):
        self.org = OrganizationFactory()
        self.user = UserFactory()
        _join_org(self.user, self.org)

    def test_member_whoami_returns_member_role(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/current-user/whoami')

        assert response.status_code == 200, response.content
        body = response.json()
        assert body['organization_role'] == OrganizationRole.MEMBER.value
        assert body['is_super_admin'] is False

    def test_super_admin_role_whoami_flags_super_admin(self):
        _join_org(self.user, self.org, OrganizationRole.SUPER_ADMIN)
        self.client.force_authenticate(user=self.user)

        body = self.client.get('/api/current-user/whoami').json()
        assert body['organization_role'] == OrganizationRole.SUPER_ADMIN.value
        assert body['is_super_admin'] is True

    def test_django_superuser_is_reported_as_super_admin(self):
        self.user.is_superuser = True
        self.user.save(update_fields=['is_superuser'])
        self.client.force_authenticate(user=self.user)

        body = self.client.get('/api/current-user/whoami').json()
        # Org role stays plain, but the flag is True because of Django is_superuser.
        assert body['organization_role'] == OrganizationRole.MEMBER.value
        assert body['is_super_admin'] is True
