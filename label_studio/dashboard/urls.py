"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from django.urls import path

from . import api

app_name = 'dashboard'

urlpatterns = [
    path(
        'api/dashboard/summary/',
        api.DashboardSummaryAPI.as_view(),
        name='dashboard-summary',
    ),
]
