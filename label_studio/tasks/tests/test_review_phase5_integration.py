"""Phase 5 — integration-level review flow tests.

Covers three scenarios that the unit-level `test_review_phase5.py` does not:

1. **Reject → rework (reassignment) chain.** The HTTP `reject` endpoint must
   (a) flip the annotation to `REJECTED`, (b) clear any `ReviewerLock` held on
   it, and (c) let the `rework_annotation` helper spawn a *child* annotation
   linked via `parent_annotation_id`, driven back to `ASSIGNED`.
2. **Self-review prohibition** beyond the single accept/reject 403 cases —
   predicate behavior in isolation, dual-role users (annotator *and* reviewer
   on the same project), and cross-annotation safety.
3. **Batch review mode** (`fflag_batch_review`) — when the flag is on and a
   project hits its `review_batch_size`, `route_batch_to_review` walks
   annotations from `ANNOTATED` into `WILL_REVIEWED` so the `/accept/` and
   `/reject/` endpoints can act on them end-to-end.

These exercise real HTTP requests + real FSM transitions (no mocking of the
StateManager) so a regression anywhere along the pipeline surfaces here.
"""

from datetime import timedelta
from unittest import mock

import pytest  # type: ignore[import]
from core.current_request import CurrentContext
from django.utils import timezone
from fsm.annotation_transitions import rework_annotation
from fsm.batch_review import route_batch_to_review
from fsm.state_choices import AnnotationStateChoices
from fsm.state_manager import StateManager
from fsm.state_models import AnnotationState
from organizations.tests.factories import OrganizationFactory
from projects.tests.factories import ProjectFactory
from rest_framework.test import APITestCase
from tasks.models import Annotation, ReviewerLock
from tasks.tests.factories import AnnotationFactory, TaskFactory
from users.rules import not_self_review
from users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers (mirror test_review_phase5.py)
# ---------------------------------------------------------------------------


def _prime_fsm(user):
    CurrentContext.clear()
    CurrentContext.set_user(user)


def _drive_to_will_reviewed(annotation, user):
    _prime_fsm(user)
    StateManager.execute_transition(entity=annotation, transition_name='assign_annotation', user=user)
    StateManager.execute_transition(entity=annotation, transition_name='mark_annotated', user=user)
    StateManager.execute_transition(entity=annotation, transition_name='move_to_review', user=user)


def _annotation_state(annotation):
    return AnnotationState.get_current_state_value(annotation)


def _batch_flag(on: bool):
    """Flip `fflag_batch_review` at the consumer module."""
    return mock.patch(
        'fsm.batch_review.flag_set',
        side_effect=lambda name, **kw: on if name == 'fflag_batch_review' else False,
    )


# ---------------------------------------------------------------------------
# 1. Reject → rework (reassignment) chain
# ---------------------------------------------------------------------------


