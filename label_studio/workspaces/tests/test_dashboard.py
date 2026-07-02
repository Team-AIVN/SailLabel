"""Tests for the workspace dashboard endpoints (summary, project cards, datasets)."""

import json

from django.core.files.base import ContentFile
from organizations.models import OrganizationMember
from organizations.tests.factories import OrganizationFactory
from projects.models import Project
from projects.tests.factories import ProjectFactory
from rest_framework.test import APITestCase
from workspaces.models import Workspace, WorkspaceFileUpload, WorkspaceMember

TEXT_CONFIG = '<View><Text name="text" value="$text"/><Choices name="c" toName="text"><Choice value="a"/></Choices></View>'


def _join_org(user, org):
    user.active_organization = org
    user.save(update_fields=['active_organization'])
    OrganizationMember.objects.get_or_create(user=user, organization=org)


class WorkspaceDashboardTests(APITestCase):
    def setUp(self):
        self.org = OrganizationFactory()
        self.owner = self.org.created_by
        _join_org(self.owner, self.org)
        self.ws = Workspace.objects.create(organization=self.org, title='WS', created_by=self.owner)
        WorkspaceMember.objects.create(workspace=self.ws, user=self.owner, role=WorkspaceMember.Role.WORKSPACE_MANAGER)
        self.client.force_authenticate(user=self.owner)

    def test_summary_totals(self):
        ProjectFactory(organization=self.org, workspace=self.ws, created_by=self.owner, label_config=TEXT_CONFIG)
        WorkspaceFileUpload.objects.create(
            workspace=self.ws, user=self.owner, file=ContentFile(b'[]', name='d.json')
        )
        res = self.client.get(f'/api/workspaces/{self.ws.id}/summary/')
        assert res.status_code == 200, res.content
        body = res.json()
        assert body['total_projects'] == 1
        assert body['total_datasets'] == 1
        assert body['total_users'] == 1

    def test_project_cards_have_derived_fields(self):
        ProjectFactory(
            organization=self.org,
            workspace=self.ws,
            created_by=self.owner,
            label_config=TEXT_CONFIG,
            tags=['nlp', 'urgent'],
        )
        res = self.client.get(f'/api/workspaces/{self.ws.id}/projects/')
        assert res.status_code == 200, res.content
        payload = res.json()
        rows = payload['results'] if isinstance(payload, dict) and 'results' in payload else payload
        card = rows[0]
        assert card['label_type'] == 'Choices'
        assert card['review_progress'] == 0  # no tasks yet
        assert card['tags'] == ['nlp', 'urgent']
        assert 'due_date' in card

    def test_project_search_and_tag_filter(self):
        ProjectFactory(organization=self.org, workspace=self.ws, created_by=self.owner, title='Alpha', tags=['x'])
        ProjectFactory(organization=self.org, workspace=self.ws, created_by=self.owner, title='Beta', tags=['y'])
        res = self.client.get(f'/api/workspaces/{self.ws.id}/projects/?search=Alph')
        rows = res.json()
        rows = rows['results'] if isinstance(rows, dict) and 'results' in rows else rows
        assert [r['title'] for r in rows] == ['Alpha']

        res = self.client.get(f'/api/workspaces/{self.ws.id}/projects/?tag=y')
        rows = res.json()
        rows = rows['results'] if isinstance(rows, dict) and 'results' in rows else rows
        assert [r['title'] for r in rows] == ['Beta']

    def test_create_project_in_workspace(self):
        res = self.client.post(
            f'/api/workspaces/{self.ws.id}/projects/',
            {'title': 'Created In WS', 'tags': ['a']},
            format='json',
        )
        assert res.status_code == 201, res.content
        proj = Project.objects.get(title='Created In WS')
        assert proj.workspace_id == self.ws.id
        assert proj.organization_id == self.org.id

    def test_datasets_endpoint(self):
        WorkspaceFileUpload.objects.create(
            workspace=self.ws, user=self.owner, file=ContentFile(b'[]', name='images.csv')
        )
        res = self.client.get(f'/api/workspaces/{self.ws.id}/datasets/')
        assert res.status_code == 200, res.content
        rows = res.json()
        rows = rows['results'] if isinstance(rows, dict) and 'results' in rows else rows
        assert rows[0]['data_type'] == 'CSV'
        assert 'last_updated' in rows[0]
