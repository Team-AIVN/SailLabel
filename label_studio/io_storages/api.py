"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

import inspect
import logging
import os
import time

from core.api_permissions import WorkspaceManagerBodyPermission, WorkspaceManagerSubresourcePermission
from core.permissions import ViewClassPermission, all_permissions
from core.utils.io import read_yaml
from django.conf import settings
from drf_spectacular.utils import extend_schema
from io_storages.serializers import ExportStorageSerializer, ImportStorageSerializer
from projects.models import Project
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.settings import api_settings
from users.rules import is_super_admin, is_workspace_manager_of
from workspaces.models import Workspace
from workspaces.rules import is_workspace_manager, is_workspace_member

logger = logging.getLogger(__name__)


def _require_project_manager(user, project):
    """Cloud storage connects external data sources, so only WM/SA may manage it
    (project managers are excluded per team decision)."""
    workspace = getattr(project, 'workspace', None)
    if project is not None and (is_super_admin.test(user) or (workspace and is_workspace_manager_of.test(user, workspace))):
        return
    raise PermissionDenied('Only workspace managers or super admins can manage storage.')


class ImportStorageListAPI(generics.ListCreateAPIView):
    permission_required = ViewClassPermission(
        GET=all_permissions.storages_view,
        POST=all_permissions.storages_change,
    )
    permission_classes = api_settings.DEFAULT_PERMISSION_CLASSES + [WorkspaceManagerBodyPermission]
    parser_classes = (JSONParser, FormParser, MultiPartParser)

    serializer_class = ImportStorageSerializer

    def get_queryset(self):
        project_pk = self.request.query_params.get('project')
        if not project_pk:
            raise ValidationError('query parameter "project" is required')

        project = generics.get_object_or_404(Project, pk=project_pk)
        self.check_object_permissions(self.request, project)
        StorageClass = self.serializer_class.Meta.model
        storages = StorageClass.objects.filter(project_id=project.id)

        # check failed jobs and sync their statuses
        StorageClass.ensure_storage_statuses(storages)
        return storages

    def perform_create(self, serializer):
        _require_project_manager(self.request.user, serializer.validated_data.get('project'))
        serializer.save()


class ImportStorageDetailAPI(generics.RetrieveUpdateDestroyAPIView):
    """RUD storage by pk specified in URL"""

    permission_required = ViewClassPermission(
        GET=all_permissions.storages_view,
        PATCH=all_permissions.storages_change,
        PUT=all_permissions.storages_change,
        DELETE=all_permissions.storages_change,
    )
    permission_classes = api_settings.DEFAULT_PERMISSION_CLASSES + [WorkspaceManagerSubresourcePermission]
    parser_classes = (JSONParser, FormParser, MultiPartParser)
    serializer_class = ImportStorageSerializer

    @extend_schema(exclude=True)
    def put(self, request, *args, **kwargs):
        return super(ImportStorageDetailAPI, self).put(request, *args, **kwargs)


class ExportStorageListAPI(generics.ListCreateAPIView):
    permission_required = ViewClassPermission(
        GET=all_permissions.storages_view,
        POST=all_permissions.storages_change,
    )
    permission_classes = api_settings.DEFAULT_PERMISSION_CLASSES + [WorkspaceManagerBodyPermission]
    parser_classes = (JSONParser, FormParser, MultiPartParser)
    serializer_class = ExportStorageSerializer

    def get_queryset(self):
        project_pk = self.request.query_params.get('project')
        if not project_pk:
            raise ValidationError('query parameter "project" is required')

        project = generics.get_object_or_404(Project, pk=project_pk)
        self.check_object_permissions(self.request, project)
        StorageClass = self.serializer_class.Meta.model
        storages = StorageClass.objects.filter(project_id=project.id)

        # check failed jobs and sync their statuses
        StorageClass.ensure_storage_statuses(storages)
        return storages

    def perform_create(self, serializer):
        _require_project_manager(self.request.user, serializer.validated_data.get('project'))
        # double check: not export storages don't validate connection in serializer,
        # just make another explicit check here, note: in this create API we have credentials in request.data
        instance = serializer.Meta.model(**serializer.validated_data)
        try:
            instance.validate_connection()
        except Exception as exc:
            raise ValidationError(exc)

        storage = serializer.save()
        if settings.SYNC_ON_TARGET_STORAGE_CREATION:
            storage.sync()


