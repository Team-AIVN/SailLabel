"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from django.urls import include, path

from . import api

app_name = 'settlement'

_project_api_urlpatterns = [
    path(
        '<int:project_pk>/pricing/',
        api.ProjectPricingAPI.as_view(),
        name='project-pricing',
    ),
    path(
        '<int:project_pk>/settlements/',
        api.ProjectSettlementListAPI.as_view(),
        name='project-settlement-list',
    ),
]

_batch_api_urlpatterns = [
    path(
        '<int:pk>/',
        api.SettlementBatchDetailAPI.as_view(),
        name='settlement-detail',
    ),
    path(
        '<int:pk>/report/',
        api.SettlementReportAPI.as_view(),
        name='settlement-report',
    ),
]


urlpatterns = [
    path(
        'api/projects/',
        include((_project_api_urlpatterns, app_name), namespace='project-settlement'),
    ),
    path(
        'api/settlements/',
        include((_batch_api_urlpatterns, app_name), namespace='settlement'),
    ),
]
