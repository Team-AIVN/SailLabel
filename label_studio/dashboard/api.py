"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

import logging

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import build_dashboard_summary

logger = logging.getLogger(__name__)


@extend_schema(
    tags=['Dashboard'],
    summary='Role-branched dashboard summary',
    description=(
        'Return the set of widget payloads the caller is entitled to see. The '
        'response always carries a top-level `roles` array — the frontend picks '
        'which cards to render from there. Each of super_admin, '
        'workspace_manager, project_manager, annotator, reviewer is populated '
        'independently based on the caller\'s memberships.'
    ),
)
class DashboardSummaryAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization = getattr(request.user, 'active_organization', None)
        payload = build_dashboard_summary(request.user, organization)
        return Response(payload)
