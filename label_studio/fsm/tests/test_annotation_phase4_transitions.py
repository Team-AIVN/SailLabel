"""Phase 4A tests — explicit annotation pipeline transitions.

These cover the five transitions registered in `fsm/annotation_transitions.py`:
`assign_annotation`, `mark_annotated`, `move_to_review`, `accept_annotation`,
`reject_annotation`.

The transitions are explicit (both `triggers_on_create` and
`triggers_on_update` are False), so they only fire via direct
`StateManager.execute_transition()` calls — never on plain `.save()`. These
tests exercise that contract and verify the `Annotation.current_state`
denormalized column stays in sync with the FSM history tail.
"""

import pytest  # type: ignore[import]
from core.current_request import CurrentContext
from fsm.state_choices import AnnotationStateChoices
from fsm.state_manager import StateManager
from tasks.models import Annotation
from tasks.tests.factories import AnnotationFactory

pytestmark = pytest.mark.django_db


def _prime_fsm(user):
    """Set up CurrentContext so FSM transitions execute in tests."""
    CurrentContext.clear()
    CurrentContext.set_user(user)


def _current_state(annotation: Annotation) -> str:
    annotation.refresh_from_db(fields=['current_state'])
    return annotation.current_state


def _run(annotation, transition_name, user):
    StateManager.execute_transition(
        entity=annotation, transition_name=transition_name, user=user
    )


def test_assign_annotation_sets_state_and_column():
    annotation = AnnotationFactory()
    _prime_fsm(annotation.completed_by)

    _run(annotation, 'assign_annotation', user=annotation.completed_by)

    assert StateManager.get_current_state_value(annotation) == AnnotationStateChoices.ASSIGNED
    assert _current_state(annotation) == AnnotationStateChoices.ASSIGNED


def test_mark_annotated_after_assign():
    annotation = AnnotationFactory()
    user = annotation.completed_by
    _prime_fsm(user)

    _run(annotation, 'assign_annotation', user=user)
    _run(annotation, 'mark_annotated', user=user)

    assert StateManager.get_current_state_value(annotation) == AnnotationStateChoices.ANNOTATED
    assert _current_state(annotation) == AnnotationStateChoices.ANNOTATED


def test_move_to_review_from_annotated():
    annotation = AnnotationFactory()
    user = annotation.completed_by
    _prime_fsm(user)

    _run(annotation, 'assign_annotation', user=user)
    _run(annotation, 'mark_annotated', user=user)
    _run(annotation, 'move_to_review', user=user)

    assert StateManager.get_current_state_value(annotation) == AnnotationStateChoices.WILL_REVIEWED
    assert _current_state(annotation) == AnnotationStateChoices.WILL_REVIEWED


def test_accept_annotation_flips_ground_truth_and_clears_siblings():
    annotation = AnnotationFactory()
    task = annotation.task
    sibling = AnnotationFactory(task=task, project=task.project, ground_truth=True)

    user = annotation.completed_by
    _prime_fsm(user)

    _run(annotation, 'move_to_review', user=user)
    _run(annotation, 'accept_annotation', user=user)

    annotation.refresh_from_db()
    sibling.refresh_from_db()

    assert StateManager.get_current_state_value(annotation) == AnnotationStateChoices.ACCEPTED
    assert annotation.current_state == AnnotationStateChoices.ACCEPTED
    assert annotation.ground_truth is True
    # Sibling's ground_truth must have been cleared — only one GT per task.
    assert sibling.ground_truth is False


def test_reject_annotation_clears_ground_truth():
    annotation = AnnotationFactory(ground_truth=True)
    user = annotation.completed_by
    _prime_fsm(user)

    _run(annotation, 'move_to_review', user=user)
    _run(annotation, 'reject_annotation', user=user)

    annotation.refresh_from_db()

    assert StateManager.get_current_state_value(annotation) == AnnotationStateChoices.REJECTED
    assert annotation.current_state == AnnotationStateChoices.REJECTED
    assert annotation.ground_truth is False


def test_rework_chain_reassigns_child_annotation():
    """Rejection → create a child annotation linked via parent_annotation →
    re-run `assign_annotation` on the child to close the rework loop."""
    parent = AnnotationFactory()
    user = parent.completed_by
    _prime_fsm(user)

    _run(parent, 'move_to_review', user=user)
    _run(parent, 'reject_annotation', user=user)

    child = AnnotationFactory(
        task=parent.task,
        project=parent.project,
        completed_by=user,
        parent_annotation=parent,
    )
    _run(child, 'assign_annotation', user=user)

    parent.refresh_from_db()
    child.refresh_from_db()

    assert parent.current_state == AnnotationStateChoices.REJECTED
    assert child.current_state == AnnotationStateChoices.ASSIGNED
    assert child.parent_annotation_id == parent.id


def test_pipeline_transitions_do_not_auto_fire_on_save():
    """Explicit transitions must stay dormant on plain .save() — only the
    pre-existing AnnotationCreatedTransition should produce a state record."""
    annotation = AnnotationFactory()
    _prime_fsm(annotation.completed_by)

    # At this point `annotation` was created, so the legacy CREATED transition
    # may have fired. current_state should NOT be set to any of the new
    # pipeline states since no explicit transition ran.
    assert _current_state(annotation) is None
