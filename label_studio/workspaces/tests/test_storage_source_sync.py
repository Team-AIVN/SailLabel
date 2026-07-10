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

    def _sync(self, storage=None):
        iter_keys, get_data = _fake_blobs()
        with (
            patch.object(AzureBlobWorkspaceImportStorage, 'iter_keys', iter_keys),
            patch.object(AzureBlobWorkspaceImportStorage, 'get_data', get_data),
        ):
            return (storage or self.storage).scan_and_create_source_items()

    def test_resync_refreshes_changed_blob(self):
        """블롭 내용이 바뀌면 재동기화가 기존 항목을 갱신해야 한다.

        항목은 파일 단위로 dedup 되므로, 갱신하지 않으면 옛 payload 가 영원히 남고
        이후 이 작업집합으로 만든 모든 프로젝트가 낡은 데이터를 복사받는다.
        """
        self._sync()
        item = TaskSourceItem.objects.get(storage_key='label-images/tasks/batch.json#0')
        assert item.data == {'text': 'hello'}
        assert item.predictions == PREDICTION

        # Azure 의 같은 파일이 새 형식으로 덮어써진 상황.
        new_data = {'text': 'hello', 'data_csv': '구분,길이(m)\n자선,93\n'}
        new_predictions = [{**PREDICTION[0], 'model_version': 'gpt-5.5'}]

        def iter_keys(self):
            yield 'tasks/batch.json'

        def get_data(self, key):
            return [StorageObject(key=key, row_index=0, task_data={'data': new_data, 'predictions': new_predictions})]

        with (
            patch.object(AzureBlobWorkspaceImportStorage, 'iter_keys', iter_keys),
            patch.object(AzureBlobWorkspaceImportStorage, 'get_data', get_data),
        ):
            result = self.storage.scan_and_create_source_items()

        assert result['created'] == 0  # 새 파일 없음
        assert result['refreshed'] == 1
        item.refresh_from_db()
        assert item.data == new_data
        assert item.predictions == new_predictions

        # 내용이 그대로면 다시 갱신하지 않는다.
        with (
            patch.object(AzureBlobWorkspaceImportStorage, 'iter_keys', iter_keys),
            patch.object(AzureBlobWorkspaceImportStorage, 'get_data', get_data),
        ):
            assert self.storage.scan_and_create_source_items()['refreshed'] == 0

    def test_scan_creates_source_items(self):
        created = self._sync()['created']
        assert created == 3

        items = list(TaskSourceItem.objects.filter(workspace=self.ws).order_by('index'))
        assert len(items) == 3
        assert all(it.dataset is None for it in items)
        assert all(it.source == f'azure:{self.storage.pk}' for it in items)

        image_item = items[0]
        assert image_item.data == {'image': 'azure-blob://label-images/images/ship_001.png'}
        assert image_item.data_type == 'image'
        assert image_item.storage_key == 'label-images/images/ship_001.png'

        json_items = items[1:]
        assert json_items[0].data == {'text': 'hello'}
        assert json_items[0].predictions == PREDICTION
        assert json_items[0].storage_key == 'label-images/tasks/batch.json#0'
        assert json_items[1].predictions is None

        self.storage.refresh_from_db()
        assert self.storage.last_sync_count == 3

    def test_rescan_is_idempotent(self):
        assert self._sync()['created'] == 3
        assert self._sync()['created'] == 0
        assert TaskSourceItem.objects.filter(workspace=self.ws).count() == 3

    def test_same_folder_feeds_second_pool_without_duplicates(self):
        """같은 폴더를 두 번째 작업집합에 연결하면 복사 없이 기존 아이템이 그 풀에 담긴다."""
        pool_a = TaskPool.objects.create(workspace=self.ws, title='A', created_by=self.owner)
        pool_b = TaskPool.objects.create(workspace=self.ws, title='B', created_by=self.owner)

        self.storage.task_pool = pool_a
        self.storage.save(update_fields=['task_pool'])
        first = self._sync()
        assert (first['created'], first['linked']) == (3, 0)
        assert pool_a.items.count() == 3

        second_conn = AzureBlobWorkspaceImportStorage.objects.create(
            workspace=self.ws, title='src2', container='label-images', task_pool=pool_b
        )
        second = self._sync(second_conn)
        assert (second['created'], second['linked']) == (0, 3)
        assert TaskSourceItem.objects.filter(workspace=self.ws).count() == 3  # 복사본 없음
        assert pool_b.items.count() == 3
        # 재실행해도 변화 없음
        r = self._sync(second_conn); assert (r['created'], r['linked']) == (0, 0)

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

    def test_project_auto_attaches_azure_export_storage(self):
        """env에 Azure 기본 연결이 있으면 새 프로젝트에 결과 자동 저장 스토리지가 붙는다."""
        env = {
            'AZURE_BLOB_DEFAULT_CONTAINER': 'label-images',
            'AZURE_BLOB_ACCOUNT_NAME': 'acc',
            'AZURE_BLOB_ACCOUNT_KEY': 'key',
        }
        with patch('core.utils.params.get_env', side_effect=lambda k, *a, **kw: env.get(k)):
            project = ProjectFactory(
                organization=self.org,
                created_by=self.owner,
                workspace=self.ws,
                title='선박 탐색 시연',
                label_config=TEXT_CONFIG,
            )
        st = project.io_storages_azureblobexportstorages.first()
        assert st is not None
        assert st.container == 'label-images'
        assert st.prefix == f'export/{self.ws.title}/선박 탐색 시연'

    def test_export_prefix_sanitizes_titles(self):
        """제목의 슬래시는 폴더를 쪼개지 않도록 치환하고, 빈 제목은 id로 대체한다."""
        from workspaces.signals import _blob_segment, azure_export_prefix

        assert _blob_segment('a/b\\c', 1) == 'a_b_c'
        assert _blob_segment('  두 칸   띄움  ', 1) == '두 칸 띄움'
        assert _blob_segment('trailing. ', 1) == 'trailing'
        assert _blob_segment('   ', 42) == '42'

        ws = Workspace.objects.create(organization=self.org, title='a/b', created_by=self.owner)
        project = ProjectFactory(
            organization=self.org, created_by=self.owner, workspace=ws, title='p/q', label_config=TEXT_CONFIG
        )
        assert azure_export_prefix(project) == 'export/a_b/p_q'

    def test_draft_project_attaches_export_storage_on_publish(self):
        """UI 흐름 재현: 워크스페이스 없는 draft 로 만든 뒤, 발행 PATCH 때 스토리지가 붙는다."""
        env = {
            'AZURE_BLOB_DEFAULT_CONTAINER': 'label-images',
            'AZURE_BLOB_ACCOUNT_NAME': 'acc',
            'AZURE_BLOB_ACCOUNT_KEY': 'key',
        }
        with patch('core.utils.params.get_env', side_effect=lambda k, *a, **kw: env.get(k)):
            # useDraftProject.js: POST /projects {title, is_draft: true} — 워크스페이스 없음
            project = ProjectFactory(
                organization=self.org,
                created_by=self.owner,
                workspace=None,
                is_draft=True,
                title='New Project #1',
                label_config=TEXT_CONFIG,
            )
            assert not project.io_storages_azureblobexportstorages.exists()

            # CreateProject.jsx onCreate: PATCH {workspace, is_draft: false, ...}
            project.workspace = self.ws
            project.title = '테스트 프로젝트'
            project.is_draft = False
            project.save()

        st = project.io_storages_azureblobexportstorages.first()
        assert st is not None
        assert st.prefix == f'export/{self.ws.title}/테스트 프로젝트'

        # 이후 저장이 중복 스토리지를 만들지 않는다
        with patch('core.utils.params.get_env', side_effect=lambda k, *a, **kw: env.get(k)):
            project.save()
        assert project.io_storages_azureblobexportstorages.count() == 1

    def test_project_without_env_gets_no_export_storage(self):
        with patch('core.utils.params.get_env', side_effect=lambda k, *a, **kw: None):
            project = ProjectFactory(
                organization=self.org, created_by=self.owner, workspace=self.ws, label_config=TEXT_CONFIG
            )
        assert not project.io_storages_azureblobexportstorages.exists()

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
