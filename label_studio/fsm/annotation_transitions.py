"""
FSM Transitions for Annotation model.

This module defines declarative transitions for the Annotation entity.
Annotation transitions can update related task states via post_transition_hooks.
"""

import logging
from typing import Any, Dict, Optional

from django.db import transaction
from fsm.registry import register_state_transition
from fsm.state_choices import AnnotationStateChoices
from fsm.transitions import ModelChangeTransition, StateModelType, TransitionContext

# Task / Project aggregator helpers live in sibling modules; imported lazily
# inside hooks to avoid circular-import churn at module load time.

logger = logging.getLogger(__name__)


def _sync_current_state(annotation, target_state: str) -> None:
    """Mirror the latest FSM state onto the denormalized `current_state` column.

    Writes via `queryset.update()` so we bypass `FsmHistoryStateModel.save()`
    and don't re-trigger a transition cascade on the annotation row itself.
    The in-memory instance is refreshed too so callers see the new value.
    """
    type(annotation).objects.filter(pk=annotation.pk).update(current_state=target_state)
    annotation.current_state = target_state


@register_state_transition('annotation', 'annotation_created', triggers_on_create=True, triggers_on_update=False)
class AnnotationCreatedTransition(ModelChangeTransition):
    """
    Transition when an annotation is created.

    This is the default transition for newly created annotations.

    Trigger: Automatically on creation only (triggers_on_create=True, triggers_on_update=False)
    """

    def get_target_state(self, context: Optional[TransitionContext] = None) -> str:
        return AnnotationStateChoices.CREATED

    def get_reason(self, context: TransitionContext) -> str:
        """Return detailed reason for annotation creation."""
        return 'Annotation created'

    def transition(self, context: TransitionContext) -> Dict[str, Any]:
        """Execute annotation submission transition."""
        annotation = context.entity

        return {
            'task_id': annotation.task_id,
            'project_id': annotation.project_id,
            'completed_by_id': annotation.completed_by_id,
            'lead_time': annotation.lead_time,
        }

    def post_transition_hook(self, context: TransitionContext, state_record: StateModelType) -> None:
        """
        Post-transition hook for annotation creation.

        Updates task state to COMPLETED when annotation is created.
        Then updates project state based on task completion status.
        Handles "cold start" scenarios where task may not have state record yet.
        """
        from fsm.project_transitions import update_project_state_after_task_change
        from fsm.state_choices import TaskStateChoices
        from fsm.state_manager import StateManager
        from fsm.utils import get_or_initialize_state

        annotation = context.entity
        task = annotation.task
        project = annotation.project

        # Get current task state (initialize if needed)
        current_task_state = StateManager.get_current_state_value(task)

        if current_task_state is None:
            # Task has no state record - initialize it
            # Since annotation was just created, task should be COMPLETED
            current_task_state = get_or_initialize_state(
                task, user=context.current_user, inferred_state=TaskStateChoices.COMPLETED
            )

        # Transition task to COMPLETED if not already
        if current_task_state != TaskStateChoices.COMPLETED:
            StateManager.execute_transition(entity=task, transition_name='task_completed', user=context.current_user)

        # Update project state based on task changes
        update_project_state_after_task_change(project, user=context.current_user)


@register_state_transition(
    'annotation', 'annotation_updated', triggers_on_create=False, triggers_on_update=True, force_state_record=True
)
class AnnotationUpdatedTransition(ModelChangeTransition):
    """
    Transition when an annotation is updated.

    Updates keep the annotation in CREATED state but create audit trail records.

    Trigger: On update (triggers_on_create=False, triggers_on_update=True, force_state_record=True)
    """

    def get_target_state(self, context: Optional[TransitionContext] = None) -> str:
        return AnnotationStateChoices.CREATED

    def get_reason(self, context: TransitionContext) -> str:
        """Return detailed reason for annotation update."""
        return 'Annotation updated'

    def transition(self, context: TransitionContext) -> Dict[str, Any]:
        """Execute annotation update transition."""
        annotation = context.entity

        return {
            'task_id': annotation.task_id,
            'project_id': annotation.project_id,
            'updated_by_id': getattr(annotation, 'updated_by_id', None),
            'changed_fields': list(self.changed_fields.keys()) if self.changed_fields else [],
        }

    def post_transition_hook(self, context: TransitionContext, state_record: StateModelType) -> None:
        """Post-transition hook for annotation updates."""
        pass


