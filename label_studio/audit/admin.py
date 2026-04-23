"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'action', 'actor', 'organization', 'target_type', 'target_id')
    list_filter = ('action', 'target_type')
    search_fields = ('actor__email', 'target_id')
    readonly_fields = ('created_at', 'actor', 'organization', 'action', 'target_type', 'target_id', 'metadata')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
