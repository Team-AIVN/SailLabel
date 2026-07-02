"""Assign-endpoint tests for cloud-backed workspace storage templates.

The cloud backends (S3, GCS, Azure Blob) share the ``WorkspaceStorageAssignMixin``
flow: permission check, cross-workspace guard, prefix composition, then
connection validation before persistence. We mock ``validate_connection`` so the
tests don't require real cloud credentials; the assertions focus on the wiring
that unit tests can verify (parent_storage link, prefix composition, perm
guards).
"""

from unittest.mock import patch

import pytest
from io_storages.azure_blob.models import AzureBlobImportStorage, AzureBlobWorkspaceImportStorage
from io_storages.gcs.models import GCSImportStorage, GCSWorkspaceImportStorage
from io_storages.s3.models import S3ImportStorage, S3WorkspaceImportStorage
from organizations.models import OrganizationMember
from organizations.tests.factories import OrganizationFactory
from projects.tests.factories import ProjectFactory
from rest_framework.test import APIClient
from users.tests.factories import UserFactory
from workspaces.models import WorkspaceMember
from workspaces.tests.factories import WorkspaceFactory


def _join_org(user, org):
    user.active_organization = org
    user.save(update_fields=['active_organization'])
    OrganizationMember.objects.get_or_create(user=user, organization=org)


def _setup_manager(org=None):
    org = org or OrganizationFactory()
    owner = org.created_by
    _join_org(owner, org)
    ws = WorkspaceFactory(organization=org)
    project = ProjectFactory(organization=org, workspace=ws)
    return owner, org, ws, project


# ---------- S3 ----------


def _make_s3_template(ws, prefix='tpl'):
    return S3WorkspaceImportStorage.objects.create(
        workspace=ws,
        title='s3-template',
        bucket='my-bucket',
        prefix=prefix,
        aws_access_key_id='AKIA...',
        aws_secret_access_key='secret',
    )


