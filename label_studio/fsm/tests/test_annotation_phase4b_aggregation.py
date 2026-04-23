"""Phase 4B tests — task / project aggregation driven by annotation hooks.

Covers the aggregate transitions added in Phase 4B:

- `task_accepted` when any annotation on a task is accepted
- `task_rejected` when *every* annotation on a task is rejected
- `project_can_reviewed` when `batch_review.project_can_be_reviewed()` opens
  (classic mode: all tasks `is_labeled`; batch mode: threshold met)
- `rework_annotation(parent, user)` helper spawns an `ASSIGNED` child
"""

from unittest import mock

import pytest  # type: ignore[import]
from core.current_request import CurrentContext
from fsm.annotation_transitions import rework_annotation
from fsm.state_choices import (
    AnnotationStateChoices,
    ProjectStateChoices,
    TaskStateChoices,
)
from fsm.state_manager import StateManager
from projects.tests.factories import ProjectFactory
from tasks.models import Annotation
from tasks.tests.factories import AnnotationFactory, TaskFactory

pytestmark = pytest.mark.django_db


def _prime_fsm(user):
    CurrentContext.clear()
    CurrentContext.set_user(user)


def _flag(on: bool):
    """Context manager that forces `fflag_batch_review` on/off."""
    return mock.patch(
        'fsm.batch_review.flag_set',
        side_effect=lambda name, **kw: on if name == 'fflag_batch_review' else False,
    )


def _run(entity, transition_name, user):
    StateManager.execute_transition(entity=entity, transition_name=transition_name, user=user)


def _drive_to_will_reviewed(annotation, user):
    """Walk an annotation through assign → annotated → will_reviewed."""
    _run(annotation, 'assign_annotation', user)
    _run(annotation, 'mark_annotated', user)
    _run(annotation, 'move_to_review', user)


# ---------------------------------------------------------------------------
# Task aggregation — accept
# ---------------------------------------------------------------------------


def test_task_accepted_on_first_accept():
    annotation = AnnotationFactory()
    task = annotation.task
    user = annotation.completed_by
    _prime_fsm(user)

    _drive_to_will_reviewed(annotation, user)
    _run(annotation, 'accept_annotation', user)

    assert StateManager.get_current_state_value(task) == TaskStateChoices.ACCEPTED


def test_task_accepted_even_when_siblings_pending():
    """A single accept is enough to mark the task accepted, regardless of
    sibling state."""
    annotation = AnnotationFactory()
    task = annotation.task
    AnnotationFactory(task=task, project=task.project)  # sibling stays pre-pipeline
    user = annotation.completed_by
    _prime_fsm(user)

    _drive_to_will_reviewed(annotation, user)
    _run(annotation, 'accept_annotation', user)

    assert StateManager.get_current_state_value(task) == TaskStateChoices.ACCEPTED


# ---------------------------------------------------------------------------
# Task aggregation — reject
# ---------------------------------------------------------------------------


def test_task_not_rejected_when_sibling_still_pending():
    """A pending sibling (no current_state yet) blocks task REJECTED."""
    annotation = AnnotationFactory()
    task = annotation.task
    # Sibling has no current_state — it's in the pre-pipeline legacy CREATED.
    AnnotationFactory(task=task, project=task.project)
    user = annotation.completed_by
    _prime_fsm(user)

    _drive_to_will_reviewed(annotation, user)
    _run(annotation, 'reject_annotation', user)

    assert StateManager.get_current_state_value(task) != TaskStateChoices.REJECTED


def test_task_rejected_when_all_siblings_rejected():
    annotation = AnnotationFactory()
    task = annotation.task
    sibling = AnnotationFactory(task=task, project=task.project)
    user = annotation.completed_by
    _prime_fsm(user)

    _drive_to_will_reviewed(annotation, user)
    _drive_to_will_reviewed(sibling, user)

    _run(annotation, 'reject_annotation', user)
    # After the first reject, sibling is still WILL_REVIEWED → task NOT rejected.
    assert StateManager.get_current_state_value(task) != TaskStateChoices.REJECTED

    _run(sibling, 'reject_annotation', user)
    # Now all annotations on the task are REJECTED.
    assert StateManager.get_current_state_value(task) == TaskStateChoices.REJECTED


