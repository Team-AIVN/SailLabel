"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

import logging

from core.mixins import GetParentObjectMixin
from core.permissions import ViewClassPermission, all_permissions
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from drf_spectacular.utils import OpenApiParameter, extend_schema
from projects.models import Project
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.views import APIView

from . import reports
from .jobs import enqueue_settlement_batch
from .models import BatchStatus, ProjectPricing, SettlementBatch
from .rules import is_settlement_manager, is_settlement_viewer
from .serializers import (
    ProjectPricingSerializer,
    SettlementBatchListSerializer,
    SettlementBatchSerializer,
)
from .services import set_project_pricing

logger = logging.getLogger(__name__)


class _ProjectScopedMixin(GetParentObjectMixin):
    """Resolve `<project_pk>` → Project and gate by settlement visibility."""

    parent_queryset = Project.objects.all()
    parent_lookup_url_kwarg = 'project_pk'
    parent_lookup_field = 'pk'

    def _get_project(self) -> Project:
        project = self.parent_object
        if not is_settlement_viewer(self.request.user, project):
            raise PermissionDenied('You do not have access to this project.')
        return project

    def _require_manager(self, project: Project) -> None:
        if not is_settlement_manager(self.request.user, project):
            raise PermissionDenied('Only a project/workspace manager can perform this action.')


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Settlement'],
        summary='Get project pricing',
        description='Return the current per-project unit prices (label + review).',
    ),
)
@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Settlement'],
        summary='Create or update project pricing',
        description='Upsert the per-project pricing row and append a history entry. '
        'Closed settlement batches retain the pricing snapshot they were run with, '
        'so updating pricing here does not retroactively change past payouts.',
        request=ProjectPricingSerializer,
        responses={200: ProjectPricingSerializer, 201: ProjectPricingSerializer},
    ),
)
class ProjectPricingAPI(_ProjectScopedMixin, APIView):
    permission_required = ViewClassPermission(
        GET=all_permissions.settlement_view,
        POST=all_permissions.settlement_set_pricing,
        PATCH=all_permissions.settlement_set_pricing,
    )

    def get(self, request, *args, **kwargs):
        project = self._get_project()
        try:
            pricing = project.pricing
        except ProjectPricing.DoesNotExist:
            return HttpResponse(status=404)
        return _json_response(ProjectPricingSerializer(pricing).data)

    def post(self, request, *args, **kwargs):
        return self._upsert(request)

    def patch(self, request, *args, **kwargs):
        return self._upsert(request)

    def _upsert(self, request):
        project = self._get_project()
        self._require_manager(project)
        serializer = ProjectPricingSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data
        try:
            current = project.pricing
            currency = validated.get('currency', current.currency)
            label_price = validated.get('label_price', current.label_price)
            review_price = validated.get('review_price', current.review_price)
        except ProjectPricing.DoesNotExist:
            # On first-time creation we require the full triplet.
            missing = [
                field for field in ('label_price', 'review_price', 'currency')
                if field not in validated
            ]
            if missing:
                raise ValidationError(
                    {f: 'This field is required on initial pricing creation.' for f in missing}
                )
            currency = validated['currency']
            label_price = validated['label_price']
            review_price = validated['review_price']
        pricing = set_project_pricing(
            project,
            label_price=label_price,
            review_price=review_price,
            currency=currency,
            user=request.user,
        )
        return _json_response(ProjectPricingSerializer(pricing).data)


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Settlement'],
        summary='List settlement batches for a project',
    ),
)
@method_decorator(
    name='post',
    decorator=extend_schema(
        tags=['Settlement'],
        summary='Create (and enqueue) a settlement batch',
        description='Creates a PENDING SettlementBatch for [period_start, period_end) and '
        'enqueues `run_settlement_batch` on the long-timeout queue. Response returns the '
        'batch row immediately; poll the detail endpoint to observe RUNNING → COMPLETED.',
        request=SettlementBatchSerializer,
        responses={201: SettlementBatchListSerializer},
    ),
)
class ProjectSettlementListAPI(_ProjectScopedMixin, generics.ListCreateAPIView):
    permission_required = ViewClassPermission(
        GET=all_permissions.settlement_view,
        POST=all_permissions.settlement_run_batch,
    )

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return SettlementBatchSerializer
        return SettlementBatchListSerializer

    def get_queryset(self):
        project = self._get_project()
        return SettlementBatch.objects.filter(project=project).order_by('-created_at')

    def perform_create(self, serializer):
        project = self._get_project()
        self._require_manager(project)
        batch = serializer.save(
            project=project,
            created_by=self.request.user,
            status=BatchStatus.PENDING,
        )
        enqueue_settlement_batch(batch.id)


