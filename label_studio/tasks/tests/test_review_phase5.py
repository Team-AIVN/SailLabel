"""Phase 5 — reviewer-facing HTTP endpoints.

Covers:
- `POST /api/annotations/<pk>/accept/` fires `accept_annotation` and propagates
  to `task_accepted` via the Phase 4B post-transition hook.
- `POST /api/annotations/<pk>/reject/` requires a non-empty `comment` and stores
  it in the resulting `AnnotationState.reason`.
- Permissions: unauthenticated requests are rejected; authenticated users can
  act (OSS default is `is_authenticated`).

The tests drive annotations through `assign → annotated → will_reviewed`
before hitting the review endpoint — that's the precondition the Phase 4
transitions enforce, so anything shorter would 400 at the transition layer
rather than exercising the view code we actually want to cover.
"""

import pytest  # type: ignore[import]
from core.current_request import CurrentContext
from fsm.state_choices import AnnotationStateChoices, TaskStateChoices
from fsm.state_manager import StateManager
from fsm.state_models import AnnotationState, TaskState
from organizations.tests.factories import OrganizationFactory
from projects.tests.factories import ProjectFactory
from rest_framework.test import APITestCase
from tasks.tests.factories import AnnotationFactory, TaskFactory
from users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def _prime_fsm(user):
    """Seed the thread-local context so `StateManager.*` doesn't no-op.

    The middleware clears the context after each HTTP request, so we re-prime
    after every `self.client.*` call that we want to follow with a StateManager
    query. For raw state lookups we bypass StateManager entirely and read the
    state model directly (see `_annotation_state` helper).
    """
    CurrentContext.clear()
    CurrentContext.set_user(user)


def _drive_to_will_reviewed(annotation, user):
    _prime_fsm(user)
    StateManager.execute_transition(entity=annotation, transition_name='assign_annotation', user=user)
    StateManager.execute_transition(entity=annotation, transition_name='mark_annotated', user=user)
    StateManager.execute_transition(entity=annotation, transition_name='move_to_review', user=user)


def _annotation_state(annotation):
    """Direct DB read — avoids the CurrentContext gate in StateManager."""
    return AnnotationState.get_current_state_value(annotation)


def _task_state(task):
    return TaskState.get_current_state_value(task)


class _ReviewAPIBase(APITestCase):
    """Shared setUp: separate annotator from reviewer so tests don't accidentally
    trip the self-review guard (§2.2). The org creator plays reviewer; a fresh
    UserFactory user plays annotator.
    """

    def setUp(self):
        self.org = OrganizationFactory()
        self.reviewer = self.org.created_by
        self.annotator = UserFactory()
        self.project = ProjectFactory(organization=self.org, created_by=self.reviewer)
        self.task = TaskFactory(project=self.project, is_labeled=True)
        self.annotation = AnnotationFactory(
            task=self.task, project=self.project, completed_by=self.annotator, result=[]
        )
        _drive_to_will_reviewed(self.annotation, self.annotator)


class AnnotationAcceptAPITests(_ReviewAPIBase):
    def test_accept_endpoint_fires_transition(self):
        self.client.force_authenticate(user=self.reviewer)
        response = self.client.post(f'/api/annotations/{self.annotation.id}/accept/', data={}, format='json')

        assert response.status_code == 200, response.content
        assert _annotation_state(self.annotation) == AnnotationStateChoices.ACCEPTED
        # Phase 4B hook chains through to task aggregation.
        assert _task_state(self.task) == TaskStateChoices.ACCEPTED

    def test_accept_endpoint_persists_optional_comment_as_reason(self):
        self.client.force_authenticate(user=self.reviewer)
        response = self.client.post(
            f'/api/annotations/{self.annotation.id}/accept/',
            data={'comment': 'LGTM — clean labels'},
            format='json',
        )

        assert response.status_code == 200
        latest = AnnotationState.objects.filter(
            annotation_id=self.annotation.id, transition_name='accept_annotation'
        ).order_by('-id').first()
        assert latest is not None
        assert latest.reason == 'LGTM — clean labels'
        assert latest.triggered_by_id == self.reviewer.id

    def test_accept_endpoint_rejects_unauthenticated(self):
        response = self.client.post(f'/api/annotations/{self.annotation.id}/accept/', data={}, format='json')
        assert response.status_code in (401, 403)

    def test_accept_endpoint_blocks_self_review(self):
        """Annotator cannot also be the reviewer of the same annotation."""
        self.client.force_authenticate(user=self.annotator)
        response = self.client.post(f'/api/annotations/{self.annotation.id}/accept/', data={}, format='json')

        assert response.status_code == 403, response.content
        # Annotation stays in WILL_REVIEWED — no transition ran.
        assert _annotation_state(self.annotation) == AnnotationStateChoices.WILL_REVIEWED


