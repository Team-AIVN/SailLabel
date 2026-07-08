"""Tests for workspace cloud storage -> TaskSourceItem sync (Azure -> Task Pool pipeline)."""

from unittest.mock import patch

from io_storages.azure_blob.models import AzureBlobWorkspaceImportStorage
from io_storages.utils import StorageObject
from organizations.models import OrganizationMember
from organizations.tests.factories import OrganizationFactory
from projects.tests.factories import ProjectFactory
from rest_framework.test import APITestCase
from tasks.models import Prediction, Task
from users.tests.factories import UserFactory
from workspaces.models import TaskPool, TaskPoolItem, TaskSourceItem, Workspace, WorkspaceMember

TEXT_CONFIG = '<View><Text name="text" value="$text"/><Choices name="c" toName="text"><Choice value="a"/></Choices></View>'

# Label Studio task-format prediction: list of {result: [...], model_version, score}.
PREDICTION = [
    {
        'result': [{'from_name': 'c', 'to_name': 'text', 'type': 'choices', 'value': {'choices': ['a']}}],
        'model_version': 'v1',
        'score': 0.9,
    }
]


def _join_org(user, org):
    user.active_organization = org
    user.save(update_fields=['active_organization'])
    OrganizationMember.objects.get_or_create(user=user, organization=org)


def _fake_blobs():
    """iter_keys/get_data doubles: one binary image blob + one JSON blob with 2 tasks."""

    def iter_keys(self):
        yield 'images/ship_001.png'
        yield 'tasks/batch.json'

    def get_data(self, key):
        if key.endswith('.png'):
            return [StorageObject(key=key, task_data={'image': f'azure-blob://label-images/{key}'})]
        return [
            StorageObject(
                key=key,
                row_index=0,
                task_data={'data': {'text': 'hello'}, 'predictions': PREDICTION},
            ),
            StorageObject(key=key, row_index=1, task_data={'data': {'text': 'world'}}),
        ]

    return iter_keys, get_data


class WorkspaceStorageSourceSyncTests(APITestCase):
    def setUp(self):
        self.org = OrganizationFactory()
        self.owner = self.org.created_by  # org owner -> super admin -> workspace manager
        _join_org(self.owner, self.org)
        self.ws = Workspace.objects.create(organization=self.org, title='WS', created_by=self.owner)
        self.storage = AzureBlobWorkspaceImportStorage.objects.create(
            workspace=self.ws, title='src', container='label-images'
        )
        self.client.force_authenticate(self.owner)

    def _sync(self):
        iter_keys, get_data = _fake_blobs()
        with (
            patch.object(AzureBlobWorkspaceImportStorage, 'iter_keys', iter_keys),
            patch.object(AzureBlobWorkspaceImportStorage, 'get_data', get_data),
        ):
            return self.storage.scan_and_create_source_items()

    def test_scan_creates_source_items(self):
        created = self._sync()
        assert created == 3

        items = list(TaskSourceItem.objects.filter(workspace=self.ws).order_by('index'))
        assert len(items) == 3
        assert all(it.dataset is None for it in items)
        assert all(it.source == f'azure:{self.storage.pk}' for it in items)

        image_item = items[0]
        assert image_item.data == {'image': 'azure-blob://label-images/images/ship_001.png'}
        assert image_item.data_type == 'image'
        assert image_item.storage_key == 'images/ship_001.png'

        json_items = items[1:]
        assert json_items[0].data == {'text': 'hello'}
        assert json_items[0].predictions == PREDICTION
        assert json_items[0].storage_key == 'tasks/batch.json#0'
        assert json_items[1].predictions is None

        self.storage.refresh_from_db()
        assert self.storage.last_sync_count == 3

    def test_rescan_is_idempotent(self):
        assert self._sync() == 3
        assert self._sync() == 0
        assert TaskSourceItem.objects.filter(workspace=self.ws).count() == 3

    def test_materialize_pool_passes_predictions(self):
        self._sync()
        pool = TaskPool.objects.create(workspace=self.ws, title='pool', created_by=self.owner)
        for it in TaskSourceItem.objects.filter(workspace=self.ws, data_type__in=('json', 'text')):
            TaskPoolItem.objects.create(task_pool=pool, task_source_item=it)

        # Project creation triggers pool materialization via the post_save signal.
        project = ProjectFactory(
            organization=self.org, created_by=self.owner, workspace=self.ws, task_pool=pool, label_config=TEXT_CONFIG
        )
        assert Task.objects.filter(project=project).count() == 2
        assert Prediction.objects.filter(task__project=project).count() == 1

    def test_sync_api_requires_manager(self):
        member = UserFactory()
        _join_org(member, self.org)
        WorkspaceMember.objects.create(workspace=self.ws, user=member, role=WorkspaceMember.Role.MEMBER)
        self.client.force_authenticate(member)
        resp = self.client.post(f'/api/storages/azure/workspace/{self.storage.pk}/sync')
        assert resp.status_code == 403

    def test_sync_api_creates_items(self):
        iter_keys, get_data = _fake_blobs()
        with (
            patch.object(AzureBlobWorkspaceImportStorage, 'iter_keys', iter_keys),
            patch.object(AzureBlobWorkspaceImportStorage, 'get_data', get_data),
            patch.object(AzureBlobWorkspaceImportStorage, 'validate_connection', lambda self, **kw: None),
        ):
            resp = self.client.post(f'/api/storages/azure/workspace/{self.storage.pk}/sync')
        assert resp.status_code == 200, resp.content
        assert resp.json()['created_items'] == 3
        assert TaskSourceItem.objects.filter(workspace=self.ws).count() == 3
