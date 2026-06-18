"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Currency(models.TextChoices):
    """Supported project currencies. Compensation never mixes currencies."""

    USD = 'USD', _('US Dollar')
    EUR = 'EUR', _('Euro')
    KRW = 'KRW', _('Korean Won')
    JPY = 'JPY', _('Japanese Yen')


class ProjectCompensationPolicy(models.Model):
    """Per-project pricing used to derive worker compensation.

    Compensation = unit price x qualified work count. Qualified counts are derived
    from review/annotation history (see :mod:`compensation.services`) and are never
    stored here — only the pricing inputs are. This keeps every earning reproducible
    from project configuration plus historical workflow data.
    """

    project = models.OneToOneField(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='compensation_policy',
        help_text='Project this pricing applies to.',
    )
    currency = models.CharField(
        _('currency'),
        max_length=3,
        choices=Currency.choices,
        default=Currency.USD,
        help_text='Currency for this project\'s rates and earnings.',
    )
    annotation_unit_price = models.DecimalField(
        _('annotation unit price'),
        max_digits=14,
        decimal_places=4,
        default=0,
        help_text='Paid once per qualified (compensable) annotated data item.',
    )
    review_unit_price = models.DecimalField(
        _('review unit price'),
        max_digits=14,
        decimal_places=4,
        default=0,
        help_text='Paid once per qualified (compensable) reviewed data item.',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        db_table = 'project_compensation_policy'

    def __str__(self):
        return f'CompensationPolicy(project={self.project_id}, {self.currency})'


class PaymentRecord(models.Model):
    """A manually-recorded payment to a worker. No money is moved; this is bookkeeping.

    Payments are scoped to a (workspace, user, currency) because a worker may earn in
    several currencies across projects. Remaining balance and payment status are derived
    by comparing the sum of these records against derived earnings for the same currency.
    """

    workspace = models.ForeignKey(
        'workspaces.Workspace',
        on_delete=models.CASCADE,
        related_name='payment_records',
        help_text='Workspace the payment is recorded under.',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payment_records',
        help_text='Worker (member) the payment was made to.',
    )
    currency = models.CharField(
        _('currency'),
        max_length=3,
        choices=Currency.choices,
        help_text='Currency of the payment; must match the earnings currency it settles.',
    )
    amount = models.DecimalField(
        _('amount'),
        max_digits=16,
        decimal_places=4,
        help_text='Amount paid in the given currency.',
    )
    paid_at = models.DateTimeField(_('paid at'), default=timezone.now)
    memo = models.TextField(_('memo'), blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)

    class Meta:
        db_table = 'compensation_payment_record'
        ordering = ('-paid_at', '-id')

    def __str__(self):
        return f'PaymentRecord(user={self.user_id}, {self.amount} {self.currency})'
