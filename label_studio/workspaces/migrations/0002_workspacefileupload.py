# Generated for workspace-scoped file uploads.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import workspaces.models


class Migration(migrations.Migration):

    dependencies = [
        ('workspaces', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkspaceFileUpload',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to=workspaces.models._workspace_upload_path)),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='created at')),
                (
                    'user',
                    models.ForeignKey(
                        help_text='User that uploaded the file',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='workspace_file_uploads',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'workspace',
                    models.ForeignKey(
                        help_text='Workspace that owns the file',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='file_uploads',
                        to='workspaces.workspace',
                    ),
                ),
            ],
            options={
                'db_table': 'workspace_file_upload',
                'indexes': [
                    models.Index(fields=['workspace', '-created_at'], name='workspace_f_workspa_bf3bd0_idx'),
                ],
            },
        ),
    ]
