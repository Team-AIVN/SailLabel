# Generated for Phase 1 Workspace domain app.

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('organizations', '0006_alter_organizationmember_deleted_at'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Workspace',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'title',
                    models.CharField(
                        help_text='Workspace title. 3..256 chars.',
                        max_length=256,
                        validators=[
                            django.core.validators.MinLengthValidator(3),
                            django.core.validators.MaxLengthValidator(256),
                        ],
                        verbose_name='title',
                    ),
                ),
                ('description', models.TextField(blank=True, default='', verbose_name='description')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='created at')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='updated at')),
                (
                    'deleted_at',
                    models.DateTimeField(
                        blank=True,
                        db_index=True,
                        default=None,
                        help_text='If NULL, the workspace is not considered deleted.',
                        null=True,
                        verbose_name='deleted at',
                    ),
                ),
                (
                    'created_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='workspaces_created',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='created_by',
                    ),
                ),
                (
                    'deleted_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='workspaces_deleted',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='deleted by',
                    ),
                ),
                (
                    'organization',
                    models.ForeignKey(
                        help_text='Organization that owns the workspace',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='workspaces',
                        to='organizations.organization',
                    ),
                ),
            ],
            options={
                'db_table': 'workspace',
            },
        ),
        migrations.CreateModel(
            name='WorkspaceMember',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'role',
                    models.CharField(
                        choices=[('workspace_manager', 'Workspace Manager'), ('member', 'Member')],
                        default='member',
                        max_length=32,
                        verbose_name='role',
                    ),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='created at')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='updated at')),
                (
                    'deleted_at',
                    models.DateTimeField(
                        blank=True,
                        db_index=True,
                        default=None,
                        help_text='If NULL, the membership is not considered deleted.',
                        null=True,
                        verbose_name='deleted at',
                    ),
                ),
                (
                    'user',
                    models.ForeignKey(
                        help_text='User ID',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='workspace_memberships',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'workspace',
                    models.ForeignKey(
                        help_text='Workspace ID',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='members',
                        to='workspaces.workspace',
                    ),
                ),
            ],
            options={
                'db_table': 'workspace_member',
            },
        ),
        migrations.AddConstraint(
            model_name='workspace',
            constraint=models.UniqueConstraint(
                condition=models.Q(('deleted_at__isnull', True)),
                fields=('organization', 'title'),
                name='uniq_workspace_title_per_org',
            ),
        ),
        migrations.AddIndex(
            model_name='workspace',
            index=models.Index(fields=['organization', '-created_at'], name='workspace_organiz_53b0cc_idx'),
        ),
        migrations.AddIndex(
            model_name='workspace',
            index=models.Index(fields=['organization', 'deleted_at'], name='workspace_organiz_c01df0_idx'),
        ),
        migrations.AddConstraint(
            model_name='workspacemember',
            constraint=models.UniqueConstraint(fields=('user', 'workspace'), name='uniq_workspace_member'),
        ),
    ]
