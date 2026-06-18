"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

import logging
import mimetypes

from audit.models import AuditAction
from audit.services import record_role_change, record_workspace_event
from core.decorators import override_report_only_csp
from core.mixins import GetParentObjectMixin
from core.permissions import ViewClassPermission, all_permissions
from csp.decorators import csp
from django.conf import settings
from django.db import transaction
from django.utils.decorators import method_decorator
from drf_spectacular.utils import extend_schema
from ranged_fileresponse import RangedFileResponse
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Workspace, WorkspaceFileUpload, WorkspaceMember
from .rules import is_workspace_manager, is_workspace_member
from .serializers import (
    WorkspaceDatasetSerializer,
    WorkspaceFileUploadSerializer,
    WorkspaceMemberSerializer,
    WorkspaceProjectCardSerializer,
    WorkspaceSerializer,
    WorkspaceSummarySerializer,
)

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
        qs = workspace.members.filter(deleted_at__isnull=True).select_related('user').order_by('id')
        search = self.request.query_params.get('search')
        if search:
            from django.db.models import Q

            qs = qs.filter(
                Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
                | Q(user__email__icontains=search)
            )
        return qs

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
class WorkspaceProjectsAPI(_WorkspaceScopedMixin, generics.ListCreateAPIView):
    serializer_class = WorkspaceProjectCardSerializer
    permission_required = ViewClassPermission(
        GET=all_permissions.projects_view,
        POST=all_permissions.projects_create,
    )

    # whitelist of DB-orderable fields for ?ordering=
    ORDERING_FIELDS = {
        'due_date': 'due_date',
        '-due_date': '-due_date',
        'created_at': 'created_at',
        '-created_at': '-created_at',
        'title': 'title',
        '-title': '-title',
        # progress is approximated by the count of review-finished tasks
        'progress': 'finished_task_number',
        '-progress': '-finished_task_number',
    }

    def get_queryset(self):
        from projects.models import Project

        workspace = self._get_workspace()
        # with_counts() is a manager method (adds task_number / finished_task_number
        # annotations); call it before filtering.
        qs = Project.objects.with_counts().filter(workspace=workspace, deleted_at__isnull=True)

        params = self.request.query_params
        search = params.get('search')
        if search:
            qs = qs.filter(title__icontains=search)

        label_type = params.get('label_type')
        if label_type:
            # parsed_label_config is a JSON map keyed by control name → {type, ...}
            qs = qs.filter(parsed_label_config__icontains=f'"type": "{label_type}"')

        tag = params.get('tag')
        if tag:
            qs = qs.filter(tags__icontains=tag)

        ordering = self.ORDERING_FIELDS.get(params.get('ordering'), '-created_at')
        return qs.order_by(ordering)

    def perform_create(self, serializer):
        workspace = self._get_workspace()
        if not is_workspace_manager(self.request.user, workspace):
            raise PermissionDenied('Only a workspace manager can create projects.')
        serializer.save(
            workspace=workspace,
            organization=self.request.user.active_organization,
            created_by=self.request.user,
        )


@method_decorator(
    name='get',
    decorator=extend_schema(tags=['Workspaces'], summary='Workspace summary', description='Resource totals.'),
)
class WorkspaceSummaryAPI(_WorkspaceScopedMixin, generics.RetrieveAPIView):
    serializer_class = WorkspaceSummarySerializer
    permission_required = ViewClassPermission(GET=all_permissions.workspaces_view)

    def get_object(self):
        return self._get_workspace()


@method_decorator(
    name='get',
    decorator=extend_schema(tags=['Workspaces'], summary='List workspace file uploads'),
)
def _save_workspace_upload(workspace, user, fileobj):
    """Create a WorkspaceFileUpload, sanitizing SVG content first.

    Mirrors ``data_import.uploader.create_file_upload``: uploaded SVGs are run through
    the allowlist cleaner so malicious markup (scripts, event handlers, external refs)
    can't be served back from the workspace pool.
    """
    instance = WorkspaceFileUpload(workspace=workspace, user=user, file=fileobj)
    if settings.SVG_SECURITY_CLEANUP:
        content_type, _ = mimetypes.guess_type(str(instance.file.name))
        if content_type in ['image/svg+xml']:
            from data_import.uploader import allowlist_svg

            clean_xml = allowlist_svg(instance.file.read().decode())
            instance.file.seek(0)
            instance.file.write(clean_xml.encode())
            instance.file.truncate()
    instance.save()
    # Parse the uploaded dataset into individual DatasetItems for Work Pool curation.
    from .workpools import materialize_dataset_items

    try:
        materialize_dataset_items(instance)
    except Exception:
        logger.exception('Failed to materialize dataset items for upload %s', instance.pk)
    return instance


