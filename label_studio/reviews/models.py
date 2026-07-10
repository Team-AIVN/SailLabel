"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Review(models.Model):
    """A reviewer decision on a specific annotation revision.

    Reviews link to Annotation revisions (not Tasks) so the full annotation + review
    history stays traceable. ``stage`` supports future multi-stage review pipelines
    (first review, second review, expert review, customer review, ...).
    """

    class Decision(models.TextChoices):
        ACCEPT = 'ACCEPT', _('Accept')
        REJECT = 'REJECT', _('Reject')
        FIX_AND_ACCEPT = 'FIX_AND_ACCEPT', _('Fix and accept')
        # Logged (not a reviewer action) when a labeler edits an annotation — shown in
        # the activity timeline. `reviewer` then holds the labeler who made the edit.
        RESUBMITTED = 'RESUBMITTED', _('Resubmitted after edit')

    # Decisions an actual reviewer made. Anything reading "who reviewed this / when" must
    # filter on these — a labeler's RESUBMITTED edit is an activity entry, not a review,
    # and would otherwise show the labeler in the Data Manager's "reviewer" column.
    REVIEWER_DECISIONS = (Decision.ACCEPT, Decision.REJECT, Decision.FIX_AND_ACCEPT)

    annotation = models.ForeignKey(
        'tasks.Annotation',
        on_delete=models.CASCADE,
        related_name='reviews',
        help_text='Annotation revision being reviewed.',
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='reviews',
        help_text='Project the reviewed annotation belongs to (denormalized for queries).',
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviews',
        help_text='User who performed the review.',
    )
    decision = models.CharField(_('decision'), max_length=32, choices=Decision.choices)
    comment = models.TextField(_('comment'), blank=True, default='')
    stage = models.PositiveIntegerField(
        _('stage'),
        default=1,
        help_text='Review stage (1=first review). Reserved for multi-stage review workflows.',
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)

    class Meta:
        db_table = 'review'
        indexes = [
            models.Index(fields=['project', '-created_at']),
            models.Index(fields=['annotation', 'stage']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f'Review(annotation={self.annotation_id}, decision={self.decision}, stage={self.stage})'
