"""Retention pruner for the audit_log table.

NFR §4 requires >=90 days of audit history. ``AuditLog`` rows are immutable by
policy — instance ``delete()`` raises RuntimeError and row ``save(update)`` is
refused. This command bypasses the instance guard by issuing a direct ``DELETE``
via ``QuerySet._raw_delete``, which is the only legitimate caller for the
rule-of-time retention job.

Usage::

    python manage.py purge_audit_log --days=90        # delete entries older than 90 days
    python manage.py purge_audit_log --days=90 --dry-run
"""

from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import router
from django.utils import timezone

from audit.models import AuditLog


class Command(BaseCommand):
    help = 'Delete audit log entries older than the retention window (default 90 days).'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=90, help='Retention window in days. Must be >= 90 per NFR §4.')
        parser.add_argument('--dry-run', action='store_true', help='Report the row count but do not delete.')

    def handle(self, *args, **options):
        days = options['days']
        if days < 90:
            raise CommandError('Retention window must be >= 90 days (NFR §4).')

        cutoff = timezone.now() - timedelta(days=days)
        qs = AuditLog.objects.filter(created_at__lt=cutoff)
        count = qs.count()

        if options['dry_run']:
            self.stdout.write(self.style.NOTICE(f'[dry-run] would delete {count} audit log rows older than {cutoff.isoformat()}'))
            return

        if count == 0:
            self.stdout.write(f'No audit log rows older than {cutoff.isoformat()}')
            return

        # Raw delete bypasses the model-level immutability guard deliberately —
        # this is the single authorised deletion path for audit data.
        using = router.db_for_write(AuditLog)
        qs.using(using)._raw_delete(using)
        self.stdout.write(self.style.SUCCESS(f'Deleted {count} audit log rows older than {cutoff.isoformat()}'))
