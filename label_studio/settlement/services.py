"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

import logging
from collections import defaultdict
from decimal import Decimal
from typing import Dict, Iterable, List, Optional, Tuple

from django.db import transaction
from django.utils import timezone

from fsm.state_choices import AnnotationStateChoices
from fsm.state_models import AnnotationState

from .models import (
    BatchStatus,
    ProjectPricing,
    ProjectPricingHistory,
    SettlementBatch,
    SettlementItem,
    quantize_amount,
)

logger = logging.getLogger(__name__)


# Transition names emitted by `fsm.annotation_transitions` when a reviewer acts.
_ACCEPT_TRANSITION = 'accept_annotation'
_REJECT_TRANSITION = 'reject_annotation'


def capture_pricing_history(
    project, label_price: Decimal, review_price: Decimal, currency: str, changed_by
) -> ProjectPricingHistory:
    """Record an INSERT-only audit row for a pricing change.

    Callers are responsible for writing the mutable `ProjectPricing` row first;
    this function only appends to the history log so a later batch run can still
    reconstruct what pricing was in effect at any past timestamp.
    """
    return ProjectPricingHistory.objects.create(
        project=project,
        label_price=label_price,
        review_price=review_price,
        currency=currency,
        changed_by=changed_by,
    )


def set_project_pricing(
    project,
    *,
    label_price: Decimal,
    review_price: Decimal,
    currency: str,
    user=None,
) -> ProjectPricing:
    """Upsert `ProjectPricing` and append a history row in a single transaction."""
    with transaction.atomic():
        pricing, _ = ProjectPricing.objects.update_or_create(
            project=project,
            defaults={
                'label_price': label_price,
                'review_price': review_price,
                'currency': currency,
                'updated_by': user,
            },
        )
        capture_pricing_history(
            project=project,
            label_price=label_price,
            review_price=review_price,
            currency=currency,
            changed_by=user,
        )
    return pricing


def _accepted_annotation_counts(
    project_id: int, period_start, period_end
) -> Tuple[Dict[int, int], List[int]]:
    """Count ACCEPTED-terminal annotations in-window, deduping rework chains.

    An annotation may bounce through ACCEPTED / REJECTED multiple times as the
    reviewer flips their decision, and rework creates a *new* child annotation
    (`parent_annotation_id` set) that re-enters the pipeline. We want **one**
    payout per root annotation lineage, credited to the annotator who owns the
    final ACCEPTED record.

    Strategy:
      1. Pull the most recent ACCEPTED AnnotationState row for each annotation
         whose acceptance landed inside [period_start, period_end). The MAX(id)
         per annotation picks the newest state because UUID7 is time-ordered.
      2. Resolve each annotation's lineage root via `parent_annotation_id`
         chain (Annotation table) so rework chains collapse into one lineage.
      3. For each lineage, keep only the latest acceptance (highest state id).

    Returns `({annotator_id: accepted_count}, [ledger_annotation_ids])`.
    """
    from tasks.models import Annotation

    accepted_states = (
        AnnotationState.objects.filter(
            project_id=project_id,
            state=AnnotationStateChoices.ACCEPTED,
            transition_name=_ACCEPT_TRANSITION,
            created_at__gte=period_start,
            created_at__lt=period_end,
        )
        .values('annotation_id', 'completed_by_id', 'id', 'created_at')
        .order_by('annotation_id', '-id')
    )

    # Collapse duplicates per annotation (keep the latest state row).
    latest_by_annotation: Dict[int, dict] = {}
    for row in accepted_states:
        aid = row['annotation_id']
        if aid not in latest_by_annotation:
            latest_by_annotation[aid] = row

    if not latest_by_annotation:
        return {}, []

    annotation_ids = list(latest_by_annotation.keys())

    # Resolve each annotation's parent chain into a single root id. Annotation
    # chains in practice are short (≤ a few rework cycles), so iterative lookup
    # with a memo beats a recursive CTE for the volumes we see.
    parent_map: Dict[int, Optional[int]] = dict(
        Annotation.objects.filter(id__in=annotation_ids).values_list('id', 'parent_annotation_id')
    )
    # Fill in missing ancestors we encounter during chain walks so we don't
    # re-query the DB for each step.
    full_parent_map: Dict[int, Optional[int]] = dict(parent_map)

    def _root_of(aid: int) -> int:
        visited = []
        current = aid
        while True:
            parent = full_parent_map.get(current, None)
            if parent is None:
                return current
            if parent in visited:
                # Defensive — a lineage cycle should never happen but we refuse
                # to loop forever if the data is corrupt.
                logger.warning('settlement: cycle detected in annotation parent chain at %s', current)
                return current
            visited.append(current)
            if parent not in full_parent_map:
                # Extend the memo by one hop so we can keep climbing.
                extra = dict(
                    Annotation.objects.filter(id=parent).values_list('id', 'parent_annotation_id')
                )
                full_parent_map.update(extra)
                if parent not in full_parent_map:
                    full_parent_map[parent] = None
            current = parent

    # Pick the latest acceptance per lineage root. Ties broken by state id
    # (UUID7 → newest wins).
    best_per_root: Dict[int, dict] = {}
    for aid, state_row in latest_by_annotation.items():
        root = _root_of(aid)
        prior = best_per_root.get(root)
        if prior is None or state_row['id'] > prior['id']:
            best_per_root[root] = {**state_row, 'lineage_root': root, 'annotation_id': aid}

    counts: Dict[int, int] = defaultdict(int)
    ledger: List[int] = []
    for root, row in best_per_root.items():
        annotator_id = row['completed_by_id']
        if annotator_id is None:
            # Anonymous / deleted user — skip from payout but keep ledger entry.
            ledger.append(row['annotation_id'])
            continue
        counts[annotator_id] += 1
        ledger.append(row['annotation_id'])
    return dict(counts), ledger


