"""Seed deterministic test accounts + fixture data for Playwright E2E.

Creates (or updates, if already present) one account per role in a single
"E2E" organization, plus a workspace and two projects so role-scoped
features have something to bind to.

Idempotent — re-running does not duplicate rows, it just re-applies the
password, role, and membership rows.

Usage:
    poetry run python label_studio/manage.py seed_e2e_accounts

Accounts created (all password = ``E2ETestPass!`` by default):

    superadmin@e2e.saillabel.local   OrganizationRole.SUPER_ADMIN + is_superuser
    wsmanager@e2e.saillabel.local    WorkspaceMember.Role.WORKSPACE_MANAGER on "E2E Workspace"
    pmanager@e2e.saillabel.local     ProjectRole.PROJECT_MANAGER on "E2E Project Alpha"
    reviewer@e2e.saillabel.local     ProjectRole.REVIEWER on "E2E Project Alpha"
    annotator@e2e.saillabel.local    ProjectRole.ANNOTATOR on "E2E Project Alpha"
    plainmember@e2e.saillabel.local  OrganizationRole.MEMBER with no role grants

The exact set above matches ``docs/e2e/playwright-e2e-plan.md`` —
Playwright fixtures assume these credentials verbatim.
"""

from __future__ import annotations

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction

from organizations.models import Organization, OrganizationMember
from projects.models import Project, ProjectMember
from users.constants import OrganizationRole, ProjectRole
from users.models import User
from workspaces.models import Workspace, WorkspaceMember

DEFAULT_PASSWORD = 'E2ETestPass!'
ORG_TITLE = 'E2E Organization'
WORKSPACE_TITLE = 'E2E Workspace'
PROJECT_ALPHA = 'E2E Project Alpha'
PROJECT_BETA = 'E2E Project Beta'

ACCOUNTS: list[dict] = [
    {'email': 'superadmin@e2e.saillabel.local', 'name': 'E2E Super Admin',
     'is_superuser': True, 'is_staff': True,
     'org_role': OrganizationRole.SUPER_ADMIN},
    {'email': 'wsmanager@e2e.saillabel.local', 'name': 'E2E Workspace Manager',
     'is_superuser': False, 'is_staff': False,
     'org_role': OrganizationRole.MEMBER,
     'workspace_role': WorkspaceMember.Role.WORKSPACE_MANAGER},
    {'email': 'pmanager@e2e.saillabel.local', 'name': 'E2E Project Manager',
     'is_superuser': False, 'is_staff': False,
     'org_role': OrganizationRole.MEMBER,
     'project_role': ProjectRole.PROJECT_MANAGER},
    {'email': 'reviewer@e2e.saillabel.local', 'name': 'E2E Reviewer',
     'is_superuser': False, 'is_staff': False,
     'org_role': OrganizationRole.MEMBER,
     'project_role': ProjectRole.REVIEWER},
    {'email': 'annotator@e2e.saillabel.local', 'name': 'E2E Annotator',
     'is_superuser': False, 'is_staff': False,
     'org_role': OrganizationRole.MEMBER,
     'project_role': ProjectRole.ANNOTATOR},
    {'email': 'plainmember@e2e.saillabel.local', 'name': 'E2E Plain Member',
     'is_superuser': False, 'is_staff': False,
     'org_role': OrganizationRole.MEMBER},
]


def _upsert_user(spec: dict, password: str) -> User:
    user, _ = User.objects.get_or_create(email=spec['email'], defaults={'username': spec['email']})
    user.username = spec['email']
    first, _, last = spec['name'].partition(' ')
    user.first_name = first or spec['email'].split('@')[0]
    user.last_name = last or ''
    user.is_active = True
    user.is_superuser = spec.get('is_superuser', False)
    user.is_staff = spec.get('is_staff', False)
    user.password = make_password(password)
    user.save()
    return user


class Command(BaseCommand):
    help = 'Create deterministic E2E test accounts + fixture data.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--password', default=DEFAULT_PASSWORD,
            help=f'Password for all seeded accounts (default: {DEFAULT_PASSWORD})',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        password = options['password']

        # Super admin serves as the organization owner for consistency.
        super_spec = next(a for a in ACCOUNTS if a.get('is_superuser'))
        super_user = _upsert_user(super_spec, password)

        organization, _ = Organization.objects.get_or_create(
            title=ORG_TITLE, defaults={'created_by': super_user},
        )
        if organization.created_by_id is None:
            organization.created_by = super_user
            organization.save(update_fields=['created_by'])
        super_user.active_organization = organization
        super_user.save(update_fields=['active_organization'])

        workspace, _ = Workspace.objects.get_or_create(
            organization=organization, title=WORKSPACE_TITLE,
            defaults={'created_by': super_user},
        )
        project_alpha, _ = Project.objects.get_or_create(
            organization=organization, title=PROJECT_ALPHA,
            defaults={'created_by': super_user, 'workspace': workspace},
        )
        if project_alpha.workspace_id is None:
            project_alpha.workspace = workspace
            project_alpha.save(update_fields=['workspace'])
        project_beta, _ = Project.objects.get_or_create(
            organization=organization, title=PROJECT_BETA,
            defaults={'created_by': super_user, 'workspace': workspace},
        )
        if project_beta.workspace_id is None:
            project_beta.workspace = workspace
            project_beta.save(update_fields=['workspace'])

        for spec in ACCOUNTS:
            user = _upsert_user(spec, password) if not spec.get('is_superuser') else super_user
            user.active_organization = organization
            user.save(update_fields=['active_organization'])

            OrganizationMember.objects.update_or_create(
                user=user, organization=organization,
                defaults={'role': spec['org_role'], 'deleted_at': None},
            )

            if spec.get('workspace_role'):
                WorkspaceMember.objects.update_or_create(
                    user=user, workspace=workspace,
                    defaults={'role': spec['workspace_role'], 'deleted_at': None},
                )
            if spec.get('project_role'):
                ProjectMember.objects.update_or_create(
                    user=user, project=project_alpha,
                    defaults={'role': spec['project_role'], 'enabled': True, 'deleted_at': None},
                )

            self.stdout.write(self.style.SUCCESS(
                f"  seeded {spec['email']:<40s} org={spec['org_role']:<12s} "
                f"ws={spec.get('workspace_role','-'):<20s} project={spec.get('project_role','-')}"
            ))

        self.stdout.write(self.style.SUCCESS(
            f'\nE2E seed complete. Password: {password}\n'
            f'Org: {ORG_TITLE!r}  Workspace: {WORKSPACE_TITLE!r}  '
            f'Projects: {PROJECT_ALPHA!r}, {PROJECT_BETA!r}'
        ))
