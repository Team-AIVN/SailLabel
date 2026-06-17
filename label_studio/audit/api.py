"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from django.utils.decorators import method_decorator
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination

from users.rules import is_super_admin

from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 500


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Audit'],
        summary='List audit log entries',
        description=(
            'Super-admin-only view of the immutable audit log scoped to the active '
            'organization. Supports filtering by `action` and `actor` query parameters.'
        ),
    ),
)
class AuditLogListAPI(generics.ListAPIView):
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = AuditLogPagination

    def get_queryset(self):
        user = self.request.user
        organization = getattr(user, 'active_organization', None)
        if organization is None or not is_super_admin.test(user):
            raise PermissionDenied('Audit log is restricted to organization super admins.')

        qs = AuditLog.objects.filter(organization=organization).order_by('-created_at')
        action = self.request.query_params.get('action')
        if action:
            qs = qs.filter(action=action)
        actor = self.request.query_params.get('actor')
        if actor:
            qs = qs.filter(actor_id=actor)
        return qs