# ---------------------------------------------------------------------------
# Phase 4 pipeline transitions
#
# These are explicit transitions triggered from API endpoints / service code
# via `StateManager.execute_transition(entity=annotation, transition_name=...)`.
# `triggers_on_create=False` and `triggers_on_update=False` keep them out of
# the save-time auto-discovery path — the only way they fire is by explicit
# call, which matches the annotator/reviewer action model.
# ---------------------------------------------------------------------------


class _PipelineTransition(ModelChangeTransition):
    """Shared scaffolding for the Phase 4 explicit annotation transitions.

    Subclasses set `target` on the class; the pre/post hooks mirror the state
    onto `Annotation.current_state` so list/aggregate queries stay JOIN-free.
    """

    target: str = ''  # Overridden by subclasses.

    def get_target_state(self, context: Optional[TransitionContext] = None) -> str:
        return self.target

    def transition(self, context: TransitionContext) -> Dict[str, Any]:
        annotation = context.entity
        return {
            'task_id': annotation.task_id,
            'project_id': annotation.project_id,
            'completed_by_id': annotation.completed_by_id,
            'parent_annotation_id': annotation.parent_annotation_id,
        }

    def post_transition_hook(self, context: TransitionContext, state_record: StateModelType) -> None:
        _sync_current_state(context.entity, self.target)


@register_state_transition(
    'annotation', 'assign_annotation', triggers_on_create=False, triggers_on_update=False
)
class AssignAnnotationTransition(_PipelineTransition):
    """Assign (or reassign) an annotation to its annotator.

    Entry point for the `uploaded → assigned` edge and for the rework loop
    `rejected → assigned` (in which case a child annotation is created by the
    caller with `parent_annotation=<rejected one>` first).
    """

    target: str = AnnotationStateChoices.ASSIGNED

    def get_reason(self, context: TransitionContext) -> str:
        return 'Annotation assigned to annotator'


@register_state_transition(
    'annotation', 'mark_annotated', triggers_on_create=False, triggers_on_update=False
)
class MarkAnnotatedTransition(_PipelineTransition):
    """Annotator has finished labeling — moves `assigned → annotated`.

    Post-hook opens the `project_can_reviewed` gate when
    `batch_review.project_can_be_reviewed()` reports ready (classic all-tasks
    mode or batch-threshold mode). StateManager's same-state guard makes the
    project transition idempotent.
    """

    target: str = AnnotationStateChoices.ANNOTATED

    def get_reason(self, context: TransitionContext) -> str:
        return 'Annotator submitted annotation'

    def post_transition_hook(self, context: TransitionContext, state_record: StateModelType) -> None:
        from fsm.batch_review import project_can_be_reviewed
        from fsm.state_manager import StateManager

        annotation = context.entity
        _sync_current_state(annotation, self.target)

        project = annotation.project
        if project is None:
            return
        if project_can_be_reviewed(project, user=context.current_user):
            StateManager.execute_transition(
                entity=project,
                transition_name='project_can_reviewed',
                user=context.current_user,
            )


@register_state_transition(
    'annotation', 'move_to_review', triggers_on_create=False, triggers_on_update=False
)
class MoveToReviewTransition(_PipelineTransition):
    """Task routed to a reviewer — moves `annotated → will_reviewed`."""

    target: str = AnnotationStateChoices.WILL_REVIEWED

    def get_reason(self, context: TransitionContext) -> str:
        return 'Annotation routed to reviewer queue'


