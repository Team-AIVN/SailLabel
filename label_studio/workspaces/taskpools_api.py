"""Task Pool and dataset-item APIs.

Datasets and Task Pools are managed by workspace managers; project creators only
select from existing Task Pools (handled in the project-create flow).
"""

import logging

from core.permissions import ViewClassPermission, all_permissions
from django.db.models import Count
from django.utils.decorators import method_decorator
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from .models import TaskSourceItem, Workspace, TaskPool, TaskPoolItem
from .rules import is_workspace_manager, is_workspace_member
from .serializers import TaskSourceItemSerializer, TaskPoolDetailSerializer, TaskPoolSerializer

logger = logging.getLogger(__name__)


def _get_workspace(request, pk):
    org = getattr(request.user, 'active_organization', None)
    if org is None:
        raise ValidationError('User has no active organization.')
    workspace = generics.get_object_or_404(Workspace, pk=pk)
    if workspace.organization_id != org.id:
        raise PermissionDenied('Workspace does not belong to the active organization.')
    if not is_workspace_member(request.user, workspace):
        raise PermissionDenied('Workspace membership is required.')
    return workspace


def _require_manager(user, workspace):
    if not is_workspace_manager(user, workspace):
        raise PermissionDenied('Only a workspace manager can manage datasets and task pools.')


def _get_pool(workspace, pool_pk):
    return generics.get_object_or_404(TaskPool, pk=pool_pk, workspace=workspace)


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Task Pools'],
        summary='List dataset items',
        description='Dataset items in the workspace for the Task Pool browser. Filter by '
        '`data_type`, `dataset` (id), `search`; pass `task_pool` to flag already-included items.',
    ),
)
class TaskSourceItemsAPI(generics.ListAPIView):
    serializer_class = TaskSourceItemSerializer
    permission_required = ViewClassPermission(GET=all_permissions.workspaces_view)

    def _included_ids(self, workspace):
        pool_id = self.request.query_params.get('task_pool')
        if not pool_id:
            return None
        pool = _get_pool(workspace, pool_id)
        return set(TaskPoolItem.objects.filter(task_pool=pool).values_list('task_source_item_id', flat=True))

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['included_item_ids'] = getattr(self, '_inc', None)
        return ctx

    def get_queryset(self):
        workspace = _get_workspace(self.request, self.kwargs['pk'])
        self._inc = self._included_ids(workspace)
        qs = TaskSourceItem.objects.filter(workspace=workspace)
        params = self.request.query_params
        if params.get('data_type'):
            qs = qs.filter(data_type=params['data_type'])
        if params.get('dataset'):
            qs = qs.filter(dataset_id=params['dataset'])
        if params.get('search'):
            qs = qs.filter(data__icontains=params['search'])
        return qs.order_by('dataset_id', 'index')


@method_decorator(
    name='get',
    decorator=extend_schema(tags=['Task Pools'], summary='List task pools'),
)
@method_decorator(
    name='post',
    decorator=extend_schema(tags=['Task Pools'], summary='Create task pool', request=TaskPoolSerializer),
)
class TaskPoolListCreateAPI(generics.ListCreateAPIView):
    serializer_class = TaskPoolSerializer
    permission_required = ViewClassPermission(
        GET=all_permissions.workspaces_view,
        POST=all_permissions.workspaces_change,
    )

    def get_queryset(self):
        workspace = _get_workspace(self.request, self.kwargs['pk'])
        return (
            TaskPool.objects.filter(workspace=workspace)
            .annotate(item_count_annotated=Count('items'))
            .order_by('-created_at')
        )

    def perform_create(self, serializer):
        workspace = _get_workspace(self.request, self.kwargs['pk'])
        _require_manager(self.request.user, workspace)
        serializer.save(workspace=workspace, created_by=self.request.user)


@method_decorator(
    name='get',
    decorator=extend_schema(tags=['Task Pools'], summary='Get task pool details (with items)'),
)
@method_decorator(
    name='patch',
    decorator=extend_schema(tags=['Task Pools'], summary='Rename / update task pool'),
)
@method_decorator(
    name='delete',
    decorator=extend_schema(tags=['Task Pools'], summary='Delete task pool'),
)
class TaskPoolDetailAPI(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TaskPoolDetailSerializer
    permission_required = ViewClassPermission(
        GET=all_permissions.workspaces_view,
        PATCH=all_permissions.workspaces_change,
        PUT=all_permissions.workspaces_change,
        DELETE=all_permissions.workspaces_change,
    )
    lookup_url_kwarg = 'pool_pk'

    def get_queryset(self):
        workspace = _get_workspace(self.request, self.kwargs['pk'])
        return TaskPool.objects.filter(workspace=workspace)

    def perform_update(self, serializer):
        _require_manager(self.request.user, self.get_object().workspace)
        serializer.save()

    def perform_destroy(self, instance):
        _require_manager(self.request.user, instance.workspace)
        instance.delete()


@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Task Pools'],
        summary='Add dataset items to a task pool',
        description='Body: {"task_source_item_ids": [..]}.',
    ),
)
@method_decorator(
    name='delete',
    decorator=extend_schema(
        tags=['Task Pools'],
        summary='Remove dataset items from a task pool',
        description='Body: {"task_source_item_ids": [..]}.',
    ),
)
class TaskPoolItemsAPI(generics.GenericAPIView):
    serializer_class = TaskPoolDetailSerializer
    parser_classes = (JSONParser, FormParser, MultiPartParser)
    permission_required = ViewClassPermission(
        POST=all_permissions.workspaces_change,
        DELETE=all_permissions.workspaces_change,
    )

    def _resolve(self):
        workspace = _get_workspace(self.request, self.kwargs['pk'])
        _require_manager(self.request.user, workspace)
        pool = _get_pool(workspace, self.kwargs['pool_pk'])
        ids = self.request.data.get('task_source_item_ids')
        if not isinstance(ids, list) or not ids:
            raise ValidationError({'task_source_item_ids': 'a non-empty list of dataset item ids is required'})
        # only items from this workspace are valid
        valid_ids = set(
            TaskSourceItem.objects.filter(workspace=workspace, id__in=ids).values_list('id', flat=True)
        )
        return workspace, pool, valid_ids

    def post(self, request, *args, **kwargs):
        _workspace, pool, valid_ids = self._resolve()
        existing = set(TaskPoolItem.objects.filter(task_pool=pool).values_list('task_source_item_id', flat=True))
        to_add = valid_ids - existing
        TaskPoolItem.objects.bulk_create([TaskPoolItem(task_pool=pool, task_source_item_id=i) for i in to_add])
        return Response(TaskPoolDetailSerializer(pool).data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):
        _workspace, pool, valid_ids = self._resolve()
        TaskPoolItem.objects.filter(task_pool=pool, task_source_item_id__in=valid_ids).delete()
        return Response(TaskPoolDetailSerializer(pool).data, status=status.HTTP_200_OK)
