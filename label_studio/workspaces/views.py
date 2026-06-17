"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

logger = logging.getLogger(__name__)


@login_required
def workspace_pages(request, pk=None, sub_path=None):
    """Serve the React SPA for workspace list and detail routes.

    Mirrors ``data_manager.views.task_page`` / ``projects.views.project_list``:
    the actual UI is rendered client-side by the React app; this view only
    returns the base template so a hard page load (or refresh) on a workspace
    URL resolves instead of 404-ing.
    """
    return render(request, 'base.html')