@register_state_transition(
    'annotation', 'accept_annotation', triggers_on_create=False, triggers_on_update=False
)
class AcceptAnnotationTransition(_PipelineTransition):
    """Reviewer accepts the annotation.

    Flips `ground_truth=True` on this annotation and clears it on every sibling
    so the "one ground truth per task" invariant (enforced elsewhere by
    `Task._update_ground_truth`) stays intact.
    """

    target: str = AnnotationStateChoices.ACCEPTED

    def get_reason(self, context: TransitionContext) -> str:
        return 'Reviewer accepted annotation'

    def post_transition_hook(self, context: TransitionContext, state_record: StateModelType) -> None:
        from fsm.state_manager import StateManager

        annotation = context.entity
        # `queryset.update()` bypasses `FsmHistoryStateModel.save()`, so flipping
        # booleans here will not recurse into `AnnotationUpdatedTransition`.
        with transaction.atomic():
            AnnotationModel = type(annotation)
            AnnotationModel.objects.filter(task_id=annotation.task_id).exclude(
                pk=annotation.pk
            ).update(ground_truth=False)
            AnnotationModel.objects.filter(pk=annotation.pk).update(ground_truth=True)
        annotation.ground_truth = True
        _sync_current_state(annotation, self.target)

        # Task aggregation: at least one ACCEPTED annotation → task ACCEPTED.
        task = annotation.task
        if task is not None:
            StateManager.execute_transition(
                entity=task, transition_name='task_accepted', user=context.current_user
            )


@register_state_transition(
    'annotation', 'reject_annotation', triggers_on_create=False, triggers_on_update=False
)
class RejectAnnotationTransition(_PipelineTransition):
    """Reviewer rejects the annotation.

    Moves the annotation to `REJECTED` and clears its `ground_truth` flag.
    Rework happens in Phase 4B via a signal that creates a child annotation
    with `parent_annotation=<this one>` and re-runs `assign_annotation` on it.
    """

    target: str = AnnotationStateChoices.REJECTED

    def get_reason(self, context: TransitionContext) -> str:
        return 'Reviewer rejected annotation'

    def post_transition_hook(self, context: TransitionContext, state_record: StateModelType) -> None:
        from fsm.state_manager import StateManager

        annotation = context.entity
        type(annotation).objects.filter(pk=annotation.pk).update(ground_truth=False)
        annotation.ground_truth = False
        _sync_current_state(annotation, self.target)

        # Task aggregation: task rejects only when *every* annotation on the
        # task is in REJECTED — a single pending / accepted sibling keeps the
        # task alive. `current_state` is the denormalized Phase 4A column, so
        # we can filter without a join to AnnotationState history.
        task = annotation.task
        if task is None:
            return
        AnnotationModel = type(annotation)
        has_non_rejected = (
            AnnotationModel.objects.filter(task_id=task.id)
            .exclude(current_state=AnnotationStateChoices.REJECTED)
            .exists()
        )
        if not has_non_rejected:
            StateManager.execute_transition(
                entity=task, transition_name='task_rejected', user=context.current_user
            )


# ---------------------------------------------------------------------------
# Rework helper
# ---------------------------------------------------------------------------


def rework_annotation(parent_annotation, user):
    """Spawn a rework child for a `REJECTED` annotation and assign it.

    The review pipeline closes `annotated → will_reviewed → rejected` as a
    terminal path for the rejected annotation itself; rework creates a *new*
    annotation on the same task, links it back via `parent_annotation`, and
    drives it through `assign_annotation` so it re-enters the pipeline in
    `ASSIGNED` state.

    Returns the newly created child annotation.
    """
    from fsm.state_manager import StateManager
    from tasks.models import Annotation

    with transaction.atomic():
        child = Annotation.objects.create(
            task=parent_annotation.task,
            project=parent_annotation.project,
            completed_by=user or parent_annotation.completed_by,
            parent_annotation=parent_annotation,
            result=[],
        )
        StateManager.execute_transition(
            entity=child, transition_name='assign_annotation', user=user
        )
    return child