def _review_counts(project_id: int, period_start, period_end) -> Dict[int, int]:
    """Count every accept/reject action a reviewer performed in-window.

    Unlike annotator payouts, reviewers are paid per *decision* they render —
    a rework that leads to a second review is two review actions, not one. We
    therefore do **not** dedupe on annotation or lineage here.
    """
    states = AnnotationState.objects.filter(
        project_id=project_id,
        transition_name__in=[_ACCEPT_TRANSITION, _REJECT_TRANSITION],
        created_at__gte=period_start,
        created_at__lt=period_end,
        triggered_by__isnull=False,
    ).values_list('triggered_by_id', flat=True)

    counts: Dict[int, int] = defaultdict(int)
    for reviewer_id in states:
        counts[reviewer_id] += 1
    return dict(counts)


def _build_items(
    batch: SettlementBatch,
    accepted_counts: Dict[int, int],
    review_counts: Dict[int, int],
) -> List[SettlementItem]:
    """Translate user-level counts into quantised SettlementItem rows."""
    label_price = Decimal(batch.label_price_snapshot or 0)
    review_price = Decimal(batch.review_price_snapshot or 0)
    currency = batch.currency

    user_ids: Iterable[int] = set(accepted_counts.keys()) | set(review_counts.keys())
    items: List[SettlementItem] = []
    for user_id in sorted(user_ids):
        acc = accepted_counts.get(user_id, 0)
        rev = review_counts.get(user_id, 0)
        label_amount = quantize_amount(label_price * Decimal(acc), currency)
        review_amount = quantize_amount(review_price * Decimal(rev), currency)
        total = quantize_amount(label_amount + review_amount, currency)
        items.append(
            SettlementItem(
                batch=batch,
                user_id=user_id,
                accepted_count=acc,
                review_count=rev,
                label_amount=label_amount,
                review_amount=review_amount,
                amount=total,
                currency=currency,
            )
        )
    return items


def compute_settlement(batch_id: int) -> SettlementBatch:
    """Run the settlement computation for a PENDING batch.

    Transition order:
        PENDING → RUNNING (captures pricing snapshot) → COMPLETED | FAILED

    Idempotent with respect to re-runs only for FAILED batches — a COMPLETED
    batch is immutable. Re-running RUNNING (e.g. after a worker crash) wipes
    the partial items and starts over.
    """
    batch = SettlementBatch.objects.select_related('project').get(pk=batch_id)

    if batch.status == BatchStatus.COMPLETED:
        logger.info('settlement batch %s already completed; skipping', batch_id)
        return batch

    try:
        pricing = batch.project.pricing
    except ProjectPricing.DoesNotExist:
        batch.status = BatchStatus.FAILED
        batch.error_message = 'Project has no ProjectPricing row — set pricing before running a batch.'
        batch.completed_at = timezone.now()
        batch.save(update_fields=['status', 'error_message', 'completed_at'])
        return batch

    with transaction.atomic():
        batch.status = BatchStatus.RUNNING
        batch.label_price_snapshot = pricing.label_price
        batch.review_price_snapshot = pricing.review_price
        batch.currency = pricing.currency
        batch.save(
            update_fields=['status', 'label_price_snapshot', 'review_price_snapshot', 'currency']
        )
        # Wipe any prior items if this is a re-run of a FAILED batch.
        batch.items.all().delete()

    try:
        accepted_counts, ledger = _accepted_annotation_counts(
            batch.project_id, batch.period_start, batch.period_end
        )
        review_counts = _review_counts(
            batch.project_id, batch.period_start, batch.period_end
        )
        items = _build_items(batch, accepted_counts, review_counts)

        with transaction.atomic():
            SettlementItem.objects.bulk_create(items)
            batch.accepted_annotation_count = len(ledger)
            batch.review_count = sum(review_counts.values())
            batch.total_amount = quantize_amount(
                sum((i.amount for i in items), Decimal('0')), batch.currency
            )
            batch.status = BatchStatus.COMPLETED
            batch.completed_at = timezone.now()
            batch.save(
                update_fields=[
                    'accepted_annotation_count',
                    'review_count',
                    'total_amount',
                    'status',
                    'completed_at',
                ]
            )
    except Exception as exc:  # noqa: BLE001 — any error must be captured on the batch
        logger.exception('settlement batch %s failed', batch_id)
        batch.status = BatchStatus.FAILED
        batch.error_message = f'{type(exc).__name__}: {exc}'[:4096]
        batch.completed_at = timezone.now()
        batch.save(update_fields=['status', 'error_message', 'completed_at'])
    return batch