class ExportStorageDetailAPI(generics.RetrieveUpdateDestroyAPIView):
    """RUD storage by pk specified in URL"""

    permission_required = ViewClassPermission(
        GET=all_permissions.storages_view,
        PATCH=all_permissions.storages_change,
        PUT=all_permissions.storages_change,
        DELETE=all_permissions.storages_change,
    )
    permission_classes = api_settings.DEFAULT_PERMISSION_CLASSES + [WorkspaceManagerSubresourcePermission]
    parser_classes = (JSONParser, FormParser, MultiPartParser)
    serializer_class = ExportStorageSerializer

    @extend_schema(exclude=True)
    def put(self, request, *args, **kwargs):
        return super(ExportStorageDetailAPI, self).put(request, *args, **kwargs)


class ImportStorageSyncAPI(generics.GenericAPIView):
    permission_required = ViewClassPermission(
        POST=all_permissions.storages_sync,
    )
    permission_classes = api_settings.DEFAULT_PERMISSION_CLASSES + [WorkspaceManagerSubresourcePermission]
    parser_classes = (JSONParser, FormParser, MultiPartParser)
    serializer_class = ImportStorageSerializer

    def get_queryset(self):
        ImportStorageClass = self.serializer_class.Meta.model
        return ImportStorageClass.objects.all()

    def post(self, request, *args, **kwargs):
        storage = self.get_object()
        # check connectivity & access, raise an exception if not satisfied
        if not storage.synchronizable:
            response_data = {'message': f'Storage {str(storage.id)} is not synchronizable'}
            return Response(status=status.HTTP_400_BAD_REQUEST, data=response_data)
        storage.validate_connection()
        storage.sync()
        storage.refresh_from_db()
        return Response(self.serializer_class(storage).data)


class ExportStorageSyncAPI(generics.GenericAPIView):
    permission_required = ViewClassPermission(
        POST=all_permissions.storages_sync,
    )
    permission_classes = api_settings.DEFAULT_PERMISSION_CLASSES + [WorkspaceManagerSubresourcePermission]
    parser_classes = (JSONParser, FormParser, MultiPartParser)
    serializer_class = ExportStorageSerializer

    def get_queryset(self):
        ExportStorageClass = self.serializer_class.Meta.model
        return ExportStorageClass.objects.all()

    def post(self, request, *args, **kwargs):
        storage = self.get_object()
        # check connectivity & access, raise an exception if not satisfied
        if not storage.synchronizable:
            response_data = {'message': f'Storage {str(storage.id)} is not synchronizable'}
            return Response(status=status.HTTP_400_BAD_REQUEST, data=response_data)
        storage.validate_connection()
        storage.sync()
        storage.refresh_from_db()
        return Response(self.serializer_class(storage).data)


class StorageValidateAPI(generics.CreateAPIView):
    permission_required = all_permissions.storages_change
    parser_classes = (JSONParser, FormParser, MultiPartParser)

    def create(self, request, *args, **kwargs):
        from .functions import validate_storage_instance

        validate_storage_instance(request, self.serializer_class)
        return Response()


