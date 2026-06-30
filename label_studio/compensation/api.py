"""Compensation APIs.

Project pricing (:class:`ProjectCompensationPolicy`) is configured by workspace
managers. Workspace-wide earnings are derived on read (never stored) and presented as
one row per (member, currency). Payments are recorded manually; no money is moved.
"""

import logging

from core.permissions import ViewClassPermission, all_permissions
from django.contrib.auth import get_user_model
from django.utils.decorators import method_decorator
from drf_spectacular.utils import extend_schema
from projects.models import Project
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from workspaces.rules import is_workspace_manager, is_workspace_member
from workspaces.taskpools_api import _get_workspace, _require_manager

from .models import PaymentRecord, ProjectCompensationPolicy
from .serializers import PaymentRecordSerializer, ProjectCompensationPolicySerializer
from .services import compute_member_compensation, compute_workspace_compensation

logger = logging.getLogger(__name__)


def _get_project(request, pk):
    project = generics.get_object_or_404(Project, pk=pk)
    org = getattr(request.user, 'active_organization', None)
    if org is None or project.organization_id != org.id:
        raise PermissionDenied('Project does not belong to the active organization.')
    return project


def _require_project_comp_manager(user, project):
    """Compensation is a workspace concept; only a workspace manager may configure it."""
    if project.workspace_id is None:
        raise ValidationError('Compensation policies are only available for workspace projects.')
    if not is_workspace_manager(user, project.workspace):
        raise PermissionDenied('Only a workspace manager can configure compensation.')


@method_decorator(name='get', decorator=extend_schema(tags=['Compensation'], summary='Get project compensation policy'))
@method_decorator(
    name='put',
    decorator=extend_schema(
        tags=['Compensation'],
        summary='Set project compensation policy',
        request=ProjectCompensationPolicySerializer,
    ),
)
class ProjectCompensationPolicyAPI(generics.GenericAPIView):
    serializer_class = ProjectCompensationPolicySerializer
    permission_required = ViewClassPermission(
        GET=all_permissions.projects_view,
        PUT=all_permissions.projects_change,
    )

    def get(self, request, *args, **kwargs):
        project = _get_project(request, kwargs['pk'])
        policy = ProjectCompensationPolicy.objects.filter(project=project).first()
        if policy is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(ProjectCompensationPolicySerializer(policy).data)

    def put(self, request, *args, **kwargs):
        project = _get_project(request, kwargs['pk'])
        _require_project_comp_manager(request.user, project)
        policy = ProjectCompensationPolicy.objects.filter(project=project).first()
        serializer = ProjectCompensationPolicySerializer(policy, data=request.data, partial=policy is not None)
        serializer.is_valid(raise_exception=True)
        serializer.save(project=project, created_by=policy.created_by if policy else request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Compensation'],
        summary='Workspace compensation dashboard',
        description='One row per (member, currency): earned, paid, remaining, and payment status.',
    ),
)
class WorkspaceCompensationAPI(generics.GenericAPIView):
    permission_required = ViewClassPermission(GET=all_permissions.workspaces_view)

    def get(self, request, *args, **kwargs):
        workspace = _get_workspace(request, kwargs['pk'])
        return Response({'results': compute_workspace_compensation(workspace)})


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Compensation'],
        summary='Member compensation detail',
        description='Per-project earnings breakdown and payment history for one worker.',
    ),
)
class MemberCompensationAPI(generics.GenericAPIView):
    permission_required = ViewClassPermission(GET=all_permissions.workspaces_view)

    def get(self, request, *args, **kwargs):
        workspace = _get_workspace(request, kwargs['pk'])
        user = generics.get_object_or_404(get_user_model(), pk=kwargs['user_pk'])
        return Response(compute_member_compensation(workspace, user))


@method_decorator(name='get', decorator=extend_schema(tags=['Compensation'], summary='List workspace payments'))
@method_decorator(
    name='post',
    decorator=extend_schema(tags=['Compensation'], summary='Record a payment', request=PaymentRecordSerializer),
)
class PaymentRecordListCreateAPI(generics.ListCreateAPIView):
    serializer_class = PaymentRecordSerializer
    permission_required = ViewClassPermission(
        GET=all_permissions.workspaces_view,
        POST=all_permissions.workspaces_change,
    )

    def get_queryset(self):
        workspace = _get_workspace(self.request, self.kwargs['pk'])
        qs = PaymentRecord.objects.filter(workspace=workspace)
        if self.request.query_params.get('user'):
            qs = qs.filter(user_id=self.request.query_params['user'])
        return qs

    def perform_create(self, serializer):
        workspace = _get_workspace(self.request, self.kwargs['pk'])
        _require_manager(self.request.user, workspace)
        user = serializer.validated_data.get('user')
        if user is None or not is_workspace_member(user, workspace):
            raise ValidationError({'user': 'Payee must be a member of this workspace.'})
        serializer.save(workspace=workspace, created_by=self.request.user)


@method_decorator(name='delete', decorator=extend_schema(tags=['Compensation'], summary='Delete a payment record'))
class PaymentRecordDetailAPI(generics.DestroyAPIView):
    serializer_class = PaymentRecordSerializer
    permission_required = ViewClassPermission(DELETE=all_permissions.workspaces_change)
    lookup_url_kwarg = 'payment_pk'

    def get_queryset(self):
        workspace = _get_workspace(self.request, self.kwargs['pk'])
        return PaymentRecord.objects.filter(workspace=workspace)

    def perform_destroy(self, instance):
        _require_manager(self.request.user, instance.workspace)
        instance.delete()
