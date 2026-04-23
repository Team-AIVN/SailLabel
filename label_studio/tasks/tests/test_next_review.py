"""Phase 5 random-review dispatcher — `GET /api/projects/<id>/next-review/`.

Covers the dispatcher contract:
- Returns the next `WILL_REVIEWED` annotation and locks it.
- Skips annotations the caller authored (self-review guard).
- Skips annotations another reviewer currently holds.
- Second concurrent caller gets a *different* annotation.
- Empty queue → 404.
- Calling again after releasing the lock re-serves the same annotation.
"""

import pytest  # type: ignore[import]
from core.current_request import CurrentContext
from fsm.state_manager import StateManager
from organizations.tests.factories import OrganizationFactory
from projects.tests.factories import ProjectFactory
from rest_framework.test import APITestCase
from tasks.models import ReviewerLock
from tasks.tests.factories import AnnotationFactory, TaskFactory
from users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def _prime_fsm(user):
    CurrentContext.clear()
    CurrentContext.set_user(user)


def _make_will_reviewed(project, annotator):
    """Create an annotation and drive it to WILL_REVIEWED."""
    task = TaskFactory(project=project, is_labeled=True)
    annotation = AnnotationFactory(task=task, project=project, completed_by=annotator, result=[])
    _prime_fsm(annotator)
    StateManager.execute_transition(entity=annotation, transition_name='assign_annotation', user=annotator)
    StateManager.execute_transition(entity=annotation, transition_name='mark_annotated', user=annotator)
    StateManager.execute_transition(entity=annotation, transition_name='move_to_review', user=annotator)
    annotation.refresh_from_db()
    return annotation


class NextReviewAPITests(APITestCase):
    def setUp(self):
        self.org = OrganizationFactory()
        self.reviewer = self.org.created_by
        self.other_reviewer = UserFactory()
        self.annotator = UserFactory()
        self.project = ProjectFactory(organization=self.org, created_by=self.reviewer)

    def _url(self):
        return f'/api/projects/{self.project.id}/next-review/'

    def test_empty_queue_returns_404(self):
        self.client.force_authenticate(user=self.reviewer)
        response = self.client.get(self._url())
        assert response.status_code == 404

    def test_serves_will_reviewed_annotation_and_acquires_lock(self):
        annotation = _make_will_reviewed(self.project, self.annotator)

        self.client.force_authenticate(user=self.reviewer)
        response = self.client.get(self._url())

        assert response.status_code == 200, response.content
        body = response.json()
        assert body['annotation']['id'] == annotation.id
        assert body['task']['id'] == annotation.task_id
        assert 'unique_id' in body['lock']

        # Lock persisted for the caller.
        assert ReviewerLock.objects.filter(
            annotation=annotation, user=self.reviewer
        ).count() == 1

    def test_skips_self_authored_annotation(self):
        # Only candidate in the project is one the reviewer themselves authored.
        _make_will_reviewed(self.project, self.reviewer)

        self.client.force_authenticate(user=self.reviewer)
        response = self.client.get(self._url())

        assert response.status_code == 404

    def test_skips_annotation_locked_by_another_reviewer(self):
        locked = _make_will_reviewed(self.project, self.annotator)
        free = _make_will_reviewed(self.project, self.annotator)

        # The other reviewer already holds the first one.
        ReviewerLock.acquire(locked, self.other_reviewer)

        self.client.force_authenticate(user=self.reviewer)
        response = self.client.get(self._url())

        assert response.status_code == 200
        assert response.json()['annotation']['id'] == free.id

    def test_two_reviewers_get_different_annotations(self):
        a1 = _make_will_reviewed(self.project, self.annotator)
        a2 = _make_will_reviewed(self.project, self.annotator)

        self.client.force_authenticate(user=self.reviewer)
        first = self.client.get(self._url()).json()

        self.client.force_authenticate(user=self.other_reviewer)
        second = self.client.get(self._url()).json()

        assert {first['annotation']['id'], second['annotation']['id']} == {a1.id, a2.id}

    def test_same_reviewer_reacquires_same_annotation(self):
        annotation = _make_will_reviewed(self.project, self.annotator)

        self.client.force_authenticate(user=self.reviewer)
        first = self.client.get(self._url()).json()
        # Second call: since no other reviewer has a lock and the existing
        # lock belongs to the caller, they get the same annotation back.
        second = self.client.get(self._url()).json()

        assert first['annotation']['id'] == annotation.id
        assert second['annotation']['id'] == annotation.id
        # Still exactly one lock row.
        assert ReviewerLock.objects.filter(annotation=annotation).count() == 1

    def test_unauthenticated_returns_401_or_403(self):
        _make_will_reviewed(self.project, self.annotator)
        response = self.client.get(self._url())
        assert response.status_code in (401, 403)

    def test_other_project_annotations_are_not_served(self):
        other_project = ProjectFactory(organization=self.org, created_by=self.reviewer)
        _make_will_reviewed(other_project, self.annotator)

        self.client.force_authenticate(user=self.reviewer)
        response = self.client.get(self._url())
        # No reviewable annotations in *this* project.
        assert response.status_code == 404
