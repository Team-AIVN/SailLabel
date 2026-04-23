"""Tests for project-level ``rules``-based permissions.

Verifies that ``user.has_perm(name, project)`` returns the expected boolean for
the five named project permissions across every role.
"""

from __future__ import annotations

from organizations.models import OrganizationMember
from organizations.tests.factories import OrganizationFactory
from projects.models import ProjectMember
from projects.tests.factories import ProjectFactory
from rest_framework.test import APITestCase
from users.constants import OrganizationRole, ProjectRole
from users.tests.factories import UserFactory


def _join_org(user, org, role=OrganizationRole.MEMBER):
    user.active_organization = org
    user.save(update_fields=['active_organization'])
    m, _ = OrganizationMember.objects.get_or_create(user=user, organization=org)
    if m.role != role:
        m.role = role
        m.save(update_fields=['role'])


class ProjectPermissionMatrixTests(APITestCase):
    def setUp(self):
        self.org = OrganizationFactory()
        self.project = ProjectFactory(organization=self.org)

        self.manager = UserFactory()
        _join_org(self.manager, self.org)
        ProjectMember.objects.create(
            user=self.manager, project=self.project, role=ProjectRole.PROJECT_MANAGER
        )

        self.annotator = UserFactory()
        _join_org(self.annotator, self.org)
        ProjectMember.objects.create(
            user=self.annotator, project=self.project, role=ProjectRole.ANNOTATOR
        )

        self.super_admin = UserFactory()
        _join_org(self.super_admin, self.org, OrganizationRole.SUPER_ADMIN)

    def test_project_manager_can_change_and_delete(self):
        assert self.manager.has_perm('projects.change', self.project)
        assert self.manager.has_perm('projects.delete', self.project)
        assert self.manager.has_perm('projects.reset_cache', self.project)

    def test_annotator_cannot_change_or_delete(self):
        assert not self.annotator.has_perm('projects.change', self.project)
        assert not self.annotator.has_perm('projects.delete', self.project)
        assert not self.annotator.has_perm('projects.reset_cache', self.project)

    def test_super_admin_bypasses_project_membership(self):
        assert self.super_admin.has_perm('projects.change', self.project)
        assert self.super_admin.has_perm('projects.delete', self.project)

    def test_view_and_create_remain_open_to_authenticated_users(self):
        # These stay at the `is_authenticated` default — queryset filters handle scope.
        for user in (self.manager, self.annotator, self.super_admin):
            assert user.has_perm('projects.view', self.project)
            assert user.has_perm('projects.create')
