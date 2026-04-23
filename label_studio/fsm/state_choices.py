"""
FSM state choices registry system.

This module provides the infrastructure for registering and managing
state choices for different entity types in the FSM framework.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from fsm.registry import register_state_choices

"""
Core state choice enums for Label Studio entities.
These enums define the essential states for core Label Studio entities.
"""


@register_state_choices('task')
class TaskStateChoices(models.TextChoices):
    """Task lifecycle states.

    Phase 4B adds the review-aggregation terminals `ACCEPTED` / `REJECTED` per
    §3.4.4: "Annotation 중 하나라도 ACCEPTED → Task accepted, 모두 REJECTED →
    Task rejected". `COMPLETED` is preserved as the pre-review "annotator
    submitted" state since it's wired into AnnotationCreatedTransition.
    """

    # Initial State
    CREATED = 'CREATED', _('Created')

    # Work States
    IN_PROGRESS = 'IN_PROGRESS', _('In Progress')

    # Pre-review completion (annotator submitted at least one annotation)
    COMPLETED = 'COMPLETED', _('Completed')

    # Phase 4B review aggregates
    ACCEPTED = 'ACCEPTED', _('Accepted')
    REJECTED = 'REJECTED', _('Rejected')


@register_state_choices('annotation')
class AnnotationStateChoices(models.TextChoices):
    """Annotation lifecycle states.

    The SailLabel pipeline is `UPLOADED → ASSIGNED → ANNOTATED → WILL_REVIEWED →
    {ACCEPTED | REJECTED}`, with `REJECTED` looping back into `ASSIGNED` on the
    child annotation created during rework (linked via `parent_annotation_id`).

    `CREATED` is retained as a legacy alias so pre-Phase-4 history records and
    the default `AnnotationCreatedTransition` keep working without rewriting
    existing rows.
    """

    # Legacy — kept for back-compat with `AnnotationCreatedTransition` and any
    # AnnotationState rows persisted before Phase 4.
    CREATED = 'CREATED', _('Created')

    # Phase 4 pipeline states
    UPLOADED = 'UPLOADED', _('Uploaded')
    ASSIGNED = 'ASSIGNED', _('Assigned')
    ANNOTATED = 'ANNOTATED', _('Annotated')
    WILL_REVIEWED = 'WILL_REVIEWED', _('Will be reviewed')
    ACCEPTED = 'ACCEPTED', _('Accepted')
    REJECTED = 'REJECTED', _('Rejected')


@register_state_choices('project')
class ProjectStateChoices(models.TextChoices):
    """Project lifecycle states.

    Phase 4B adds `CAN_REVIEWED` — the "reviewers may start" gate fires via
    `batch_review.project_can_be_reviewed()` once either the classic
    all-tasks-labeled condition OR the batch-review threshold is met.
    """

    # Setup States
    CREATED = 'CREATED', _('Created')

    # Work States
    IN_PROGRESS = 'IN_PROGRESS', _('In Progress')

    # Phase 4B review gate
    CAN_REVIEWED = 'CAN_REVIEWED', _('Can be reviewed')

    # Terminal State
    COMPLETED = 'COMPLETED', _('Completed')
