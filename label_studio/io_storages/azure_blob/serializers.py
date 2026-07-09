"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from core.utils.exceptions import extract_message
from io_storages.azure_blob.models import (
    AzureBlobExportStorage,
    AzureBlobImportStorage,
    AzureBlobWorkspaceImportStorage,
)
from io_storages.serializers import ExportStorageSerializer, ImportStorageSerializer
from rest_framework import serializers
from rest_framework.exceptions import ValidationError


class AzureBlobImportStorageSerializer(ImportStorageSerializer):
    type = serializers.ReadOnlyField(default='azure')
    presign = serializers.BooleanField(required=False, default=True)
    secure_fields = ['account_name', 'account_key']

    class Meta:
        model = AzureBlobImportStorage
        fields = '__all__'

    def to_representation(self, instance):
        result = super().to_representation(instance)
        for attr in AzureBlobImportStorageSerializer.secure_fields:
            result.pop(attr)
        return result

    def validate(self, data):
        data = super(AzureBlobImportStorageSerializer, self).validate(data)
        storage = self.instance
        if storage:
            for key, value in data.items():
                setattr(storage, key, value)
        else:
            if 'id' in self.initial_data:
                storage_object = self.Meta.model.objects.get(id=self.initial_data['id'])
                for attr in AzureBlobImportStorageSerializer.secure_fields:
                    data[attr] = data.get(attr) or getattr(storage_object, attr)
            storage = self.Meta.model(**data)
        try:
            storage.validate_connection()
        except Exception as exc:
            raise ValidationError(extract_message(exc))
        return data


class AzureBlobWorkspaceImportStorageSerializer(ImportStorageSerializer):
    """Workspace-scope Azure Blob template. Reuses the same credential/connection
    validation from the project-scope serializer, scoped to a workspace."""

    type = serializers.ReadOnlyField(default='azure')
    presign = serializers.BooleanField(required=False, default=True)
    task_pool_title = serializers.CharField(source='task_pool.title', read_only=True, default=None)
    secure_fields = ['account_name', 'account_key']

    class Meta:
        model = AzureBlobWorkspaceImportStorage
        fields = '__all__'

    def to_representation(self, instance):
        result = super().to_representation(instance)
        for attr in AzureBlobWorkspaceImportStorageSerializer.secure_fields:
            result.pop(attr)
        return result

    def validate(self, data):
        data = super().validate(data)
        # When the storage piggybacks on the server's shared credentials (no account_key
        # supplied → env fallback), pin the container to the deployment default. Otherwise
        # a manager could point a workspace storage at any container in the shared account.
        # A manager bringing their OWN account_key may use any container.
        from core.utils.params import get_env

        provided_key = data.get('account_key') or (self.instance and self.instance.account_key)
        if not provided_key:
            default_container = get_env('AZURE_BLOB_DEFAULT_CONTAINER')
            requested = data.get('container') or (self.instance and self.instance.container)
            if default_container and requested and requested != default_container:
                raise ValidationError(
                    {'container': f'Only the default container ({default_container}) is allowed with server credentials.'}
                )
        storage = self.instance
        if storage:
            for key, value in data.items():
                setattr(storage, key, value)
        else:
            if 'id' in self.initial_data:
                storage_object = self.Meta.model.objects.get(id=self.initial_data['id'])
                for attr in AzureBlobWorkspaceImportStorageSerializer.secure_fields:
                    data[attr] = data.get(attr) or getattr(storage_object, attr)
            storage = self.Meta.model(**data)
        try:
            storage.validate_connection()
        except Exception as exc:
            raise ValidationError(extract_message(exc))
        return data


class AzureBlobExportStorageSerializer(ExportStorageSerializer):
    type = serializers.ReadOnlyField(default='azure')

    def to_representation(self, instance):
        result = super().to_representation(instance)
        result.pop('account_name')
        result.pop('account_key')
        return result

    class Meta:
        model = AzureBlobExportStorage
        fields = '__all__'
