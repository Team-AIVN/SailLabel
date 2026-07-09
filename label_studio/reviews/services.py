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
    # If the task was already reviewed (accepted/rejected/fixed) or is awaiting review,
    # a new revision must go back to the reviewer regardless of the sampling strategy —
    # otherwise RANDOM_SAMPLING could roll NOT_SELECTED and let unreviewed rework settle
    # (and get paid). Only truly first-time selection uses the strategy.
    reviewed_states = {
        Task.ReviewStatus.PENDING,
        Task.ReviewStatus.ACCEPTED,
        Task.ReviewStatus.REJECTED,
        Task.ReviewStatus.FIXED_AND_ACCEPTED,
    }
    current = Task.objects.filter(pk=annotation.task_id).values_list('review_status', flat=True).first()
    if current in reviewed_states:
        Task.objects.filter(pk=annotation.task_id).update(review_status=Task.ReviewStatus.PENDING)
        return True

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


def on_annotation_updated(annotation):
    """A labeler edited an already-reviewed annotation.

    Editing an accepted or rejected revision invalidates that decision, so the revision
    is put back to COMPLETED and re-run through review selection (returning it to the
    reviewer's queue). Reviewer-authored revisions are new annotations (create path),
    so they are not affected here.
    """
    if annotation.was_cancelled:
        return
    if annotation.status in (Annotation.Status.APPROVED, Annotation.Status.REWORK_REQUIRED):
        # Only release the review when the labeler actually changed the result. A
        # metadata-only / bulk save (same result) must not undo an accepted decision.
        prev = getattr(annotation, '_prev_result', None)
        if prev == annotation.result:
            return
        Annotation.objects.filter(pk=annotation.pk).update(status=Annotation.Status.COMPLETED)
        annotation.status = Annotation.Status.COMPLETED
        # Edited revision goes back to the reviewer's queue regardless of the project's
        # auto-selection strategy (this project reviews manually with strategy=NONE).
        Task.objects.filter(pk=annotation.task_id).update(
            review_status=Task.ReviewStatus.PENDING,
            is_labeled=True,
        )
        # Log the edit as a timeline event (task went back to pending), unless the last
        # event was already a resubmit — so repeated edits don't pile up rows.
        last = Review.objects.filter(annotation=annotation).order_by('-created_at', '-id').first()
        if not (last and last.decision == Review.Decision.RESUBMITTED):
            Review.objects.create(
                annotation=annotation,
                project=annotation.project,
                reviewer=None,
                decision=Review.Decision.RESUBMITTED,
                comment='',
                stage=1,
            )


# --- review actions ----------------------------------------------------------


def _record_review(annotation, reviewer, decision, comment='', stage=1):
    """Record a review decision as a new timeline entry (newest first).

    Every distinct action stacks as its own row — two Fix+Accepts with different
    corrections are two rows, a reject-with-reason then a later accept are two rows.
    Only an immediate exact duplicate is skipped (see below).
    """
    comment = comment or ''
    latest = Review.objects.filter(annotation=annotation, reviewer=reviewer, stage=stage).order_by('-id').first()
    # Only an immediate EXACT duplicate (same decision AND identical comment) is skipped,
    # so an accidental double-click of Accept doesn't pile up. Anything with different
    # content (a new fix summary, a different reject reason) stacks as a new row.
    if latest and latest.decision == decision and (latest.comment or '') == comment:
        return latest
    return Review.objects.create(
        annotation=annotation,
        project=annotation.project,
        reviewer=reviewer,
        decision=decision,
        comment=comment,
        stage=stage,
    )


@transaction.atomic
def accept(annotation, reviewer, comment='', stage=1):
    # Lock the task so two reviewers can't accept/reject the same task concurrently and
    # leave contradictory rows / a decision racing a labeler edit.
    Task.objects.select_for_update().filter(pk=annotation.task_id).first()
    review = _record_review(annotation, reviewer, Review.Decision.ACCEPT, comment=comment, stage=stage)
    Annotation.objects.filter(pk=annotation.pk).update(status=Annotation.Status.APPROVED)
    Task.objects.filter(pk=annotation.task_id).update(review_status=Task.ReviewStatus.ACCEPTED)
    return review


