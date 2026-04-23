"""Phase 4C tests — `fflag_batch_review` gate and batch routing."""

from unittest import mock

import pytest  # type: ignore[import]
from core.current_request import CurrentContext
from fsm.batch_review import (
    eligible_annotations_for_review,
    is_batch_review_enabled,
    project_can_be_reviewed,
    route_batch_to_review,
)
from fsm.state_choices import AnnotationStateChoices
from fsm.state_manager import StateManager
from projects.tests.factories import ProjectFactory
from tasks.tests.factories import AnnotationFactory, TaskFactory

pytestmark = pytest.mark.django_db


def _prime_fsm(user):
    CurrentContext.clear()
    CurrentContext.set_user(user)


def _flag(on: bool):
    """Context manager that forces `fflag_batch_review` on/off.

    Patches at the consumer module (`fsm.batch_review`) since `flag_set` is
    imported by name there.
    """
    return mock.patch(
        'fsm.batch_review.flag_set',
        side_effect=lambda name, **kw: on if name == 'fflag_batch_review' else False,
    )


def _make_annotated(project, user, count: int):
    """Create `count` ANNOTATED-state annotations in `project`."""
    created = []
    for _ in range(count):
        task = TaskFactory(project=project)
        annotation = AnnotationFactory(task=task, project=project, completed_by=user)
        StateManager.execute_transition(
            entity=annotation, transition_name='mark_annotated', user=user
        )
        created.append(annotation)
    return created


# ---------------------------------------------------------------------------
# is_batch_review_enabled
# ---------------------------------------------------------------------------


def test_batch_review_disabled_when_flag_off():
    project = ProjectFactory(review_batch_size=5)
    with _flag(False):
        assert is_batch_review_enabled(project) is False


def test_batch_review_disabled_when_batch_size_unset():
    project = ProjectFactory(review_batch_size=None)
    with _flag(True):
        assert is_batch_review_enabled(project) is False


def test_batch_review_enabled_with_flag_and_batch_size():
    project = ProjectFactory(review_batch_size=5)
    with _flag(True):
        assert is_batch_review_enabled(project) is True


# ---------------------------------------------------------------------------
# project_can_be_reviewed — classic vs batch mode
# ---------------------------------------------------------------------------


def test_classic_mode_waits_for_all_tasks_labeled():
    """Flag off → fall back to `Project.finished()` semantics."""
    project = ProjectFactory(review_batch_size=None)
    TaskFactory(project=project, is_labeled=False)
    with _flag(False):
        assert project_can_be_reviewed(project) is False


def test_classic_mode_ready_when_all_labeled():
    project = ProjectFactory(review_batch_size=None)
    TaskFactory(project=project, is_labeled=True)
    with _flag(False):
        assert project_can_be_reviewed(project) is True


def test_batch_mode_blocks_below_threshold():
    user = AnnotationFactory().completed_by
    project = ProjectFactory(review_batch_size=3, created_by=user)
    _prime_fsm(user)
    _make_annotated(project, user, count=2)

    with _flag(True):
        assert project_can_be_reviewed(project, user=user) is False


def test_batch_mode_ready_at_threshold():
    user = AnnotationFactory().completed_by
    project = ProjectFactory(review_batch_size=3, created_by=user)
    _prime_fsm(user)
    _make_annotated(project, user, count=3)

    with _flag(True):
        assert project_can_be_reviewed(project, user=user) is True


# ---------------------------------------------------------------------------
# route_batch_to_review
# ---------------------------------------------------------------------------


def test_route_noop_when_flag_off():
    user = AnnotationFactory().completed_by
    project = ProjectFactory(review_batch_size=2, created_by=user)
    _prime_fsm(user)
    _make_annotated(project, user, count=3)

    with _flag(False):
        routed = route_batch_to_review(project, user=user)
    assert routed == []


def test_route_picks_up_to_batch_size():
    user = AnnotationFactory().completed_by
    project = ProjectFactory(review_batch_size=2, created_by=user)
    _prime_fsm(user)
    annotations = _make_annotated(project, user, count=5)

    with _flag(True):
        routed = route_batch_to_review(project, user=user)

    assert len(routed) == 2
    # FIFO — the two oldest annotations should be routed.
    expected = sorted(a.id for a in annotations)[:2]
    assert sorted(routed) == expected

    from tasks.models import Annotation

    for aid in routed:
        anno = Annotation.objects.get(pk=aid)
        assert anno.current_state == AnnotationStateChoices.WILL_REVIEWED


def test_route_returns_empty_when_nothing_eligible():
    user = AnnotationFactory().completed_by
    project = ProjectFactory(review_batch_size=2, created_by=user)
    _prime_fsm(user)
    # No annotations in ANNOTATED state.

    with _flag(True):
        routed = route_batch_to_review(project, user=user)

    assert routed == []


def test_second_call_routes_next_batch():
    """After the first batch is routed, the remaining eligible annotations stay
    in ANNOTATED — a second call should pick them up without overlap."""
    user = AnnotationFactory().completed_by
    project = ProjectFactory(review_batch_size=2, created_by=user)
    _prime_fsm(user)
    _make_annotated(project, user, count=5)

    with _flag(True):
        first = route_batch_to_review(project, user=user)
        second = route_batch_to_review(project, user=user)

    assert len(first) == 2
    assert len(second) == 2
    assert set(first).isdisjoint(set(second))


def test_eligible_queryset_filters_to_annotated_state():
    user = AnnotationFactory().completed_by
    project = ProjectFactory(review_batch_size=10, created_by=user)
    _prime_fsm(user)

    annotated = _make_annotated(project, user, count=2)
    # Another annotation that stays in whatever state (no explicit transition).
    unrelated = AnnotationFactory(
        task=TaskFactory(project=project), project=project, completed_by=user
    )

    eligible_ids = set(eligible_annotations_for_review(project).values_list('id', flat=True))
    assert eligible_ids == {a.id for a in annotated}
    assert unrelated.id not in eligible_ids
