"""Phase 7 — role × payload matrix.

`test_api.py` covers per-role happy paths; this file locks down the *shape* of
the response for every role combination. Two things matter for consumers:

1. **Exact key set per branch.** Frontend widgets bind to specific keys — a
   rename or accidental drop breaks the UI silently. Each assertion checks
   the full key set (not just subsets) so over- or under-populated payloads
   fail loudly.
2. **Cross-role isolation.** A user holding role A must NOT receive branch B's
   keys in their summary. The dashboard is built from an effective-roles
   union, so a regression in `_effective_roles` would let keys leak.

The test matrix iterates the five roles (super_admin, workspace_manager,
project_manager, annotator, reviewer) and asserts both presence and absence
properties.
"""

import pytest  # type: ignore[import]
from organizations.models import OrganizationMember
from organizations.tests.factories import OrganizationFactory
from projects.models import ProjectMember
from projects.tests.factories import ProjectFactory
from rest_framework.test import APITestCase
from users.constants import OrganizationRole, ProjectRole
from users.tests.factories import UserFactory
from workspaces.models import WorkspaceMember
from workspaces.tests.factories import WorkspaceFactory

pytestmark = pytest.mark.django_db


# Canonical payload contracts. Each role's branch must expose exactly these
# keys — widgets can rely on them.
EXPECTED_KEYS = {
    'super_admin': {
        'organization_count',
        'workspace_count',
        'user_count',
        'project_count',
        'completion',
    },
    'workspace_manager': {'workspaces'},
    'project_manager': {'projects'},
    'annotator': {
        'today_assigned',
        'rejected_open',
        'rejected_tasks',
        'deadlines',
    },
    'reviewer': {'pending_review', 'recent_decisions'},
}
ALL_BRANCH_KEYS = set(EXPECTED_KEYS.keys())


def _join_org(user, org, role=None):
    """Attach `user` to `org` and set active_organization.

    When `role` is None, we preserve any existing role assignment — this lets
    test helpers stack role grants without the membership-level default
    (MEMBER) accidentally demoting a super admin grant that ran earlier.
    """
    user.active_organization = org
    user.save(update_fields=['active_organization'])
    if role is None:
        OrganizationMember.objects.get_or_create(
            user=user, organization=org, defaults={'role': OrganizationRole.MEMBER}
        )
    else:
        OrganizationMember.objects.update_or_create(
            user=user, organization=org, defaults={'role': role}
        )


