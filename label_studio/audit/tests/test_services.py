"""Unit tests for ``audit.services`` helpers.

These assert that each helper writes a row with the right action name, actor,
organization resolution, and metadata shape — so the view call sites can stay
thin one-liners without re-testing payload mechanics per call site.
"""

import pytest
from audit.models import AuditAction, AuditLog
from audit.services import (
    record_data_export,
    record_project_event,
    record_role_change,
    record_workspace_event,
)
from organizations.models import OrganizationMember
from organizations.tests.factories import OrganizationFactory
from projects.tests.factories import ProjectFactory
from rest_framework.test import APITestCase
from users.constants import OrganizationRole
from users.tests.factories import UserFactory
from workspaces.models import WorkspaceMember
from workspaces.tests.factories import WorkspaceFactory


pytestmark = pytest.mark.django_db


class RecordProjectEventTests(APITestCase):
    def test_records_with_workspace_and_title(self):
        org = OrganizationFactory()
        workspace = WorkspaceFactory(organization=org)
        project = ProjectFactory(organization=org, workspace=workspace, title='Cats')
        record_project_event(action=AuditAction.PROJECT_CREATED, actor=org.created_by, project=project)

        entry = AuditLog.objects.latest('id')
        assert entry.action == AuditAction.PROJECT_CREATED
        assert entry.actor_id == org.created_by_id
        assert entry.organization_id == org.id
        assert entry.target_type == 'projects.project'
        assert entry.target_id == project.id
        assert entry.metadata['title'] == 'Cats'
        assert entry.metadata['workspace_id'] == workspace.id


class RecordWorkspaceEventTests(APITestCase):
    def test_records_workspace_title(self):
        org = OrganizationFactory()
        ws = WorkspaceFactory(organization=org, title='Ops')
        record_workspace_event(action=AuditAction.WORKSPACE_UPDATED, actor=org.created_by, workspace=ws)

        entry = AuditLog.objects.latest('id')
        assert entry.action == AuditAction.WORKSPACE_UPDATED
        assert entry.target_type == 'workspaces.workspace'
        assert entry.target_id == ws.id
        assert entry.metadata['title'] == 'Ops'


class RecordRoleChangeTests(APITestCase):
    def test_workspace_role_granted(self):
        org = OrganizationFactory()
        ws = WorkspaceFactory(organization=org)
        user = UserFactory()
        member = WorkspaceMember.objects.create(
            user=user, workspace=ws, role=WorkspaceMember.Role.MEMBER
        )
        record_role_change(
            action=AuditAction.ROLE_GRANTED,
            actor=org.created_by,
            subject=member,
            scope='workspace',
            scope_id=ws.id,
            role=member.role,
            organization=org,
        )
        entry = AuditLog.objects.latest('id')
        assert entry.action == AuditAction.ROLE_GRANTED
        assert entry.metadata == {
            'scope': 'workspace',
            'scope_id': ws.id,
            'user_id': user.id,
            'role': 'member',
        }

    def test_role_changed_carries_previous(self):
        org = OrganizationFactory()
        ws = WorkspaceFactory(organization=org)
        user = UserFactory()
        member = WorkspaceMember.objects.create(
            user=user, workspace=ws, role=WorkspaceMember.Role.WORKSPACE_MANAGER
        )
        record_role_change(
            action=AuditAction.ROLE_CHANGED,
            actor=org.created_by,
            subject=member,
            scope='workspace',
            scope_id=ws.id,
            role=member.role,
            previous_role='member',
            organization=org,
        )
        entry = AuditLog.objects.latest('id')
        assert entry.metadata['previous_role'] == 'member'
        assert entry.metadata['role'] == 'workspace_manager'

    def test_organization_role_revoked(self):
        org = OrganizationFactory()
        user = UserFactory()
        member = OrganizationMember.objects.create(
            user=user, organization=org, role=OrganizationRole.MEMBER
        )
        record_role_change(
            action=AuditAction.ROLE_REVOKED,
            actor=org.created_by,
            subject=member,
            scope='organization',
            scope_id=org.id,
            role=member.role,
            organization=org,
        )
        entry = AuditLog.objects.latest('id')
        assert entry.action == AuditAction.ROLE_REVOKED
        assert entry.metadata['scope'] == 'organization'
        assert entry.metadata['scope_id'] == org.id


class RecordDataExportTests(APITestCase):
    def test_records_export_with_project_context(self):
        org = OrganizationFactory()
        project = ProjectFactory(organization=org, title='exports')
        record_data_export(actor=org.created_by, project=project, metadata={'export_type': 'JSON'})

        entry = AuditLog.objects.latest('id')
        assert entry.action == AuditAction.DATA_EXPORTED
        assert entry.target_type == 'projects.project'
        assert entry.organization_id == org.id
        assert entry.metadata['project_id'] == project.id
        assert entry.metadata['export_type'] == 'JSON'
