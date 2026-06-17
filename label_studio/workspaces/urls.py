"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from django.urls import include, path

from . import api

app_name = 'workspaces'

_api_urlpatterns = [
    path('', api.WorkspaceListAPI.as_view(), name='workspace-list'),
    path('<int:pk>/', api.WorkspaceDetailAPI.as_view(), name='workspace-detail'),
    path('<int:pk>/members/', api.WorkspaceMembersAPI.as_view(), name='workspace-members'),
    path(
        '<int:pk>/members/<int:member_pk>/',
        api.WorkspaceMemberDetailAPI.as_view(),
        name='workspace-member-detail',
    ),
    path('<int:pk>/projects/', api.WorkspaceProjectsAPI.as_view(), name='workspace-projects'),
    path('<int:pk>/assign/', api.WorkspaceAssignDatasetAPI.as_view(), name='workspace-assign-dataset'),
    path('<int:pk>/workload/', api.WorkspaceWorkloadAPI.as_view(), name='workspace-workload'),
    path('<int:pk>/import/', api.WorkspaceImportAPI.as_view(), name='workspace-import'),
    path('<int:pk>/file-uploads/', api.WorkspaceFileUploadsAPI.as_view(), name='workspace-file-uploads'),
    path(
        '<int:pk>/file-uploads/<int:upload_pk>/',
        api.WorkspaceFileUploadDetailAPI.as_view(),
        name='workspace-file-upload-detail',
    ),
]


urlpatterns = [
    path('api/workspaces/', include((_api_urlpatterns, app_name), namespace='api')),
]
