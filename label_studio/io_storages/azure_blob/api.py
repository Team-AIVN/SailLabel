"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from django.utils.decorators import method_decorator
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from io_storages.api import (
    ExportStorageDetailAPI,
    ExportStorageFormLayoutAPI,
    ExportStorageListAPI,
    ExportStorageSyncAPI,
    ExportStorageValidateAPI,
    ImportStorageDetailAPI,
    ImportStorageFormLayoutAPI,
    ImportStorageListAPI,
    ImportStorageSyncAPI,
    ImportStorageValidateAPI,
    WorkspaceImportStorageDetailAPI,
    WorkspaceImportStorageListAPI,
    WorkspaceImportStorageSyncAPI,
    WorkspaceStorageAssignMixin,
    _compose_prefix,
)
from io_storages.azure_blob.models import (
    AzureBlobExportStorage,
    AzureBlobImportStorage,
    AzureBlobWorkspaceImportStorage,
)
from io_storages.azure_blob.serializers import (
    AzureBlobExportStorageSerializer,
    AzureBlobImportStorageSerializer,
    AzureBlobWorkspaceImportStorageSerializer,
)

from core.permissions import ViewClassPermission, all_permissions
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from .openapi_schema import (
    _azure_blob_export_storage_schema,
    _azure_blob_export_storage_schema_with_id,
    _azure_blob_import_storage_schema,
    _azure_blob_import_storage_schema_with_id,
)


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Storage: Azure'],
        summary='Get all import storage',
        description='Get list of all Azure import storage connections.',
        parameters=[
            OpenApiParameter(
                name='project',
                type=OpenApiTypes.INT,
                location='query',
                description='Project ID',
                required=True,
            ),
        ],
        request=None,
        extensions={
            'x-fern-sdk-group-name': ['import_storage', 'azure'],
            'x-fern-sdk-method-name': 'list',
            'x-fern-audiences': ['public'],
        },
    ),
)
@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Storage: Azure'],
        summary='Create new storage',
        description='Create new Azure import storage',
        request={
            'application/json': _azure_blob_import_storage_schema,
        },
        extensions={
            'x-fern-sdk-group-name': ['import_storage', 'azure'],
            'x-fern-sdk-method-name': 'create',
            'x-fern-audiences': ['public'],
        },
    ),
)
class AzureBlobImportStorageListAPI(ImportStorageListAPI):
    queryset = AzureBlobImportStorage.objects.all()
    serializer_class = AzureBlobImportStorageSerializer


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Storage: Azure'],
        summary='Get import storage',
        description='Get a specific Azure import storage connection.',
        request=None,
        extensions={
            'x-fern-sdk-group-name': ['import_storage', 'azure'],
            'x-fern-sdk-method-name': 'get',
            'x-fern-audiences': ['public'],
        },
    ),
)
@method_decorator(
    name='patch',
    decorator=extend_schema(
        tags=['Storage: Azure'],
        summary='Update import storage',
        description='Update a specific Azure import storage connection.',
        request={
            'application/json': _azure_blob_import_storage_schema,
        },
        extensions={
            'x-fern-sdk-group-name': ['import_storage', 'azure'],
            'x-fern-sdk-method-name': 'update',
            'x-fern-audiences': ['public'],
        },
    ),
)
@method_decorator(
    name='delete',
    decorator=extend_schema(
        tags=['Storage: Azure'],
        summary='Delete import storage',
        description='Delete a specific Azure import storage connection.',
        request=None,
        extensions={
            'x-fern-sdk-group-name': ['import_storage', 'azure'],
            'x-fern-sdk-method-name': 'delete',
            'x-fern-audiences': ['public'],
        },
    ),
)
class AzureBlobImportStorageDetailAPI(ImportStorageDetailAPI):
    queryset = AzureBlobImportStorage.objects.all()
    serializer_class = AzureBlobImportStorageSerializer


