"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from rest_framework import serializers

from .models import PaymentRecord, ProjectCompensationPolicy


class ProjectCompensationPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectCompensationPolicy
        fields = (
            'id',
            'project',
            'currency',
            'annotation_unit_price',
            'review_unit_price',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'project', 'created_at', 'updated_at')
        # Every pricing field has a model default, so an empty payload would otherwise
        # validate and silently create a "USD, 0.00" policy — money quietly set to zero.
        # Required on create; a partial update (existing policy) bypasses this.
        extra_kwargs = {
            'currency': {'required': True},
            'annotation_unit_price': {'required': True},
            'review_unit_price': {'required': True},
        }

    def validate_annotation_unit_price(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError('annotation_unit_price must be >= 0.')
        return value

    def validate_review_unit_price(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError('review_unit_price must be >= 0.')
        return value


class PaymentRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentRecord
        fields = (
            'id',
            'workspace',
            'project',
            'user',
            'currency',
            'amount',
            'paid_at',
            'memo',
            'created_at',
        )
        read_only_fields = ('id', 'workspace', 'created_at')

    def validate_amount(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError('amount must be greater than 0.')
        return value
