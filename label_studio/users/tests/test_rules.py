"""Unit tests for users.rules predicates.

Scope: verify every role predicate returns the correct truth value against the
three relevant scopes (super admin, workspace manager, project role) and that
``can_review_annotation`` denies self-review.
"""

from __future__ import annotations

from organizations.models import OrganizationMember
from organizations.tests.factories import OrganizationFactory
from projects.models import ProjectMember
from projects.tests.factories import ProjectFactory
from rest_framework.test import APITestCase
from users.constants import OrganizationRole, ProjectRole
from users.rules import (
    can_review_annotation,
    is_annotator_of,
    is_project_manager_of,
    is_project_member_of,
    is_reviewer_of,
    is_super_admin,
    is_worker_of,
    is_workspace_manager_of,
)
from users.tests.factories import UserFactory
from workspaces.models import WorkspaceMember
from workspaces.tests.factories import WorkspaceFactory


def _join_org(user, org, role=OrganizationRole.MEMBER):
    user.active_organization = org
    user.save(update_fields=['active_organization'])
    m, _ = OrganizationMember.objects.get_or_create(user=user, organization=org)
    if m.role != role:
        m.role = role
        m.save(update_fields=['role'])
    return m


class SuperAdminPredicateTests(APITestCase):
    def setUp(self):
        self.org = OrganizationFactory()
        self.user = UserFactory()
        _join_org(self.user, self.org)

    def test_django_superuser_is_super_admin(self):
        self.user.is_superuser = True
        self.user.save(update_fields=['is_superuser'])
        assert is_super_admin.test(self.user)

    def test_org_role_super_admin_is_super_admin(self):
        _join_org(self.user, self.org, OrganizationRole.SUPER_ADMIN)
        assert is_super_admin.test(self.user)

    def test_plain_member_is_not_super_admin(self):
        assert not is_super_admin.test(self.user)

    def test_anonymous_is_not_super_admin(self):
        from django.contrib.auth.models import AnonymousUser

        assert not is_super_admin.test(AnonymousUser())


class ProjectRolePredicateTests(APITestCase):
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

        self.reviewer = UserFactory()
        _join_org(self.reviewer, self.org)
        ProjectMember.objects.create(
            user=self.reviewer, project=self.project, role=ProjectRole.REVIEWER
        )

        self.outsider = UserFactory()
        _join_org(self.outsider, self.org)

    def test_project_manager_predicate(self):
        assert is_project_manager_of.test(self.manager, self.project)
        assert not is_project_manager_of.test(self.annotator, self.project)
        assert not is_project_manager_of.test(self.outsider, self.project)

    def test_annotator_predicate(self):
        assert is_annotator_of.test(self.annotator, self.project)
        assert not is_annotator_of.test(self.reviewer, self.project)

    def test_reviewer_predicate(self):
        assert is_reviewer_of.test(self.reviewer, self.project)
        assert not is_reviewer_of.test(self.annotator, self.project)

    def test_worker_is_union_of_annotator_and_reviewer(self):
        assert is_worker_of.test(self.annotator, self.project)
        assert is_worker_of.test(self.reviewer, self.project)
        assert not is_worker_of.test(self.manager, self.project)
        assert not is_worker_of.test(self.outsider, self.project)

    def test_project_member_includes_all_active_roles(self):
        for user in (self.manager, self.annotator, self.reviewer):
            assert is_project_member_of.test(user, self.project)
        assert not is_project_member_of.test(self.outsider, self.project)

    def test_soft_deleted_membership_is_ignored(self):
        pm = ProjectMember.objects.get(user=self.annotator, project=self.project)
        from django.utils import timezone

        pm.deleted_at = timezone.now()
        pm.save(update_fields=['deleted_at'])
        assert not is_annotator_of.test(self.annotator, self.project)
        assert not is_project_member_of.test(self.annotator, self.project)


class WorkspaceEscalationTests(APITestCase):
    def setUp(self):
        self.org = OrganizationFactory()
        self.workspace = WorkspaceFactory(organization=self.org)
        self.project = ProjectFactory(organization=self.org, workspace=self.workspace)

    def test_workspace_manager_is_implicit_project_manager(self):
        ws_manager = UserFactory()
        _join_org(ws_manager, self.org)
        WorkspaceMember.objects.create(
            user=ws_manager, workspace=self.workspace, role=WorkspaceMember.Role.WORKSPACE_MANAGER
        )

        assert is_workspace_manager_of.test(ws_manager, self.workspace)
        assert is_workspace_manager_of.test(ws_manager, self.project)
        # And the project-manager predicate flows through.
        assert is_project_manager_of.test(ws_manager, self.project)

    def test_workspace_plain_member_is_not_project_manager(self):
        ws_member = UserFactory()
        _join_org(ws_member, self.org)
        WorkspaceMember.objects.create(
            user=ws_member, workspace=self.workspace, role=WorkspaceMember.Role.MEMBER
        )
        assert not is_project_manager_of.test(ws_member, self.project)


class CanReviewAnnotationTests(APITestCase):
    def setUp(self):
        self.org = OrganizationFactory()
        self.project = ProjectFactory(organization=self.org)
        self.reviewer = UserFactory()
        _join_org(self.reviewer, self.org)
        ProjectMember.objects.create(
            user=self.reviewer, project=self.project, role=ProjectRole.REVIEWER
        )

    def _make_annotation(self, completed_by):
        from tasks.models import Annotation, Task

        task = Task.objects.create(project=self.project, data={})
        return Annotation.objects.create(task=task, project=self.project, completed_by=completed_by, result=[])

    def test_reviewer_can_review_others_annotation(self):
        author = UserFactory()
        _join_org(author, self.org)
        ProjectMember.objects.create(user=author, project=self.project, role=ProjectRole.ANNOTATOR)
        annotation = self._make_annotation(completed_by=author)
        assert can_review_annotation.test(self.reviewer, annotation)

    def test_reviewer_cannot_review_own_annotation(self):
        annotation = self._make_annotation(completed_by=self.reviewer)
        assert not can_review_annotation.test(self.reviewer, annotation)

    def test_non_reviewer_cannot_review(self):
        outsider = UserFactory()
        _join_org(outsider, self.org)
        annotation = self._make_annotation(completed_by=self.reviewer)
        assert not can_review_annotation.test(outsider, annotation)