@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Storage: Azure'],
        summary='Sync import storage',
        description='Sync tasks from an Azure import storage connection.',
        parameters=[
            OpenApiParameter(
                name='id',
                type=OpenApiTypes.INT,
                location='path',
                description='Storage ID',
            ),
        ],
        request=None,
        extensions={
            'x-fern-sdk-group-name': ['import_storage', 'azure'],
            'x-fern-sdk-method-name': 'sync',
            'x-fern-audiences': ['public'],
        },
    ),
)
class AzureBlobImportStorageSyncAPI(ImportStorageSyncAPI):
    serializer_class = AzureBlobImportStorageSerializer


@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Storage: Azure'],
        summary='Sync export storage',
        description='Sync tasks from an Azure export storage connection.',
        request=None,
        extensions={
            'x-fern-sdk-group-name': ['export_storage', 'azure'],
            'x-fern-sdk-method-name': 'sync',
            'x-fern-audiences': ['public'],
        },
    ),
)
class AzureBlobExportStorageSyncAPI(ExportStorageSyncAPI):
    serializer_class = AzureBlobExportStorageSerializer


@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Storage: Azure'],
        summary='Validate import storage',
        description='Validate a specific Azure import storage connection.',
        request={
            'application/json': _azure_blob_import_storage_schema_with_id,
        },
        responses={200: OpenApiResponse(description='Validation successful')},
        extensions={
            'x-fern-sdk-group-name': ['import_storage', 'azure'],
            'x-fern-sdk-method-name': 'validate',
            'x-fern-audiences': ['public'],
        },
    ),
)
class AzureBlobImportStorageValidateAPI(ImportStorageValidateAPI):
    serializer_class = AzureBlobImportStorageSerializer


@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Storage: Azure'],
        summary='Validate export storage',
        description='Validate a specific Azure export storage connection.',
        request={
            'application/json': _azure_blob_export_storage_schema_with_id,
        },
        responses={200: OpenApiResponse(description='Validation successful')},
        extensions={
            'x-fern-sdk-group-name': ['export_storage', 'azure'],
            'x-fern-sdk-method-name': 'validate',
            'x-fern-audiences': ['public'],
        },
    ),
)
class AzureBlobExportStorageValidateAPI(ExportStorageValidateAPI):
    serializer_class = AzureBlobExportStorageSerializer


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Storage: Azure'],
        summary='Get all export storage',
        description='Get a list of all Azure export storage connections.',
        parameters=[
            OpenApiParameter(
                name='project',
                type=OpenApiTypes.INT,
                location='query',
                description='Project ID',
                required=True,
            ),
        ],
        extensions={
            'x-fern-sdk-group-name': ['export_storage', 'azure'],
            'x-fern-sdk-method-name': 'list',
            'x-fern-audiences': ['public'],
        },
    ),
)
@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Storage: Azure'],
        summary='Create export storage',
        description='Create a new Azure export storage connection to store annotations.',
        request={
            'application/json': _azure_blob_export_storage_schema,
        },
        extensions={
            'x-fern-sdk-group-name': ['export_storage', 'azure'],
            'x-fern-sdk-method-name': 'create',
            'x-fern-audiences': ['public'],
        },
    ),
)
class AzureBlobExportStorageListAPI(ExportStorageListAPI):
    queryset = AzureBlobExportStorage.objects.all()
    serializer_class = AzureBlobExportStorageSerializer


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Storage: Azure'],
        summary='Get export storage',
        description='Get a specific Azure export storage connection.',
        request=None,
        extensions={
            'x-fern-sdk-group-name': ['export_storage', 'azure'],
            'x-fern-sdk-method-name': 'get',
            'x-fern-audiences': ['public'],
        },
    ),
)
@method_decorator(
    name='patch',
    decorator=extend_schema(
        tags=['Storage: Azure'],
        summary='Update export storage',
        description='Update a specific Azure export storage connection.',
        request={
            'application/json': _azure_blob_export_storage_schema,
        },
        extensions={
            'x-fern-sdk-group-name': ['export_storage', 'azure'],
            'x-fern-sdk-method-name': 'update',
            'x-fern-audiences': ['public'],
        },
    ),
)
@method_decorator(
    name='delete',
    decorator=extend_schema(
        tags=['Storage: Azure'],
        summary='Delete export storage',
        description='Delete a specific Azure export storage connection.',
        request=None,
        extensions={
            'x-fern-sdk-group-name': ['export_storage', 'azure'],
            'x-fern-sdk-method-name': 'delete',
            'x-fern-audiences': ['public'],
        },
    ),
)
class AzureBlobExportStorageDetailAPI(ExportStorageDetailAPI):
    queryset = AzureBlobExportStorage.objects.all()
    serializer_class = AzureBlobExportStorageSerializer


