"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from rest_framework import serializers
from users.serializers import UserSimpleSerializer

from .models import Workspace, WorkspaceMember


class WorkspaceSerializer(serializers.ModelSerializer):
    project_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Workspace
        fields = (
            'id',
            'title',
            'description',
            'organization',
            'created_by',
            'created_at',
            'updated_at',
            'project_count',
        )
        read_only_fields = ('organization', 'created_by', 'created_at', 'updated_at', 'project_count')

    def get_project_count(self, obj: Workspace) -> int:
        # Uses the related manager named "projects" declared on Project.workspace FK.
        projects = getattr(obj, 'projects', None)
        if projects is None:
            return 0
        return projects.filter(deleted_at__isnull=True).count()


class WorkspaceMemberSerializer(serializers.ModelSerializer):
    user_detail = UserSimpleSerializer(source='user', read_only=True)

    class Meta:
        model = WorkspaceMember
        fields = ('id', 'user', 'user_detail', 'role', 'created_at', 'updated_at')
        read_only_fields = ('created_at', 'updated_at')