def test_task_not_rejected_when_one_accepted_one_rejected():
    accepted = AnnotationFactory()
    task = accepted.task
    rejected = AnnotationFactory(task=task, project=task.project)
    user = accepted.completed_by
    _prime_fsm(user)

    _drive_to_will_reviewed(accepted, user)
    _drive_to_will_reviewed(rejected, user)

    _run(accepted, 'accept_annotation', user)
    _run(rejected, 'reject_annotation', user)

    # ACCEPTED sibling keeps the task alive.
    assert StateManager.get_current_state_value(task) != TaskStateChoices.REJECTED
    # …and the earlier accept already moved the task to ACCEPTED.
    assert StateManager.get_current_state_value(task) == TaskStateChoices.ACCEPTED


# ---------------------------------------------------------------------------
# Project aggregation — can-review gate
# ---------------------------------------------------------------------------


def test_project_can_reviewed_in_classic_mode_when_all_tasks_labeled():
    """Classic mode (no batch size): fires once every task is `is_labeled`."""
    user = AnnotationFactory().completed_by
    project = ProjectFactory(review_batch_size=None, created_by=user)
    _prime_fsm(user)

    task = TaskFactory(project=project, is_labeled=True)
    annotation = AnnotationFactory(task=task, project=project, completed_by=user, result=[])

    _run(annotation, 'assign_annotation', user)
    with _flag(False):
        _run(annotation, 'mark_annotated', user)

    assert StateManager.get_current_state_value(project) == ProjectStateChoices.CAN_REVIEWED


def test_project_stays_put_when_classic_gate_not_met():
    user = AnnotationFactory().completed_by
    project = ProjectFactory(review_batch_size=None, created_by=user)
    _prime_fsm(user)

    # One unlabeled task in the project keeps the classic gate closed.
    TaskFactory(project=project, is_labeled=False)
    labeled_task = TaskFactory(project=project, is_labeled=True)
    annotation = AnnotationFactory(task=labeled_task, project=project, completed_by=user)

    _run(annotation, 'assign_annotation', user)
    with _flag(False):
        _run(annotation, 'mark_annotated', user)

    assert StateManager.get_current_state_value(project) != ProjectStateChoices.CAN_REVIEWED


def test_project_can_reviewed_in_batch_mode_when_threshold_met():
    """Batch mode: flag on + threshold met → project opens even though
    not every task is labeled."""
    user = AnnotationFactory().completed_by
    project = ProjectFactory(review_batch_size=2, created_by=user)
    _prime_fsm(user)

    a1 = AnnotationFactory(task=TaskFactory(project=project), project=project, completed_by=user)
    a2 = AnnotationFactory(task=TaskFactory(project=project), project=project, completed_by=user)

    _run(a1, 'assign_annotation', user)
    _run(a2, 'assign_annotation', user)

    with _flag(True):
        _run(a1, 'mark_annotated', user)
        assert StateManager.get_current_state_value(project) != ProjectStateChoices.CAN_REVIEWED

        _run(a2, 'mark_annotated', user)
        assert StateManager.get_current_state_value(project) == ProjectStateChoices.CAN_REVIEWED


def test_project_stays_put_below_batch_threshold():
    user = AnnotationFactory().completed_by
    project = ProjectFactory(review_batch_size=3, created_by=user)
    _prime_fsm(user)

    a1 = AnnotationFactory(task=TaskFactory(project=project), project=project, completed_by=user)
    _run(a1, 'assign_annotation', user)

    with _flag(True):
        _run(a1, 'mark_annotated', user)

    assert StateManager.get_current_state_value(project) != ProjectStateChoices.CAN_REVIEWED


# ---------------------------------------------------------------------------
# rework_annotation helper
# ---------------------------------------------------------------------------


def test_rework_annotation_creates_assigned_child():
    parent = AnnotationFactory()
    user = parent.completed_by
    _prime_fsm(user)

    _drive_to_will_reviewed(parent, user)
    _run(parent, 'reject_annotation', user)

    child = rework_annotation(parent, user=user)

    assert isinstance(child, Annotation)
    assert child.parent_annotation_id == parent.id
    assert child.task_id == parent.task_id
    assert child.project_id == parent.project_id
    assert child.current_state == AnnotationStateChoices.ASSIGNED
    assert StateManager.get_current_state_value(child) == AnnotationStateChoices.ASSIGNED

    # Parent stays in its terminal REJECTED state.
    parent.refresh_from_db()
    assert parent.current_state == AnnotationStateChoices.REJECTED
