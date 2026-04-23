"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from rest_framework import serializers
from users.serializers import UserSimpleSerializer

from .models import Currency, ProjectPricing, SettlementBatch, SettlementItem


class ProjectPricingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectPricing
        fields = (
            'id',
            'project',
            'label_price',
            'review_price',
            'currency',
            'updated_at',
            'updated_by',
        )
        read_only_fields = ('project', 'updated_at', 'updated_by')

    def validate_label_price(self, value):
        if value < 0:
            raise serializers.ValidationError('label_price must be non-negative.')
        return value

    def validate_review_price(self, value):
        if value < 0:
            raise serializers.ValidationError('review_price must be non-negative.')
        return value

    def validate_currency(self, value):
        if value not in Currency.values:
            raise serializers.ValidationError(f'currency must be one of {list(Currency.values)}.')
        return value


class SettlementItemSerializer(serializers.ModelSerializer):
    user_detail = UserSimpleSerializer(source='user', read_only=True)

    class Meta:
        model = SettlementItem
        fields = (
            'id',
            'batch',
            'user',
            'user_detail',
            'accepted_count',
            'review_count',
            'label_amount',
            'review_amount',
            'amount',
            'currency',
        )
        read_only_fields = fields


class SettlementBatchSerializer(serializers.ModelSerializer):
    items = SettlementItemSerializer(many=True, read_only=True)

    class Meta:
        model = SettlementBatch
        fields = (
            'id',
            'project',
            'period_start',
            'period_end',
            'status',
            'label_price_snapshot',
            'review_price_snapshot',
            'currency',
            'total_amount',
            'accepted_annotation_count',
            'review_count',
            'created_by',
            'created_at',
            'completed_at',
            'error_message',
            'items',
        )
        read_only_fields = (
            'project',
            'status',
            'label_price_snapshot',
            'review_price_snapshot',
            'currency',
            'total_amount',
            'accepted_annotation_count',
            'review_count',
            'created_by',
            'created_at',
            'completed_at',
            'error_message',
            'items',
        )

    def validate(self, attrs):
        period_start = attrs.get('period_start')
        period_end = attrs.get('period_end')
        if period_start and period_end and period_end <= period_start:
            raise serializers.ValidationError('period_end must be strictly greater than period_start.')
        return attrs


class SettlementBatchListSerializer(serializers.ModelSerializer):
    """Lighter projection for list endpoints — omits nested items."""

    class Meta:
        model = SettlementBatch
        fields = (
            'id',
            'project',
            'period_start',
            'period_end',
            'status',
            'currency',
            'total_amount',
            'accepted_annotation_count',
            'review_count',
            'created_by',
            'created_at',
            'completed_at',
        )
        read_only_fields = fields
