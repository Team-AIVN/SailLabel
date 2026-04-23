"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from decimal import Decimal

import pytest
from projects.tests.factories import ProjectFactory

from settlement.models import (
    Currency,
    ProjectPricing,
    ProjectPricingHistory,
    SettlementBatch,
    SettlementItem,
    quantize_amount,
)


@pytest.mark.django_db
def test_quantize_amount_rejects_float():
    with pytest.raises(TypeError):
        quantize_amount(1.23, Currency.USD)


@pytest.mark.django_db
def test_quantize_amount_honours_currency_precision():
    assert quantize_amount(Decimal('10.567'), Currency.USD) == Decimal('10.57')
    assert quantize_amount(Decimal('10.567'), Currency.KRW) == Decimal('11')
    assert quantize_amount(Decimal('10.499'), Currency.JPY) == Decimal('10')


@pytest.mark.django_db
def test_project_pricing_unique_per_project():
    project = ProjectFactory()
    ProjectPricing.objects.create(
        project=project,
        label_price=Decimal('100'),
        review_price=Decimal('50'),
        currency=Currency.KRW,
    )
    from django.db import IntegrityError
    with pytest.raises(IntegrityError):
        ProjectPricing.objects.create(
            project=project,
            label_price=Decimal('200'),
            review_price=Decimal('100'),
            currency=Currency.KRW,
        )


@pytest.mark.django_db
def test_settlement_item_unique_batch_user():
    from users.tests.factories import UserFactory

    project = ProjectFactory()
    user = UserFactory()
    batch = SettlementBatch.objects.create(
        project=project,
        period_start='2026-01-01T00:00:00Z',
        period_end='2026-02-01T00:00:00Z',
    )
    SettlementItem.objects.create(batch=batch, user=user, amount=Decimal('0'), currency=Currency.KRW)

    from django.db import IntegrityError
    with pytest.raises(IntegrityError):
        SettlementItem.objects.create(
            batch=batch, user=user, amount=Decimal('0'), currency=Currency.KRW
        )


@pytest.mark.django_db
def test_pricing_history_insert_only_audit():
    project = ProjectFactory()
    for amount in (Decimal('10'), Decimal('20'), Decimal('30')):
        ProjectPricingHistory.objects.create(
            project=project,
            label_price=amount,
            review_price=amount,
            currency=Currency.KRW,
        )
    assert ProjectPricingHistory.objects.filter(project=project).count() == 3
