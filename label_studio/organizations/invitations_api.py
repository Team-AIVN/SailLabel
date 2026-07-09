"""Create per-recipient invitations.

An invitation places the recipient into a workspace, and optionally a project with
a role, as soon as they sign up via the invite link. Permissions:
- Workspace managers / super admins may invite into their workspace with any role
  (including project_manager for a chosen project).
- A project manager may invite into their own project, but only as a worker
  (annotator / reviewer / member) — a PM cannot mint another PM.
"""

from __future__ import annotations

from datetime import timedelta

from core.utils.params import get_env
from django.urls import reverse
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from organizations.models import Invitation
from projects.models import Project
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from users.rules import is_project_manager_of, is_super_admin, is_workspace_manager_of
from workspaces.models import Workspace

WORKSPACE_ROLES = {'workspace_manager', 'member'}
PROJECT_ROLES = {'project_manager', 'annotator', 'reviewer', 'member'}
PROJECT_WORKER_ROLES = {'annotator', 'reviewer', 'member'}


@extend_schema(tags=['Invitations'], summary='Create an invitation link')
class InvitationCreateAPI(generics.CreateAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Invitation.objects.all()

    def post(self, request, *args, **kwargs):
        user = request.user
        org = getattr(user, 'active_organization', None)
        if org is None:
            raise ValidationError('No active organization.')

        # Email is optional — the link places whoever signs up through it; the email
        # is only a record of the intended recipient.
        email = (request.data.get('email') or '').strip().lower()

        project_id = request.data.get('project')
        workspace_id = request.data.get('workspace')
        role = (request.data.get('role') or '').strip()

        project = None
        workspace = None
        if project_id:
            project = Project.objects.filter(pk=project_id, organization=org).first()
            if project is None:
                raise ValidationError({'project': 'Project not found in this organization.'})
            workspace = project.workspace
        elif workspace_id:
            workspace = Workspace.objects.filter(pk=workspace_id, organization=org).first()
            if workspace is None:
                raise ValidationError({'workspace': 'Workspace not found in this organization.'})
        else:
            raise ValidationError('A workspace or project is required.')

        role = self._resolve_role(user, workspace, project, role)

        # Bound the link's lifetime so a leaked invite can't be used forever.
        # Configurable via INVITE_LINK_TTL_DAYS (default 14).
        ttl_days = int(get_env('INVITE_LINK_TTL_DAYS', 14))
        expires_at = timezone.now() + timedelta(days=ttl_days) if ttl_days > 0 else None

        invitation = Invitation.objects.create(
            email=email,
            organization=org,
            workspace=workspace,
            project=project,
            role=role,
            created_by=user,
            expires_at=expires_at,
        )
        link = request.build_absolute_uri(reverse('user-signup')) + f'?invite={invitation.token}'
        return Response({'token': invitation.token, 'link': link, 'role': role}, status=status.HTTP_201_CREATED)

    @staticmethod
    def _resolve_role(user, workspace, project, role):
        sa = is_super_admin.test(user)
        wm = workspace is not None and is_workspace_manager_of.test(user, workspace)

        if project is not None:
            # Project-scoped invite: role must be a project role.
            if not (sa or wm or is_project_manager_of.test(user, project)):
                raise PermissionDenied('Only project/workspace managers or super admins can invite to this project.')
            role = role or 'annotator'
            if role not in PROJECT_ROLES:
                raise ValidationError({'role': f'Invalid project role: {role}'})
            # A plain project manager (not WM/SA) may only invite workers.
            if not (sa or wm) and role not in PROJECT_WORKER_ROLES:
                raise PermissionDenied('Project managers can only invite workers, not other managers.')
            return role

        # Workspace-only invite: workspace managers / super admins only.
        if not (sa or wm):
            raise PermissionDenied('Only workspace managers or super admins can invite to a workspace.')
        role = role or 'member'
        if role not in WORKSPACE_ROLES:
            raise ValidationError({'role': f'Invalid workspace role: {role}'})
        return role
