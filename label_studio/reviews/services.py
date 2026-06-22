"""Annotation review workflow services.

Review runs as a workflow *inside* a project (no separate review project). Annotations
form a linear revision chain per task; ``Task.current_annotation`` points at the latest
revision. Reviews attach to annotation revisions so history is fully auditable.
"""

import logging
import random

from django.db import transaction
from django.db.models import Max
from projects.models import Project
from rest_framework.exceptions import ValidationError
from tasks.models import Annotation, Task

from .models import Review

logger = logging.getLogger(__name__)

# The Review table itself (reviewer, decision, comment, stage, created_at) plus the
# preserved Annotation revision chain are the auditable review history required by spec.


# --- revision tracking -------------------------------------------------------


def assign_revision(annotation):
    """Stamp the annotation's version and point its task at it as the current revision.

    Uses .update() so it does not re-trigger the Annotation post_save signal.
    """
    task_id = annotation.task_id
    highest = (
        Annotation.objects.filter(task_id=task_id).exclude(pk=annotation.pk).aggregate(m=Max('version'))['m'] or 0
    )
    version = highest + 1
    Annotation.objects.filter(pk=annotation.pk).update(version=version)
    annotation.version = version
    Task.objects.filter(pk=task_id).update(current_annotation=annotation)


def _custom_rule_selects(annotation):
    """Extensible hook for CUSTOM_RULE selection. No-op default (selects nothing)."""
    return False


def apply_review_selection(annotation):
    """Select (or not) the task's current annotation for review per the project strategy.

    Returns True if the annotation was selected (task.review_status set to PENDING).
    """
    project = annotation.project
    strategy = project.review_strategy
    select = False
    if strategy == Project.ReviewStrategy.FULL_REVIEW:
        select = True
    elif strategy == Project.ReviewStrategy.RANDOM_SAMPLING:
        select = random.random() < (project.review_ratio or 0.0)
    elif strategy == Project.ReviewStrategy.CUSTOM_RULE:
        select = _custom_rule_selects(annotation)
    new_status = Task.ReviewStatus.PENDING if select else Task.ReviewStatus.NOT_SELECTED
    Task.objects.filter(pk=annotation.task_id).update(review_status=new_status)
    return select


def on_annotation_created(annotation):
    """Signal handler body (create-only): set revision pointers and run review selection.

    Only freshly created COMPLETED annotations (annotator submissions) are eligible for
    selection; reviewer-authored APPROVED revisions (fix-and-accept) update the pointers
    but keep the review status set by the review action.
    """
    if annotation.was_cancelled:
        return
    assign_revision(annotation)
    if annotation.status == Annotation.Status.COMPLETED:
        apply_review_selection(annotation)


# --- review actions ----------------------------------------------------------


@transaction.atomic
def accept(annotation, reviewer, comment='', stage=1):
    review = Review.objects.create(
        annotation=annotation,
        project=annotation.project,
        reviewer=reviewer,
        decision=Review.Decision.ACCEPT,
        comment=comment or '',
        stage=stage,
    )
    Annotation.objects.filter(pk=annotation.pk).update(status=Annotation.Status.APPROVED)
    Task.objects.filter(pk=annotation.task_id).update(review_status=Task.ReviewStatus.ACCEPTED)
    return review


@transaction.atomic
def reject(annotation, reviewer, comment='', stage=1):
    review = Review.objects.create(
        annotation=annotation,
        project=annotation.project,
        reviewer=reviewer,
        decision=Review.Decision.REJECT,
        comment=comment or '',
        stage=stage,
    )
    # Mark the current revision as needing rework and return the task to the
    # annotator's queue (is_labeled=False makes it eligible for next-task again).
    Annotation.objects.filter(pk=annotation.pk).update(status=Annotation.Status.REWORK_REQUIRED)
    Task.objects.filter(pk=annotation.task_id).update(
        review_status=Task.ReviewStatus.REJECTED,
        is_labeled=False,
    )
    return review


@transaction.atomic
def fix_and_accept(annotation, reviewer, content=None, comment='', stage=1):
    """Create a new revision authored by the reviewer and approve it.

    Previous revisions are preserved; the new revision becomes the task's current
    annotation. The review is recorded against the revision that was reviewed.
    """
    task = annotation.task
    new_revision = Annotation.objects.create(
        task=task,
        project=annotation.project,
        completed_by=reviewer,
        result=content if content is not None else annotation.result,
        parent_annotation=annotation,
        status=Annotation.Status.APPROVED,
    )
    # Point the task at the new revision and stamp its version explicitly. The post_save
    # signal does this for review-enabled projects, but not for review_strategy=NONE
    # projects (where the signal is not connected), so do it here to be self-sufficient.
    assign_revision(new_revision)
    review = Review.objects.create(
        annotation=annotation,
        project=annotation.project,
        reviewer=reviewer,
        decision=Review.Decision.FIX_AND_ACCEPT,
        comment=comment or '',
        stage=stage,
    )
    Task.objects.filter(pk=task.pk).update(review_status=Task.ReviewStatus.FIXED_AND_ACCEPTED)
    return review, new_revision


def review_annotation(annotation, reviewer, decision, comment='', content=None, stage=1):
    """Dispatch a review decision to the matching workflow."""
    if decision == Review.Decision.ACCEPT:
        return accept(annotation, reviewer, comment=comment, stage=stage)
    if decision == Review.Decision.REJECT:
        return reject(annotation, reviewer, comment=comment, stage=stage)
    if decision == Review.Decision.FIX_AND_ACCEPT:
        review, _ = fix_and_accept(annotation, reviewer, content=content, comment=comment, stage=stage)
        return review
    raise ValidationError(f'Unknown review decision: {decision}')


# --- progress ----------------------------------------------------------------


def annotation_progress(project):
    """Percent of tasks whose current annotation is APPROVED (incl. fix-and-accept)."""
    total = Task.objects.filter(project=project).count()
    if not total:
        return 0
    approved = Task.objects.filter(
        project=project, current_annotation__status=Annotation.Status.APPROVED
    ).count()
    return round(approved / total * 100)


def review_progress(project):
    """Percent of review-selected tasks that have a final review decision."""
    base = Task.objects.filter(project=project).exclude(review_status=Task.ReviewStatus.NOT_SELECTED)
    selected = base.count()
    if not selected:
        return 0
    reviewed = base.filter(
        review_status__in=[
            Task.ReviewStatus.ACCEPTED,
            Task.ReviewStatus.REJECTED,
            Task.ReviewStatus.FIXED_AND_ACCEPTED,
        ]
    ).count()
    return round(reviewed / selected * 100)
