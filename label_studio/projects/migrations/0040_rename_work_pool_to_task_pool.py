"""Terminology rename: Project.work_pool -> Project.task_pool (FK now points at
workspaces.TaskPool). Depends on the workspaces rename migration so the renamed
model exists first.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('projects', '0039_project_work_pool'),
        ('workspaces', '0005_rename_task_pool_terms'),
    ]

    operations = [
        migrations.RenameField(model_name='project', old_name='work_pool', new_name='task_pool'),
    ]
