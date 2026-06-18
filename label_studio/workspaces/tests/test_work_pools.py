"""Tests for datasets -> dataset items -> work pools -> project materialization."""

import json

from django.core.files.base import ContentFile
from organizations.models import OrganizationMember
from organizations.tests.factories import OrganizationFactory
from projects.models import Project
from projects.tests.factories import ProjectFactory
from rest_framework.test import APITestCase
from tasks.models import Task
from users.tests.factories import UserFactory
from workspaces.models import DatasetItem, Workspace, WorkPool, WorkPoolItem, WorkspaceFileUpload
from workspaces.workpools import materialize_dataset_items

TEXT_CONFIG = '<View><Text name="text" value="$text"/><Choices name="c" toName="text"><Choice value="a"/></Choices></View>'


def _join_org(user, org):
    user.active_organization = org
    user.save(update_fields=['active_organization'])
    OrganizationMember.objects.get_or_create(user=user, organization=org)


class WorkPoolTests(APITestCase):
    def setUp(self):
        self.org = OrganizationFactory()
        self.owner = self.org.created_by  # org owner -> implicit workspace manager
        _join_org(self.owner, self.org)
        self.ws = Workspace.objects.create(organization=self.org, title='WS', created_by=self.owner)

        # a dataset (file upload) with 3 items
        self.dataset = WorkspaceFileUpload.objects.create(
            workspace=self.ws,
            user=self.owner,
            file=ContentFile(json.dumps([{'data': {'text': f's{i}'}} for i in range(3)]).encode(), name='d.json'),
        )
        materialize_dataset_items(self.dataset)
        self.items = list(DatasetItem.objects.filter(dataset=self.dataset).order_by('index'))
        self.client.force_authenticate(self.owner)

    def test_dataset_items_materialized(self):
        assert len(self.items) == 3
        assert self.items[0].data == {'text': 's0'}

    def test_list_dataset_items_with_included_flag(self):
        pool = WorkPool.objects.create(workspace=self.ws, title='P', created_by=self.owner)
        WorkPoolItem.objects.create(work_pool=pool, dataset_item=self.items[0])
        res = self.client.get(f'/api/workspaces/{self.ws.id}/dataset-items/?work_pool={pool.id}')
        assert res.status_code == 200, res.content
        rows = res.json()
        rows = rows['results'] if isinstance(rows, dict) and 'results' in rows else rows
        by_id = {r['id']: r for r in rows}
        assert by_id[self.items[0].id]['included'] is True
        assert by_id[self.items[1].id]['included'] is False

    def test_create_pool_and_add_remove_items(self):
        # create
        r = self.client.post(f'/api/workspaces/{self.ws.id}/work-pools/', {'title': 'Pool A'}, format='json')
        assert r.status_code == 201, r.content
        pool_id = r.json()['id']
        # add 2 items
        ids = [self.items[0].id, self.items[1].id]
        r = self.client.post(
            f'/api/workspaces/{self.ws.id}/work-pools/{pool_id}/items/',
            {'dataset_item_ids': ids},
            format='json',
        )
        assert r.status_code == 200, r.content
        assert r.json()['item_count'] == 2
        # detail shows items
        r = self.client.get(f'/api/workspaces/{self.ws.id}/work-pools/{pool_id}/')
        assert r.json()['item_count'] == 2
        assert len(r.json()['items']) == 2
        # remove 1
        r = self.client.delete(
            f'/api/workspaces/{self.ws.id}/work-pools/{pool_id}/items/',
            {'dataset_item_ids': [self.items[0].id]},
            format='json',
        )
        assert r.status_code == 200, r.content
        assert r.json()['item_count'] == 1

    def test_rename_and_delete_pool(self):
        pool = WorkPool.objects.create(workspace=self.ws, title='Old', created_by=self.owner)
        r = self.client.patch(
            f'/api/workspaces/{self.ws.id}/work-pools/{pool.id}/', {'title': 'New'}, format='json'
        )
        assert r.status_code == 200, r.content
        assert r.json()['title'] == 'New'
        r = self.client.delete(f'/api/workspaces/{self.ws.id}/work-pools/{pool.id}/')
        assert r.status_code == 204
        assert not WorkPool.objects.filter(id=pool.id).exists()

    def test_non_manager_cannot_create_pool(self):
        member = UserFactory()
        _join_org(member, self.org)
        from workspaces.models import WorkspaceMember

        WorkspaceMember.objects.create(workspace=self.ws, user=member, role=WorkspaceMember.Role.MEMBER)
        self.client.force_authenticate(member)
        r = self.client.post(f'/api/workspaces/{self.ws.id}/work-pools/', {'title': 'X'}, format='json')
        assert r.status_code == 403

    def test_project_materializes_tasks_from_work_pool(self):
        pool = WorkPool.objects.create(workspace=self.ws, title='Pool', created_by=self.owner)
        for it in self.items:
            WorkPoolItem.objects.create(work_pool=pool, dataset_item=it)
        # creating a published project bound to the pool seeds its tasks (post_save signal)
        project = ProjectFactory(
            organization=self.org,
            workspace=self.ws,
            created_by=self.owner,
            label_config=TEXT_CONFIG,
            work_pool=pool,
            is_draft=False,
        )
        assert Task.objects.filter(project=project).count() == 3