class DashboardRolePayloadMatrixTests(APITestCase):
    """5 roles × exact key sets × cross-role isolation."""

    url = '/api/dashboard/summary/'

    def setUp(self):
        self.organization = OrganizationFactory()
        self.owner = self.organization.created_by
        self.owner.active_organization = self.organization
        self.owner.save(update_fields=['active_organization'])

    # -- Role grant helpers -------------------------------------------------

    def _grant_super_admin(self, user):
        _join_org(user, self.organization, role=OrganizationRole.SUPER_ADMIN)

    def _grant_workspace_manager(self, user):
        _join_org(user, self.organization)
        workspace = WorkspaceFactory(organization=self.organization, title='WS-mgr')
        WorkspaceMember.objects.create(
            user=user, workspace=workspace, role=WorkspaceMember.Role.WORKSPACE_MANAGER,
        )
        return workspace

    def _grant_project_manager(self, user):
        _join_org(user, self.organization)
        project = ProjectFactory(organization=self.organization, created_by=user)
        ProjectMember.objects.create(
            user=user, project=project, role=ProjectRole.PROJECT_MANAGER, enabled=True,
        )
        return project

    def _grant_annotator(self, user):
        _join_org(user, self.organization)
        project = ProjectFactory(organization=self.organization, created_by=self.owner)
        ProjectMember.objects.create(
            user=user, project=project, role=ProjectRole.ANNOTATOR, enabled=True,
        )
        return project

    def _grant_reviewer(self, user):
        _join_org(user, self.organization)
        project = ProjectFactory(organization=self.organization, created_by=self.owner)
        ProjectMember.objects.create(
            user=user, project=project, role=ProjectRole.REVIEWER, enabled=True,
        )
        return project

    # -- Matrix: single-role users ------------------------------------------

    def test_super_admin_exact_key_set(self):
        user = UserFactory()
        self._grant_super_admin(user)
        self.client.force_authenticate(user=user)

        body = self.client.get(self.url).json()
        assert OrganizationRole.SUPER_ADMIN in body['roles']
        assert set(body['summary'].keys()) == {'super_admin'}
        assert set(body['summary']['super_admin'].keys()) == EXPECTED_KEYS['super_admin']

    def test_workspace_manager_exact_key_set(self):
        user = UserFactory()
        self._grant_workspace_manager(user)
        self.client.force_authenticate(user=user)

        body = self.client.get(self.url).json()
        assert WorkspaceMember.Role.WORKSPACE_MANAGER in body['roles']
        assert set(body['summary'].keys()) == {'workspace_manager'}
        wm = body['summary']['workspace_manager']
        assert set(wm.keys()) == EXPECTED_KEYS['workspace_manager']
        # Every workspace row must carry the documented shape.
        for row in wm['workspaces']:
            assert set(row.keys()) == {'workspace_id', 'title', 'project_count', 'completion'}
            assert set(row['completion'].keys()) == {'total', 'finished', 'percent'}

    def test_project_manager_exact_key_set(self):
        user = UserFactory()
        self._grant_project_manager(user)
        self.client.force_authenticate(user=user)

        body = self.client.get(self.url).json()
        assert ProjectRole.PROJECT_MANAGER in body['roles']
        assert set(body['summary'].keys()) == {'project_manager'}
        pm = body['summary']['project_manager']
        assert set(pm.keys()) == EXPECTED_KEYS['project_manager']
        for row in pm['projects']:
            assert set(row.keys()) == {
                'project_id', 'title', 'total', 'finished', 'percent',
                'type', 'worker_progress', 'estimated_settlement',
            }

    def test_annotator_exact_key_set(self):
        user = UserFactory()
        self._grant_annotator(user)
        self.client.force_authenticate(user=user)

        body = self.client.get(self.url).json()
        assert ProjectRole.ANNOTATOR in body['roles']
        assert set(body['summary'].keys()) == {'annotator'}
        assert set(body['summary']['annotator'].keys()) == EXPECTED_KEYS['annotator']

    def test_reviewer_exact_key_set(self):
        user = UserFactory()
        self._grant_reviewer(user)
        self.client.force_authenticate(user=user)

        body = self.client.get(self.url).json()
        assert ProjectRole.REVIEWER in body['roles']
        assert set(body['summary'].keys()) == {'reviewer'}
        assert set(body['summary']['reviewer'].keys()) == EXPECTED_KEYS['reviewer']

    # -- Cross-role isolation -----------------------------------------------

    def test_single_role_does_not_leak_other_branches(self):
        """A user with exactly one role must only see that one branch —
        regression guard for `_effective_roles` leaking memberships across
        role categories."""
        matrix = [
            ('super_admin', self._grant_super_admin),
            ('workspace_manager', self._grant_workspace_manager),
            ('project_manager', self._grant_project_manager),
            ('annotator', self._grant_annotator),
            ('reviewer', self._grant_reviewer),
        ]
        for branch, grant in matrix:
            user = UserFactory()
            grant(user)
            self.client.force_authenticate(user=user)
            body = self.client.get(self.url).json()

            present = set(body['summary'].keys())
            assert present == {branch}, (
                f'Role {branch!r} leaked branches: {present - {branch}}'
            )
            # Every other branch must be absent.
            for other in ALL_BRANCH_KEYS - {branch}:
                assert other not in body['summary']

    # -- Union payloads (multi-role) ----------------------------------------

    def test_all_five_roles_yields_full_payload(self):
        """A user granted every role gets every branch, each with its exact
        key set intact — the union is additive, not mutating."""
        user = UserFactory()
        self._grant_super_admin(user)
        self._grant_workspace_manager(user)
        self._grant_project_manager(user)
        self._grant_annotator(user)
        self._grant_reviewer(user)

        self.client.force_authenticate(user=user)
        body = self.client.get(self.url).json()

        # Every role flag must appear.
        assert OrganizationRole.SUPER_ADMIN in body['roles']
        assert WorkspaceMember.Role.WORKSPACE_MANAGER in body['roles']
        assert ProjectRole.PROJECT_MANAGER in body['roles']
        assert ProjectRole.ANNOTATOR in body['roles']
        assert ProjectRole.REVIEWER in body['roles']

        # All five branches present, each with canonical keys.
        assert set(body['summary'].keys()) == ALL_BRANCH_KEYS
        for branch, keys in EXPECTED_KEYS.items():
            assert set(body['summary'][branch].keys()) == keys, (
                f'Branch {branch!r} drifted from canonical contract'
            )

    def test_annotator_plus_reviewer_splits_cleanly(self):
        """Worker-scope dual role — both branches appear, manager branches
        absent (the spec treats worker roles as project-scoped peers, not
        escalations)."""
        user = UserFactory()
        self._grant_annotator(user)
        self._grant_reviewer(user)

        self.client.force_authenticate(user=user)
        body = self.client.get(self.url).json()

        assert set(body['summary'].keys()) == {'annotator', 'reviewer'}
        for absent in ('super_admin', 'workspace_manager', 'project_manager'):
            assert absent not in body['summary']

    def test_super_admin_plus_reviewer_union(self):
        """Super admin does not suppress other membership-based branches —
        both should render."""
        user = UserFactory()
        self._grant_super_admin(user)
        self._grant_reviewer(user)

        self.client.force_authenticate(user=user)
        body = self.client.get(self.url).json()

        assert set(body['summary'].keys()) == {'super_admin', 'reviewer'}

    # -- Envelope invariants -------------------------------------------------

    def test_envelope_shape_is_stable(self):
        """Top-level keys are fixed regardless of role: roles, organization_id,
        summary, generated_at."""
        user = UserFactory()
        self._grant_reviewer(user)
        self.client.force_authenticate(user=user)

        body = self.client.get(self.url).json()
        assert set(body.keys()) == {'roles', 'organization_id', 'summary', 'generated_at'}
        assert body['organization_id'] == self.organization.id
        assert isinstance(body['roles'], list)
        assert isinstance(body['summary'], dict)
        assert isinstance(body['generated_at'], str)

    def test_plain_member_gets_envelope_but_empty_summary(self):
        """A user with an org membership but no role-granting memberships sees
        the envelope with `roles=[]` and `summary={}` — no branch leaks from
        the owner's memberships."""
        plain = UserFactory()
        _join_org(plain, self.organization)
        self.client.force_authenticate(user=plain)

        body = self.client.get(self.url).json()
        assert body['roles'] == []
        assert body['summary'] == {}
        assert body['organization_id'] == self.organization.id
