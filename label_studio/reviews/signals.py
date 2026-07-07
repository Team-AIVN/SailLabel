"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from projects.models import Project
from tasks.models import Annotation

from . import services


@receiver(pre_save, sender=Annotation)
def annotation_pre_save(sender, instance, **kwargs):
    # Snapshot the stored result before the save so post_save can tell whether the
    # labeler actually changed the annotation content (vs a metadata-only / bulk save).
    if instance.pk:
        instance._prev_result = Annotation.objects.filter(pk=instance.pk).values_list('result', flat=True).first()
    else:
        instance._prev_result = None


@receiver(post_save, sender=Annotation)
def annotation_post_save(sender, instance, created, **kwargs):
    project = instance.project
    if project is None:
        return
    if created:
        # Auto-selection only runs for projects with a review strategy; plain projects
        # keep the stock annotation flow untouched.
        if project.review_strategy != Project.ReviewStrategy.NONE:
            services.on_annotation_created(instance)
    else:
        # A labeler updating an already-reviewed revision releases the prior decision.
        # Gated by the annotation's own reviewed status, so never-reviewed annotations
        # (plain projects) are a no-op here.
        services.on_annotation_updated(instance)
