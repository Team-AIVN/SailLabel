"""Terminology rename: DatasetItem -> TaskSourceItem, WorkPool -> TaskPool,
WorkPoolItem -> TaskPoolItem (and its FK fields/columns).

Table names are kept (no table rename). The unique constraint and index that
reference the renamed FK fields are dropped here BEFORE the field rename (so the
rename does not collide with them) and re-created in migration 0006.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('workspaces', '0004_datasetitem_workpool_workpoolitem_and_more'),
    ]

    operations = [
        # Drop objects referencing the columns being renamed (re-added in 0006).
        migrations.RemoveConstraint(model_name='workpoolitem', name='uniq_work_pool_item'),
        migrations.RemoveIndex(model_name='workpoolitem', name='work_pool_i_work_po_d7fb34_idx'),
        # Rename the models (db_table kept -> no table rename).
        migrations.RenameModel(old_name='DatasetItem', new_name='TaskSourceItem'),
        migrations.RenameModel(old_name='WorkPool', new_name='TaskPool'),
        migrations.RenameModel(old_name='WorkPoolItem', new_name='TaskPoolItem'),
        # Rename the FK fields (columns: work_pool_id -> task_pool_id, dataset_item_id -> task_source_item_id).
        migrations.RenameField(model_name='taskpoolitem', old_name='work_pool', new_name='task_pool'),
        migrations.RenameField(model_name='taskpoolitem', old_name='dataset_item', new_name='task_source_item'),
    ]
