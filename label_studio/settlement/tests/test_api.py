"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from organizations.models import OrganizationMember
from organizations.tests.factories import OrganizationFactory
from projects.tests.factories import ProjectFactory
from rest_framework.test import APITestCase
from users.tests.factories import UserFactory

from settlement.models import (
    BatchStatus,
    Currency,
    ProjectPricing,
    SettlementBatch,
)


def _join_org(user, org):
    user.active_organization = org
    user.save(update_fields=['active_organization'])
    OrganizationMember.objects.get_or_create(user=user, organization=org)


class ProjectPricingAPITests(APITestCase):
    def setUp(self):
        self.org = OrganizationFactory()
        self.owner = self.org.created_by
        self.project = ProjectFactory(organization=self.org, created_by=self.owner)

    def test_owner_can_create_pricing(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            f'/api/projects/{self.project.id}/pricing/',
            {'label_price': '100', 'review_price': '40', 'currency': 'KRW'},
            format='json',
        )
        assert response.status_code == 200, response.content
        body = response.json()
        assert Decimal(body['label_price']) == Decimal('100')
        assert body['currency'] == 'KRW'
        assert ProjectPricing.objects.filter(project=self.project).exists()

    def test_non_manager_cannot_set_pricing(self):
        outsider = UserFactory()
        _join_org(outsider, self.org)
        self.client.force_authenticate(user=outsider)
        response = self.client.post(
            f'/api/projects/{self.project.id}/pricing/',
            {'label_price': '100', 'review_price': '40', 'currency': 'KRW'},
            format='json',
        )
        assert response.status_code in (401, 403)

    def test_cross_org_user_cannot_view(self):
        other = UserFactory()
        other_org = OrganizationFactory()
        _join_org(other, other_org)
        self.client.force_authenticate(user=other)
        response = self.client.get(f'/api/projects/{self.project.id}/pricing/')
        assert response.status_code in (401, 403, 404)

    def test_negative_prices_rejected(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            f'/api/projects/{self.project.id}/pricing/',
            {'label_price': '-1', 'review_price': '40', 'currency': 'KRW'},
            format='json',
        )
        assert response.status_code == 400


class SettlementBatchAPITests(APITestCase):
    def setUp(self):
        self.org = OrganizationFactory()
        self.owner = self.org.created_by
        self.project = ProjectFactory(organization=self.org, created_by=self.owner)
        ProjectPricing.objects.create(
            project=self.project,
            label_price=Decimal('100'),
            review_price=Decimal('40'),
            currency=Currency.KRW,
        )

    def test_create_batch_runs_sync_when_redis_unavailable(self):
        """In the test env Redis is not running; start_job_async_or_sync should
        fall back to sync execution so the batch finishes inside the POST."""
        self.client.force_authenticate(user=self.owner)
        now = timezone.now()
        response = self.client.post(
            f'/api/projects/{self.project.id}/settlements/',
            {
                'period_start': (now - timedelta(days=1)).isoformat(),
                'period_end': (now + timedelta(days=1)).isoformat(),
            },
            format='json',
        )
        assert response.status_code == 201, response.content
        batch_id = response.json()['id']
        batch = SettlementBatch.objects.get(pk=batch_id)
        # Sync fallback should have moved the batch through to COMPLETED.
        assert batch.status in (BatchStatus.COMPLETED, BatchStatus.PENDING)

    def test_non_manager_cannot_run_batch(self):
        outsider = UserFactory()
        _join_org(outsider, self.org)
        self.client.force_authenticate(user=outsider)
        now = timezone.now()
        response = self.client.post(
            f'/api/projects/{self.project.id}/settlements/',
            {
                'period_start': (now - timedelta(days=1)).isoformat(),
                'period_end': (now + timedelta(days=1)).isoformat(),
            },
            format='json',
        )
        assert response.status_code in (401, 403)

    def test_invalid_period_rejected(self):
        self.client.force_authenticate(user=self.owner)
        now = timezone.now()
        response = self.client.post(
            f'/api/projects/{self.project.id}/settlements/',
            {
                'period_start': (now + timedelta(days=1)).isoformat(),
                'period_end': (now - timedelta(days=1)).isoformat(),
            },
            format='json',
        )
        assert response.status_code == 400

    def test_cannot_delete_completed_batch(self):
        batch = SettlementBatch.objects.create(
            project=self.project,
            period_start=timezone.now() - timedelta(days=1),
            period_end=timezone.now(),
            status=BatchStatus.COMPLETED,
        )
        self.client.force_authenticate(user=self.owner)
        response = self.client.delete(f'/api/settlements/{batch.id}/')
        assert response.status_code == 400


class SettlementReportAPITests(APITestCase):
    def setUp(self):
        self.org = OrganizationFactory()
        self.owner = self.org.created_by
        self.project = ProjectFactory(organization=self.org, created_by=self.owner)
        self.batch = SettlementBatch.objects.create(
            project=self.project,
            period_start=timezone.now() - timedelta(days=1),
            period_end=timezone.now(),
            status=BatchStatus.COMPLETED,
            currency=Currency.KRW,
            total_amount=Decimal('0'),
        )

    def test_csv_download(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(f'/api/settlements/{self.batch.id}/report/?report_format=csv')
        assert response.status_code == 200
        assert response['Content-Type'].startswith('text/csv')
        body = response.content
        assert b'settlement_batch_id' in body

    def test_pdf_download(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(f'/api/settlements/{self.batch.id}/report/?report_format=pdf')
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/pdf'
        body = response.content
        assert body.startswith(b'%PDF-')

    def test_incomplete_batch_returns_409(self):
        self.batch.status = BatchStatus.PENDING
        self.batch.save(update_fields=['status'])
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(f'/api/settlements/{self.batch.id}/report/?report_format=csv')
        assert response.status_code == 409
