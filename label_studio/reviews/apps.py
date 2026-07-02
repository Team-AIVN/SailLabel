"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from django.apps import AppConfig


class ReviewsConfig(AppConfig):
    name = 'reviews'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        # Register the annotation-completion signal that assigns revision versions
        # and applies review selection for review-enabled projects.
        from reviews import signals  # noqa: F401
