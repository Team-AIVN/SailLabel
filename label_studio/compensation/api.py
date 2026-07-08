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
from projects.models import Project, ProjectMember
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from users.constants import ProjectRole
from users.rules import is_project_manager_of, is_super_admin
from workspaces.models import Workspace
from workspaces.rules import is_workspace_manager, is_workspace_member
from workspaces.taskpools_api import _get_workspace

from .models import PaymentRecord, ProjectCompensationPolicy
from .serializers import PaymentRecordSerializer, ProjectCompensationPolicySerializer
from .services import compensation_projects, compute_member_compensation, compute_project_compensation

logger = logging.getLogger(__name__)


def _get_project(request, pk):
    project = generics.get_object_or_404(Project, pk=pk)
    org = getattr(request.user, 'active_organization', None)
    if org is None or project.organization_id != org.id:
        raise PermissionDenied('Project does not belong to the active organization.')
    return project


def _require_project_comp_manager(user, project):
    """Compensation rates are a budget policy: only workspace managers or super admins
    may configure them (project managers handle settlement, not pricing)."""
    if project.workspace_id is None:
        raise ValidationError('Compensation policies are only available for workspace projects.')
    if not (is_super_admin.test(user) or is_workspace_manager(user, project.workspace)):
        raise PermissionDenied('Only a workspace manager or super admin can configure compensation.')


def _get_workspace_for_compensation(request, pk):
    """Workspace access for the compensation tab. Workspace members and project managers
    of any project in the workspace may view it (rows are further scoped per project)."""
    org = getattr(request.user, 'active_organization', None)
    workspace = generics.get_object_or_404(Workspace, pk=pk)
    if org is None or workspace.organization_id != org.id:
        raise PermissionDenied('Workspace does not belong to the active organization.')
    if is_workspace_member(request.user, workspace):
        return workspace
    is_pm = ProjectMember.objects.filter(
        project__workspace=workspace,
        user=request.user,
        role=ProjectRole.PROJECT_MANAGER,
        deleted_at__isnull=True,
    ).exists()
    if is_pm:
        return workspace
    raise PermissionDenied('You do not have access to this workspace.')


def _allowed_project_ids(user, workspace):
    """Projects the user may see compensation for: all (workspace manager) or only the
    projects they manage (project manager)."""
    base = Project.objects.filter(workspace=workspace, deleted_at__isnull=True)
    if is_workspace_manager(user, workspace):
        return set(base.values_list('id', flat=True))
    return set(
        ProjectMember.objects.filter(
            project__in=base,
            user=user,
            role=ProjectRole.PROJECT_MANAGER,
            deleted_at__isnull=True,
        ).values_list('project_id', flat=True)
    )


def _require_project_pay_manager(user, project):
    """Only a workspace manager or the project's manager may record/delete its payments."""
    if project is None or not is_project_manager_of.test(user, project):
        raise PermissionDenied('Only a workspace manager or the project manager can manage these payments.')


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
        summary='Workspace compensation dashboard (per project)',
        description='One row per (project, member): qualified counts, earnings, amount paid, '
        'remaining, and status. Scoped to the projects the caller may see; ?project=<id> filters.',
    ),
)
class WorkspaceCompensationAPI(generics.GenericAPIView):
    permission_required = ViewClassPermission(GET=all_permissions.workspaces_view)

    def get(self, request, *args, **kwargs):
        workspace = _get_workspace_for_compensation(request, kwargs['pk'])
        allowed = _allowed_project_ids(request.user, workspace)
        project_id = request.query_params.get('project')
        if project_id:
            project_id = int(project_id)
            if project_id not in allowed:
                raise PermissionDenied('You do not have access to this project.')
        return Response(
            {
                'results': compute_project_compensation(workspace, allowed, project_id=project_id or None),
                'projects': compensation_projects(workspace, allowed),
            }
        )


@method_decorator(
    name='get',
    decorator=extend_schema(
        tags=['Compensation'],
        summary='Member compensation detail',
        description='Per-project earnings breakdown and payment history for one worker (scoped).',
    ),
)
class MemberCompensationAPI(generics.GenericAPIView):
    permission_required = ViewClassPermission(GET=all_permissions.workspaces_view)

    def get(self, request, *args, **kwargs):
        workspace = _get_workspace_for_compensation(request, kwargs['pk'])
        allowed = _allowed_project_ids(request.user, workspace)
        user = generics.get_object_or_404(get_user_model(), pk=kwargs['user_pk'])
        return Response(compute_member_compensation(workspace, user, allowed_project_ids=allowed))


@method_decorator(name='get', decorator=extend_schema(tags=['Compensation'], summary='List payments (scoped)'))
@method_decorator(
    name='post',
    decorator=extend_schema(tags=['Compensation'], summary='Record a project payment', request=PaymentRecordSerializer),
)
class PaymentRecordListCreateAPI(generics.ListCreateAPIView):
    serializer_class = PaymentRecordSerializer
    permission_required = ViewClassPermission(
        GET=all_permissions.workspaces_view,
        POST=all_permissions.workspaces_view,
    )

    def get_queryset(self):
        workspace = _get_workspace_for_compensation(self.request, self.kwargs['pk'])
        allowed = _allowed_project_ids(self.request.user, workspace)
        qs = PaymentRecord.objects.filter(workspace=workspace, project_id__in=allowed)
        params = self.request.query_params
        if params.get('user'):
            qs = qs.filter(user_id=params['user'])
        if params.get('project'):
            qs = qs.filter(project_id=params['project'])
        return qs

    def perform_create(self, serializer):
        workspace = _get_workspace_for_compensation(self.request, self.kwargs['pk'])
        project = serializer.validated_data.get('project')
        if project is None or project.workspace_id != workspace.id:
            raise ValidationError({'project': 'A project in this workspace is required (settlement is per project).'})
        _require_project_pay_manager(self.request.user, project)
        user = serializer.validated_data.get('user')
        if user is None or not is_workspace_member(user, workspace):
            raise ValidationError({'user': 'Payee must be a member of this workspace.'})
        serializer.save(workspace=workspace, created_by=self.request.user)


@method_decorator(name='delete', decorator=extend_schema(tags=['Compensation'], summary='Delete a payment record'))
class PaymentRecordDetailAPI(generics.DestroyAPIView):
    serializer_class = PaymentRecordSerializer
    permission_required = ViewClassPermission(DELETE=all_permissions.workspaces_view)
    lookup_url_kwarg = 'payment_pk'

    def get_queryset(self):
        workspace = _get_workspace_for_compensation(self.request, self.kwargs['pk'])
        allowed = _allowed_project_ids(self.request.user, workspace)
        return PaymentRecord.objects.filter(workspace=workspace, project_id__in=allowed)

    def perform_destroy(self, instance):
        _require_project_pay_manager(self.request.user, instance.project)
        instance.delete()