@transaction.atomic
def reject(annotation, reviewer, comment='', stage=1):
    Task.objects.select_for_update().filter(pk=annotation.task_id).first()
    review = _record_review(annotation, reviewer, Review.Decision.REJECT, comment=comment, stage=stage)
    # Mark the current revision as needing rework and return the task to the
    # annotator's queue (is_labeled=False makes it eligible for next-task again).
    Annotation.objects.filter(pk=annotation.pk).update(status=Annotation.Status.REWORK_REQUIRED)
    Task.objects.filter(pk=annotation.task_id).update(
        review_status=Task.ReviewStatus.REJECTED,
        is_labeled=False,
    )
    return review


def _choice_display(parsed_config, from_name, saved_value):
    """Map a saved choice value (its alias, e.g. PORT) to the displayed label
    (e.g. 좌현 변침) using the project's parsed config."""
    field = (parsed_config or {}).get(from_name) or {}
    attrs = field.get('labels_attrs') or {}
    return (attrs.get(saved_value) or {}).get('value') or saved_value


def _field_label(parsed_config, from_name):
    """Human field label (from the associated Text tag) or the raw from_name."""
    field = (parsed_config or {}).get(from_name) or {}
    inputs = field.get('inputs') or []
    return (inputs[0].get('value') if inputs else None) or from_name


def _result_field_map(result, parsed_config=None):
    """Flatten an annotation result into {from_name: human-readable value}."""
    out = {}
    for r in result or []:
        if not isinstance(r, dict):
            continue
        from_name = r.get('from_name', '?')
        value = r.get('value', {})
        if 'choices' in value:
            shown = ', '.join(_choice_display(parsed_config, from_name, c) for c in (value.get('choices') or []))
        elif 'text' in value:
            text = value.get('text')
            shown = ' '.join(text) if isinstance(text, list) else str(text)
        else:
            shown = str(value)
        out[from_name] = shown
    return out


def build_fix_summary(original, corrected, parsed_config=None):
    """Readable field-level summary of what the reviewer changed (old -> new).

    When the project's parsed config is supplied, field names and choice values are
    shown with their human labels (e.g. "권고 조종 방향: 좌현 변침 → 우현 변침").
    """
    before = _result_field_map(original, parsed_config)
    after = _result_field_map(corrected, parsed_config)
    keys = list(dict.fromkeys(list(before.keys()) + list(after.keys())))
    lines = []
    for k in keys:
        b = before.get(k, '(없음)')
        a = after.get(k, '(없음)')
        if b != a:
            lines.append(f'{_field_label(parsed_config, k)}: {b or "(없음)"} → {a or "(없음)"}')
    if not lines:
        return '[수정 후 승인] 변경 없음'
    return '[수정 후 승인]\n' + '\n'.join(lines)


@transaction.atomic
def fix_and_accept(annotation, reviewer, content=None, comment='', stage=1):
    """Apply the reviewer's correction to the annotation in place and approve it.

    The correction overwrites the reviewed revision so the task keeps a SINGLE
    annotation (no confusing second tab in the editor). What the reviewer changed is
    preserved as a field-level summary in the review record for audit. ``.update()``
    is used so this does not re-fire the annotation post_save signal.
    """
    corrected = content if content is not None else annotation.result
    # Field-level change summary (with human labels), captured before overwrite.
    try:
        parsed = annotation.project.get_parsed_config()
    except Exception:
        parsed = None
    summary = build_fix_summary(annotation.result, corrected, parsed)
    Annotation.objects.filter(pk=annotation.pk).update(result=corrected, status=Annotation.Status.APPROVED)
    annotation.result = corrected
    annotation.status = Annotation.Status.APPROVED
    review = _record_review(annotation, reviewer, Review.Decision.FIX_AND_ACCEPT, comment=summary, stage=stage)
    Task.objects.filter(pk=annotation.task_id).update(
        review_status=Task.ReviewStatus.FIXED_AND_ACCEPTED,
        current_annotation=annotation,
    )
    return review, annotation


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
