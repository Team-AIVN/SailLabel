"""Backfill `Annotation.current_state` for rows that pre-date Phase 4.

Mapping (per `instructions.md` §Phase 4 / §8):
- `ground_truth=True`   → ACCEPTED
- `was_cancelled=True`  → REJECTED
- otherwise             → ANNOTATED

This is advisory — new rows will have their state managed by the FSM
transition hooks, so this migration only covers the historical backlog.
"""

from django.db import migrations


BATCH_SIZE = 5000


def _chunked_update(manager, predicate, new_state):
    qs = manager.filter(predicate, current_state__isnull=True).values_list('pk', flat=True)
    ids = list(qs)
    for start in range(0, len(ids), BATCH_SIZE):
        batch = ids[start:start + BATCH_SIZE]
        manager.filter(pk__in=batch).update(current_state=new_state)


def forwards(apps, schema_editor):
    Annotation = apps.get_model('tasks', 'Annotation')
    from django.db.models import Q

    _chunked_update(Annotation.objects, Q(ground_truth=True), 'ACCEPTED')
    _chunked_update(
        Annotation.objects, Q(was_cancelled=True) & Q(ground_truth=False), 'REJECTED'
    )
    _chunked_update(
        Annotation.objects,
        Q(ground_truth=False) & Q(was_cancelled=False),
        'ANNOTATED',
    )


def backwards(apps, schema_editor):
    Annotation = apps.get_model('tasks', 'Annotation')
    Annotation.objects.update(current_state=None)


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0062_annotation_current_state'),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
