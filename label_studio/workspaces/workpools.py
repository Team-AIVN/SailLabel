"""Work Pool services: dataset-item materialization and pool-to-project task seeding.

A "dataset" is a :class:`WorkspaceFileUpload`; its :class:`DatasetItem` rows are the
selectable units curated into :class:`WorkPool` s. Projects bind to one Work Pool and
its items are materialised into project tasks.
"""

import csv
import io
import json
import logging
import os

from django.db import transaction
from projects.models import ProjectSummary

from .models import DatasetItem, WorkPoolItem

logger = logging.getLogger(__name__)

_MEDIA_BY_EXT = {
    'jpg': 'image', 'jpeg': 'image', 'png': 'image', 'gif': 'image', 'bmp': 'image', 'webp': 'image', 'svg': 'image',
    'mp3': 'audio', 'wav': 'audio', 'ogg': 'audio', 'flac': 'audio', 'm4a': 'audio',
    'mp4': 'video', 'webm': 'video', 'mov': 'video', 'avi': 'video',
    'txt': 'text', 'html': 'html', 'htm': 'html', 'json': 'json', 'csv': 'csv', 'tsv': 'csv', 'pdf': 'pdf',
}


def _ext(name):
    return os.path.splitext(name or '')[1].lstrip('.').lower()


def _media_type_for_ext(ext):
    return _MEDIA_BY_EXT.get(ext, 'file')


def _infer_item_type(data, default):
    """Infer a media type from an item's values (e.g. an image URL -> 'image')."""
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, str):
                t = _MEDIA_BY_EXT.get(_ext(value))
                if t and t not in ('json', 'csv', 'text'):
                    return t
    return default


def materialize_dataset_items(upload, max_items=10000):
    """Parse a WorkspaceFileUpload into DatasetItem rows. Returns the count created."""
    name = upload.file_name
    ext = _ext(name)
    try:
        upload.file.open('rb')
        raw = upload.file.read()
    finally:
        upload.file.close()

    records = None
    if ext == 'json':
        try:
            parsed = json.loads(raw.decode('utf-8'))
            records = parsed if isinstance(parsed, list) else [parsed]
        except Exception:
            records = None
    elif ext in ('csv', 'tsv'):
        try:
            reader = csv.DictReader(io.StringIO(raw.decode('utf-8')), delimiter='\t' if ext == 'tsv' else ',')
            records = [dict(r) for r in reader]
        except Exception:
            records = None

    items = []
    if records is not None:
        default_type = 'json' if ext == 'json' else 'csv'
        for i, rec in enumerate(records[:max_items]):
            data = rec.get('data', rec) if isinstance(rec, dict) else {'value': rec}
            items.append(
                DatasetItem(
                    dataset=upload,
                    workspace=upload.workspace,
                    data=data,
                    data_type=_infer_item_type(data, default_type),
                    index=i,
                )
            )
    else:
        media = _media_type_for_ext(ext)
        key = media if media in ('image', 'audio', 'video', 'text', 'pdf', 'html') else 'url'
        items.append(
            DatasetItem(
                dataset=upload,
                workspace=upload.workspace,
                data={key: upload.url or name},
                data_type=media,
                index=0,
            )
        )

    DatasetItem.objects.bulk_create(items)
    return len(items)


@transaction.atomic
def materialize_pool_to_project(project):
    """Create project tasks from the project's selected Work Pool items.

    Returns the number of tasks created. Safe to call once at project setup; callers
    should guard against re-running (e.g. only when the project has no tasks yet).
    """
    pool = project.work_pool
    if pool is None:
        return 0
    from data_import.serializers import ImportApiSerializer

    dataset_items = DatasetItem.objects.filter(pool_items__work_pool=pool).order_by('id')
    tasks = [{'data': it.data} for it in dataset_items]
    if not tasks:
        return 0

    ProjectSummary.objects.get_or_create(project=project)
    summary = ProjectSummary.objects.select_for_update().get(project=project)
    serializer = ImportApiSerializer(data=tasks, many=True, context={'project': project})
    serializer.is_valid(raise_exception=True)
    saved = serializer.save(project_id=project.id)
    project.update_tasks_counters_and_task_states(
        tasks_queryset=saved,
        maximum_annotations_changed=False,
        overlap_cohort_percentage_changed=False,
        tasks_number_changed=True,
        recalculate_stats_counts={
            'task_count': len(saved),
            'annotation_count': len(serializer.db_annotations),
            'prediction_count': len(serializer.db_predictions),
        },
    )
    summary.update_data_columns(saved)
    return len(saved)
