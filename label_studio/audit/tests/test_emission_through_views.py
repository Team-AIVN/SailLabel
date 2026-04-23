"""End-to-end checks: HTTP actions write the expected audit rows.

We keep these minimal — one assertion per call site proving the audit row
appears with the right action. The ``services`` unit tests already cover the
metadata shape, so here we just confirm the view is wired up.
"""

from audit.models import AuditAction, AuditLog
from organizations.models import OrganizationMember
from organizations.tests.factories import OrganizationFactory
from projects.tests.factories import ProjectFactory
from rest_framework.test import APITestCase
from users.constants import OrganizationRole
from users.tests.factories import UserFactory
from workspaces.models import WorkspaceMember
from workspaces.tests.factories import WorkspaceFactory


def _join_org(user, org, role=OrganizationRole.MEMBER):
    user.active_organization = org
    user.save(update_fields=['active_organization'])
    OrganizationMember.objects.update_or_create(
        user=user, organization=org, defaults={'role': role}
    )


class ProjectCrudAuditTests(APITestCase):
    def setUp(self):
        self.org = OrganizationFactory()
        self.owner = self.org.created_by
        self.owner.active_organization = self.org
        self.owner.save(update_fields=['active_organization'])
        self.client.force_authenticate(user=self.owner)

    def test_create_project_emits_audit_row(self):
        self.client.post(
            '/api/projects/',
            data={'title': 'Audited Project', 'label_config': '<View></View>'},
            format='json',
        )
        assert AuditLog.objects.filter(
            action=AuditAction.PROJECT_CREATED, actor=self.owner
        ).exists()

    def test_patch_project_emits_audit_row(self):
        project = ProjectFactory(organization=self.org, created_by=self.owner)
        self.client.patch(
            f'/api/projects/{project.id}/', data={'title': 'Renamed'}, format='json'
        )
        assert AuditLog.objects.filter(
            action=AuditAction.PROJECT_UPDATED, target_id=project.id
        ).exists()

    def test_delete_project_emits_audit_row(self):
        project = ProjectFactory(organization=self.org, created_by=self.owner)
        self.client.delete(f'/api/projects/{project.id}/')
        assert AuditLog.objects.filter(
            action=AuditAction.PROJECT_DELETED, target_id=project.id
        ).exists()


class WorkspaceCrudAuditTests(APITestCase):
    def setUp(self):
        self.org = OrganizationFactory()
        self.owner = self.org.created_by
        self.owner.active_organization = self.org
        self.owner.save(update_fields=['active_organization'])
        self.client.force_authenticate(user=self.owner)

    def test_create_workspace_emits_audit_row(self):
        response = self.client.post(
            '/api/workspaces/', data={'title': 'Audited WS'}, format='json'
        )
        assert response.status_code == 201, response.content
        assert AuditLog.objects.filter(
            action=AuditAction.WORKSPACE_CREATED, actor=self.owner
        ).exists()

    def test_delete_workspace_emits_audit_row(self):
        ws = WorkspaceFactory(organization=self.org)
        WorkspaceMember.objects.create(
            user=self.owner, workspace=ws, role=WorkspaceMember.Role.WORKSPACE_MANAGER
        )
        self.client.delete(f'/api/workspaces/{ws.id}/')
        assert AuditLog.objects.filter(
            action=AuditAction.WORKSPACE_DELETED, target_id=ws.id
        ).exists()


class OrganizationMemberDeleteAuditTests(APITestCase):
    def test_delete_member_emits_role_revoked(self):
        org = OrganizationFactory()
        admin = org.created_by
        admin.active_organization = org
        admin.save(update_fields=['active_organization'])

        victim = UserFactory()
        _join_org(victim, org)

        self.client.force_authenticate(user=admin)
        response = self.client.delete(f'/api/organizations/{org.id}/memberships/{victim.id}/')
        assert response.status_code == 204, response.content
        assert AuditLog.objects.filter(
            action=AuditAction.ROLE_REVOKED, actor=admin, organization=org
        ).exists()
