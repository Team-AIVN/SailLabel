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
from io_storages.s3.models import S3ExportStorage, S3ImportStorage, S3WorkspaceImportStorage
from io_storages.s3.serializers import (
    S3ExportStorageSerializer,
    S3ImportStorageSerializer,
    S3WorkspaceImportStorageSerializer,
)

from .openapi_schema import (
    _s3_export_storage_schema,
    _s3_export_storage_schema_with_id,
    _s3_import_storage_schema,
    _s3_import_storage_schema_with_id,
)


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Storage: S3'],
        summary='List S3 import storage',
        description='Get a list of all S3 import storage connections.',
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
            'x-fern-sdk-group-name': ['import_storage', 's3'],
            'x-fern-sdk-method-name': 'list',
            'x-fern-audiences': ['public'],
        },
    ),
)
@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Storage: S3'],
        summary='Create new S3 storage',
        description='Create new S3 import storage',
        request={
            'application/json': _s3_import_storage_schema,
        },
        extensions={
            'x-fern-sdk-group-name': ['import_storage', 's3'],
            'x-fern-sdk-method-name': 'create',
            'x-fern-audiences': ['public'],
        },
    ),
)
class S3ImportStorageListAPI(ImportStorageListAPI):
    queryset = S3ImportStorage.objects.all()
    serializer_class = S3ImportStorageSerializer


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Storage: S3'],
        summary='Get import storage',
        description='Get a specific S3 import storage connection.',
        request=None,
        extensions={
            'x-fern-sdk-group-name': ['import_storage', 's3'],
            'x-fern-sdk-method-name': 'get',
            'x-fern-audiences': ['public'],
        },
    ),
)
@method_decorator(
    name='patch',
    decorator=extend_schema(
        tags=['Storage: S3'],
        summary='Update import storage',
        description='Update a specific S3 import storage connection.',
        request={
            'application/json': _s3_import_storage_schema,
        },
        extensions={
            'x-fern-sdk-group-name': ['import_storage', 's3'],
            'x-fern-sdk-method-name': 'update',
            'x-fern-audiences': ['public'],
        },
    ),
)
@method_decorator(
    name='delete',
    decorator=extend_schema(
        tags=['Storage: S3'],
        summary='Delete import storage',
        description='Delete a specific S3 import storage connection.',
        request=None,
        extensions={
            'x-fern-sdk-group-name': ['import_storage', 's3'],
            'x-fern-sdk-method-name': 'delete',
            'x-fern-audiences': ['public'],
        },
    ),
)
class S3ImportStorageDetailAPI(ImportStorageDetailAPI):
    queryset = S3ImportStorage.objects.all()
    serializer_class = S3ImportStorageSerializer


@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Storage: S3'],
        summary='Sync import storage',
        description='Sync tasks from an S3 import storage connection.',
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
            'x-fern-sdk-group-name': ['import_storage', 's3'],
            'x-fern-sdk-method-name': 'sync',
            'x-fern-audiences': ['public'],
        },
    ),
)
class S3ImportStorageSyncAPI(ImportStorageSyncAPI):
    serializer_class = S3ImportStorageSerializer


@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Storage: S3'],
        summary='Validate import storage',
        description='Validate a specific S3 import storage connection.',
        request={
            'application/json': _s3_import_storage_schema_with_id,
        },
        responses={200: OpenApiResponse(description='Validation successful')},
        extensions={
            'x-fern-sdk-group-name': ['import_storage', 's3'],
            'x-fern-sdk-method-name': 'validate',
            'x-fern-audiences': ['public'],
        },
    ),
)
class S3ImportStorageValidateAPI(ImportStorageValidateAPI):
    serializer_class = S3ImportStorageSerializer


