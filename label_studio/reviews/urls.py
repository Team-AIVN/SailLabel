"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from django.urls import include, path

from . import api

app_name = 'reviews'

_api_urlpatterns = [
    path('projects/<int:pk>/review/candidates/', api.ReviewCandidatesAPI.as_view(), name='review-candidates'),
    path('projects/<int:pk>/review/tasks/', api.ReviewTasksAPI.as_view(), name='review-tasks'),
    path('projects/<int:pk>/review/progress/', api.ReviewProgressAPI.as_view(), name='review-progress'),
    path('annotations/<int:pk>/review/', api.AnnotationReviewAPI.as_view(), name='annotation-review'),
]

urlpatterns = [
    path('api/', include((_api_urlpatterns, app_name), namespace='api')),
]
