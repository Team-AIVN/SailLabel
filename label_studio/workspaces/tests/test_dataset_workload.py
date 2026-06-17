"""Tests for workspace dataset assignment and workload reporting."""

import json

from django.core.files.base import ContentFile
from organizations.models import OrganizationMember
from organizations.tests.factories import OrganizationFactory
from projects.models import Project
from projects.tests.factories import ProjectFactory
from rest_framework.test import APITestCase
from tasks.models import Annotation, Task
from users.tests.factories import UserFactory
from workspaces.models import Workspace, WorkspaceFileUpload, WorkspaceMember

TEXT_CONFIG = '<View><Text name="text" value="$text"/><Choices name="c" toName="text"><Choice value="a"/></Choices></View>'


def _join_org(user, org):
    user.active_organization = org
    user.save(update_fields=['active_organization'])
    OrganizationMember.objects.get_or_create(user=user, organization=org)


def _records(n):
    return [{'data': {'text': f'sample {i}'}} for i in range(n)]


class DatasetAssignmentTests(APITestCase):
    def setUp(self):
        self.org = OrganizationFactory()
        self.owner = self.org.created_by
        _join_org(self.owner, self.org)
        self.workspace = Workspace.objects.create(organization=self.org, title='WS', created_by=self.owner)
        WorkspaceMember.objects.create(
            workspace=self.workspace, user=self.owner, role=WorkspaceMember.Role.WORKSPACE_MANAGER
        )
        self.project = ProjectFactory(
            organization=self.org, workspace=self.workspace, created_by=self.owner, label_config=TEXT_CONFIG
        )
        self.upload = WorkspaceFileUpload.objects.create(
            workspace=self.workspace,
            user=self.owner,
            file=ContentFile(json.dumps(_records(10)).encode(), name='data.json'),
        )
        self.client.force_authenticate(user=self.owner)

    def test_assign_by_count(self):
        response = self.client.post(
            f'/api/workspaces/{self.workspace.id}/assign/',
            {'project': self.project.id, 'count': 4},
            format='json',
        )
        assert response.status_code == 201, response.content
        body = response.json()
        assert body['assigned'] == 4
        assert body['available'] == 10
        assert Task.objects.filter(project=self.project).count() == 4

    def test_assign_by_ratio(self):
        response = self.client.post(
            f'/api/workspaces/{self.workspace.id}/assign/',
            {'project': self.project.id, 'ratio': 0.5},
            format='json',
        )
        assert response.status_code == 201, response.content
        assert response.json()['assigned'] == 5
        assert Task.objects.filter(project=self.project).count() == 5

    def test_count_clamped_to_available(self):
        response = self.client.post(
            f'/api/workspaces/{self.workspace.id}/assign/',
            {'project': self.project.id, 'count': 999},
            format='json',
        )
        assert response.status_code == 201, response.content
        assert response.json()['assigned'] == 10

    def test_requires_exactly_one_of_count_or_ratio(self):
        both = self.client.post(
            f'/api/workspaces/{self.workspace.id}/assign/',
            {'project': self.project.id, 'count': 1, 'ratio': 0.5},
            format='json',
        )
        assert both.status_code == 400
        neither = self.client.post(
            f'/api/workspaces/{self.workspace.id}/assign/',
            {'project': self.project.id},
            format='json',
        )
        assert neither.status_code == 400

    def test_project_must_belong_to_workspace(self):
        other_project = ProjectFactory(organization=self.org, created_by=self.owner, label_config=TEXT_CONFIG)
        response = self.client.post(
            f'/api/workspaces/{self.workspace.id}/assign/',
            {'project': other_project.id, 'count': 1},
            format='json',
        )
        assert response.status_code == 400

    def test_non_manager_cannot_assign(self):
        member = UserFactory()
        _join_org(member, self.org)
        WorkspaceMember.objects.create(workspace=self.workspace, user=member, role=WorkspaceMember.Role.MEMBER)
        self.client.force_authenticate(user=member)
        response = self.client.post(
            f'/api/workspaces/{self.workspace.id}/assign/',
            {'project': self.project.id, 'count': 1},
            format='json',
        )
        assert response.status_code == 403


class WorkloadReportTests(APITestCase):
    def setUp(self):
        self.org = OrganizationFactory()
        self.owner = self.org.created_by
        _join_org(self.owner, self.org)
        self.workspace = Workspace.objects.create(organization=self.org, title='WS', created_by=self.owner)
        WorkspaceMember.objects.create(
            workspace=self.workspace, user=self.owner, role=WorkspaceMember.Role.WORKSPACE_MANAGER
        )
        self.project = ProjectFactory(
            organization=self.org, workspace=self.workspace, created_by=self.owner, label_config=TEXT_CONFIG
        )

    def _annotate(self, user, n, cancelled=False):
        for _ in range(n):
            task = Task.objects.create(project=self.project, data={'text': 'x'})
            Annotation.objects.create(
                task=task, project=self.project, completed_by=user, was_cancelled=cancelled, result=[]
            )

    def test_workload_aggregates_per_user(self):
        worker = UserFactory()
        _join_org(worker, self.org)
        self._annotate(self.owner, 3)
        self._annotate(worker, 2)
        self._annotate(worker, 1, cancelled=True)

        self.client.force_authenticate(user=self.owner)
        response = self.client.get(f'/api/workspaces/{self.workspace.id}/workload/')
        assert response.status_code == 200, response.content
        results = {row['user']: row for row in response.json()['results']}

        assert results[self.owner.id]['annotation_count'] == 3
        assert results[worker.id]['annotation_count'] == 2
        assert results[worker.id]['cancelled_count'] == 1
        assert results[worker.id]['project_count'] == 1
