"""Backfill Project.workspace by creating a per-organization Default workspace.

For every Organization, ensure a Workspace named 'Default' exists and assign every
Project in that organization whose workspace is NULL to it. The Organization owner is
registered as a workspace_manager so they can immediately manage the default workspace.
"""

from django.db import migrations


def forwards(apps, schema_editor):
    Organization = apps.get_model('organizations', 'Organization')
    Workspace = apps.get_model('workspaces', 'Workspace')
    WorkspaceMember = apps.get_model('workspaces', 'WorkspaceMember')
    Project = apps.get_model('projects', 'Project')

    for org in Organization.objects.all():
        workspace, created = Workspace.objects.get_or_create(
            organization=org,
            title='Default',
            defaults={
                'created_by_id': org.created_by_id,
                'description': '',
            },
        )

        if created and org.created_by_id:
            WorkspaceMember.objects.get_or_create(
                user_id=org.created_by_id,
                workspace=workspace,
                defaults={'role': 'workspace_manager'},
            )

        Project.objects.filter(organization=org, workspace__isnull=True).update(workspace=workspace)


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0035_project_workspace'),
        ('workspaces', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
