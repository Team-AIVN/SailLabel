"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = (
            'id',
            'created_at',
            'actor',
            'actor_email',
            'organization',
            'action',
            'target_type',
            'target_id',
            'metadata',
        )
        read_only_fields = fields

    def get_actor_email(self, obj):
        return getattr(obj.actor, 'email', None)
