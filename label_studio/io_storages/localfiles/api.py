"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

import os

from core.permissions import ViewClassPermission, all_permissions
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
    _resolve_workspace_for_user,
)
from io_storages.localfiles.models import (
    LocalFilesExportStorage,
    LocalFilesImportStorage,
    LocalFilesWorkspaceImportStorage,
)
from io_storages.localfiles.serializers import (
    LocalFilesExportStorageSerializer,
    LocalFilesImportStorageSerializer,
    LocalFilesWorkspaceImportStorageSerializer,
)
from projects.models import Project
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from workspaces.rules import is_workspace_manager

from .openapi_schema import (
    _local_files_export_storage_schema,
    _local_files_export_storage_schema_with_id,
    _local_files_import_storage_schema,
    _local_files_import_storage_schema_with_id,
)


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Storage: Local'],
        summary='Get all import storage',
        description='Get a list of all local file import storage connections.',
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
            'x-fern-sdk-group-name': ['import_storage', 'local'],
            'x-fern-sdk-method-name': 'list',
            'x-fern-audiences': ['public'],
        },
    ),
)
@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Storage: Local'],
        summary='Create import storage',
        description='Create a new local file import storage connection.',
        request={
            'application/json': _local_files_import_storage_schema,
        },
        extensions={
            'x-fern-sdk-group-name': ['import_storage', 'local'],
            'x-fern-sdk-method-name': 'create',
            'x-fern-audiences': ['public'],
        },
    ),
)
class LocalFilesImportStorageListAPI(ImportStorageListAPI):
    queryset = LocalFilesImportStorage.objects.all()
    serializer_class = LocalFilesImportStorageSerializer


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Storage: Local'],
        summary='Get import storage',
        description='Get a specific local file import storage connection.',
        request=None,
        extensions={
            'x-fern-sdk-group-name': ['import_storage', 'local'],
            'x-fern-sdk-method-name': 'get',
            'x-fern-audiences': ['public'],
        },
    ),
)
@method_decorator(
    name='patch',
    decorator=extend_schema(
        tags=['Storage: Local'],
        summary='Update import storage',
        description='Update a specific local file import storage connection.',
        request={
            'application/json': _local_files_import_storage_schema,
        },
        extensions={
            'x-fern-sdk-group-name': ['import_storage', 'local'],
            'x-fern-sdk-method-name': 'update',
            'x-fern-audiences': ['public'],
        },
    ),
)
@method_decorator(
    name='delete',
    decorator=extend_schema(
        tags=['Storage: Local'],
        summary='Delete import storage',
        description='Delete a specific local file import storage connection.',
        request=None,
        extensions={
            'x-fern-sdk-group-name': ['import_storage', 'local'],
            'x-fern-sdk-method-name': 'delete',
            'x-fern-audiences': ['public'],
        },
    ),
)
class LocalFilesImportStorageDetailAPI(ImportStorageDetailAPI):
    queryset = LocalFilesImportStorage.objects.all()
    serializer_class = LocalFilesImportStorageSerializer


@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Storage: Local'],
        summary='Sync import storage',
        description='Sync tasks from a local file import storage connection.',
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
            'x-fern-sdk-group-name': ['import_storage', 'local'],
            'x-fern-sdk-method-name': 'sync',
            'x-fern-audiences': ['public'],
        },
    ),
)
class LocalFilesImportStorageSyncAPI(ImportStorageSyncAPI):
    serializer_class = LocalFilesImportStorageSerializer


@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Storage: Local'],
        summary='Sync export storage',
        description='Sync tasks from a local file export storage connection.',
        request=None,
        extensions={
            'x-fern-sdk-group-name': ['export_storage', 'local'],
            'x-fern-sdk-method-name': 'sync',
            'x-fern-audiences': ['public'],
        },
    ),
)
class LocalFilesExportStorageSyncAPI(ExportStorageSyncAPI):
    serializer_class = LocalFilesExportStorageSerializer