@extend_schema(exclude=True)
class ImportStorageListFilesAPI(generics.CreateAPIView):
    permission_required = all_permissions.storages_change
    parser_classes = (JSONParser, FormParser, MultiPartParser)
    serializer_class = None  # Default serializer

    def __init__(self, serializer_class=None, *args, **kwargs):
        self.serializer_class = serializer_class
        super().__init__(*args, **kwargs)

    @extend_schema(exclude=True)
    def create(self, request, *args, **kwargs):
        from .functions import validate_storage_instance

        instance = validate_storage_instance(request, self.serializer_class)
        limit = int(request.data.get('limit', settings.DEFAULT_STORAGE_LIST_LIMIT))

        try:
            files = []
            start_time = time.time()
            timeout_seconds = 30

            for object in instance.iter_objects():
                files.append(instance.get_unified_metadata(object))

                # Check if we've reached the file limit
                if len(files) >= limit:
                    files.append({'key': None, 'last_modified': None, 'size': None})
                    break

                # Check if we've exceeded the timeout
                if time.time() - start_time > timeout_seconds:
                    files.append({'key': '... storage scan timeout reached ...', 'last_modified': None, 'size': None})
                    break

            return Response({'files': files})
        except Exception as exc:
            logger.exception('Error listing storage files: %s', exc)
            raise ValidationError('Failed to list storage files')


@extend_schema(exclude=True)
class StorageFormLayoutAPI(generics.RetrieveAPIView):
    permission_required = all_permissions.storages_change
    parser_classes = (JSONParser, FormParser, MultiPartParser)
    storage_type = None

    @extend_schema(exclude=True)
    def get(self, request, *args, **kwargs):
        form_layout_file = os.path.join(os.path.dirname(inspect.getfile(self.__class__)), 'form_layout.yml')
        if not os.path.exists(form_layout_file):
            raise NotFound(f'"form_layout.yml" is not found for {self.__class__.__name__}')

        form_layout = read_yaml(form_layout_file)
        form_layout = self.post_process_form(form_layout)
        return Response(form_layout[self.storage_type])

    def post_process_form(self, form_layout):
        return form_layout


def _resolve_workspace_for_user(request, workspace_pk):
    """Fetch a workspace within the user's active org, enforcing membership.

    Mirrors the gating performed by `workspaces.api._WorkspaceScopedMixin` so
    storage endpoints inherit the same cross-org protections (rather than
    falling back to the LSE-only object permission check).
    """
    org = getattr(request.user, 'active_organization', None)
    if org is None:
        raise ValidationError('User has no active organization; cannot access workspace storages.')
    workspace = generics.get_object_or_404(Workspace, pk=workspace_pk)
    if workspace.organization_id != org.id:
        raise PermissionDenied('Workspace does not belong to the active organization.')
    if not is_workspace_member(request.user, workspace):
        raise PermissionDenied('Workspace membership is required.')
    return workspace


class WorkspaceImportStorageListAPI(generics.ListCreateAPIView):
    """List/create workspace-scope import storages.

    Filters by `workspace` query param (mirrors the `project` filter used by
    project-scope storage APIs). Mutations require workspace manager role.
    """

    permission_required = ViewClassPermission(
        GET=all_permissions.workspaces_view,
        POST=all_permissions.workspaces_change,
    )
    parser_classes = (JSONParser, FormParser, MultiPartParser)
    serializer_class = ImportStorageSerializer

    def get_queryset(self):
        workspace_pk = self.request.query_params.get('workspace')
        if not workspace_pk:
            raise ValidationError('query parameter "workspace" is required')
        workspace = _resolve_workspace_for_user(self.request, workspace_pk)
        StorageClass = self.serializer_class.Meta.model
        return StorageClass.objects.filter(workspace_id=workspace.id)

    def perform_create(self, serializer):
        workspace_id = self.request.data.get('workspace')
        if not workspace_id:
            raise ValidationError('field "workspace" is required')
        workspace = _resolve_workspace_for_user(self.request, workspace_id)
        if not is_workspace_manager(self.request.user, workspace):
            raise PermissionDenied('Only a workspace manager can create workspace storages.')
        serializer.save(workspace=workspace)


