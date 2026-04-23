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
    """
    Core task states for basic Label Studio workflow.
    Simplified states covering the essential task lifecycle:
    - Creation and assignment
    - Annotation work
    - Completion
    """

    # Initial State
    CREATED = 'CREATED', _('Created')

    # Work States
    IN_PROGRESS = 'IN_PROGRESS', _('In Progress')

    # Terminal State
    COMPLETED = 'COMPLETED', _('Completed')


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
    """
    Core project states for basic Label Studio workflow.
    Simplified states covering the essential project lifecycle:
    - Setup and configuration
    - Active work
    - Completion
    """

    # Setup States
    CREATED = 'CREATED', _('Created')

    # Work States
    IN_PROGRESS = 'IN_PROGRESS', _('In Progress')

    # Terminal State
    COMPLETED = 'COMPLETED', _('Completed')
