"""Task Pool services: dataset-item materialization and pool-to-project task seeding.

A "dataset" is a :class:`WorkspaceFileUpload`; its :class:`TaskSourceItem` rows are the
selectable units curated into :class:`TaskPool` s. Projects bind to one Task Pool and
its items are materialised into project tasks.
"""

import csv
import io
import json
import logging
import os
from collections import defaultdict

from django.db import transaction
from projects.models import ProjectSummary

from .models import TaskSourceItem, TaskPoolItem

logger = logging.getLogger(__name__)

# data_type for a merged image + tabular item (sibling keys: {"image": url, "data": [rows]}).
PAIR_DATA_TYPE = 'pair'
_TABULAR_EXTS = ('csv', 'tsv')

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


def _basename(name):
    return os.path.splitext(name or '')[0]


def _infer_item_type(data, default):
    """Infer a media type from an item's values (e.g. an image URL -> 'image')."""
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, str):
                t = _MEDIA_BY_EXT.get(_ext(value))
                if t and t not in ('json', 'csv', 'text'):
                    return t
    return default


def _read_upload_bytes(upload):
    try:
        upload.file.open('rb')
        return upload.file.read()
    finally:
        upload.file.close()


def parse_tabular_rows(raw, ext):
    """Parse csv/tsv bytes into the WHOLE file as a list of row dicts.

    Raises on malformed input (e.g. non-UTF-8 bytes); callers decide the fallback.
    """
    delimiter = '\t' if ext == 'tsv' else ','
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8')), delimiter=delimiter)
    return [dict(r) for r in reader]


def create_paired_task_source_item(image_upload, rows):
    """Create ONE 'pair' TaskSourceItem merging an image upload with parsed CSV rows.

    Uses sibling keys so the target config ($image + $data) resolves directly:
    ``{"image": <served url>, "data": [ {<col>: <val>, ...}, ... ]}``.
    """
    return TaskSourceItem.objects.create(
        dataset=image_upload,
        workspace=image_upload.workspace,
        data={'image': image_upload.url, 'data': rows},
        data_type=PAIR_DATA_TYPE,
        index=0,
    )


def materialize_task_source_items(upload, max_items=10000):
    """Parse a WorkspaceFileUpload into TaskSourceItem rows. Returns the count created."""
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
                TaskSourceItem(
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
            TaskSourceItem(
                dataset=upload,
                workspace=upload.workspace,
                data={key: upload.url or name},
                data_type=media,
                index=0,
            )
        )

    TaskSourceItem.objects.bulk_create(items)
    return len(items)


def materialize_uploads_with_pairing(named_uploads):
    """Materialize a single upload request, auto-pairing same-basename image + csv/tsv.

    ``named_uploads`` is a list of ``(original_filename, WorkspaceFileUpload)`` — the
    original filename is required because the stored name carries a UUID prefix.

    Same-basename groups of exactly one image + one tabular file merge into a single
    ``pair`` TaskSourceItem (sibling keys ``{"image": url, "data": [rows]}``). Every other
    upload — and any pair whose CSV fails to parse — falls back to the unchanged
    per-file :func:`materialize_task_source_items` path. Regression-safe for the common
    single-file case (a lone file is just an unpaired group).
    """
    groups = defaultdict(list)  # basename -> [(ext, upload), ...]
    for name, upload in named_uploads:
        groups[_basename(name)].append((_ext(name), upload))

    consumed = set()  # upload pks already turned into a pair item
    for members in groups.values():
        if len(members) != 2:
            continue
        images = [u for ext, u in members if _media_type_for_ext(ext) == 'image']
        tabulars = [(ext, u) for ext, u in members if ext in _TABULAR_EXTS]
        if len(images) != 1 or len(tabulars) != 1:
            continue
        image_upload = images[0]
        tab_ext, tab_upload = tabulars[0]
        try:
            rows = parse_tabular_rows(_read_upload_bytes(tab_upload), tab_ext)
        except Exception:
            # Malformed tabular file: leave both files to per-file materialization.
            logger.exception('Failed to parse tabular file for pairing (upload %s)', tab_upload.pk)
            continue
        create_paired_task_source_item(image_upload, rows)
        consumed.add(image_upload.pk)
        consumed.add(tab_upload.pk)

    for _name, upload in named_uploads:
        if upload.pk in consumed:
            continue
        try:
            materialize_task_source_items(upload)
        except Exception:
            logger.exception('Failed to materialize dataset items for upload %s', upload.pk)


@transaction.atomic
def materialize_pool_to_project(project):
    """Create project tasks from the project's selected Task Pool items.

    Returns the number of tasks created. Safe to call once at project setup; callers
    should guard against re-running (e.g. only when the project has no tasks yet).
    """
    pool = project.task_pool
    if pool is None:
        return 0
    from data_import.serializers import ImportApiSerializer
    from projects.models import Project

    # Lock the project row and re-check emptiness inside the lock: the caller's
    # tasks.exists() guard runs outside any lock, so two concurrent project saves could
    # both pass it and double-materialize the pool. Whoever gets the lock second sees the
    # tasks the first created and bails.
    Project.objects.select_for_update().filter(pk=project.pk).first()
    if project.tasks.exists():
        return 0

    task_source_items = TaskSourceItem.objects.filter(pool_items__task_pool=pool).order_by('id')
    tasks = []
    for it in task_source_items:
        task = {'data': it.data}
        if it.predictions:
            # Cloud-storage items may carry model predictions; pass them through.
            task['predictions'] = it.predictions
        tasks.append(task)
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
