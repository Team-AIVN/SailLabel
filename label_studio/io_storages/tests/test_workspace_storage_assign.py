"""Tests for the workspace → project storage assign endpoint (Phase 3B-1)."""

import pytest  # type: ignore[import]
from io_storages.localfiles.models import (
    LocalFilesImportStorage,
    LocalFilesWorkspaceImportStorage,
)
from organizations.models import OrganizationMember
from organizations.tests.factories import OrganizationFactory
from projects.tests.factories import ProjectFactory
from rest_framework.test import APIClient
from users.tests.factories import UserFactory
from workspaces.models import WorkspaceMember
from workspaces.tests.factories import WorkspaceFactory


def _configure_root_with_subdir(settings, tmp_path, extra='nested'):
    root = tmp_path / 'root'
    root.mkdir()
    sub = root / 'sub'
    sub.mkdir()
    (sub / extra).mkdir()
    settings.LOCAL_FILES_DOCUMENT_ROOT = str(root)
    settings.LOCAL_FILES_SERVING_ENABLED = True
    return root, sub


def _join_org(user, org):
    user.active_organization = org
    user.save(update_fields=['active_organization'])
    OrganizationMember.objects.get_or_create(user=user, organization=org)


def _setup_manager_and_project(settings, tmp_path):
    _, sub = _configure_root_with_subdir(settings, tmp_path)
    org = OrganizationFactory()
    owner = org.created_by
    _join_org(owner, org)
    ws = WorkspaceFactory(organization=org)
    project = ProjectFactory(organization=org, workspace=ws)
    template = LocalFilesWorkspaceImportStorage.objects.create(
        workspace=ws, title='tpl', path=str(sub)
    )
    return owner, ws, project, template, sub


@pytest.mark.django_db
def test_assign_creates_child_storage(settings, tmp_path):
    owner, ws, project, template, sub = _setup_manager_and_project(settings, tmp_path)

    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.post(
        f'/api/storages/localfiles/workspace/{template.id}/assign',
        {'project': project.id},
        format='json',
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert body['project'] == project.id
    assert body['parent_storage'] == template.id
    assert body['path'] == str(sub)
    assert LocalFilesImportStorage.objects.filter(
        project=project, parent_storage=template
    ).exists()


@pytest.mark.django_db
def test_assign_joins_subpath_under_template(settings, tmp_path):
    owner, ws, project, template, sub = _setup_manager_and_project(settings, tmp_path)

    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.post(
        f'/api/storages/localfiles/workspace/{template.id}/assign',
        {'project': project.id, 'subpath': 'nested'},
        format='json',
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert body['path'] == str(sub / 'nested')


@pytest.mark.django_db
def test_assign_rejects_path_traversal(settings, tmp_path):
    owner, ws, project, template, sub = _setup_manager_and_project(settings, tmp_path)

    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.post(
        f'/api/storages/localfiles/workspace/{template.id}/assign',
        {'project': project.id, 'subpath': '../escape'},
        format='json',
    )
    assert response.status_code == 400
    # Child storage must not have been persisted.
    assert not LocalFilesImportStorage.objects.filter(project=project).exists()


@pytest.mark.django_db
def test_assign_rejects_absolute_subpath(settings, tmp_path):
    owner, ws, project, template, sub = _setup_manager_and_project(settings, tmp_path)

    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.post(
        f'/api/storages/localfiles/workspace/{template.id}/assign',
        {'project': project.id, 'subpath': '/etc'},
        format='json',
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_assign_requires_workspace_manager(settings, tmp_path):
    _, sub = _configure_root_with_subdir(settings, tmp_path)
    org = OrganizationFactory()
    _join_org(org.created_by, org)
    member = UserFactory()
    _join_org(member, org)
    ws = WorkspaceFactory(organization=org)
    WorkspaceMember.objects.create(workspace=ws, user=member, role=WorkspaceMember.Role.MEMBER)
    project = ProjectFactory(organization=org, workspace=ws)
    template = LocalFilesWorkspaceImportStorage.objects.create(
        workspace=ws, title='tpl', path=str(sub)
    )

    client = APIClient()
    client.force_authenticate(user=member)
    response = client.post(
        f'/api/storages/localfiles/workspace/{template.id}/assign',
        {'project': project.id},
        format='json',
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_assign_rejects_project_in_other_workspace(settings, tmp_path):
    owner, ws, _project, template, sub = _setup_manager_and_project(settings, tmp_path)
    other_ws = WorkspaceFactory(organization=ws.organization)
    other_project = ProjectFactory(organization=ws.organization, workspace=other_ws)

    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.post(
        f'/api/storages/localfiles/workspace/{template.id}/assign',
        {'project': other_project.id},
        format='json',
    )
    assert response.status_code == 400
    assert not LocalFilesImportStorage.objects.filter(project=other_project).exists()


@pytest.mark.django_db
def test_assign_rejects_cross_org_template(settings, tmp_path):
    _, sub = _configure_root_with_subdir(settings, tmp_path)
    org_a = OrganizationFactory()
    org_b = OrganizationFactory()
    user_a = org_a.created_by
    _join_org(user_a, org_a)
    ws_b = WorkspaceFactory(organization=org_b)
    project_b = ProjectFactory(organization=org_b, workspace=ws_b)
    template_b = LocalFilesWorkspaceImportStorage.objects.create(
        workspace=ws_b, title='tpl', path=str(sub)
    )

    client = APIClient()
    client.force_authenticate(user=user_a)
    response = client.post(
        f'/api/storages/localfiles/workspace/{template_b.id}/assign',
        {'project': project_b.id},
        format='json',
    )
    assert response.status_code in (403, 404)
