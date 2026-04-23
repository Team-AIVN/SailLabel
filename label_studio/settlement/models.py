"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

import logging
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


class Currency(models.TextChoices):
    """Supported settlement currencies.

    Single-currency deployments should set every `ProjectPricing.currency` to
    the same value; the math only compares `(amount, currency)` pairs so a
    stray other-currency pricing row can never leak into an aggregate total.
    """

    KRW = 'KRW', _('Korean Won')
    USD = 'USD', _('US Dollar')
    EUR = 'EUR', _('Euro')
    JPY = 'JPY', _('Japanese Yen')


DEFAULT_CURRENCY = Currency.KRW

# Fractional units per currency — used for Decimal quantisation. KRW/JPY have
# no subunit in practice; USD/EUR carry two decimal places.
CURRENCY_DECIMALS = {
    Currency.KRW: 0,
    Currency.JPY: 0,
    Currency.USD: 2,
    Currency.EUR: 2,
}


def quantize_amount(amount: Decimal, currency: str) -> Decimal:
    """Round `amount` to the currency's subunit precision (banker's rounding).

    Every payout passes through this function so totals cannot drift on float
    intermediate values. Callers must already be Decimal — we refuse plain
    floats to avoid silent precision loss.
    """
    if not isinstance(amount, Decimal):
        raise TypeError('quantize_amount requires a Decimal input.')
    digits = CURRENCY_DECIMALS.get(currency, 2)
    quant = Decimal(10) ** -digits
    return amount.quantize(quant)


class BatchStatus(models.TextChoices):
    PENDING = 'PENDING', _('Pending')
    RUNNING = 'RUNNING', _('Running')
    COMPLETED = 'COMPLETED', _('Completed')
    FAILED = 'FAILED', _('Failed')


class ProjectPricing(models.Model):
    """Per-project unit prices for accepted annotations and completed reviews.

    Current pricing is a 1:1 with Project so joins stay cheap; history lives in
    `ProjectPricingHistory` (INSERT-only, matches the audit-trail style used by
    the FSM app — keeps the rollback story trivial without introducing the
    django-simple-history dependency).
    """

    project = models.OneToOneField(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='pricing',
    )
    label_price = models.DecimalField(
        _('label price'),
        max_digits=14,
        decimal_places=4,
        default=Decimal('0'),
        help_text='Unit price paid to the annotator for each accepted annotation.',
    )
    review_price = models.DecimalField(
        _('review price'),
        max_digits=14,
        decimal_places=4,
        default=Decimal('0'),
        help_text='Unit price paid to the reviewer for each completed review (accept or reject).',
    )
    currency = models.CharField(
        _('currency'),
        max_length=8,
        choices=Currency.choices,
        default=DEFAULT_CURRENCY,
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )

    class Meta:
        db_table = 'project_pricing'

    def has_permission(self, user):
        # Object-level access is enforced in views via the settlement rules
        # predicates; this stub keeps the DRF default permission class happy.
        return True


class ProjectPricingHistory(models.Model):
    """INSERT-only pricing audit — one row per update, queryable by timestamp.

    Each settlement batch captures the pricing snapshot that was current *at
    the time the batch ran*, so later rate changes cannot retroactively alter
    a closed batch. This table exists to make the change history auditable
    outside of the batch record itself.
    """

    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='pricing_history',
    )
    label_price = models.DecimalField(max_digits=14, decimal_places=4)
    review_price = models.DecimalField(max_digits=14, decimal_places=4)
    currency = models.CharField(max_length=8, choices=Currency.choices)
    changed_at = models.DateTimeField(auto_now_add=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )

    class Meta:
        db_table = 'project_pricing_history'
        indexes = [
            models.Index(fields=['project', '-changed_at']),
        ]


class SettlementBatch(models.Model):
    """One settlement run for a project over [period_start, period_end)."""

    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='settlement_batches',
    )
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    status = models.CharField(
        max_length=16,
        choices=BatchStatus.choices,
        default=BatchStatus.PENDING,
    )
    # Pricing snapshot — captured when the batch transitions RUNNING so later
    # pricing changes cannot retroactively shift a closed batch's payouts.
    label_price_snapshot = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True,
    )
    review_price_snapshot = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True,
    )
    currency = models.CharField(
        max_length=8,
        choices=Currency.choices,
        default=DEFAULT_CURRENCY,
    )
    total_amount = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal('0'),
    )
    accepted_annotation_count = models.PositiveIntegerField(default=0)
    review_count = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'settlement_batch'
        indexes = [
            models.Index(fields=['project', '-created_at']),
            models.Index(fields=['project', 'status']),
        ]

    def __str__(self):
        return f'SettlementBatch(project={self.project_id}, {self.period_start}..{self.period_end}, status={self.status})'

    def has_permission(self, user):
        return True


class SettlementItem(models.Model):
    """Per-user payout line inside a single settlement batch."""

    batch = models.ForeignKey(
        SettlementBatch,
        on_delete=models.CASCADE,
        related_name='items',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='+',
    )
    accepted_count = models.PositiveIntegerField(default=0)
    review_count = models.PositiveIntegerField(default=0)
    label_amount = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0'))
    review_amount = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0'))
    amount = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0'))
    currency = models.CharField(max_length=8, choices=Currency.choices)

    class Meta:
        db_table = 'settlement_item'
        constraints = [
            models.UniqueConstraint(fields=['batch', 'user'], name='uniq_settlement_item_batch_user'),
        ]
        indexes = [
            models.Index(fields=['batch', '-amount']),
        ]

    def __str__(self):
        return f'SettlementItem(batch={self.batch_id}, user={self.user_id}, amount={self.amount} {self.currency})'

    def has_permission(self, user):
        return True
