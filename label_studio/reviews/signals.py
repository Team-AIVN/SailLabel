"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from django.db.models.signals import post_save
from django.dispatch import receiver
from projects.models import Project
from tasks.models import Annotation

from . import services


@receiver(post_save, sender=Annotation)
def annotation_post_save(sender, instance, created, **kwargs):
    # Only act on newly created annotations in review-enabled projects; non-review
    # projects keep the stock annotation flow untouched.
    if not created:
        return
    project = instance.project
    if project is None or project.review_strategy == Project.ReviewStrategy.NONE:
        return
    services.on_annotation_created(instance)
