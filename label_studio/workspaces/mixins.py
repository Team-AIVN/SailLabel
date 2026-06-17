"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""


class WorkspaceMixin:
    """OSS no-op mixin. LSE can override settings.WORKSPACE_MIXIN to inject fields/methods."""

    def has_permission(self, user):
        user.workspace = self  # link for activity log, same pattern as ProjectMixin
        return True