@method_decorator(
    name='get',
    decorator=extend_schema(tags=['Settlement'], summary='Get settlement batch detail'),
)
@method_decorator(
    name='delete',
    decorator=extend_schema(tags=['Settlement'], summary='Delete a settlement batch (FAILED only)'),
)
class SettlementBatchDetailAPI(generics.RetrieveDestroyAPIView):
    serializer_class = SettlementBatchSerializer
    permission_required = ViewClassPermission(
        GET=all_permissions.settlement_view,
        DELETE=all_permissions.settlement_delete,
    )
    queryset = SettlementBatch.objects.select_related('project').prefetch_related('items', 'items__user')

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)
        if request.method == 'GET':
            if not is_settlement_viewer(request.user, obj.project):
                raise PermissionDenied('You do not have access to this settlement batch.')
        else:
            if not is_settlement_manager(request.user, obj.project):
                raise PermissionDenied('Only a project/workspace manager can modify this batch.')

    def perform_destroy(self, instance):
        # Closed (COMPLETED) batches are immutable — refuse to delete them to
        # keep the payout audit trail intact. Only clean up aborted runs.
        if instance.status == BatchStatus.COMPLETED:
            raise ValidationError('Cannot delete a COMPLETED settlement batch.')
        instance.delete()


@extend_schema(
    tags=['Settlement'],
    summary='Download settlement report',
    description='Return the batch report as either CSV (default) or PDF. Only COMPLETED '
    'batches can be downloaded — pending/running/failed batches return 409. '
    'The `format` query parameter is reserved by DRF, so this endpoint uses '
    '`report_format` instead.',
    parameters=[
        OpenApiParameter(
            name='report_format',
            description='Report format: csv | pdf (default: csv)',
            required=False,
            type=str,
        ),
    ],
)
class SettlementReportAPI(APIView):
    permission_required = ViewClassPermission(GET=all_permissions.settlement_view)

    def get(self, request, pk=None):
        batch = (
            SettlementBatch.objects
            .select_related('project')
            .prefetch_related('items', 'items__user')
            .filter(pk=pk)
            .first()
        )
        if batch is None:
            return HttpResponse(status=404)
        if not is_settlement_viewer(request.user, batch.project):
            raise PermissionDenied('You do not have access to this settlement batch.')
        if batch.status != BatchStatus.COMPLETED:
            return HttpResponse(
                f'Batch is not COMPLETED (status={batch.status}).', status=409
            )

        # Accept either `report_format` (preferred) or `format` for convenience.
        fmt = (
            request.query_params.get('report_format')
            or request.query_params.get('format')
            or 'csv'
        ).lower()
        if fmt == 'csv':
            body = reports.render_csv(batch)
            resp = HttpResponse(body, content_type='text/csv; charset=utf-8')
            resp['Content-Disposition'] = (
                f'attachment; filename="settlement_batch_{batch.id}.csv"'
            )
            return resp
        if fmt == 'pdf':
            body = reports.render_pdf(batch)
            resp = HttpResponse(body, content_type='application/pdf')
            resp['Content-Disposition'] = (
                f'attachment; filename="settlement_batch_{batch.id}.pdf"'
            )
            return resp
        raise ValidationError({'format': 'Must be one of: csv, pdf.'})


def _json_response(data):
    from rest_framework.response import Response
    return Response(data)
