"""Backfill TaskSourceItem rows for WorkspaceFileUploads uploaded before Task Pool
materialization existed (or whose materialization failed).

Safe to re-run: uploads that already have TaskSourceItems are skipped unless --force.
"""

import logging

from django.core.management.base import BaseCommand

from workspaces.models import TaskSourceItem, WorkspaceFileUpload
from workspaces.taskpools import materialize_task_source_items

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Create TaskSourceItems for workspace uploads that have none.'

    def add_arguments(self, parser):
        parser.add_argument('--workspace', type=int, default=None, help='Limit to a single workspace id.')
        parser.add_argument(
            '--force',
            action='store_true',
            help='Re-materialize even uploads that already have TaskSourceItems (deletes existing ones first).',
        )

    def handle(self, *args, **options):
        uploads = WorkspaceFileUpload.objects.all().order_by('id')
        if options['workspace']:
            uploads = uploads.filter(workspace_id=options['workspace'])

        total_uploads = 0
        total_items = 0
        for upload in uploads:
            existing = TaskSourceItem.objects.filter(dataset=upload)
            if existing.exists():
                if not options['force']:
                    self.stdout.write(f'  skip upload {upload.id} ({upload.file_name}) — already has items')
                    continue
                existing.delete()
            try:
                count = materialize_task_source_items(upload)
            except Exception:
                logger.exception('Failed to materialize upload %s', upload.id)
                self.stderr.write(f'  FAILED upload {upload.id} ({upload.file_name})')
                continue
            total_uploads += 1
            total_items += count
            self.stdout.write(f'  upload {upload.id} ({upload.file_name}) -> {count} item(s)')

        self.stdout.write(self.style.SUCCESS(f'Done: {total_items} items across {total_uploads} upload(s).'))
