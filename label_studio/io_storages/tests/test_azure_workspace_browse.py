"""Workspace storage folder browser (`/api/storages/azure/workspace/browse`).

The workspace UI walks this endpoint one level at a time and only offers "작업집합으로
가져오기" on leaf folders. So the planned `tasks/작업1/`, `tasks/작업2/` layout must come
back as subfolders of `tasks`, not as a flat list.
"""

from unittest.mock import MagicMock, patch

import pytest
from azure.storage.blob import BlobPrefix
from organizations.models import OrganizationMember
from organizations.tests.factories import OrganizationFactory
from rest_framework.test import APIClient
from users.tests.factories import UserFactory
from workspaces.models import Workspace, WorkspaceMember

BROWSE = '/api/storages/azure/workspace/browse'
ENV = {
    'AZURE_BLOB_DEFAULT_CONTAINER': 'label-images',
    'AZURE_BLOB_ACCOUNT_NAME': 'acc',
    'AZURE_BLOB_ACCOUNT_KEY': 'key',
}


def _prefix(name):
    prefix = BlobPrefix()
    prefix.name = name
    return prefix


# `walk_blobs(name_starts_with=..., delimiter='/')` yields BlobPrefix per subfolder and
# a blob per file at that level.
LAYOUT = {
    None: [_prefix('tasks/'), _prefix('images/'), _prefix('export/')],
    'tasks/': [_prefix('tasks/작업1/'), _prefix('tasks/작업2/')],
    'tasks/작업1/': [MagicMock(spec=[]), MagicMock(spec=[])],
}


def _walk(name_starts_with=None, delimiter='/'):
    return iter(LAYOUT.get(name_starts_with, []))


@pytest.fixture
def manager_client():
    user = UserFactory()
    org = OrganizationFactory(created_by=user)
    user.active_organization = org
    user.save()
    OrganizationMember.objects.get_or_create(user=user, organization=org)
    workspace = Workspace.objects.create(organization=org, title='테스트', created_by=user)
    WorkspaceMember.objects.create(workspace=workspace, user=user, role=WorkspaceMember.Role.WORKSPACE_MANAGER)
    client = APIClient()
    client.force_authenticate(user)
    return client, workspace


@pytest.mark.django_db
def test_browse_lists_nested_task_folders(manager_client):
    client, workspace = manager_client
    container = MagicMock()
    container.walk_blobs.side_effect = _walk

    with (
        patch('core.utils.params.get_env', side_effect=lambda k, *a, **kw: ENV.get(k)),
        patch('io_storages.azure_blob.utils.AZURE.get_client_and_container', return_value=(None, container)),
    ):
        root = client.get(f'{BROWSE}?workspace={workspace.pk}')
        nested = client.get(f'{BROWSE}?workspace={workspace.pk}&path=tasks/')
        leaf = client.get(f'{BROWSE}?workspace={workspace.pk}&path=tasks/작업1/')

    # images/ and export/ are never import targets and stay hidden.
    assert [f['name'] for f in root.json()['folders']] == ['tasks']

    assert [f['name'] for f in nested.json()['folders']] == ['작업1', '작업2']
    # `path` is what the UI posts as the storage `prefix` when connecting a task pool.
    assert [f['path'] for f in nested.json()['folders']] == ['tasks/작업1/', 'tasks/작업2/']

    # No subfolders => the UI treats it as a leaf and shows the "connect" button there,
    # not on the `tasks` parent.
    assert leaf.json()['folders'] == []
    assert leaf.json()['file_count'] == 2
