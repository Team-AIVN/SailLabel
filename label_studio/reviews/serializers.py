"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from rest_framework import serializers
from users.serializers import UserSimpleSerializer

from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    reviewer_detail = UserSimpleSerializer(source='reviewer', read_only=True)

    class Meta:
        model = Review
        fields = ('id', 'annotation', 'project', 'reviewer', 'reviewer_detail', 'decision', 'comment', 'stage', 'created_at')
        read_only_fields = ('project', 'reviewer', 'created_at')


class ReviewSubmitSerializer(serializers.Serializer):
    """Input for submitting a review decision on an annotation."""

    decision = serializers.ChoiceField(choices=Review.Decision.choices)
    comment = serializers.CharField(required=False, allow_blank=True, default='')
    # required only for FIX_AND_ACCEPT — the corrected annotation result
    content = serializers.JSONField(required=False)
    stage = serializers.IntegerField(required=False, min_value=1, default=1)


class ReviewCandidateSerializer(serializers.Serializer):
    """A task whose current annotation is awaiting review (Task List UI source)."""

    task_id = serializers.IntegerField(source='id')
    current_annotation_id = serializers.IntegerField()
    annotation_version = serializers.SerializerMethodField()
    annotator = serializers.SerializerMethodField()
    review_status = serializers.CharField()
    reviewer = serializers.SerializerMethodField()

    def get_annotation_version(self, task):
        return getattr(task.current_annotation, 'version', None)

    def get_annotator(self, task):
        # The original annotator = earliest annotation in the task. For FIX_AND_ACCEPT the
        # task's current_annotation is a reviewer-authored revision, so reading current
        # would wrongly show the reviewer as the annotator.
        root = task.annotations.order_by('id').first()
        user = getattr(root, 'completed_by', None) if root else None
        return UserSimpleSerializer(user).data if user else None

    def get_reviewer(self, task):
        # Latest review across ALL of the task's annotation revisions. For FIX_AND_ACCEPT
        # the Review is attached to the original annotation while current_annotation points
        # at the new revision, so looking only at current_annotation.reviews misses it.
        review = (
            Review.objects.filter(annotation__task=task)
            .select_related('reviewer')
            .order_by('-created_at', '-id')
            .first()
        )
        return UserSimpleSerializer(review.reviewer).data if review and review.reviewer else None


class ReviewProgressSerializer(serializers.Serializer):
    annotation_progress = serializers.IntegerField()
    review_progress = serializers.IntegerField()
    total_tasks = serializers.IntegerField()
    review_selected = serializers.IntegerField()
    review_completed = serializers.IntegerField()
