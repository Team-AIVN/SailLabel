"""Batch-review helpers (Phase 4C, gated by `fflag_batch_review`).

Classic Label Studio waits until *every* task in a project is `is_labeled=True`
before reviewers can start — fine for small projects, but a bottleneck once a
project grows into the tens of thousands. The `fflag_batch_review` flag opens
a middle path:

    reviewers can begin once `Project.review_batch_size` annotations are in
    the `ANNOTATED` state.

This module isolates all of the flag / batch logic so callers (review APIs in
Phase 5) can plug in with a single import.

Phase 4C intentionally does *not* wire up post-accept/post-reject task
aggregation — that belongs to Phase 4B. If 4B isn't merged yet, batch review
still works: it just routes annotations into `WILL_REVIEWED`, and the
reviewer endpoints added in Phase 5 will drive `accept_annotation` /
`reject_annotation` on each one.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from core.feature_flags import flag_set
from django.db import transaction
from fsm.state_choices import AnnotationStateChoices
from fsm.state_manager import get_state_manager

logger = logging.getLogger(__name__)

FEATURE_FLAG = 'fflag_batch_review'


def is_batch_review_enabled(project, user=None) -> bool:
    """True when the project opted into batch review AND the flag is on.

    Both halves matter: flipping the global flag must not silently change
    behavior for projects that never set a `review_batch_size`.
    """
    if getattr(project, 'review_batch_size', None) in (None, 0):
        return False
    ff_user = user if user is not None else getattr(project, 'created_by', None)
    return bool(flag_set(FEATURE_FLAG, user=ff_user))


def project_can_be_reviewed(project, user=None) -> bool:
    """Gate for "may reviewers start now?".

    - Batch mode: at least `review_batch_size` annotations in `ANNOTATED`.
    - Classic mode: every task in the project is `is_labeled=True` (the
      pre-Phase-4 behavior — `Project.finished()` mirror).
    """
    if is_batch_review_enabled(project, user=user):
        from tasks.models import Annotation

        eligible = Annotation.objects.filter(
            project=project, current_state=AnnotationStateChoices.ANNOTATED
        ).count()
        return eligible >= int(project.review_batch_size)

    return not project.tasks.filter(is_labeled=False).exists()


def eligible_annotations_for_review(project):
    """QuerySet of annotations ready to be routed into the review queue.

    Ordered by id so batches are reproducible — callers that want FIFO across
    reviewers can just `.values_list('id', flat=True)[:n]` off this.
    """
    from tasks.models import Annotation

    return (
        Annotation.objects.filter(
            project=project, current_state=AnnotationStateChoices.ANNOTATED
        )
        .order_by('id')
    )


def route_batch_to_review(project, user, batch_size: Optional[int] = None) -> List[int]:
    """Route up to `batch_size` ANNOTATED annotations into WILL_REVIEWED.

    Returns the list of routed annotation IDs. Returns `[]` silently when the
    flag is off, the project hasn't opted in, or nothing is eligible — the
    caller can decide whether to surface that as a 409 or a no-op.
    """
    if not is_batch_review_enabled(project, user=user):
        return []

    size = batch_size if batch_size is not None else project.review_batch_size
    if size is None or int(size) <= 0:
        return []

    StateManager = get_state_manager()
    routed: List[int] = []

    with transaction.atomic():
        # `select_for_update` so two concurrent review-start calls don't both
        # pick up the same annotations. `skip_locked` so a second caller can
        # grab the *next* batch instead of blocking.
        pks = list(
            eligible_annotations_for_review(project)
            .select_for_update(skip_locked=True)
            .values_list('id', flat=True)[: int(size)]
        )
        if not pks:
            return []

        from tasks.models import Annotation

        for annotation in Annotation.objects.filter(pk__in=pks):
            StateManager.execute_transition(
                entity=annotation, transition_name='move_to_review', user=user
            )
            routed.append(annotation.id)

    logger.info(
        'Batch review routed %s annotations for project %s', len(routed), project.id,
        extra={
            'event': 'fsm.batch_review_routed',
            'project_id': project.id,
            'batch_size': size,
            'routed_count': len(routed),
        },
    )
    return routed
