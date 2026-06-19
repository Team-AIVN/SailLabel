"""Tests for auto-pairing same-basename image + csv/tsv uploads into one 'pair' item."""

from django.core.files.uploadedfile import SimpleUploadedFile
from organizations.models import OrganizationMember
from organizations.tests.factories import OrganizationFactory
from projects.models import Project
from projects.tests.factories import ProjectFactory
from rest_framework.test import APITestCase
from tasks.models import Task
from workspaces.models import DatasetItem, Workspace, WorkPool, WorkPoolItem, WorkspaceFileUpload, WorkspaceMember

PAIR_CONFIG = (
    '<View><Image name="image" value="$image"/><Table name="data" value="$data"/>'
    '<TextArea name="caption" toName="image" rows="5" maxSubmissions="1"/></View>'
)

JPEG = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00fake-image-bytes'


def _join_org(user, org):
    user.active_organization = org
    user.save(update_fields=['active_organization'])
    OrganizationMember.objects.get_or_create(user=user, organization=org)


class PairingUploadTests(APITestCase):
    def setUp(self):
        self.org = OrganizationFactory()
        self.owner = self.org.created_by
        _join_org(self.owner, self.org)
        self.ws = Workspace.objects.create(organization=self.org, title='WS', created_by=self.owner)
        WorkspaceMember.objects.create(workspace=self.ws, user=self.owner, role=WorkspaceMember.Role.WORKSPACE_MANAGER)
        self.client.force_authenticate(self.owner)

    def _upload(self, files):
        """POST a multipart import with {filename: SimpleUploadedFile}; return response."""
        resp = self.client.post(f'/api/workspaces/{self.ws.id}/import/', files, format='multipart')
        assert resp.status_code == 201, resp.content
        return resp

    def _img(self, name):
        return SimpleUploadedFile(name, JPEG, content_type='image/jpeg')

    def _file(self, name, content, content_type):
        return SimpleUploadedFile(name, content, content_type=content_type)

    def _items(self):
        return list(DatasetItem.objects.filter(workspace=self.ws).order_by('id'))

    def _upload_by_suffix(self, suffix):
        return WorkspaceFileUpload.objects.get(workspace=self.ws, file__endswith=suffix)

    # --- core pairing ---

    def test_image_plus_csv_merges_into_single_pair_item(self):
        csv_bytes = b'col1,col2\nv1,v2\nv3,v4\n'
        self._upload(
            {
                'sample_001.jpg': self._img('sample_001.jpg'),
                'sample_001.csv': self._file('sample_001.csv', csv_bytes, 'text/csv'),
            }
        )
        items = self._items()
        assert len(items) == 1, items
        item = items[0]
        assert item.data_type == 'pair'

        image_upload = self._upload_by_suffix('sample_001.jpg')
        # The merged item is anchored on the image upload, with sibling keys.
        assert item.dataset_id == image_upload.id
        assert item.data['image'] == image_upload.url
        assert item.data['data'] == [{'col1': 'v1', 'col2': 'v2'}, {'col1': 'v3', 'col2': 'v4'}]
        assert len(item.data['data']) == 2
        assert item.data['data'][0]['col2'] == 'v2'

        # No per-row csv items, no standalone image item for this basename.
        assert DatasetItem.objects.filter(workspace=self.ws).count() == 1

    def test_pair_item_materializes_to_one_task(self):
        self._upload(
            {
                'sample_001.jpg': self._img('sample_001.jpg'),
                'sample_001.csv': self._file('sample_001.csv', b'a,b\n1,2\n', 'text/csv'),
            }
        )
        item = self._items()[0]
        pool = WorkPool.objects.create(workspace=self.ws, title='P', created_by=self.owner)
        WorkPoolItem.objects.create(work_pool=pool, dataset_item=item)

        project = ProjectFactory(
            organization=self.org,
            workspace=self.ws,
            created_by=self.owner,
            label_config=PAIR_CONFIG,
            work_pool=pool,
            is_draft=False,
        )
        tasks = list(Task.objects.filter(project=project))
        assert len(tasks) == 1
        assert tasks[0].data == item.data
        assert tasks[0].data['data'] == [{'a': '1', 'b': '2'}]

    def test_tsv_pairing_uses_tab_delimiter(self):
        self._upload(
            {
                'sample_002.jpg': self._img('sample_002.jpg'),
                'sample_002.tsv': self._file('sample_002.tsv', b'x\ty\n1\t2\n', 'text/tab-separated-values'),
            }
        )
        items = self._items()
        assert len(items) == 1
        assert items[0].data_type == 'pair'
        assert items[0].data['data'] == [{'x': '1', 'y': '2'}]

    # --- non-paired fallbacks (regression-safe) ---

    def test_image_only_materializes_normally(self):
        self._upload({'lonely.jpg': self._img('lonely.jpg')})
        items = self._items()
        assert len(items) == 1
        assert items[0].data_type == 'image'
        assert 'image' in items[0].data
        assert DatasetItem.objects.filter(workspace=self.ws, data_type='pair').count() == 0

    def test_csv_only_materializes_per_row(self):
        self._upload({'rows.csv': self._file('rows.csv', b'c\nr1\nr2\nr3\n', 'text/csv')})
        items = self._items()
        assert len(items) == 3  # one DatasetItem per CSV row, unchanged path
        assert all(it.data_type != 'pair' for it in items)

    def test_mismatched_basenames_do_not_pair(self):
        self._upload(
            {
                'a.jpg': self._img('a.jpg'),
                'b.csv': self._file('b.csv', b'k\n1\n2\n', 'text/csv'),
            }
        )
        assert DatasetItem.objects.filter(workspace=self.ws, data_type='pair').count() == 0
        # image -> 1 image item; csv -> 2 per-row items
        assert DatasetItem.objects.filter(workspace=self.ws, data_type='image').count() == 1
        assert DatasetItem.objects.filter(workspace=self.ws).count() == 3

    def test_three_files_same_basename_do_not_pair(self):
        self._upload(
            {
                'dup.jpg': self._img('dup.jpg'),
                'dup.png': self._img('dup.png'),
                'dup.csv': self._file('dup.csv', b'k\n1\n', 'text/csv'),
            }
        )
        assert DatasetItem.objects.filter(workspace=self.ws, data_type='pair').count() == 0

    # --- defensive parsing ---

    def test_malformed_csv_falls_back_without_error(self):
        # Invalid UTF-8 bytes make parse_tabular_rows raise -> fall back to per-file.
        bad_csv = b'\xff\xfe\x00col1,col2\nv1,v2\n'
        self._upload(
            {
                'sample_003.jpg': self._img('sample_003.jpg'),
                'sample_003.csv': self._file('sample_003.csv', bad_csv, 'text/csv'),
            }
        )
        assert DatasetItem.objects.filter(workspace=self.ws, data_type='pair').count() == 0
        # Both files still materialized via the unchanged per-file path.
        assert DatasetItem.objects.filter(workspace=self.ws, data_type='image').count() == 1
        assert DatasetItem.objects.filter(workspace=self.ws).count() >= 2
