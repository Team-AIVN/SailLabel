"""Tests for the ``purge_audit_log`` management command.

The model refuses ``delete()`` on instances; the command must still succeed
via the raw delete path. Retention floor (90 days) is enforced.
"""

from datetime import timedelta
from io import StringIO

import pytest
from audit.models import AuditAction, AuditLog
from django.core.management import CommandError, call_command
from django.utils import timezone
from rest_framework.test import APITestCase
from users.tests.factories import UserFactory


class PurgeAuditLogCommandTests(APITestCase):
    def _make_entry(self, days_ago):
        entry = AuditLog.record(action=AuditAction.ROLE_GRANTED, actor=UserFactory())
        # Direct UPDATE bypasses immutability guard but is confined to this test.
        AuditLog.objects.filter(pk=entry.pk).update(
            created_at=timezone.now() - timedelta(days=days_ago)
        )
        return entry

    def test_retention_floor_is_enforced(self):
        with pytest.raises(CommandError, match='>= 90'):
            call_command('purge_audit_log', '--days=30')

    def test_purges_rows_older_than_window(self):
        old = self._make_entry(days_ago=120)
        recent = self._make_entry(days_ago=10)

        buf = StringIO()
        call_command('purge_audit_log', '--days=90', stdout=buf)

        assert not AuditLog.objects.filter(pk=old.pk).exists()
        assert AuditLog.objects.filter(pk=recent.pk).exists()
        assert 'Deleted 1' in buf.getvalue()

    def test_dry_run_reports_count_without_deleting(self):
        entry = self._make_entry(days_ago=120)

        buf = StringIO()
        call_command('purge_audit_log', '--days=90', '--dry-run', stdout=buf)

        assert AuditLog.objects.filter(pk=entry.pk).exists()
        assert 'would delete 1' in buf.getvalue()
