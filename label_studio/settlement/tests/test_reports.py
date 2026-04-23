"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from projects.tests.factories import ProjectFactory
from users.tests.factories import UserFactory

from settlement.models import (
    BatchStatus,
    Currency,
    SettlementBatch,
    SettlementItem,
)
from settlement.reports import render_csv, render_pdf


def _make_batch_with_items():
    project = ProjectFactory(title='Sample project')
    user1 = UserFactory(email='alice@example.com')
    user2 = UserFactory(email='bob@example.com')
    batch = SettlementBatch.objects.create(
        project=project,
        period_start=timezone.now() - timedelta(days=7),
        period_end=timezone.now(),
        status=BatchStatus.COMPLETED,
        currency=Currency.KRW,
        total_amount=Decimal('500'),
        accepted_annotation_count=3,
        review_count=2,
    )
    SettlementItem.objects.create(
        batch=batch, user=user1,
        accepted_count=3, review_count=0,
        label_amount=Decimal('300'), review_amount=Decimal('0'), amount=Decimal('300'),
        currency=Currency.KRW,
    )
    SettlementItem.objects.create(
        batch=batch, user=user2,
        accepted_count=0, review_count=2,
        label_amount=Decimal('0'), review_amount=Decimal('200'), amount=Decimal('200'),
        currency=Currency.KRW,
    )
    return batch


@pytest.mark.django_db
def test_render_csv_contains_metadata_and_rows():
    batch = _make_batch_with_items()
    body = render_csv(batch)
    text = body.decode('utf-8')
    assert '# settlement_batch_id' in text
    assert 'alice@example.com' in text
    assert 'bob@example.com' in text
    assert 'TOTAL' in text


@pytest.mark.django_db
def test_render_pdf_produces_valid_pdf_bytes():
    batch = _make_batch_with_items()
    body = render_pdf(batch)
    assert body.startswith(b'%PDF-')
    # End-of-file marker — a truncated PDF won't contain this.
    assert b'%%EOF' in body[-1024:]
