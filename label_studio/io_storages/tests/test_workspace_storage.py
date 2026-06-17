"""Tests for workspace-scope local-files storage (Phase 3A).

These cover the model/serializer plumbing plus the workspace-manager vs
non-manager gating on the new /api/storages/localfiles/workspace endpoints.
The heavy filesystem validation is already covered by test_localfiles_validation
— here we focus on the permission boundary and model wiring.
"""

import pytest  # type: ignore[import]
from io_storages.localfiles.models import (
    LocalFilesImportStorage,
    LocalFilesWorkspaceImportStorage,
)
from organizations.models import OrganizationMember
from organizations.tests.factories import OrganizationFactory
from rest_framework.test import APIClient
from users.tests.factories import UserFactory
from workspaces.models import WorkspaceMember
from workspaces.tests.factories import WorkspaceFactory


def _configure_local_files_root(settings, tmp_path):
    root = tmp_path / 'root'
    root.mkdir()
    sub = root / 'sub'
    sub.mkdir()
    settings.LOCAL_FILES_DOCUMENT_ROOT = str(root)
    settings.LOCAL_FILES_SERVING_ENABLED = True
    return sub


def _join_org(user, org):
    user.active_organization = org
    user.save(update_fields=['active_organization'])
    OrganizationMember.objects.get_or_create(user=user, organization=org)


@pytest.mark.django_db
def test_workspace_storage_model_persists(settings, tmp_path):
    """Model can be instantiated and saved with a workspace FK only (no project)."""
    sub = _configure_local_files_root(settings, tmp_path)
    workspace = WorkspaceFactory()

    storage = LocalFilesWorkspaceImportStorage.objects.create(
        workspace=workspace,
        title='ws-template',
        path=str(sub),
    )
    assert storage.pk is not None
    assert storage.workspace_id == workspace.id
    # No project FK should exist on workspace-scope storage.
    assert not hasattr(storage, 'project')


@pytest.mark.django_db
def test_workspace_storage_scan_is_disabled(settings, tmp_path):
    """Workspace templates must not sync tasks — there is no project to attach to."""
    sub = _configure_local_files_root(settings, tmp_path)
    workspace = WorkspaceFactory()
    storage = LocalFilesWorkspaceImportStorage.objects.create(
        workspace=workspace, title='ws-template', path=str(sub)
    )
    with pytest.raises(NotImplementedError):
        storage.scan_and_create_links()


@pytest.mark.django_db
def test_project_storage_can_reference_workspace_parent(settings, tmp_path):
    """LocalFilesImportStorage.parent_storage wires a project storage to its workspace template."""
    from projects.tests.factories import ProjectFactory

    sub = _configure_local_files_root(settings, tmp_path)
    workspace = WorkspaceFactory()
    project = ProjectFactory(organization=workspace.organization, workspace=workspace)

    template = LocalFilesWorkspaceImportStorage.objects.create(
        workspace=workspace, title='ws-template', path=str(sub)
    )
    child = LocalFilesImportStorage.objects.create(
        project=project, parent_storage=template, title='child', path=str(sub)
    )
    assert child.parent_storage_id == template.id
    assert list(template.child_storages.all()) == [child]


@pytest.mark.django_db
def test_list_requires_workspace_query_param(settings, tmp_path):
    org = OrganizationFactory()
    user = org.created_by
    _join_org(user, org)

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.get('/api/storages/localfiles/workspace/')
    assert response.status_code == 400


@pytest.mark.django_db
def test_list_scoped_to_workspace(settings, tmp_path):
    sub = _configure_local_files_root(settings, tmp_path)
    org = OrganizationFactory()
    owner = org.created_by
    _join_org(owner, org)

    ws = WorkspaceFactory(organization=org)
    other_ws = WorkspaceFactory(organization=org)
    LocalFilesWorkspaceImportStorage.objects.create(workspace=ws, title='in-scope', path=str(sub))
    LocalFilesWorkspaceImportStorage.objects.create(workspace=other_ws, title='out-of-scope', path=str(sub))

    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.get(f'/api/storages/localfiles/workspace/?workspace={ws.id}')
    assert response.status_code == 200, response.content
    payload = response.json()
    results = payload['results'] if isinstance(payload, dict) and 'results' in payload else payload
    titles = {row['title'] for row in results}
    assert titles == {'in-scope'}