class AzureBlobImportStorageFormLayoutAPI(ImportStorageFormLayoutAPI):
    pass


class AzureBlobExportStorageFormLayoutAPI(ExportStorageFormLayoutAPI):
    pass


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Storage: Azure'],
        summary='List workspace-scope import storage',
        description='List Azure import storage templates for a workspace.',
        parameters=[
            OpenApiParameter(
                name='workspace',
                type=OpenApiTypes.INT,
                location='query',
                description='Workspace ID',
                required=True,
            ),
        ],
        request=None,
    ),
)
@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Storage: Azure'],
        summary='Create workspace-scope import storage',
        description='Create a workspace-scope Azure Blob import storage template.',
    ),
)
class AzureBlobWorkspaceImportStorageListAPI(WorkspaceImportStorageListAPI):
    queryset = AzureBlobWorkspaceImportStorage.objects.all()
    serializer_class = AzureBlobWorkspaceImportStorageSerializer


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Storage: Azure'],
        summary='Get workspace-scope import storage',
        description='Get a workspace-scope Azure Blob import storage template.',
        request=None,
    ),
)
@method_decorator(
    name='patch',
    decorator=extend_schema(
        tags=['Storage: Azure'],
        summary='Update workspace-scope import storage',
        description='Update a workspace-scope Azure Blob import storage template.',
    ),
)
@method_decorator(
    name='delete',
    decorator=extend_schema(
        tags=['Storage: Azure'],
        summary='Delete workspace-scope import storage',
        description='Delete a workspace-scope Azure Blob import storage template.',
        request=None,
    ),
)
class AzureBlobWorkspaceImportStorageDetailAPI(WorkspaceImportStorageDetailAPI):
    queryset = AzureBlobWorkspaceImportStorage.objects.all()
    serializer_class = AzureBlobWorkspaceImportStorageSerializer


