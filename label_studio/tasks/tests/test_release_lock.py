"""Phase 5 — ReviewerLock release paths.

Covers:
- Accept / reject auto-release: once the review resolves, the lock must drop
  so `/next-review/` can serve this annotation slot to nobody (it's moved past
  WILL_REVIEWED) or, more importantly, free the queue for the reviewer's next
  pick.
- `POST /api/annotations/<id>/release-lock/` is the explicit escape hatch for
  abandoned reviews (page unload, navigate away) so the 30-minute TTL doesn't
  gate the queue.
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


def _drive_to_will_reviewed(annotation, user):
    CurrentContext.clear()
    CurrentContext.set_user(user)
    StateManager.execute_transition(entity=annotation, transition_name='assign_annotation', user=user)
    StateManager.execute_transition(entity=annotation, transition_name='mark_annotated', user=user)
    StateManager.execute_transition(entity=annotation, transition_name='move_to_review', user=user)


class _Base(APITestCase):
    def setUp(self):
        self.org = OrganizationFactory()
        self.reviewer = self.org.created_by
        self.other_reviewer = UserFactory()
        self.annotator = UserFactory()
        self.project = ProjectFactory(organization=self.org, created_by=self.reviewer)
        self.task = TaskFactory(project=self.project, is_labeled=True)
        self.annotation = AnnotationFactory(
            task=self.task, project=self.project, completed_by=self.annotator, result=[]
        )
        _drive_to_will_reviewed(self.annotation, self.annotator)


class AutoReleaseOnReviewTests(_Base):
    def test_accept_drops_existing_lock(self):
        ReviewerLock.acquire(self.annotation, self.reviewer)
        assert ReviewerLock.objects.filter(annotation=self.annotation).exists()

        self.client.force_authenticate(user=self.reviewer)
        response = self.client.post(
            f'/api/annotations/{self.annotation.id}/accept/', data={}, format='json'
        )
        assert response.status_code == 200, response.content
        assert not ReviewerLock.objects.filter(annotation=self.annotation).exists()

    def test_reject_drops_existing_lock(self):
        ReviewerLock.acquire(self.annotation, self.reviewer)

        self.client.force_authenticate(user=self.reviewer)
        response = self.client.post(
            f'/api/annotations/{self.annotation.id}/reject/',
            data={'comment': 'needs rework'},
            format='json',
        )
        assert response.status_code == 200, response.content
        assert not ReviewerLock.objects.filter(annotation=self.annotation).exists()


class ReleaseLockAPITests(_Base):
    def _url(self):
        return f'/api/annotations/{self.annotation.id}/release-lock/'

    def test_releases_callers_lock(self):
        ReviewerLock.acquire(self.annotation, self.reviewer)
        self.client.force_authenticate(user=self.reviewer)

        response = self.client.post(self._url(), data={}, format='json')

        assert response.status_code == 200, response.content
        assert response.json() == {'released': True}
        assert not ReviewerLock.objects.filter(
            annotation=self.annotation, user=self.reviewer
        ).exists()

    def test_idempotent_when_no_lock_exists(self):
        self.client.force_authenticate(user=self.reviewer)
        response = self.client.post(self._url(), data={}, format='json')

        assert response.status_code == 200
        assert response.json() == {'released': False}

    def test_forbidden_when_lock_belongs_to_other_reviewer(self):
        ReviewerLock.acquire(self.annotation, self.other_reviewer)
        self.client.force_authenticate(user=self.reviewer)

        response = self.client.post(self._url(), data={}, format='json')

        assert response.status_code == 403, response.content
        # The other reviewer's lock must be untouched.
        assert ReviewerLock.objects.filter(
            annotation=self.annotation, user=self.other_reviewer
        ).exists()

    def test_unauthenticated_returns_401_or_403(self):
        ReviewerLock.acquire(self.annotation, self.reviewer)
        response = self.client.post(self._url(), data={}, format='json')
        assert response.status_code in (401, 403)
        # Nothing got deleted by an unauthed call.
        assert ReviewerLock.objects.filter(annotation=self.annotation).exists()