@pytest.mark.django_db
@patch.object(S3ImportStorage, 'validate_connection', return_value=None)
def test_s3_assign_creates_child_storage(_mock_vc):
    owner, _org, ws, project = _setup_manager()
    template = _make_s3_template(ws, prefix='tpl')

    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.post(
        f'/api/storages/s3/workspace/{template.id}/assign',
        {'project': project.id},
        format='json',
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert body['project'] == project.id
    assert body['parent_storage'] == template.id
    assert body['bucket'] == 'my-bucket'
    assert body['prefix'] == 'tpl'
    assert S3ImportStorage.objects.filter(parent_storage=template, project=project).exists()


@pytest.mark.django_db
@patch.object(S3ImportStorage, 'validate_connection', return_value=None)
def test_s3_assign_joins_subpath_under_template(_mock_vc):
    owner, _org, ws, project = _setup_manager()
    template = _make_s3_template(ws, prefix='tpl')

    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.post(
        f'/api/storages/s3/workspace/{template.id}/assign',
        {'project': project.id, 'subpath': 'nested/dir'},
        format='json',
    )
    assert response.status_code == 201, response.content
    assert response.json()['prefix'] == 'tpl/nested/dir'


@pytest.mark.django_db
@patch.object(S3ImportStorage, 'validate_connection', return_value=None)
def test_s3_assign_rejects_path_traversal(_mock_vc):
    owner, _org, ws, project = _setup_manager()
    template = _make_s3_template(ws, prefix='tpl')

    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.post(
        f'/api/storages/s3/workspace/{template.id}/assign',
        {'project': project.id, 'subpath': '../escape'},
        format='json',
    )
    assert response.status_code == 400
    assert not S3ImportStorage.objects.filter(project=project).exists()


@pytest.mark.django_db
def test_s3_assign_requires_workspace_manager():
    org = OrganizationFactory()
    _join_org(org.created_by, org)
    member = UserFactory()
    _join_org(member, org)
    ws = WorkspaceFactory(organization=org)
    WorkspaceMember.objects.create(workspace=ws, user=member, role=WorkspaceMember.Role.MEMBER)
    project = ProjectFactory(organization=org, workspace=ws)
    template = _make_s3_template(ws)

    client = APIClient()
    client.force_authenticate(user=member)
    response = client.post(
        f'/api/storages/s3/workspace/{template.id}/assign',
        {'project': project.id},
        format='json',
    )
    assert response.status_code == 403


# ---------- GCS ----------


def _make_gcs_template(ws, prefix='tpl'):
    return GCSWorkspaceImportStorage.objects.create(
        workspace=ws,
        title='gcs-template',
        bucket='my-gcs-bucket',
        prefix=prefix,
        google_application_credentials='{"type": "service_account"}',
        google_project_id='my-project',
    )


@pytest.mark.django_db
@patch.object(GCSImportStorage, 'validate_connection', return_value=None)
def test_gcs_assign_creates_child_storage(_mock_vc):
    owner, _org, ws, project = _setup_manager()
    template = _make_gcs_template(ws, prefix='tpl')

    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.post(
        f'/api/storages/gcs/workspace/{template.id}/assign',
        {'project': project.id},
        format='json',
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert body['parent_storage'] == template.id
    assert body['bucket'] == 'my-gcs-bucket'
    assert body['prefix'] == 'tpl'


@pytest.mark.django_db
@patch.object(GCSImportStorage, 'validate_connection', return_value=None)
def test_gcs_assign_joins_subpath(_mock_vc):
    owner, _org, ws, project = _setup_manager()
    template = _make_gcs_template(ws, prefix='tpl')

    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.post(
        f'/api/storages/gcs/workspace/{template.id}/assign',
        {'project': project.id, 'subpath': 'a/b'},
        format='json',
    )
    assert response.status_code == 201, response.content
    assert response.json()['prefix'] == 'tpl/a/b'


@pytest.mark.django_db
def test_gcs_assign_rejects_cross_workspace_project():
    owner, org, ws, _project = _setup_manager()
    other_ws = WorkspaceFactory(organization=org)
    other_project = ProjectFactory(organization=org, workspace=other_ws)
    template = _make_gcs_template(ws)

    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.post(
        f'/api/storages/gcs/workspace/{template.id}/assign',
        {'project': other_project.id},
        format='json',
    )
    assert response.status_code == 400


# ---------- Azure Blob ----------


def _make_azure_template(ws, prefix='tpl'):
    return AzureBlobWorkspaceImportStorage.objects.create(
        workspace=ws,
        title='azure-template',
        container='my-container',
        prefix=prefix,
        account_name='acct',
        account_key='key',
    )


@pytest.mark.django_db
@patch.object(AzureBlobImportStorage, 'validate_connection', return_value=None)
def test_azure_assign_creates_child_storage(_mock_vc):
    owner, _org, ws, project = _setup_manager()
    template = _make_azure_template(ws, prefix='tpl')

    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.post(
        f'/api/storages/azure/workspace/{template.id}/assign',
        {'project': project.id},
        format='json',
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert body['parent_storage'] == template.id
    assert body['container'] == 'my-container'
    assert body['prefix'] == 'tpl'


@pytest.mark.django_db
@patch.object(AzureBlobImportStorage, 'validate_connection', return_value=None)
def test_azure_assign_joins_subpath(_mock_vc):
    owner, _org, ws, project = _setup_manager()
    template = _make_azure_template(ws, prefix='tpl')

    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.post(
        f'/api/storages/azure/workspace/{template.id}/assign',
        {'project': project.id, 'subpath': 'sub/area'},
        format='json',
    )
    assert response.status_code == 201, response.content
    assert response.json()['prefix'] == 'tpl/sub/area'


@pytest.mark.django_db
def test_azure_assign_rejects_cross_org_template():
    org_a = OrganizationFactory()
    org_b = OrganizationFactory()
    user_a = org_a.created_by
    _join_org(user_a, org_a)
    ws_b = WorkspaceFactory(organization=org_b)
    project_b = ProjectFactory(organization=org_b, workspace=ws_b)
    template_b = _make_azure_template(ws_b)

    client = APIClient()
    client.force_authenticate(user=user_a)
    response = client.post(
        f'/api/storages/azure/workspace/{template_b.id}/assign',
        {'project': project_b.id},
        format='json',
    )
    assert response.status_code in (403, 404)