class WorkspaceImportStorageDetailAPI(generics.RetrieveUpdateDestroyAPIView):
    """RUD workspace-scope import storage by pk."""

    permission_required = ViewClassPermission(
        GET=all_permissions.workspaces_view,
        PATCH=all_permissions.workspaces_change,
        PUT=all_permissions.workspaces_change,
        DELETE=all_permissions.workspaces_change,
    )
    parser_classes = (JSONParser, FormParser, MultiPartParser)
    serializer_class = ImportStorageSerializer

    def get_queryset(self):
        StorageClass = self.serializer_class.Meta.model
        org = getattr(self.request.user, 'active_organization', None)
        if org is None:
            return StorageClass.objects.none()
        # Narrow to storages inside active-org workspaces so cross-org ID probes 404.
        return StorageClass.objects.filter(workspace__organization=org)

    def _require_manager(self):
        storage = self.get_object()
        if not is_workspace_manager(self.request.user, storage.workspace):
            raise PermissionDenied('Only a workspace manager can modify workspace storages.')
        return storage

    def perform_update(self, serializer):
        self._require_manager()
        serializer.save()

    def perform_destroy(self, instance):
        if not is_workspace_manager(self.request.user, instance.workspace):
            raise PermissionDenied('Only a workspace manager can delete workspace storages.')
        instance.delete()

    @extend_schema(exclude=True)
    def put(self, request, *args, **kwargs):
        return super(WorkspaceImportStorageDetailAPI, self).put(request, *args, **kwargs)


def _compose_prefix(parent_prefix: str, subprefix: str) -> str:
    """Join an object-store prefix with a caller-supplied sub-prefix safely.

    Shared by cloud backends (S3 / GCS / Azure) that use slash-delimited
    prefixes under a bucket/container. Rejects absolute or escaping segments
    (``/foo``, ``../foo``) and produces a single normalized forward-slash
    prefix with no trailing slash. Empty inputs are handled at both ends.
    """
    parent = (parent_prefix or '').strip('/')
    sub = (subprefix or '').strip('/')
    if not sub:
        return parent
    if '..' in sub.split('/'):
        raise ValidationError({'subpath': 'must resolve to a location inside the workspace storage prefix'})
    joined = f'{parent}/{sub}' if parent else sub
    # Collapse accidental double slashes from callers passing "foo//bar".
    return '/'.join(segment for segment in joined.split('/') if segment)


class WorkspaceStorageAssignMixin(generics.GenericAPIView):
    """Shared POST handler for deriving a project-scope storage from a workspace template.

    Subclasses must set:
    - ``queryset`` / ``serializer_class`` for the workspace-scope model
    - ``child_serializer_class`` — DRF serializer for the project-scope model
    - override ``build_child(template, project, request)`` to construct (but not
      save) a concrete project-scope storage instance, applying backend-specific
      path/prefix composition and field inheritance.
    """

    permission_required = ViewClassPermission(
        POST=all_permissions.workspaces_change,
    )
    parser_classes = (JSONParser, FormParser, MultiPartParser)
    child_serializer_class = None

    def get_queryset(self):
        org = getattr(self.request.user, 'active_organization', None)
        if org is None:
            return self.serializer_class.Meta.model.objects.none()
        return self.serializer_class.Meta.model.objects.filter(workspace__organization=org)

    def build_child(self, template, project, request):  # pragma: no cover - abstract
        raise NotImplementedError

    def post(self, request, *args, **kwargs):
        template = self.get_object()
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

        child = self.build_child(template, project, request)
        try:
            child.validate_connection()
        except Exception as exc:
            raise ValidationError(str(exc))
        child.save()
        body = self.child_serializer_class(child).data
        return Response(body, status=status.HTTP_201_CREATED)


class ImportStorageValidateAPI(StorageValidateAPI):
    serializer_class = ImportStorageSerializer


class ExportStorageValidateAPI(StorageValidateAPI):
    serializer_class = ExportStorageSerializer


class ImportStorageFormLayoutAPI(StorageFormLayoutAPI):
    storage_type = 'ImportStorage'


class ExportStorageFormLayoutAPI(StorageFormLayoutAPI):
    storage_type = 'ExportStorage'
