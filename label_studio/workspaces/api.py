"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

import logging

from audit.models import AuditAction
from audit.services import record_role_change, record_workspace_event
from core.mixins import GetParentObjectMixin
from core.permissions import ViewClassPermission, all_permissions
from django.db import transaction
from django.utils.decorators import method_decorator
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from .models import Workspace, WorkspaceFileUpload, WorkspaceMember
from .rules import is_workspace_manager, is_workspace_member
from .serializers import WorkspaceFileUploadSerializer, WorkspaceMemberSerializer, WorkspaceSerializer

logger = logging.getLogger(__name__)


def _active_org_or_400(user):
    org = getattr(user, 'active_organization', None)
    if org is None:
        raise ValidationError('User has no active organization; cannot access workspaces.')
    return org


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Workspaces'],
        summary='List workspaces',
        description='List workspaces in the user\'s active organization.',
    ),
)
@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Workspaces'],
        summary='Create workspace',
        description='Create a workspace in the user\'s active organization. The creator is '
        'automatically added as a workspace_manager.',
        request=WorkspaceSerializer,
        responses={201: WorkspaceSerializer},
    ),
)
class WorkspaceListAPI(generics.ListCreateAPIView):
    serializer_class = WorkspaceSerializer
    permission_required = ViewClassPermission(
        GET=all_permissions.workspaces_view,
        POST=all_permissions.workspaces_create,
    )

    def get_queryset(self):
        org = _active_org_or_400(self.request.user)
        return Workspace.objects.filter(organization=org).order_by('-created_at')

    @transaction.atomic
    def perform_create(self, serializer):
        org = _active_org_or_400(self.request.user)
        workspace = serializer.save(organization=org, created_by=self.request.user)
        WorkspaceMember.objects.get_or_create(
            user=self.request.user,
            workspace=workspace,
            defaults={'role': WorkspaceMember.Role.WORKSPACE_MANAGER},
        )
        record_workspace_event(
            action=AuditAction.WORKSPACE_CREATED,
            actor=self.request.user,
            workspace=workspace,
        )