@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Storage: Azure'],
        summary='Sync workspace-scope import storage',
        description=(
            'Scan the Azure container and load blobs as workspace task-pool source items '
            '(TaskSourceItem). Idempotent: already-imported blobs are skipped.'
        ),
    ),
)
class AzureBlobWorkspaceImportStorageSyncAPI(WorkspaceImportStorageSyncAPI):
    queryset = AzureBlobWorkspaceImportStorage.objects.all()
    serializer_class = AzureBlobWorkspaceImportStorageSerializer


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Storage: Azure'],
        summary='Browse Azure container folders',
        description=(
            'List folders (one level) of the deployment-default Azure container using the '
            'server credentials (AZURE_BLOB_ACCOUNT_NAME/KEY, AZURE_BLOB_DEFAULT_CONTAINER). '
            'Used by the workspace storage UI so managers can pick a folder without knowing '
            'container/prefix jargon.'
        ),
        parameters=[
            OpenApiParameter(name='workspace', type=OpenApiTypes.INT, location='query', required=True),
            OpenApiParameter(name='path', type=OpenApiTypes.STR, location='query', required=False),
        ],
    ),
)
class AzureBlobWorkspaceStorageBrowseAPI(generics.GenericAPIView):
    permission_required = ViewClassPermission(GET=all_permissions.workspaces_view)
    serializer_class = AzureBlobWorkspaceImportStorageSerializer  # for permission plumbing only

    def get(self, request, *args, **kwargs):
        from azure.storage.blob import BlobPrefix
        from core.utils.params import get_env
        from io_storages.api import _resolve_workspace_for_user
        from io_storages.azure_blob.utils import AZURE
        from workspaces.rules import is_workspace_manager

        workspace_pk = request.query_params.get('workspace')
        if not workspace_pk:
            raise ValidationError('query parameter "workspace" is required')
        workspace = _resolve_workspace_for_user(request, workspace_pk)
        if not is_workspace_manager(request.user, workspace):
            raise PermissionDenied('Only a workspace manager can browse storage folders.')

        # Container is fixed server-side to the deployment default — never trust a
        # client-supplied container, or a manager could browse arbitrary containers
        # using the shared server credentials (cross-tenant leak).
        container_name = get_env('AZURE_BLOB_DEFAULT_CONTAINER')
        if not container_name:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={
                    'configured': False,
                    'detail': (
                        '서버에 Azure 연결 정보가 없습니다. 환경변수 AZURE_BLOB_ACCOUNT_NAME, '
                        'AZURE_BLOB_ACCOUNT_KEY, AZURE_BLOB_DEFAULT_CONTAINER를 설정해 주세요.'
                    ),
                },
            )
        path = (request.query_params.get('path') or '').lstrip('/')
        if path and not path.endswith('/'):
            path += '/'
        # Folders that are never import targets (image originals, annotation exports).
        hidden = {n.strip() for n in (get_env('AZURE_BLOB_BROWSE_HIDE') or 'images,export').split(',') if n.strip()}
        try:
            _, container = AZURE.get_client_and_container(container_name)
            folders, file_count = [], 0
            for entry in container.walk_blobs(name_starts_with=path or None, delimiter='/'):
                if isinstance(entry, BlobPrefix):
                    name = entry.name[len(path) :].rstrip('/')
                    if name in hidden:
                        continue
                    folders.append({'name': name, 'path': entry.name})
                else:
                    file_count += 1
        except ValueError as e:  # missing env credentials
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'configured': False, 'detail': str(e)})
        except Exception as e:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={'configured': True, 'detail': f'Azure 연결에 실패했습니다: {e}'},
            )
        return Response(
            {'configured': True, 'container': container_name, 'path': path, 'folders': folders, 'file_count': file_count}
        )


@extend_schema(
    tags=['Storage: Azure'],
    summary='Assign workspace storage to a project',
    description=(
        'Derive a project-scope AzureBlobImportStorage from a workspace-scope template. '
        'The child storage inherits the container + credentials; the prefix can be '
        'extended with a relative subpath under the template prefix.'
    ),
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'project': {'type': 'integer', 'description': 'Project ID in the same workspace'},
                'subpath': {
                    'type': 'string',
                    'description': 'Optional relative prefix under the template prefix',
                },
                'title': {'type': 'string'},
            },
            'required': ['project'],
        },
    },
    responses={201: AzureBlobImportStorageSerializer},
)
class AzureBlobWorkspaceImportStorageAssignAPI(WorkspaceStorageAssignMixin):
    queryset = AzureBlobWorkspaceImportStorage.objects.all()
    serializer_class = AzureBlobWorkspaceImportStorageSerializer
    child_serializer_class = AzureBlobImportStorageSerializer

    def build_child(self, template, project, request):
        subpath = request.data.get('subpath') or ''
        target_prefix = _compose_prefix(template.prefix or '', subpath)
        title = request.data.get('title') or template.title or f'From {template.title or "workspace template"}'
        return AzureBlobImportStorage(
            project=project,
            parent_storage=template,
            title=title,
            container=template.container,
            prefix=target_prefix or None,
            regex_filter=template.regex_filter,
            use_blob_urls=template.use_blob_urls,
            account_name=template.account_name,
            account_key=template.account_key,
            presign=template.presign,
            presign_ttl=template.presign_ttl,
            recursive_scan=template.recursive_scan,
        )
