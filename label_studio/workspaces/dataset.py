"""Dataset assignment: distribute a workspace's uploaded data to a project.

A workspace owns a pool of :class:`workspaces.models.WorkspaceFileUpload` files. A
workspace manager assigns a slice of that pool to a project inside the workspace, by
absolute ``count`` of task records or by ``ratio`` of the whole dataset. The slice is
materialised as ordinary project tasks via the standard import pipeline, so everything
downstream (data manager, export, annotation) works unchanged.
"""

import logging
import math

from data_import.models import FileUpload
from data_import.serializers import ImportApiSerializer
from data_import.uploader import create_file_upload
from django.core.files import File
from django.db import transaction
from projects.models import ProjectSummary
from rest_framework.exceptions import ValidationError

logger = logging.getLogger(__name__)


def resolve_assignment_size(total, count=None, ratio=None):
    """Return how many records to assign given exactly one of count/ratio."""
    if (count is None) == (ratio is None):
        raise ValidationError('Provide exactly one of `count` or `ratio`.')

    if count is not None:
        try:
            n = int(count)
        except (TypeError, ValueError):
            raise ValidationError('`count` must be an integer.')
        if n < 0:
            raise ValidationError('`count` must be >= 0.')
        return min(n, total)

    try:
        r = float(ratio)
    except (TypeError, ValueError):
        raise ValidationError('`ratio` must be a number between 0 and 1.')
    if not 0 <= r <= 1:
        raise ValidationError('`ratio` must be between 0 and 1.')
    # round up so a non-zero ratio of a non-empty dataset always assigns at least one.
    return min(total, math.ceil(r * total))


@transaction.atomic
def assign_workspace_dataset(*, workspace, project, user, count=None, ratio=None, file_upload_ids=None):
    """Copy a slice of the workspace dataset into a project as tasks.

    Returns ``{'project', 'assigned', 'available'}`` where ``available`` is the total
    number of task records found across the selected workspace files.
    """
    if project.workspace_id != workspace.id:
        raise ValidationError('Project does not belong to this workspace.')

    ws_uploads = workspace.file_uploads.all().order_by('created_at', 'id')
    if file_upload_ids:
        ws_uploads = ws_uploads.filter(id__in=file_upload_ids)
    ws_uploads = list(ws_uploads)
    if not ws_uploads:
        raise ValidationError('No workspace files available to assign.')

    # Copy each source file into the project-scoped import pool so the standard
    # parser (which is project-aware) can read it.
    new_upload_ids = []
    for ws in ws_uploads:
        ws.file.open('rb')
        try:
            project_file = create_file_upload(user, project, File(ws.file, name=ws.file_name))
        finally:
            ws.file.close()
        new_upload_ids.append(project_file.id)

    tasks, _formats, _data_fields = FileUpload.load_tasks_from_uploaded_files(
        project, file_upload_ids=new_upload_ids
    )
    total = len(tasks)
    n = resolve_assignment_size(total, count=count, ratio=ratio)
    selected = tasks[:n]

    created = 0
    if selected:
        ProjectSummary.objects.get_or_create(project=project)
        summary = ProjectSummary.objects.select_for_update().get(project=project)
        serializer = ImportApiSerializer(data=selected, many=True, context={'project': project})
        serializer.is_valid(raise_exception=True)
        saved = serializer.save(project_id=project.id)
        created = len(saved)
        project.update_tasks_counters_and_task_states(
            tasks_queryset=saved,
            maximum_annotations_changed=False,
            overlap_cohort_percentage_changed=False,
            tasks_number_changed=True,
            recalculate_stats_counts={
                'task_count': created,
                'annotation_count': len(serializer.db_annotations),
                'prediction_count': len(serializer.db_predictions),
            },
        )
        summary.update_data_columns(saved)

    return {'project': project.id, 'assigned': created, 'available': total}
