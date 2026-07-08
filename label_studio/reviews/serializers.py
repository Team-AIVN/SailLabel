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
    reviews = serializers.SerializerMethodField()

    def get_annotation_version(self, task):
        return getattr(task.current_annotation, 'version', None)

    def get_annotator(self, task):
        # The original annotator = earliest annotation in the task. For FIX_AND_ACCEPT the
        # task's current_annotation is a reviewer-authored revision, so reading current
        # would wrongly show the reviewer as the annotator. Uses the prefetched
        # annotations (sorted in Python) to avoid a per-task query.
        anns = sorted(task.annotations.all(), key=lambda a: a.id)
        user = getattr(anns[0], 'completed_by', None) if anns else None
        return UserSimpleSerializer(user).data if user else None

    def get_reviews(self, task):
        # Every review decision on the task (across revisions), newest first, so the
        # Review page can list each decision as its own row. Reads from the prefetched
        # annotations/reviews (no per-task query).
        rows = [(r, ann.version) for ann in task.annotations.all() for r in ann.reviews.all()]
        rows.sort(key=lambda pair: (pair[0].created_at, pair[0].id), reverse=True)
        return [
            {
                'id': r.id,
                'decision': r.decision,
                'comment': r.comment or '',
                'reviewer': UserSimpleSerializer(r.reviewer).data if r.reviewer else None,
                'created_at': r.created_at,
                'annotation_version': version,
            }
            for r, version in rows
        ]


class ReviewProgressSerializer(serializers.Serializer):
    annotation_progress = serializers.IntegerField()
    review_progress = serializers.IntegerField()
    total_tasks = serializers.IntegerField()
    review_selected = serializers.IntegerField()
    review_completed = serializers.IntegerField()