@method_decorator(
    name='get',
    decorator=extend_schema(tags=['Workspaces'], summary='Get workspace by ID'),
)
@method_decorator(
    name='patch',
    decorator=extend_schema(tags=['Workspaces'], summary='Update workspace'),
)
@method_decorator(
    name='delete',
    decorator=extend_schema(tags=['Workspaces'], summary='Soft-delete workspace'),
)
class WorkspaceDetailAPI(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = WorkspaceSerializer
    permission_required = ViewClassPermission(
        GET=all_permissions.workspaces_view,
        PATCH=all_permissions.workspaces_change,
        PUT=all_permissions.workspaces_change,
        DELETE=all_permissions.workspaces_delete,
    )
    queryset = Workspace.objects.all()

    def get_queryset(self):
        org = _active_org_or_400(self.request.user)
        return Workspace.objects.filter(organization=org)

    def _require_manager(self, workspace):
        if not is_workspace_manager(self.request.user, workspace):
            raise PermissionDenied('Workspace manager role is required.')

    def perform_update(self, serializer):
        self._require_manager(self.get_object())
        workspace = serializer.save()
        record_workspace_event(
            action=AuditAction.WORKSPACE_UPDATED,
            actor=self.request.user,
            workspace=workspace,
            metadata={'fields': sorted((self.request.data or {}).keys())},
        )

    def perform_destroy(self, instance):
        self._require_manager(instance)
        record_workspace_event(
            action=AuditAction.WORKSPACE_DELETED,
            actor=self.request.user,
            workspace=instance,
        )
        instance.soft_delete(user=self.request.user)


class _WorkspaceScopedMixin(GetParentObjectMixin):
    parent_queryset = Workspace.objects.all()
    parent_lookup_url_kwarg = 'pk'

    def _get_workspace(self) -> Workspace:
        org = _active_org_or_400(self.request.user)
        workspace = self.parent_object
        if workspace.organization_id != org.id:
            # Prevent cross-org enumeration via direct ID guess.
            raise PermissionDenied('Workspace does not belong to the active organization.')
        if not is_workspace_member(self.request.user, workspace):
            raise PermissionDenied('Workspace membership is required.')
        return workspace


@method_decorator(
    name='get',
    decorator=extend_schema(tags=['Workspaces'], summary='List workspace members'),
)
@method_decorator(
    name='post',
    decorator=extend_schema(tags=['Workspaces'], summary='Invite workspace member'),
)
class WorkspaceMembersAPI(_WorkspaceScopedMixin, generics.ListCreateAPIView):
    serializer_class = WorkspaceMemberSerializer
    permission_required = ViewClassPermission(
        GET=all_permissions.workspaces_view,
        POST=all_permissions.workspaces_invite,
    )

    def get_queryset(self):
        workspace = self._get_workspace()
        return workspace.members.filter(deleted_at__isnull=True).order_by('id')

    def perform_create(self, serializer):
        workspace = self._get_workspace()
        if not is_workspace_manager(self.request.user, workspace):
            raise PermissionDenied('Only a workspace manager can invite members.')
        member = serializer.save(workspace=workspace)
        record_role_change(
            action=AuditAction.ROLE_GRANTED,
            actor=self.request.user,
            subject=member,
            scope='workspace',
            scope_id=workspace.id,
            role=getattr(member, 'role', None),
            organization=workspace.organization,
        )


@method_decorator(
    name='get',
    decorator=extend_schema(tags=['Workspaces'], summary='Get workspace member'),
)
@method_decorator(
    name='patch',
    decorator=extend_schema(tags=['Workspaces'], summary='Update workspace member'),
)
@method_decorator(
    name='delete',
    decorator=extend_schema(tags=['Workspaces'], summary='Remove workspace member'),
)
class WorkspaceMemberDetailAPI(_WorkspaceScopedMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = WorkspaceMemberSerializer
    permission_required = ViewClassPermission(
        GET=all_permissions.workspaces_view,
        PATCH=all_permissions.workspaces_change,
        PUT=all_permissions.workspaces_change,
        DELETE=all_permissions.workspaces_change,
    )
    lookup_url_kwarg = 'member_pk'

    def get_queryset(self):
        workspace = self._get_workspace()
        return workspace.members.all()

    def perform_update(self, serializer):
        workspace = self._get_workspace()
        if not is_workspace_manager(self.request.user, workspace):
            raise PermissionDenied('Only a workspace manager can update membership.')
        previous_role = getattr(serializer.instance, 'role', None)
        member = serializer.save()
        new_role = getattr(member, 'role', None)
        if previous_role != new_role:
            record_role_change(
                action=AuditAction.ROLE_CHANGED,
                actor=self.request.user,
                subject=member,
                scope='workspace',
                scope_id=workspace.id,
                role=new_role,
                previous_role=previous_role,
                organization=workspace.organization,
            )

    def perform_destroy(self, instance):
        workspace = self._get_workspace()
        if not is_workspace_manager(self.request.user, workspace):
            raise PermissionDenied('Only a workspace manager can remove members.')
        record_role_change(
            action=AuditAction.ROLE_REVOKED,
            actor=self.request.user,
            subject=instance,
            scope='workspace',
            scope_id=workspace.id,
            role=getattr(instance, 'role', None),
            organization=workspace.organization,
        )
        # Soft delete to preserve audit trail.
        from django.utils import timezone
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['deleted_at', 'updated_at'])


@method_decorator(
    name='get',
    decorator=extend_schema(tags=['Workspaces'], summary='List projects in workspace'),
)
class WorkspaceProjectsAPI(_WorkspaceScopedMixin, generics.ListAPIView):
    permission_required = ViewClassPermission(GET=all_permissions.projects_view)

    def get_serializer_class(self):
        # Import lazily to avoid circular import at module load time.
        from projects.serializers import ProjectSerializer
        return ProjectSerializer

    def get_queryset(self):
        from projects.models import Project

        workspace = self._get_workspace()
        return Project.objects.filter(workspace=workspace).order_by('-created_at')

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['created_by'] = self.request.user
        return ctx


@method_decorator(
    name='get',
    decorator=extend_schema(tags=['Workspaces'], summary='List workspace file uploads'),
)
class WorkspaceFileUploadsAPI(_WorkspaceScopedMixin, generics.ListAPIView):
    serializer_class = WorkspaceFileUploadSerializer
    permission_required = ViewClassPermission(GET=all_permissions.workspaces_view)

    def get_queryset(self):
        workspace = self._get_workspace()
        query = self.request.query_params.get('ids')
        qs = workspace.file_uploads.all().order_by('-created_at')
        if query:
            import json as _json
            try:
                ids = _json.loads(query)
            except Exception:
                raise ValidationError('ids must be a JSON-encoded integer array')
            if not isinstance(ids, list):
                raise ValidationError('ids must be a JSON-encoded integer array')
            qs = qs.filter(id__in=ids)
        return qs


@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Workspaces'],
        summary='Import files into a workspace',
        description='Store one or more files (multipart) or a single `url` (application/x-www-form-urlencoded) '
        'as workspace-scoped file uploads. Files become the workspace default import pool.',
    ),
)
class WorkspaceImportAPI(_WorkspaceScopedMixin, generics.GenericAPIView):
    serializer_class = WorkspaceFileUploadSerializer
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    permission_required = ViewClassPermission(POST=all_permissions.workspaces_change)

    def post(self, request, *args, **kwargs):
        workspace = self._get_workspace()
        if not is_workspace_manager(request.user, workspace):
            raise PermissionDenied('Only a workspace manager can import files.')

        uploaded = []
        # Case 1 — URL form payload
        url = request.data.get('url') if hasattr(request.data, 'get') else None
        if url:
            filename = url.rstrip('/').split('/')[-1] or 'url-upload'
            obj = WorkspaceFileUpload.objects.create(
                workspace=workspace,
                user=request.user,
                file=_remote_url_placeholder(filename, url),
            )
            uploaded.append(obj)
        else:
            # Case 2 — multipart files
            files = [f for _, f in request.FILES.items()]
            if not files:
                raise ValidationError('Provide at least one file (multipart) or a `url` field.')
            for fileobj in files:
                obj = WorkspaceFileUpload.objects.create(
                    workspace=workspace,
                    user=request.user,
                    file=fileobj,
                )
                uploaded.append(obj)

        data = WorkspaceFileUploadSerializer(uploaded, many=True).data
        return Response(
            {
                'file_upload_ids': [item['id'] for item in data],
                'files': data,
            },
            status=status.HTTP_201_CREATED,
        )


@method_decorator(
    name='delete',
    decorator=extend_schema(tags=['Workspaces'], summary='Delete workspace file upload'),
)
class WorkspaceFileUploadDetailAPI(_WorkspaceScopedMixin, generics.DestroyAPIView):
    serializer_class = WorkspaceFileUploadSerializer
    permission_required = ViewClassPermission(DELETE=all_permissions.workspaces_change)
    lookup_url_kwarg = 'upload_pk'

    def get_queryset(self):
        workspace = self._get_workspace()
        return workspace.file_uploads.all()

    def perform_destroy(self, instance):
        workspace = self._get_workspace()
        if not is_workspace_manager(self.request.user, workspace):
            raise PermissionDenied('Only a workspace manager can delete files.')
        instance.file.delete(save=False)
        instance.delete()


def _remote_url_placeholder(filename, url):
    """Store a tiny placeholder file that records the referenced URL.

    The Phase 3 storage pipeline will replace this with a real fetch pipeline; for now
    we persist just enough information (the URL) so the UI can reflect the uploaded row.
    """
    from django.core.files.base import ContentFile
    placeholder = ContentFile(url.encode('utf-8'))
    placeholder.name = filename
    return placeholder
