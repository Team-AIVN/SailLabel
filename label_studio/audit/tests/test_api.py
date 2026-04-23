"""HTTP-level tests for ``/api/audit-logs/``.

Scope-tested:
- unauthenticated → 401/403
- plain member → 403 (super-admin-only)
- super admin in another organization → 403 (per-org scoping)
- super admin in active org → sees own-org entries, filters by action/actor
"""

from audit.models import AuditAction, AuditLog
from organizations.models import OrganizationMember
from organizations.tests.factories import OrganizationFactory
from rest_framework.test import APITestCase
from users.constants import OrganizationRole
from users.tests.factories import UserFactory


def _join_org(user, org, role=OrganizationRole.MEMBER):
    user.active_organization = org
    user.save(update_fields=['active_organization'])
    OrganizationMember.objects.update_or_create(
        user=user, organization=org, defaults={'role': role}
    )


class AuditLogListAPITests(APITestCase):
    url = '/api/audit-logs/'

    def setUp(self):
        self.org = OrganizationFactory()
        self.admin = UserFactory()
        _join_org(self.admin, self.org, role=OrganizationRole.SUPER_ADMIN)

    def test_unauthenticated_denied(self):
        response = self.client.get(self.url)
        assert response.status_code in (401, 403)

    def test_plain_member_denied(self):
        member = UserFactory()
        _join_org(member, self.org)
        self.client.force_authenticate(user=member)
        response = self.client.get(self.url)
        assert response.status_code == 403

    def test_super_admin_scoped_to_active_org(self):
        AuditLog.record(
            action=AuditAction.PROJECT_CREATED,
            actor=self.admin,
            organization=self.org,
            metadata={'title': 'in-org'},
        )
        other_org = OrganizationFactory()
        AuditLog.record(
            action=AuditAction.PROJECT_CREATED,
            actor=self.admin,
            organization=other_org,
            metadata={'title': 'cross-org'},
        )

        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.url).json()
        titles = {row['metadata'].get('title') for row in body['results']}
        assert titles == {'in-org'}

    def test_filter_by_action(self):
        AuditLog.record(action=AuditAction.PROJECT_CREATED, organization=self.org, actor=self.admin)
        AuditLog.record(action=AuditAction.DATA_EXPORTED, organization=self.org, actor=self.admin)

        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url, data={'action': AuditAction.DATA_EXPORTED})
        body = response.json()
        actions = {row['action'] for row in body['results']}
        assert actions == {AuditAction.DATA_EXPORTED}

    def test_filter_by_actor(self):
        other_admin = UserFactory()
        _join_org(other_admin, self.org, role=OrganizationRole.SUPER_ADMIN)

        AuditLog.record(action=AuditAction.PROJECT_CREATED, organization=self.org, actor=self.admin)
        AuditLog.record(action=AuditAction.PROJECT_CREATED, organization=self.org, actor=other_admin)

        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url, data={'actor': other_admin.id})
        body = response.json()
        actors = {row['actor'] for row in body['results']}
        assert actors == {other_admin.id}
