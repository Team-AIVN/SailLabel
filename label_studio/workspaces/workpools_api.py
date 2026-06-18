"""Work Pool and dataset-item APIs.

Datasets and Work Pools are managed by workspace managers; project creators only
select from existing Work Pools (handled in the project-create flow).
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

from .models import DatasetItem, Workspace, WorkPool, WorkPoolItem
from .rules import is_workspace_manager, is_workspace_member
from .serializers import DatasetItemSerializer, WorkPoolDetailSerializer, WorkPoolSerializer

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
        raise PermissionDenied('Only a workspace manager can manage datasets and work pools.')


def _get_pool(workspace, pool_pk):
    return generics.get_object_or_404(WorkPool, pk=pool_pk, workspace=workspace)


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Work Pools'],
        summary='List dataset items',
        description='Dataset items in the workspace for the Work Pool browser. Filter by '
        '`data_type`, `dataset` (id), `search`; pass `work_pool` to flag already-included items.',
    ),
)
class DatasetItemsAPI(generics.ListAPIView):
    serializer_class = DatasetItemSerializer
    permission_required = ViewClassPermission(GET=all_permissions.workspaces_view)

    def _included_ids(self, workspace):
        pool_id = self.request.query_params.get('work_pool')
        if not pool_id:
            return None
        pool = _get_pool(workspace, pool_id)
        return set(WorkPoolItem.objects.filter(work_pool=pool).values_list('dataset_item_id', flat=True))

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['included_item_ids'] = getattr(self, '_inc', None)
        return ctx

    def get_queryset(self):
        workspace = _get_workspace(self.request, self.kwargs['pk'])
        self._inc = self._included_ids(workspace)
        qs = DatasetItem.objects.filter(workspace=workspace)
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
    decorator=extend_schema(tags=['Work Pools'], summary='List work pools'),
)
@method_decorator(
    name='post',
    decorator=extend_schema(tags=['Work Pools'], summary='Create work pool', request=WorkPoolSerializer),
)
class WorkPoolListCreateAPI(generics.ListCreateAPIView):
    serializer_class = WorkPoolSerializer
    permission_required = ViewClassPermission(
        GET=all_permissions.workspaces_view,
        POST=all_permissions.workspaces_change,
    )

    def get_queryset(self):
        workspace = _get_workspace(self.request, self.kwargs['pk'])
        return (
            WorkPool.objects.filter(workspace=workspace)
            .annotate(item_count_annotated=Count('items'))
            .order_by('-created_at')
        )

    def perform_create(self, serializer):
        workspace = _get_workspace(self.request, self.kwargs['pk'])
        _require_manager(self.request.user, workspace)
        serializer.save(workspace=workspace, created_by=self.request.user)


@method_decorator(
    name='get',
    decorator=extend_schema(tags=['Work Pools'], summary='Get work pool details (with items)'),
)
@method_decorator(
    name='patch',
    decorator=extend_schema(tags=['Work Pools'], summary='Rename / update work pool'),
)
@method_decorator(
    name='delete',
    decorator=extend_schema(tags=['Work Pools'], summary='Delete work pool'),
)
class WorkPoolDetailAPI(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = WorkPoolDetailSerializer
    permission_required = ViewClassPermission(
        GET=all_permissions.workspaces_view,
        PATCH=all_permissions.workspaces_change,
        PUT=all_permissions.workspaces_change,
        DELETE=all_permissions.workspaces_change,
    )
    lookup_url_kwarg = 'pool_pk'

    def get_queryset(self):
        workspace = _get_workspace(self.request, self.kwargs['pk'])
        return WorkPool.objects.filter(workspace=workspace)

    def perform_update(self, serializer):
        _require_manager(self.request.user, self.get_object().workspace)
        serializer.save()

    def perform_destroy(self, instance):
        _require_manager(self.request.user, instance.workspace)
        instance.delete()


@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Work Pools'],
        summary='Add dataset items to a work pool',
        description='Body: {"dataset_item_ids": [..]}.',
    ),
)
@method_decorator(
    name='delete',
    decorator=extend_schema(
        tags=['Work Pools'],
        summary='Remove dataset items from a work pool',
        description='Body: {"dataset_item_ids": [..]}.',
    ),
)
class WorkPoolItemsAPI(generics.GenericAPIView):
    serializer_class = WorkPoolDetailSerializer
    parser_classes = (JSONParser, FormParser, MultiPartParser)
    permission_required = ViewClassPermission(
        POST=all_permissions.workspaces_change,
        DELETE=all_permissions.workspaces_change,
    )

    def _resolve(self):
        workspace = _get_workspace(self.request, self.kwargs['pk'])
        _require_manager(self.request.user, workspace)
        pool = _get_pool(workspace, self.kwargs['pool_pk'])
        ids = self.request.data.get('dataset_item_ids')
        if not isinstance(ids, list) or not ids:
            raise ValidationError({'dataset_item_ids': 'a non-empty list of dataset item ids is required'})
        # only items from this workspace are valid
        valid_ids = set(
            DatasetItem.objects.filter(workspace=workspace, id__in=ids).values_list('id', flat=True)
        )
        return workspace, pool, valid_ids

    def post(self, request, *args, **kwargs):
        _workspace, pool, valid_ids = self._resolve()
        existing = set(WorkPoolItem.objects.filter(work_pool=pool).values_list('dataset_item_id', flat=True))
        to_add = valid_ids - existing
        WorkPoolItem.objects.bulk_create([WorkPoolItem(work_pool=pool, dataset_item_id=i) for i in to_add])
        return Response(WorkPoolDetailSerializer(pool).data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):
        _workspace, pool, valid_ids = self._resolve()
        WorkPoolItem.objects.filter(work_pool=pool, dataset_item_id__in=valid_ids).delete()
        return Response(WorkPoolDetailSerializer(pool).data, status=status.HTTP_200_OK)