def _store_workspace_files(workspace, user, request):
    """Persist uploaded files (multipart) or a single `url` into a workspace's pool.

    Shared by the workspace file-uploads POST and the import endpoint. Returns the
    list of created :class:`WorkspaceFileUpload` rows.
    """
    uploaded = []
    url = request.data.get('url') if hasattr(request.data, 'get') else None
    if url:
        filename = url.rstrip('/').split('/')[-1] or 'url-upload'
        uploaded.append(
            WorkspaceFileUpload.objects.create(
                workspace=workspace,
                user=user,
                file=_remote_url_placeholder(filename, url),
            )
        )
    else:
        files = [f for _, f in request.FILES.items()]
        if not files:
            raise ValidationError('Provide at least one file (multipart) or a `url` field.')
        for fileobj in files:
            uploaded.append(_save_workspace_upload(workspace, user, fileobj))
    return uploaded


@method_decorator(
    name='get',
    decorator=extend_schema(tags=['Import', 'Workspaces'], summary='List workspace file uploads'),
)
@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Import', 'Workspaces'],
        summary='Upload files to a workspace',
        description='Workspace-scope analogue of `/api/projects/<id>/file-uploads`: stores '
        'one or more files (multipart) or a single `url` into the workspace import pool.',
    ),
)
class WorkspaceFileUploadsAPI(_WorkspaceScopedMixin, generics.ListCreateAPIView):
    serializer_class = WorkspaceFileUploadSerializer
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    permission_required = ViewClassPermission(
        GET=all_permissions.workspaces_view,
        POST=all_permissions.workspaces_change,
    )

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

    def post(self, request, *args, **kwargs):
        workspace = self._get_workspace()
        if not is_workspace_manager(request.user, workspace):
            raise PermissionDenied('Only a workspace manager can upload files.')
        uploaded = _store_workspace_files(workspace, request.user, request)
        data = WorkspaceFileUploadSerializer(uploaded, many=True).data
        return Response(
            {'file_upload_ids': [item['id'] for item in data], 'files': data},
            status=status.HTTP_201_CREATED,
        )


@method_decorator(
    name='get',
    decorator=extend_schema(tags=['Workspaces'], summary='List workspace datasets'),
)
class WorkspaceDatasetsAPI(_WorkspaceScopedMixin, generics.ListAPIView):
    """Workspace file uploads presented as dataset rows for the dashboard."""

    serializer_class = WorkspaceDatasetSerializer
    permission_required = ViewClassPermission(GET=all_permissions.workspaces_view)

    def get_queryset(self):
        workspace = self._get_workspace()
        qs = workspace.file_uploads.all().order_by('-created_at')
        search = self.request.query_params.get('search')
        if search:
            from django.db.models import Q

            qs = qs.filter(Q(file__icontains=search))
        return qs


@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Import', 'Workspaces'],
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

        uploaded = _store_workspace_files(workspace, request.user, request)
        data = WorkspaceFileUploadSerializer(uploaded, many=True).data
        return Response(
            {
                'file_upload_ids': [item['id'] for item in data],
                'files': data,
            },
            status=status.HTTP_201_CREATED,
        )