class AnnotationRejectAPITests(_ReviewAPIBase):
    def test_reject_without_comment_returns_400(self):
        self.client.force_authenticate(user=self.reviewer)
        response = self.client.post(f'/api/annotations/{self.annotation.id}/reject/', data={}, format='json')

        assert response.status_code == 400, response.content
        # Annotation must remain in WILL_REVIEWED — the 400 should short-circuit.
        assert _annotation_state(self.annotation) == AnnotationStateChoices.WILL_REVIEWED

    def test_reject_with_whitespace_only_comment_returns_400(self):
        self.client.force_authenticate(user=self.reviewer)
        response = self.client.post(
            f'/api/annotations/{self.annotation.id}/reject/',
            data={'comment': '   '},
            format='json',
        )
        assert response.status_code == 400

    def test_reject_with_comment_fires_transition_and_stores_reason(self):
        self.client.force_authenticate(user=self.reviewer)
        response = self.client.post(
            f'/api/annotations/{self.annotation.id}/reject/',
            data={'comment': 'Missing bbox on the cat'},
            format='json',
        )

        assert response.status_code == 200, response.content
        assert _annotation_state(self.annotation) == AnnotationStateChoices.REJECTED

        latest = AnnotationState.objects.filter(
            annotation_id=self.annotation.id, transition_name='reject_annotation'
        ).order_by('-id').first()
        assert latest is not None
        assert latest.reason == 'Missing bbox on the cat'
        assert latest.triggered_by_id == self.reviewer.id

    def test_reject_endpoint_blocks_self_review(self):
        self.client.force_authenticate(user=self.annotator)
        response = self.client.post(
            f'/api/annotations/{self.annotation.id}/reject/',
            data={'comment': 'self-review should be blocked'},
            format='json',
        )

        assert response.status_code == 403, response.content
        assert _annotation_state(self.annotation) == AnnotationStateChoices.WILL_REVIEWED