@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Storage: S3'],
        summary='Validate export storage',
        description='Validate a specific S3 export storage connection.',
        request={
            'application/json': _s3_export_storage_schema_with_id,
        },
        responses={200: OpenApiResponse(description='Validation successful')},
        extensions={
            'x-fern-sdk-group-name': ['export_storage', 's3'],
            'x-fern-sdk-method-name': 'validate',
            'x-fern-audiences': ['public'],
        },
    ),
)
class S3ExportStorageValidateAPI(ExportStorageValidateAPI):
    serializer_class = S3ExportStorageSerializer


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Storage: S3'],
        summary='Get all export storage',
        description='Get a list of all S3 export storage connections.',
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
            'x-fern-sdk-group-name': ['export_storage', 's3'],
            'x-fern-sdk-method-name': 'list',
            'x-fern-audiences': ['public'],
        },
    ),
)
@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Storage: S3'],
        summary='Create export storage',
        description='Create a new S3 export storage connection to store annotations.',
        request={
            'application/json': _s3_export_storage_schema,
        },
        extensions={
            'x-fern-sdk-group-name': ['export_storage', 's3'],
            'x-fern-sdk-method-name': 'create',
            'x-fern-audiences': ['public'],
        },
    ),
)
class S3ExportStorageListAPI(ExportStorageListAPI):
    queryset = S3ExportStorage.objects.all()
    serializer_class = S3ExportStorageSerializer


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Storage: S3'],
        summary='Get export storage',
        description='Get a specific S3 export storage connection.',
        request=None,
        extensions={
            'x-fern-sdk-group-name': ['export_storage', 's3'],
            'x-fern-sdk-method-name': 'get',
            'x-fern-audiences': ['public'],
        },
    ),
)
@method_decorator(
    name='patch',
    decorator=extend_schema(
        tags=['Storage: S3'],
        summary='Update export storage',
        description='Update a specific S3 export storage connection.',
        request={
            'application/json': _s3_export_storage_schema,
        },
        extensions={
            'x-fern-sdk-group-name': ['export_storage', 's3'],
            'x-fern-sdk-method-name': 'update',
            'x-fern-audiences': ['public'],
        },
    ),
)
@method_decorator(
    name='delete',
    decorator=extend_schema(
        tags=['Storage: S3'],
        summary='Delete export storage',
        description='Delete a specific S3 export storage connection.',
        request=None,
        extensions={
            'x-fern-sdk-group-name': ['export_storage', 's3'],
            'x-fern-sdk-method-name': 'delete',
            'x-fern-audiences': ['public'],
        },
    ),
)
class S3ExportStorageDetailAPI(ExportStorageDetailAPI):
    queryset = S3ExportStorage.objects.all()
    serializer_class = S3ExportStorageSerializer


@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Storage: S3'],
        summary='Sync export storage',
        description='Sync tasks from an S3 export storage connection.',
        request=None,
        extensions={
            'x-fern-sdk-group-name': ['export_storage', 's3'],
            'x-fern-sdk-method-name': 'sync',
            'x-fern-audiences': ['public'],
        },
    ),
)
class S3ExportStorageSyncAPI(ExportStorageSyncAPI):
    serializer_class = S3ExportStorageSerializer


class S3ImportStorageFormLayoutAPI(ImportStorageFormLayoutAPI):
    pass


class S3ExportStorageFormLayoutAPI(ExportStorageFormLayoutAPI):
    pass


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Storage: S3'],
        summary='List workspace-scope import storage',
        description='List S3 import storage templates for a workspace.',
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
        tags=['Storage: S3'],
        summary='Create workspace-scope import storage',
        description='Create a workspace-scope S3 import storage template.',
    ),
)
class S3WorkspaceImportStorageListAPI(WorkspaceImportStorageListAPI):
    queryset = S3WorkspaceImportStorage.objects.all()
    serializer_class = S3WorkspaceImportStorageSerializer


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Storage: S3'],
        summary='Get workspace-scope import storage',
        description='Get a workspace-scope S3 import storage template.',
        request=None,
    ),
)
@method_decorator(
    name='patch',
    decorator=extend_schema(
        tags=['Storage: S3'],
        summary='Update workspace-scope import storage',
        description='Update a workspace-scope S3 import storage template.',
    ),
)
@method_decorator(
    name='delete',
    decorator=extend_schema(
        tags=['Storage: S3'],
        summary='Delete workspace-scope import storage',
        description='Delete a workspace-scope S3 import storage template.',
        request=None,
    ),
)
class S3WorkspaceImportStorageDetailAPI(WorkspaceImportStorageDetailAPI):
    queryset = S3WorkspaceImportStorage.objects.all()
    serializer_class = S3WorkspaceImportStorageSerializer


@extend_schema(
    tags=['Storage: S3'],
    summary='Assign workspace storage to a project',
    description=(
        'Derive a project-scope S3ImportStorage from a workspace-scope template. '
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
    responses={201: S3ImportStorageSerializer},
)
class S3WorkspaceImportStorageAssignAPI(WorkspaceStorageAssignMixin):
    queryset = S3WorkspaceImportStorage.objects.all()
    serializer_class = S3WorkspaceImportStorageSerializer
    child_serializer_class = S3ImportStorageSerializer

    def build_child(self, template, project, request):
        subpath = request.data.get('subpath') or ''
        target_prefix = _compose_prefix(template.prefix or '', subpath)
        title = request.data.get('title') or template.title or 'From workspace template'
        return S3ImportStorage(
            project=project,
            parent_storage=template,
            title=title,
            bucket=template.bucket,
            prefix=target_prefix or None,
            regex_filter=template.regex_filter,
            use_blob_urls=template.use_blob_urls,
            aws_access_key_id=template.aws_access_key_id,
            aws_secret_access_key=template.aws_secret_access_key,
            aws_session_token=template.aws_session_token,
            aws_sse_kms_key_id=template.aws_sse_kms_key_id,
            region_name=template.region_name,
            s3_endpoint=template.s3_endpoint,
            presign=template.presign,
            presign_ttl=template.presign_ttl,
            recursive_scan=template.recursive_scan,
        )