@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Storage: Local'],
        summary='Validate import storage',
        description='Validate a specific local file import storage connection.',
        request={
            'application/json': _local_files_import_storage_schema_with_id,
        },
        responses={200: OpenApiResponse(description='Validation successful')},
        extensions={
            'x-fern-sdk-group-name': ['import_storage', 'local'],
            'x-fern-sdk-method-name': 'validate',
            'x-fern-audiences': ['public'],
        },
    ),
)
class LocalFilesImportStorageValidateAPI(ImportStorageValidateAPI):
    serializer_class = LocalFilesImportStorageSerializer


@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Storage: Local'],
        summary='Validate export storage',
        description='Validate a specific local file export storage connection.',
        request={
            'application/json': _local_files_export_storage_schema_with_id,
        },
        responses={200: OpenApiResponse(description='Validation successful')},
        extensions={
            'x-fern-sdk-group-name': ['export_storage', 'local'],
            'x-fern-sdk-method-name': 'validate',
            'x-fern-audiences': ['public'],
        },
    ),
)
class LocalFilesExportStorageValidateAPI(ExportStorageValidateAPI):
    serializer_class = LocalFilesExportStorageSerializer


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Storage: Local'],
        summary='Get all export storage',
        description='Get a list of all local file export storage connections.',
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
            'x-fern-sdk-group-name': ['export_storage', 'local'],
            'x-fern-sdk-method-name': 'list',
            'x-fern-audiences': ['public'],
        },
    ),
)
@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Storage: Local'],
        summary='Create export storage',
        description='Create a new local file export storage connection to store annotations.',
        request={
            'application/json': _local_files_export_storage_schema,
        },
        extensions={
            'x-fern-sdk-group-name': ['export_storage', 'local'],
            'x-fern-sdk-method-name': 'create',
            'x-fern-audiences': ['public'],
        },
    ),
)
class LocalFilesExportStorageListAPI(ExportStorageListAPI):
    queryset = LocalFilesExportStorage.objects.all()
    serializer_class = LocalFilesExportStorageSerializer


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Storage: Local'],
        summary='Get export storage',
        description='Get a specific local file export storage connection.',
        request=None,
        extensions={
            'x-fern-sdk-group-name': ['export_storage', 'local'],
            'x-fern-sdk-method-name': 'get',
            'x-fern-audiences': ['public'],
        },
    ),
)
@method_decorator(
    name='patch',
    decorator=extend_schema(
        tags=['Storage: Local'],
        summary='Update export storage',
        description='Update a specific local file export storage connection.',
        request={
            'application/json': _local_files_export_storage_schema,
        },
        extensions={
            'x-fern-sdk-group-name': ['export_storage', 'local'],
            'x-fern-sdk-method-name': 'update',
            'x-fern-audiences': ['public'],
        },
    ),
)
@method_decorator(
    name='delete',
    decorator=extend_schema(
        tags=['Storage: Local'],
        summary='Delete export storage',
        description='Delete a specific local file export storage connection.',
        request=None,
        extensions={
            'x-fern-sdk-group-name': ['export_storage', 'local'],
            'x-fern-sdk-method-name': 'delete',
            'x-fern-audiences': ['public'],
        },
    ),
)
class LocalFilesExportStorageDetailAPI(ExportStorageDetailAPI):
    queryset = LocalFilesExportStorage.objects.all()
    serializer_class = LocalFilesExportStorageSerializer


class LocalFilesImportStorageFormLayoutAPI(ImportStorageFormLayoutAPI):
    pass


class LocalFilesExportStorageFormLayoutAPI(ExportStorageFormLayoutAPI):
    pass


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Storage: Local'],
        summary='List workspace-scope import storage',
        description='List local-file import storage templates for a workspace.',
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
        tags=['Storage: Local'],
        summary='Create workspace-scope import storage',
        description='Create a workspace-scope local-file import storage template.',
    ),
)
class LocalFilesWorkspaceImportStorageListAPI(WorkspaceImportStorageListAPI):
    queryset = LocalFilesWorkspaceImportStorage.objects.all()
    serializer_class = LocalFilesWorkspaceImportStorageSerializer


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Storage: Local'],
        summary='Get workspace-scope import storage',
        description='Get a workspace-scope local-file import storage template.',
        request=None,
    ),
)
@method_decorator(
    name='patch',
    decorator=extend_schema(
        tags=['Storage: Local'],
        summary='Update workspace-scope import storage',
        description='Update a workspace-scope local-file import storage template.',
    ),
)
@method_decorator(
    name='delete',
    decorator=extend_schema(
        tags=['Storage: Local'],
        summary='Delete workspace-scope import storage',
        description='Delete a workspace-scope local-file import storage template.',
        request=None,
    ),
)
class LocalFilesWorkspaceImportStorageDetailAPI(WorkspaceImportStorageDetailAPI):
    queryset = LocalFilesWorkspaceImportStorage.objects.all()
    serializer_class = LocalFilesWorkspaceImportStorageSerializer


