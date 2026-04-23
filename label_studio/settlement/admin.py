"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from django.contrib import admin

from .models import (
    ProjectPricing,
    ProjectPricingHistory,
    SettlementBatch,
    SettlementItem,
)


@admin.register(ProjectPricing)
class ProjectPricingAdmin(admin.ModelAdmin):
    list_display = ('project', 'label_price', 'review_price', 'currency', 'updated_at')
    list_filter = ('currency',)
    search_fields = ('project__title',)
    raw_id_fields = ('project', 'updated_by')


@admin.register(ProjectPricingHistory)
class ProjectPricingHistoryAdmin(admin.ModelAdmin):
    list_display = ('project', 'label_price', 'review_price', 'currency', 'changed_at', 'changed_by')
    list_filter = ('currency',)
    raw_id_fields = ('project', 'changed_by')
    readonly_fields = ('changed_at',)


class SettlementItemInline(admin.TabularInline):
    model = SettlementItem
    extra = 0
    can_delete = False
    readonly_fields = (
        'user', 'accepted_count', 'review_count', 'label_amount', 'review_amount',
        'amount', 'currency',
    )
    raw_id_fields = ('user',)


@admin.register(SettlementBatch)
class SettlementBatchAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'project', 'period_start', 'period_end', 'status', 'total_amount',
        'currency', 'created_at', 'completed_at',
    )
    list_filter = ('status', 'currency')
    search_fields = ('project__title',)
    raw_id_fields = ('project', 'created_by')
    inlines = [SettlementItemInline]


@admin.register(SettlementItem)
class SettlementItemAdmin(admin.ModelAdmin):
    list_display = (
        'batch', 'user', 'accepted_count', 'review_count', 'label_amount',
        'review_amount', 'amount', 'currency',
    )
    list_filter = ('currency',)
    raw_id_fields = ('batch', 'user')
