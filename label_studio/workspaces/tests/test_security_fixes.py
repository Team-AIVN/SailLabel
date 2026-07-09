"""Regression tests for the audit security fixes (S1/S7/S8/B2)."""

from organizations.models import OrganizationMember
from organizations.tests.factories import OrganizationFactory
from rest_framework.test import APITestCase
from users.tests.factories import UserFactory
from workspaces.models import Workspace, WorkspaceMember


def _join(user, org):
    user.active_organization = org
    user.save(update_fields=['active_organization'])
    OrganizationMember.objects.get_or_create(user=user, organization=org)


class SecurityFixTests(APITestCase):
    def setUp(self):
        self.org = OrganizationFactory()
        self.owner = self.org.created_by  # super-admin-ish (org creator)
        _join(self.owner, self.org)
        self.wm = UserFactory()
        _join(self.wm, self.org)
        self.ws = Workspace.objects.create(organization=self.org, title='WS', created_by=self.owner)
        WorkspaceMember.objects.create(workspace=self.ws, user=self.wm, role=WorkspaceMember.Role.WORKSPACE_MANAGER)
        # A second workspace nobody but the owner belongs to.
        self.ws2 = Workspace.objects.create(organization=self.org, title='Other', created_by=self.owner)

    # S8 — workspace detail must not be readable by a non-member.
    def test_non_member_cannot_read_workspace_detail(self):
        outsider = UserFactory()
        _join(outsider, self.org)
        self.client.force_authenticate(outsider)
        assert self.client.get(f'/api/workspaces/{self.ws.id}/').status_code == 404
        # a member can read
        self.client.force_authenticate(self.wm)
        assert self.client.get(f'/api/workspaces/{self.ws.id}/').status_code == 200

    # S7 — inviting a user from another org must be rejected.
    def test_cannot_add_member_from_other_org(self):
        other_org = OrganizationFactory()
        stranger = UserFactory()
        _join(stranger, other_org)
        self.client.force_authenticate(self.wm)
        resp = self.client.post(f'/api/workspaces/{self.ws.id}/members', {'user': stranger.id, 'role': 'member'})
        assert resp.status_code == 400

    # B2 — remove then re-invite the same member must not 500.
    def test_remove_then_reinvite_member(self):
        member = UserFactory()
        _join(member, self.org)
        self.client.force_authenticate(self.wm)
        r1 = self.client.post(f'/api/workspaces/{self.ws.id}/members', {'user': member.id, 'role': 'member'})
        assert r1.status_code == 201
        mid = r1.json()['id']
        assert self.client.delete(f'/api/workspaces/{self.ws.id}/members/{mid}').status_code == 204
        # re-invite: previously raised IntegrityError 500
        r2 = self.client.post(f'/api/workspaces/{self.ws.id}/members', {'user': member.id, 'role': 'workspace_manager'})
        assert r2.status_code == 201, r2.content
        assert WorkspaceMember.objects.filter(workspace=self.ws, user=member, deleted_at__isnull=True).count() == 1