class UserReviewsAPITests(APITestCase):
    """`/api/current-user/reviews/` reads AnnotationState filtered by triggered_by."""

    def setUp(self):
        self.org = OrganizationFactory()
        self.reviewer = self.org.created_by

        # Separate org + reviewer so we can assert the endpoint isolates by user.
        self.other_org = OrganizationFactory()
        self.other_reviewer = self.other_org.created_by

        self.project = ProjectFactory(organization=self.org, created_by=self.reviewer)
        self.other_project = ProjectFactory(organization=self.other_org, created_by=self.other_reviewer)

    def _make_reviewed(self, *, reviewer, project, transition, comment=''):
        task = TaskFactory(project=project, is_labeled=True)
        annotation = AnnotationFactory(task=task, project=project, completed_by=reviewer, result=[])
        _drive_to_will_reviewed(annotation, reviewer)
        reason = comment or None
        StateManager.execute_transition(
            entity=annotation, transition_name=transition, user=reviewer, reason=reason,
        )
        return annotation

    def test_returns_only_requesting_users_reviews(self):
        mine = self._make_reviewed(reviewer=self.reviewer, project=self.project, transition='accept_annotation')
        self._make_reviewed(
            reviewer=self.other_reviewer, project=self.other_project, transition='accept_annotation'
        )

        self.client.force_authenticate(user=self.reviewer)
        response = self.client.get('/api/current-user/reviews/')
        assert response.status_code == 200, response.content

        body = response.json()
        annotation_ids = {row['annotation_id'] for row in body}
        assert annotation_ids == {mine.id}

    def test_rows_carry_transition_state_and_comment(self):
        annotation = self._make_reviewed(
            reviewer=self.reviewer,
            project=self.project,
            transition='reject_annotation',
            comment='needs rework',
        )

        self.client.force_authenticate(user=self.reviewer)
        body = self.client.get('/api/current-user/reviews/').json()
        assert len(body) == 1
        row = body[0]
        assert row['annotation_id'] == annotation.id
        assert row['task_id'] == annotation.task_id
        assert row['project_id'] == annotation.project_id
        assert row['transition_name'] == 'reject_annotation'
        assert row['state'] == AnnotationStateChoices.REJECTED
        assert row['comment'] == 'needs rework'

    def test_filter_by_state(self):
        accepted = self._make_reviewed(
            reviewer=self.reviewer, project=self.project, transition='accept_annotation'
        )
        self._make_reviewed(
            reviewer=self.reviewer, project=self.project,
            transition='reject_annotation', comment='nope',
        )

        self.client.force_authenticate(user=self.reviewer)
        body = self.client.get(f'/api/current-user/reviews/?state={AnnotationStateChoices.ACCEPTED}').json()
        annotation_ids = {row['annotation_id'] for row in body}
        assert annotation_ids == {accepted.id}

    def test_filter_by_project(self):
        other_project_in_same_org = ProjectFactory(organization=self.org, created_by=self.reviewer)
        targeted = self._make_reviewed(
            reviewer=self.reviewer, project=self.project, transition='accept_annotation'
        )
        self._make_reviewed(
            reviewer=self.reviewer, project=other_project_in_same_org, transition='accept_annotation'
        )

        self.client.force_authenticate(user=self.reviewer)
        body = self.client.get(f'/api/current-user/reviews/?project={self.project.id}').json()
        annotation_ids = {row['annotation_id'] for row in body}
        assert annotation_ids == {targeted.id}

    def test_filter_by_transition(self):
        self._make_reviewed(reviewer=self.reviewer, project=self.project, transition='accept_annotation')
        rejected = self._make_reviewed(
            reviewer=self.reviewer, project=self.project,
            transition='reject_annotation', comment='fix',
        )

        self.client.force_authenticate(user=self.reviewer)
        body = self.client.get('/api/current-user/reviews/?transition=reject_annotation').json()
        annotation_ids = {row['annotation_id'] for row in body}
        assert annotation_ids == {rejected.id}

    def test_unauthenticated_returns_401_or_403(self):
        response = self.client.get('/api/current-user/reviews/')
        assert response.status_code in (401, 403)

    def test_users_me_alias_mirrors_current_user_route(self):
        """instructions.md §3.6.2 lists the endpoint as `/api/users/me/reviews/`.
        Both URL shapes must return the same payload for the authenticated user."""
        mine = self._make_reviewed(
            reviewer=self.reviewer, project=self.project, transition='accept_annotation'
        )
        self.client.force_authenticate(user=self.reviewer)

        current = self.client.get('/api/current-user/reviews/')
        alias = self.client.get('/api/users/me/reviews/')

        assert current.status_code == 200
        assert alias.status_code == 200
        assert current.json() == alias.json()
        assert {row['annotation_id'] for row in alias.json()} == {mine.id}

    def test_users_me_alias_honors_filters(self):
        accepted = self._make_reviewed(
            reviewer=self.reviewer, project=self.project, transition='accept_annotation'
        )
        self._make_reviewed(
            reviewer=self.reviewer, project=self.project,
            transition='reject_annotation', comment='nope',
        )
        self.client.force_authenticate(user=self.reviewer)

        body = self.client.get(
            f'/api/users/me/reviews/?state={AnnotationStateChoices.ACCEPTED}'
        ).json()
        assert {row['annotation_id'] for row in body} == {accepted.id}