def _resolve_subpath_under(parent_path: str, subpath: str) -> str:
    """Join a workspace-template path with a caller-supplied subpath safely.

    Rejects any combination that escapes the parent (via ``..`` or absolute
    segments) so a project-scope storage derived from a workspace template can
    never be pointed outside the templated root. Returns the normalized
    absolute path.
    """
    if not subpath:
        return parent_path
    if os.path.isabs(subpath):
        raise ValidationError({'subpath': 'must be relative to the workspace storage path'})
    joined = os.path.normpath(os.path.join(parent_path, subpath))
    parent_norm = os.path.normpath(parent_path)
    # ``commonpath`` raises for mixed drives on Windows; here we only care that
    # the joined path stays inside the parent.
    if joined != parent_norm and not joined.startswith(parent_norm + os.sep):
        raise ValidationError({'subpath': 'must resolve to a location inside the workspace storage path'})
    return joined


@extend_schema(
    tags=['Storage: Local'],
    summary='Assign workspace storage to a project',
    description=(
        'Derive a project-scope LocalFilesImportStorage from a workspace-scope '
        'template. The child storage inherits the template path (optionally '
        'joined with a relative subpath) and is wired back via parent_storage '
        'so future rebalancing can identify workspace-originated storages.'
    ),
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'project': {'type': 'integer', 'description': 'Project ID in the same workspace'},
                'subpath': {
                    'type': 'string',
                    'description': 'Optional relative subdirectory under the template path',
                },
                'title': {'type': 'string'},
            },
            'required': ['project'],
        },
    },
    responses={201: LocalFilesImportStorageSerializer},
)
class LocalFilesWorkspaceImportStorageAssignAPI(generics.GenericAPIView):
    """Create a project-scope LocalFilesImportStorage from a workspace template."""

    permission_required = ViewClassPermission(
        POST=all_permissions.workspaces_change,
    )
    serializer_class = LocalFilesImportStorageSerializer

    def get_queryset(self):
        org = getattr(self.request.user, 'active_organization', None)
        if org is None:
            return LocalFilesWorkspaceImportStorage.objects.none()
        return LocalFilesWorkspaceImportStorage.objects.filter(workspace__organization=org)

    def post(self, request, *args, **kwargs):
        template = self.get_object()
        # Reuse the shared workspace resolver to apply org + membership checks.
        workspace = _resolve_workspace_for_user(request, template.workspace_id)
        if not is_workspace_manager(request.user, workspace):
            raise PermissionDenied('Only a workspace manager can assign storage to a project.')

        project_id = request.data.get('project')
        if not project_id:
            raise ValidationError({'project': 'this field is required'})
        project = generics.get_object_or_404(Project, pk=project_id)
        if project.organization_id != workspace.organization_id:
            raise PermissionDenied('Project belongs to a different organization.')
        if project.workspace_id != workspace.id:
            raise ValidationError({'project': 'must live inside the same workspace as the template'})

        subpath = request.data.get('subpath') or ''
        target_path = _resolve_subpath_under(template.path or '', subpath)

        title = request.data.get('title') or template.title or f'From {template.title or "workspace template"}'
        child = LocalFilesImportStorage(
            project=project,
            parent_storage=template,
            path=target_path,
            title=title,
            regex_filter=template.regex_filter,
            use_blob_urls=template.use_blob_urls,
            recursive_scan=template.recursive_scan,
        )
        # Re-run the connection validation for the concrete path so we surface the
        # same ValidationError users see when creating a project-scope storage manually.
        try:
            child.validate_connection()
        except Exception as exc:
            raise ValidationError(str(exc))
        child.save()

        body = LocalFilesImportStorageSerializer(child).data
        return Response(body, status=status.HTTP_201_CREATED)