@pytest.mark.django_db
def test_non_member_cannot_list_workspace_storages(settings, tmp_path):
    """Users outside the workspace (even in same org) are denied — owner is implicit manager so use a plain member."""
    sub = _configure_local_files_root(settings, tmp_path)
    org = OrganizationFactory()
    owner = org.created_by
    _join_org(owner, org)

    outsider = UserFactory()
    _join_org(outsider, org)

    ws = WorkspaceFactory(organization=org)
    LocalFilesWorkspaceImportStorage.objects.create(workspace=ws, title='x', path=str(sub))

    client = APIClient()
    client.force_authenticate(user=outsider)
    response = client.get(f'/api/storages/localfiles/workspace/?workspace={ws.id}')
    assert response.status_code == 403


@pytest.mark.django_db
def test_cross_org_workspace_access_denied(settings, tmp_path):
    sub = _configure_local_files_root(settings, tmp_path)
    org_a = OrganizationFactory()
    org_b = OrganizationFactory()
    user_a = org_a.created_by
    _join_org(user_a, org_a)
    ws_b = WorkspaceFactory(organization=org_b)
    LocalFilesWorkspaceImportStorage.objects.create(workspace=ws_b, title='x', path=str(sub))

    client = APIClient()
    client.force_authenticate(user=user_a)
    response = client.get(f'/api/storages/localfiles/workspace/?workspace={ws_b.id}')
    # Out-of-org lookup must not leak the workspace existence.
    assert response.status_code in (403, 404)


@pytest.mark.django_db
def test_non_manager_cannot_create_workspace_storage(settings, tmp_path):
    sub = _configure_local_files_root(settings, tmp_path)
    org = OrganizationFactory()
    owner = org.created_by  # org owner is implicit workspace manager
    _join_org(owner, org)
    plain_member = UserFactory()
    _join_org(plain_member, org)

    ws = WorkspaceFactory(organization=org)
    WorkspaceMember.objects.create(
        workspace=ws, user=plain_member, role=WorkspaceMember.Role.MEMBER
    )

    client = APIClient()
    client.force_authenticate(user=plain_member)
    response = client.post(
        '/api/storages/localfiles/workspace/',
        {'workspace': ws.id, 'title': 'nope', 'path': str(sub)},
        format='json',
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_manager_can_create_workspace_storage(settings, tmp_path):
    sub = _configure_local_files_root(settings, tmp_path)
    org = OrganizationFactory()
    owner = org.created_by
    _join_org(owner, org)
    ws = WorkspaceFactory(organization=org)

    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.post(
        '/api/storages/localfiles/workspace/',
        {'workspace': ws.id, 'title': 'template', 'path': str(sub)},
        format='json',
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert body['title'] == 'template'
    assert body['workspace'] == ws.id
    assert LocalFilesWorkspaceImportStorage.objects.filter(workspace=ws, title='template').exists()


@pytest.mark.django_db
def test_non_manager_cannot_delete_workspace_storage(settings, tmp_path):
    sub = _configure_local_files_root(settings, tmp_path)
    org = OrganizationFactory()
    owner = org.created_by
    _join_org(owner, org)
    plain_member = UserFactory()
    _join_org(plain_member, org)

    ws = WorkspaceFactory(organization=org)
    WorkspaceMember.objects.create(
        workspace=ws, user=plain_member, role=WorkspaceMember.Role.MEMBER
    )
    storage = LocalFilesWorkspaceImportStorage.objects.create(
        workspace=ws, title='t', path=str(sub)
    )

    client = APIClient()
    client.force_authenticate(user=plain_member)
    response = client.delete(f'/api/storages/localfiles/workspace/{storage.id}')
    assert response.status_code == 403
    assert LocalFilesWorkspaceImportStorage.objects.filter(pk=storage.pk).exists()