class RejectReassignChainTests(APITestCase):
    """`POST /api/annotations/<pk>/reject/` → `REJECTED` → `rework_annotation`
    spawns a new child annotation in `ASSIGNED`, linked via `parent_annotation`.
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

    def test_reject_clears_reviewer_lock(self):
        """A live ReviewerLock held by the reviewer must be dropped when the
        reject endpoint resolves the review — otherwise another reviewer can't
        pick up the annotation before TTL even though its state terminates."""
        ReviewerLock.objects.create(
            annotation=self.annotation,
            user=self.reviewer,
            expire_at=timezone.now() + timedelta(minutes=30),
        )
        assert ReviewerLock.objects.filter(annotation=self.annotation).exists()

        self.client.force_authenticate(user=self.reviewer)
        response = self.client.post(
            f'/api/annotations/{self.annotation.id}/reject/',
            data={'comment': 'Missing labels'},
            format='json',
        )
        assert response.status_code == 200, response.content
        assert _annotation_state(self.annotation) == AnnotationStateChoices.REJECTED
        assert not ReviewerLock.objects.filter(annotation=self.annotation).exists()

    def test_reject_then_rework_spawns_child_in_assigned(self):
        """End-to-end: HTTP reject terminates the parent, then
        `rework_annotation` creates a fresh child annotation driven to
        ASSIGNED — the rework helper is the designated reassignment path
        (fsm/annotation_transitions.py:318-343)."""
        self.client.force_authenticate(user=self.reviewer)
        response = self.client.post(
            f'/api/annotations/{self.annotation.id}/reject/',
            data={'comment': 'Re-do this one'},
            format='json',
        )
        assert response.status_code == 200, response.content

        self.annotation.refresh_from_db()
        assert self.annotation.current_state == AnnotationStateChoices.REJECTED

        _prime_fsm(self.annotator)
        child = rework_annotation(self.annotation, user=self.annotator)

        assert child.pk != self.annotation.pk
        assert child.parent_annotation_id == self.annotation.id
        assert child.task_id == self.annotation.task_id
        assert child.project_id == self.annotation.project_id

        child.refresh_from_db()
        assert child.current_state == AnnotationStateChoices.ASSIGNED
        # The parent's terminal state is unchanged — rework spawns a sibling,
        # it doesn't resurrect the rejected record.
        self.annotation.refresh_from_db()
        assert self.annotation.current_state == AnnotationStateChoices.REJECTED

    def test_rework_child_can_be_driven_through_review_again(self):
        """The rework child is a full-fledged annotation and must follow the
        same `ASSIGNED → ANNOTATED → WILL_REVIEWED` path as the original."""
        self.client.force_authenticate(user=self.reviewer)
        self.client.post(
            f'/api/annotations/{self.annotation.id}/reject/',
            data={'comment': 'fix'},
            format='json',
        )

        _prime_fsm(self.annotator)
        child = rework_annotation(self.annotation, user=self.annotator)

        # Re-drive the child; must not raise.
        StateManager.execute_transition(entity=child, transition_name='mark_annotated', user=self.annotator)
        StateManager.execute_transition(entity=child, transition_name='move_to_review', user=self.annotator)
        child.refresh_from_db()
        assert child.current_state == AnnotationStateChoices.WILL_REVIEWED

    def test_rework_chain_can_be_deep(self):
        """Reject → rework → reject → rework keeps linking children through
        `parent_annotation`. Nothing in the helper limits depth; this guards
        against a regression that accidentally adds one."""
        self.client.force_authenticate(user=self.reviewer)
        self.client.post(
            f'/api/annotations/{self.annotation.id}/reject/',
            data={'comment': 'v1 wrong'},
            format='json',
        )
        _prime_fsm(self.annotator)
        child1 = rework_annotation(self.annotation, user=self.annotator)

        StateManager.execute_transition(entity=child1, transition_name='mark_annotated', user=self.annotator)
        StateManager.execute_transition(entity=child1, transition_name='move_to_review', user=self.annotator)

        self.client.force_authenticate(user=self.reviewer)
        self.client.post(
            f'/api/annotations/{child1.id}/reject/',
            data={'comment': 'v2 still wrong'},
            format='json',
        )
        _prime_fsm(self.annotator)
        child2 = rework_annotation(child1, user=self.annotator)

        assert child1.parent_annotation_id == self.annotation.id
        assert child2.parent_annotation_id == child1.id
        child2.refresh_from_db()
        assert child2.current_state == AnnotationStateChoices.ASSIGNED


# ---------------------------------------------------------------------------
# 2. Self-review prohibition — predicate + dual-role scenarios
# ---------------------------------------------------------------------------


class SelfReviewProhibitionTests(APITestCase):
    """`not_self_review` is the single source of truth — exercised through the
    predicate directly, via both HTTP endpoints, and with a user who holds
    both annotator and reviewer roles on the same project.
    """

    def setUp(self):
        self.org = OrganizationFactory()
        self.owner = self.org.created_by
        self.annotator = UserFactory()
        self.project = ProjectFactory(organization=self.org, created_by=self.owner)
        self.task = TaskFactory(project=self.project, is_labeled=True)
        self.annotation = AnnotationFactory(
            task=self.task, project=self.project, completed_by=self.annotator, result=[]
        )
        _drive_to_will_reviewed(self.annotation, self.annotator)

    def test_predicate_blocks_completed_by_user(self):
        assert not_self_review.test(self.annotator, self.annotation) is False

    def test_predicate_allows_different_user(self):
        assert not_self_review.test(self.owner, self.annotation) is True

    def test_predicate_rejects_none_annotation(self):
        assert not_self_review.test(self.owner, None) is False

    def test_predicate_rejects_unauthenticated(self):
        """Anonymous users hit the guard before any role check."""
        from django.contrib.auth.models import AnonymousUser
        assert not_self_review.test(AnonymousUser(), self.annotation) is False

    def test_predicate_allows_when_completed_by_is_null(self):
        """Machine-generated annotations have `completed_by=None` — those are
        reviewable by anyone authenticated; the self-review guard is a no-op."""
        Annotation.objects.filter(pk=self.annotation.pk).update(completed_by=None)
        self.annotation.refresh_from_db()
        assert not_self_review.test(self.owner, self.annotation) is True

    def test_dual_role_user_cannot_review_own_annotation(self):
        """A user who is simultaneously annotator *and* reviewer on the same
        project still can't accept/reject their own annotation — the guard is
        per-annotation (`completed_by`), not per-project-role."""
        self.client.force_authenticate(user=self.annotator)

        accept = self.client.post(
            f'/api/annotations/{self.annotation.id}/accept/', data={}, format='json'
        )
        reject = self.client.post(
            f'/api/annotations/{self.annotation.id}/reject/',
            data={'comment': 'self-rework'},
            format='json',
        )
        assert accept.status_code == 403, accept.content
        assert reject.status_code == 403, reject.content
        # State must not have advanced.
        assert _annotation_state(self.annotation) == AnnotationStateChoices.WILL_REVIEWED

    def test_dual_role_user_can_review_peer_annotation(self):
        """Same user can review a *peer's* annotation on the same project —
        the prohibition is strictly self-scoped."""
        peer = UserFactory()
        peer_task = TaskFactory(project=self.project, is_labeled=True)
        peer_annotation = AnnotationFactory(
            task=peer_task, project=self.project, completed_by=peer, result=[]
        )
        _drive_to_will_reviewed(peer_annotation, peer)

        self.client.force_authenticate(user=self.annotator)
        response = self.client.post(
            f'/api/annotations/{peer_annotation.id}/accept/', data={}, format='json'
        )
        assert response.status_code == 200, response.content
        assert _annotation_state(peer_annotation) == AnnotationStateChoices.ACCEPTED


# ---------------------------------------------------------------------------
# 3. Batch review mode — API-level flow
# ---------------------------------------------------------------------------


class BatchReviewIntegrationTests(APITestCase):
    """With `fflag_batch_review` on and `review_batch_size` met, batch routing
    walks annotations from ANNOTATED into WILL_REVIEWED; the reject endpoint
    then acts on them exactly like the classic flow.
    """

    def setUp(self):
        self.org = OrganizationFactory()
        self.reviewer = self.org.created_by
        self.annotator = UserFactory()
        # Batch threshold = 2, so 2 annotated is the tripping point.
        self.project = ProjectFactory(
            organization=self.org, created_by=self.reviewer, review_batch_size=2
        )

    def _make_annotated(self, count: int):
        """Create `count` annotations driven to ANNOTATED by `self.annotator`."""
        annotations = []
        _prime_fsm(self.annotator)
        for _ in range(count):
            task = TaskFactory(project=self.project, is_labeled=True)
            annotation = AnnotationFactory(
                task=task, project=self.project, completed_by=self.annotator, result=[]
            )
            StateManager.execute_transition(
                entity=annotation, transition_name='assign_annotation', user=self.annotator
            )
            StateManager.execute_transition(
                entity=annotation, transition_name='mark_annotated', user=self.annotator
            )
            annotations.append(annotation)
        return annotations

    def test_flag_off_does_not_route_even_at_threshold(self):
        """Flag-off must be a full no-op so projects that set
        `review_batch_size` but never flipped the feature don't silently change
        behavior (mirrors `is_batch_review_enabled` semantics)."""
        self._make_annotated(count=3)
        with _batch_flag(False):
            routed = route_batch_to_review(self.project, user=self.reviewer)
        assert routed == []

    def test_flag_on_routes_annotated_to_will_reviewed_and_accept_succeeds(self):
        """Full chain: ANNOTATED → (batch route) → WILL_REVIEWED → (accept HTTP
        endpoint) → ACCEPTED. Exercises the actual flag-gated path end-to-end."""
        annotations = self._make_annotated(count=3)

        with _batch_flag(True):
            routed = route_batch_to_review(self.project, user=self.reviewer)

        assert len(routed) == 2
        for aid in routed:
            refreshed = Annotation.objects.get(pk=aid)
            assert refreshed.current_state == AnnotationStateChoices.WILL_REVIEWED

        # Now hit the HTTP accept endpoint on the first routed annotation.
        target = Annotation.objects.get(pk=routed[0])
        self.client.force_authenticate(user=self.reviewer)
        response = self.client.post(
            f'/api/annotations/{target.id}/accept/', data={}, format='json'
        )
        assert response.status_code == 200, response.content
        assert _annotation_state(target) == AnnotationStateChoices.ACCEPTED

        # The un-routed third annotation stays in ANNOTATED.
        untouched_id = {a.id for a in annotations} - set(routed)
        (uid,) = untouched_id
        assert Annotation.objects.get(pk=uid).current_state == AnnotationStateChoices.ANNOTATED

    def test_flag_on_routed_annotation_can_be_rejected_and_reworked(self):
        """Batch-routed annotations participate fully in the reject→rework
        flow — verifies that batch mode doesn't silently skip the
        ReviewerLock/rework side-effects the HTTP endpoint wires up."""
        self._make_annotated(count=2)

        with _batch_flag(True):
            routed = route_batch_to_review(self.project, user=self.reviewer)
        assert len(routed) == 2

        target = Annotation.objects.get(pk=routed[0])
        ReviewerLock.objects.create(
            annotation=target,
            user=self.reviewer,
            expire_at=timezone.now() + timedelta(minutes=30),
        )

        self.client.force_authenticate(user=self.reviewer)
        response = self.client.post(
            f'/api/annotations/{target.id}/reject/',
            data={'comment': 'batch flow reject'},
            format='json',
        )
        assert response.status_code == 200, response.content
        assert _annotation_state(target) == AnnotationStateChoices.REJECTED
        assert not ReviewerLock.objects.filter(annotation=target).exists()

        _prime_fsm(self.annotator)
        child = rework_annotation(target, user=self.annotator)
        assert child.parent_annotation_id == target.id
        child.refresh_from_db()
        assert child.current_state == AnnotationStateChoices.ASSIGNED

    def test_flag_on_without_batch_size_is_still_a_noop(self):
        """If the project never opted in (`review_batch_size` is None), the
        flag alone shouldn't change behavior — both halves of the gate must
        agree before routing happens."""
        project = ProjectFactory(
            organization=self.org, created_by=self.reviewer, review_batch_size=None
        )
        _prime_fsm(self.annotator)
        for _ in range(3):
            task = TaskFactory(project=project, is_labeled=True)
            annotation = AnnotationFactory(
                task=task, project=project, completed_by=self.annotator, result=[]
            )
            StateManager.execute_transition(
                entity=annotation, transition_name='assign_annotation', user=self.annotator
            )
            StateManager.execute_transition(
                entity=annotation, transition_name='mark_annotated', user=self.annotator
            )

        with _batch_flag(True):
            routed = route_batch_to_review(project, user=self.reviewer)
        assert routed == []
