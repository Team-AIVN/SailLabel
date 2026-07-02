"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from django.apps import AppConfig


class WorkspacesConfig(AppConfig):
    name = 'workspaces'

    def ready(self):
        # Register rules/predicates on app ready so django-rules picks them up.
        from . import rules, signals  # noqa: F401
