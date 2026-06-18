"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from django.urls import include, path

from . import api

app_name = 'compensation'

_api_urlpatterns = [
    path(
        'projects/<int:pk>/compensation-policy/',
        api.ProjectCompensationPolicyAPI.as_view(),
        name='project-compensation-policy',
    ),
    path(
        'workspaces/<int:pk>/compensation/',
        api.WorkspaceCompensationAPI.as_view(),
        name='workspace-compensation',
    ),
    path(
        'workspaces/<int:pk>/compensation/members/<int:user_pk>/',
        api.MemberCompensationAPI.as_view(),
        name='member-compensation',
    ),
    path(
        'workspaces/<int:pk>/payments/',
        api.PaymentRecordListCreateAPI.as_view(),
        name='workspace-payments',
    ),
    path(
        'workspaces/<int:pk>/payments/<int:payment_pk>/',
        api.PaymentRecordDetailAPI.as_view(),
        name='workspace-payment-detail',
    ),
]

urlpatterns = [
    path('api/', include((_api_urlpatterns, app_name), namespace='api')),
]
