"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from fsm.state_choices import AnnotationStateChoices
from fsm.state_models import AnnotationState
from projects.tests.factories import ProjectFactory
from tasks.tests.factories import AnnotationFactory
from users.tests.factories import UserFactory

from settlement.models import (
    BatchStatus,
    Currency,
    ProjectPricing,
    SettlementBatch,
    SettlementItem,
)
from settlement.services import compute_settlement


def _accept(annotation, reviewer, created_at=None):
    """Insert an ACCEPTED AnnotationState row for `annotation` at `created_at`.

    We write the audit row directly because `StateManager.execute_transition`
    re-runs the entire transition chain and flips sibling ground_truth flags —
    heavier than we need and harder to target a specific timestamp.
    """
    state = AnnotationState.objects.create(
        annotation=annotation,
        task_id=annotation.task.id,
        project_id=annotation.task.project_id,
        completed_by_id=annotation.completed_by_id,
        state=AnnotationStateChoices.ACCEPTED,
        transition_name='accept_annotation',
        triggered_by=reviewer,
    )
    if created_at is not None:
        AnnotationState.objects.filter(pk=state.pk).update(created_at=created_at)
        state.refresh_from_db()
    return state


def _reject(annotation, reviewer, created_at=None):
    state = AnnotationState.objects.create(
        annotation=annotation,
        task_id=annotation.task.id,
        project_id=annotation.task.project_id,
        completed_by_id=annotation.completed_by_id,
        state=AnnotationStateChoices.REJECTED,
        transition_name='reject_annotation',
        triggered_by=reviewer,
    )
    if created_at is not None:
        AnnotationState.objects.filter(pk=state.pk).update(created_at=created_at)
    return state


@pytest.mark.django_db
def test_compute_settlement_happy_path():
    project = ProjectFactory()
    annotator = UserFactory()
    reviewer = UserFactory()

    ProjectPricing.objects.create(
        project=project,
        label_price=Decimal('100'),
        review_price=Decimal('40'),
        currency=Currency.KRW,
    )

    now = timezone.now()
    # Three accepted annotations by the annotator, all reviewed by reviewer.
    for _ in range(3):
        ann = AnnotationFactory(task__project=project, completed_by=annotator)
        _accept(ann, reviewer, created_at=now - timedelta(hours=1))

    batch = SettlementBatch.objects.create(
        project=project,
        period_start=now - timedelta(days=1),
        period_end=now + timedelta(days=1),
    )

    compute_settlement(batch.id)
    batch.refresh_from_db()

    assert batch.status == BatchStatus.COMPLETED
    assert batch.accepted_annotation_count == 3
    assert batch.review_count == 3
    # Annotator: 3 * 100 = 300; Reviewer: 3 * 40 = 120.
    assert batch.total_amount == Decimal('420.0000')

    items = {item.user_id: item for item in batch.items.all()}
    assert items[annotator.id].label_amount == Decimal('300.0000')
    assert items[annotator.id].review_amount == Decimal('0.0000')
    assert items[reviewer.id].review_amount == Decimal('120.0000')
    assert items[reviewer.id].label_amount == Decimal('0.0000')


@pytest.mark.django_db
def test_compute_settlement_excludes_outside_window():
    project = ProjectFactory()
    annotator = UserFactory()
    reviewer = UserFactory()
    ProjectPricing.objects.create(
        project=project,
        label_price=Decimal('100'),
        review_price=Decimal('40'),
        currency=Currency.KRW,
    )

    now = timezone.now()
    in_window = AnnotationFactory(task__project=project, completed_by=annotator)
    before = AnnotationFactory(task__project=project, completed_by=annotator)
    after = AnnotationFactory(task__project=project, completed_by=annotator)

    _accept(in_window, reviewer, created_at=now)
    _accept(before, reviewer, created_at=now - timedelta(days=10))
    _accept(after, reviewer, created_at=now + timedelta(days=10))

    batch = SettlementBatch.objects.create(
        project=project,
        period_start=now - timedelta(days=1),
        period_end=now + timedelta(days=1),
    )
    compute_settlement(batch.id)
    batch.refresh_from_db()

    assert batch.accepted_annotation_count == 1
    assert batch.review_count == 1
    assert batch.total_amount == Decimal('140.0000')


@pytest.mark.django_db
def test_rework_chain_counted_once_and_credits_latest_annotator():
    """Rework lineage: parent REJECTED → child ACCEPTED → only 1 payout."""
    project = ProjectFactory()
    annotator_a = UserFactory()
    annotator_b = UserFactory()
    reviewer = UserFactory()
    ProjectPricing.objects.create(
        project=project,
        label_price=Decimal('100'),
        review_price=Decimal('40'),
        currency=Currency.KRW,
    )
    now = timezone.now()

    parent = AnnotationFactory(task__project=project, completed_by=annotator_a)
    _reject(parent, reviewer, created_at=now - timedelta(hours=2))

    # Child rework picks up the same task, different annotator.
    child = AnnotationFactory(
        task=parent.task, completed_by=annotator_b, parent_annotation=parent,
    )
    _accept(child, reviewer, created_at=now - timedelta(hours=1))

    batch = SettlementBatch.objects.create(
        project=project,
        period_start=now - timedelta(days=1),
        period_end=now + timedelta(days=1),
    )
    compute_settlement(batch.id)
    batch.refresh_from_db()

    # Exactly one accepted annotation in the lineage.
    assert batch.accepted_annotation_count == 1
    items = {item.user_id: item for item in batch.items.all()}
    # Reviewer did two actions (reject + accept) → paid for both.
    assert items[reviewer.id].review_count == 2
    assert items[reviewer.id].review_amount == Decimal('80.0000')
    # Only the child's annotator (B) gets the label payout.
    assert items[annotator_b.id].label_amount == Decimal('100.0000')
    assert annotator_a.id not in items or items[annotator_a.id].label_amount == Decimal('0.0000')


@pytest.mark.django_db
def test_compute_settlement_without_pricing_fails():
    project = ProjectFactory()
    now = timezone.now()
    batch = SettlementBatch.objects.create(
        project=project,
        period_start=now - timedelta(days=1),
        period_end=now + timedelta(days=1),
    )

    compute_settlement(batch.id)
    batch.refresh_from_db()
    assert batch.status == BatchStatus.FAILED
    assert 'pricing' in batch.error_message.lower()


@pytest.mark.django_db
def test_compute_settlement_captures_pricing_snapshot():
    project = ProjectFactory()
    pricing = ProjectPricing.objects.create(
        project=project,
        label_price=Decimal('100'),
        review_price=Decimal('40'),
        currency=Currency.USD,
    )
    now = timezone.now()
    batch = SettlementBatch.objects.create(
        project=project,
        period_start=now - timedelta(days=1),
        period_end=now + timedelta(days=1),
    )
    compute_settlement(batch.id)
    batch.refresh_from_db()
    assert batch.label_price_snapshot == pricing.label_price
    assert batch.review_price_snapshot == pricing.review_price
    assert batch.currency == Currency.USD

    # Mutating pricing later should not change the closed batch.
    pricing.label_price = Decimal('9999')
    pricing.save()
    batch.refresh_from_db()
    assert batch.label_price_snapshot == Decimal('100')