@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Import', 'Workspaces'],
        summary='Import predictions into a workspace',
        description='Workspace-scope analogue of `/api/projects/<id>/import/predictions`. '
        'Predictions attach to project tasks, which do not exist at the workspace '
        'level, so import the dataset into a project first and POST predictions there.',
    ),
)
class WorkspaceImportPredictionsAPI(_WorkspaceScopedMixin, generics.GenericAPIView):
    serializer_class = WorkspaceFileUploadSerializer
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    permission_required = ViewClassPermission(POST=all_permissions.workspaces_change)

    def post(self, request, *args, **kwargs):
        workspace = self._get_workspace()
        if not is_workspace_manager(request.user, workspace):
            raise PermissionDenied('Only a workspace manager can import predictions.')
        # Predictions require concrete project tasks; the workspace only holds an
        # un-assigned dataset pool. Direct the caller to the per-project endpoint.
        raise ValidationError(
            'Predictions cannot be imported at the workspace scope. Assign the dataset to a '
            'project first, then POST to /api/projects/<project_id>/import/predictions.'
        )


@method_decorator(
    name='delete',
    decorator=extend_schema(tags=['Import', 'Workspaces'], summary='Delete workspace file upload'),
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


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Workspaces'],
        summary='Workspace workload report',
        description='Per-user annotation workload across every project in the workspace — '
        'the source data for contributor rewards. Counts submitted annotations '
        '(excluding skips), skips, and the number of projects each user contributed to.',
    ),
)
class WorkspaceWorkloadAPI(_WorkspaceScopedMixin, generics.GenericAPIView):
    permission_required = ViewClassPermission(GET=all_permissions.workspaces_view)

    def get(self, request, *args, **kwargs):
        from django.db.models import Count, Q
        from tasks.models import Annotation
        from users.models import User
        from users.serializers import UserSimpleSerializer

        workspace = self._get_workspace()

        rows = (
            Annotation.objects.filter(project__workspace=workspace, completed_by__isnull=False)
            .values('completed_by')
            .annotate(
                annotation_count=Count('id', filter=Q(was_cancelled=False)),
                cancelled_count=Count('id', filter=Q(was_cancelled=True)),
                project_count=Count('project', distinct=True),
            )
            .order_by('-annotation_count')
        )

        users_by_id = {u.id: u for u in User.objects.filter(id__in=[r['completed_by'] for r in rows])}
        results = []
        for row in rows:
            user = users_by_id.get(row['completed_by'])
            results.append(
                {
                    'user': row['completed_by'],
                    'user_detail': UserSimpleSerializer(user).data if user else None,
                    'annotation_count': row['annotation_count'],
                    'cancelled_count': row['cancelled_count'],
                    'project_count': row['project_count'],
                }
            )

        return Response({'workspace': workspace.id, 'results': results})


class WorkspaceUploadedFileResponse(generics.RetrieveAPIView):
    """Serve a workspace upload by its media path.

    Workspace-scope analogue of ``data_import.UploadedFileResponse``: the stored
    ``WorkspaceFileUpload.url`` resolves to ``/data/workspace-upload/<ws>/<file>``,
    so this view backs that path with a permission-checked file response.
    """

    permission_classes = (IsAuthenticated,)

    @override_report_only_csp
    @csp(SANDBOX=[])
    def get(self, *args, **kwargs):
        request = self.request
        # ``filename`` is everything after /data/workspace-upload/, e.g. "2/abcd-img.jpeg".
        file = 'workspace-upload/' + kwargs['filename']
        logger.debug(f'Fetch workspace upload by user {request.user} => {file}')
        file_upload = WorkspaceFileUpload.objects.filter(file=file).last()

        if file_upload is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if not file_upload.has_permission(request.user):
            return Response(status=status.HTTP_403_FORBIDDEN)

        stored = file_upload.file
        if stored.storage.exists(stored.name):
            content_type, _ = mimetypes.guess_type(str(stored.name))
            content_type = content_type or 'application/octet-stream'
            return RangedFileResponse(request, stored.open(mode='rb'), content_type=content_type)

        return Response(status=status.HTTP_404_NOT_FOUND)


def _remote_url_placeholder(filename, url):
    """Store a tiny placeholder file that records the referenced URL.

    The Phase 3 storage pipeline will replace this with a real fetch pipeline; for now
    we persist just enough information (the URL) so the UI can reflect the uploaded row.
    """
    from django.core.files.base import ContentFile
    placeholder = ContentFile(url.encode('utf-8'))
    placeholder.name = filename
    return placeholder
