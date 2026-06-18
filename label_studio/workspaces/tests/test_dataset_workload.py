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
