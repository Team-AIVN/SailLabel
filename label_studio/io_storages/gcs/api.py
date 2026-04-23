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
    WorkspaceStorageAssignMixin,
    _compose_prefix,
)
from io_storages.gcs.models import GCSExportStorage, GCSImportStorage, GCSWorkspaceImportStorage
from io_storages.gcs.serializers import (
    GCSExportStorageSerializer,
    GCSImportStorageSerializer,
    GCSWorkspaceImportStorageSerializer,
)

from .openapi_schema import (
    _gcs_export_storage_schema,
    _gcs_export_storage_schema_with_id,
    _gcs_import_storage_schema,
    _gcs_import_storage_schema_with_id,
)


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Storage: GCS'],
        summary='Get all import storage',
        description='Get a list of all GCS import storage connections.',
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
            'x-fern-sdk-group-name': ['import_storage', 'gcs'],
            'x-fern-sdk-method-name': 'list',
            'x-fern-audiences': ['public'],
        },
    ),
)
@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Storage: GCS'],
        summary='Create import storage',
        description='Create a new GCS import storage connection.',
        request={
            'application/json': _gcs_import_storage_schema,
        },
        extensions={
            'x-fern-sdk-group-name': ['import_storage', 'gcs'],
            'x-fern-sdk-method-name': 'create',
            'x-fern-audiences': ['public'],
        },
    ),
)
class GCSImportStorageListAPI(ImportStorageListAPI):
    queryset = GCSImportStorage.objects.all()
    serializer_class = GCSImportStorageSerializer


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Storage: GCS'],
        summary='Get import storage',
        description='Get a specific GCS import storage connection.',
        request=None,
        extensions={
            'x-fern-sdk-group-name': ['import_storage', 'gcs'],
            'x-fern-sdk-method-name': 'get',
            'x-fern-audiences': ['public'],
        },
    ),
)
@method_decorator(
    name='patch',
    decorator=extend_schema(
        tags=['Storage: GCS'],
        summary='Update import storage',
        description='Update a specific GCS import storage connection.',
        request={
            'application/json': _gcs_import_storage_schema,
        },
        extensions={
            'x-fern-sdk-group-name': ['import_storage', 'gcs'],
            'x-fern-sdk-method-name': 'update',
            'x-fern-audiences': ['public'],
        },
    ),
)
@method_decorator(
    name='delete',
    decorator=extend_schema(
        tags=['Storage: GCS'],
        summary='Delete import storage',
        description='Delete a specific GCS import storage connection.',
        request=None,
        extensions={
            'x-fern-sdk-group-name': ['import_storage', 'gcs'],
            'x-fern-sdk-method-name': 'delete',
            'x-fern-audiences': ['public'],
        },
    ),
)
class GCSImportStorageDetailAPI(ImportStorageDetailAPI):
    queryset = GCSImportStorage.objects.all()
    serializer_class = GCSImportStorageSerializer


@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Storage: GCS'],
        summary='Sync import storage',
        description='Sync tasks from a GCS import storage connection.',
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
            'x-fern-sdk-group-name': ['import_storage', 'gcs'],
            'x-fern-sdk-method-name': 'sync',
            'x-fern-audiences': ['public'],
        },
    ),
)
class GCSImportStorageSyncAPI(ImportStorageSyncAPI):
    serializer_class = GCSImportStorageSerializer


@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Storage: GCS'],
        summary='Sync export storage',
        description='Sync tasks from an GCS export storage connection.',
        request=None,
        extensions={
            'x-fern-sdk-group-name': ['export_storage', 'gcs'],
            'x-fern-sdk-method-name': 'sync',
            'x-fern-audiences': ['public'],
        },
    ),
)
class GCSExportStorageSyncAPI(ExportStorageSyncAPI):
    serializer_class = GCSExportStorageSerializer


@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Storage: GCS'],
        summary='Validate import storage',
        description='Validate a specific GCS import storage connection.',
        request={
            'application/json': _gcs_import_storage_schema_with_id,
        },
        responses={200: OpenApiResponse(description='Validation successful')},
        extensions={
            'x-fern-sdk-group-name': ['import_storage', 'gcs'],
            'x-fern-sdk-method-name': 'validate',
            'x-fern-audiences': ['public'],
        },
    ),
)
class GCSImportStorageValidateAPI(ImportStorageValidateAPI):
    serializer_class = GCSImportStorageSerializer


