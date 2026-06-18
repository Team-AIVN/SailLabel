"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

import os

from projects.models import Project
from rest_framework import serializers
from users.serializers import UserSimpleSerializer

from .models import DatasetItem, Workspace, WorkPool, WorkspaceFileUpload, WorkspaceMember


def _derive_label_type(parsed_label_config):
    """Pick a human-facing labeling type from a project's parsed label config."""
    if not parsed_label_config:
        return None
    for cfg in parsed_label_config.values():
        control_type = cfg.get('type') if isinstance(cfg, dict) else None
        if control_type:
            return control_type
    return None


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


class WorkspaceFileUploadSerializer(serializers.ModelSerializer):
    file = serializers.SerializerMethodField(read_only=True)
    size = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = WorkspaceFileUpload
        fields = ('id', 'workspace', 'user', 'file', 'size', 'created_at')
        read_only_fields = ('workspace', 'user', 'file', 'size', 'created_at')

    def get_file(self, obj: WorkspaceFileUpload) -> str:
        return obj.file_name

    def get_size(self, obj: WorkspaceFileUpload):
        return obj.size


class WorkspaceSummarySerializer(serializers.ModelSerializer):
    """Workspace header summary with resource totals for the dashboard."""

    total_users = serializers.SerializerMethodField()
    total_datasets = serializers.SerializerMethodField()
    total_projects = serializers.SerializerMethodField()
    total_work_pools = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = (
            'id',
            'title',
            'description',
            'created_at',
            'total_users',
            'total_datasets',
            'total_projects',
            'total_work_pools',
        )

    def get_total_users(self, obj) -> int:
        return obj.members.filter(deleted_at__isnull=True).count()

    def get_total_datasets(self, obj) -> int:
        return obj.file_uploads.count()

    def get_total_projects(self, obj) -> int:
        return obj.projects.filter(deleted_at__isnull=True).count()

    def get_total_work_pools(self, obj) -> int:
        return obj.work_pools.count()


class WorkspaceDatasetSerializer(serializers.ModelSerializer):
    """A workspace file upload presented as a dataset row."""

    name = serializers.SerializerMethodField()
    data_type = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()
    last_updated = serializers.DateTimeField(source='created_at', read_only=True)
    size = serializers.SerializerMethodField()

    class Meta:
        model = WorkspaceFileUpload
        fields = ('id', 'name', 'data_type', 'item_count', 'last_updated', 'size')

    def get_name(self, obj) -> str:
        return obj.file_name

    def get_data_type(self, obj) -> str:
        ext = os.path.splitext(obj.file_name or '')[1].lstrip('.').upper()
        return ext or 'FILE'

    def get_item_count(self, obj):
        # Record-level counts require parsing the file; left null for the list view.
        return None

    def get_size(self, obj):
        return obj.size


class WorkspaceProjectCardSerializer(serializers.ModelSerializer):
    """Project card for the workspace dashboard.

    ``label_type`` is derived from the parsed label config; ``review_progress``
    is the share of fully-completed (review-finished) tasks. Count fields come
    from ``Project.objects.with_counts()`` annotations.
    """

    label_type = serializers.SerializerMethodField()
    review_progress = serializers.SerializerMethodField()
    task_number = serializers.IntegerField(read_only=True, default=None)
    finished_task_number = serializers.IntegerField(read_only=True, default=None)

    class Meta:
        model = Project
        fields = (
            'id',
            'title',
            'description',
            'label_type',
            'review_progress',
            'due_date',
            'tags',
            'task_number',
            'finished_task_number',
            'created_at',
        )

    def get_label_type(self, obj):
        return _derive_label_type(obj.parsed_label_config)

    def get_review_progress(self, obj) -> int:
        total = getattr(obj, 'task_number', None) or 0
        finished = getattr(obj, 'finished_task_number', None) or 0
        if not total:
            return 0
        return round(finished / total * 100)


class DatasetItemSerializer(serializers.ModelSerializer):
    """A dataset item for the Work Pool left-panel browser."""

    thumbnail = serializers.SerializerMethodField()
    included = serializers.SerializerMethodField()

    class Meta:
        model = DatasetItem
        fields = ('id', 'dataset', 'data', 'data_type', 'index', 'thumbnail', 'included')

    def get_thumbnail(self, obj):
        if isinstance(obj.data, dict):
            for value in obj.data.values():
                if isinstance(value, str) and ('://' in value or value.startswith('/')):
                    return value
        return None

    def get_included(self, obj):
        ids = self.context.get('included_item_ids')
        return obj.id in ids if ids is not None else False


class WorkPoolSerializer(serializers.ModelSerializer):
    item_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = WorkPool
        fields = ('id', 'workspace', 'title', 'description', 'item_count', 'created_by', 'created_at', 'updated_at')
        read_only_fields = ('workspace', 'created_by', 'created_at', 'updated_at', 'item_count')

    def get_item_count(self, obj) -> int:
        return getattr(obj, 'item_count_annotated', None) if hasattr(obj, 'item_count_annotated') else obj.items.count()


class WorkPoolDetailSerializer(WorkPoolSerializer):
    items = serializers.SerializerMethodField()

    class Meta(WorkPoolSerializer.Meta):
        fields = WorkPoolSerializer.Meta.fields + ('items',)

    def get_items(self, obj):
        dataset_items = [pi.dataset_item for pi in obj.items.select_related('dataset_item').order_by('id')]
        return DatasetItemSerializer(dataset_items, many=True, context=self.context).data