@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Storage: GCS'],
        summary='Validate export storage',
        description='Validate a specific GCS export storage connection.',
        request={
            'application/json': _gcs_export_storage_schema_with_id,
        },
        responses={200: OpenApiResponse(description='Validation successful')},
        extensions={
            'x-fern-sdk-group-name': ['export_storage', 'gcs'],
            'x-fern-sdk-method-name': 'validate',
            'x-fern-audiences': ['public'],
        },
    ),
)
class GCSExportStorageValidateAPI(ExportStorageValidateAPI):
    serializer_class = GCSExportStorageSerializer


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Storage: GCS'],
        summary='Get all export storage',
        description='Get a list of all GCS export storage connections.',
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
            'x-fern-sdk-group-name': ['export_storage', 'gcs'],
            'x-fern-sdk-method-name': 'list',
            'x-fern-audiences': ['public'],
        },
    ),
)
@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Storage: GCS'],
        summary='Create export storage',
        description='Create a new GCS export storage connection to store annotations.',
        request={
            'application/json': _gcs_export_storage_schema,
        },
        extensions={
            'x-fern-sdk-group-name': ['export_storage', 'gcs'],
            'x-fern-sdk-method-name': 'create',
            'x-fern-audiences': ['public'],
        },
    ),
)
class GCSExportStorageListAPI(ExportStorageListAPI):
    queryset = GCSExportStorage.objects.all()
    serializer_class = GCSExportStorageSerializer


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Storage: GCS'],
        summary='Get export storage',
        description='Get a specific GCS export storage connection.',
        request=None,
        extensions={
            'x-fern-sdk-group-name': ['export_storage', 'gcs'],
            'x-fern-sdk-method-name': 'get',
            'x-fern-audiences': ['public'],
        },
    ),
)
@method_decorator(
    name='patch',
    decorator=extend_schema(
        tags=['Storage: GCS'],
        summary='Update export storage',
        description='Update a specific GCS export storage connection.',
        request={
            'application/json': _gcs_export_storage_schema,
        },
        extensions={
            'x-fern-sdk-group-name': ['export_storage', 'gcs'],
            'x-fern-sdk-method-name': 'update',
            'x-fern-audiences': ['public'],
        },
    ),
)
@method_decorator(
    name='delete',
    decorator=extend_schema(
        tags=['Storage: GCS'],
        summary='Delete export storage',
        description='Delete a specific GCS export storage connection.',
        request=None,
        extensions={
            'x-fern-sdk-group-name': ['export_storage', 'gcs'],
            'x-fern-sdk-method-name': 'delete',
            'x-fern-audiences': ['public'],
        },
    ),
)
class GCSExportStorageDetailAPI(ExportStorageDetailAPI):
    queryset = GCSExportStorage.objects.all()
    serializer_class = GCSExportStorageSerializer


class GCSImportStorageFormLayoutAPI(ImportStorageFormLayoutAPI):
    pass


class GCSExportStorageFormLayoutAPI(ExportStorageFormLayoutAPI):
    pass


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Storage: GCS'],
        summary='List workspace-scope import storage',
        description='List GCS import storage templates for a workspace.',
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
        tags=['Storage: GCS'],
        summary='Create workspace-scope import storage',
        description='Create a workspace-scope GCS import storage template.',
    ),
)
class GCSWorkspaceImportStorageListAPI(WorkspaceImportStorageListAPI):
    queryset = GCSWorkspaceImportStorage.objects.all()
    serializer_class = GCSWorkspaceImportStorageSerializer


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Storage: GCS'],
        summary='Get workspace-scope import storage',
        description='Get a workspace-scope GCS import storage template.',
        request=None,
    ),
)
@method_decorator(
    name='patch',
    decorator=extend_schema(
        tags=['Storage: GCS'],
        summary='Update workspace-scope import storage',
        description='Update a workspace-scope GCS import storage template.',
    ),
)
@method_decorator(
    name='delete',
    decorator=extend_schema(
        tags=['Storage: GCS'],
        summary='Delete workspace-scope import storage',
        description='Delete a workspace-scope GCS import storage template.',
        request=None,
    ),
)
class GCSWorkspaceImportStorageDetailAPI(WorkspaceImportStorageDetailAPI):
    queryset = GCSWorkspaceImportStorage.objects.all()
    serializer_class = GCSWorkspaceImportStorageSerializer


@extend_schema(
    tags=['Storage: GCS'],
    summary='Assign workspace storage to a project',
    description=(
        'Derive a project-scope GCSImportStorage from a workspace-scope template. '
        'The child storage inherits the bucket + credentials; the prefix can be '
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
    responses={201: GCSImportStorageSerializer},
)
class GCSWorkspaceImportStorageAssignAPI(WorkspaceStorageAssignMixin):
    queryset = GCSWorkspaceImportStorage.objects.all()
    serializer_class = GCSWorkspaceImportStorageSerializer
    child_serializer_class = GCSImportStorageSerializer

    def build_child(self, template, project, request):
        subpath = request.data.get('subpath') or ''
        target_prefix = _compose_prefix(template.prefix or '', subpath)
        title = request.data.get('title') or template.title or f'From {template.title or "workspace template"}'
        return GCSImportStorage(
            project=project,
            parent_storage=template,
            title=title,
            bucket=template.bucket,
            prefix=target_prefix or None,
            regex_filter=template.regex_filter,
            use_blob_urls=template.use_blob_urls,
            google_application_credentials=template.google_application_credentials,
            google_project_id=template.google_project_id,
            presign=template.presign,
            presign_ttl=template.presign_ttl,
            recursive_scan=template.recursive_scan,
        )
