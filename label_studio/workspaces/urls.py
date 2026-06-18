"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from django.urls import include, path

from . import api, views

app_name = 'workspaces'

# SPA page routes — render the React app so direct loads / refreshes resolve.
# Both slash variants are registered so neither relies on APPEND_SLASH redirects
# (which would change the path the React router has to match).
_page_urlpatterns = [
    path('workspaces/', views.workspace_pages, name='workspace-index'),
    path('workspaces/<int:pk>', views.workspace_pages, name='workspace-detail-page'),
    path('workspaces/<int:pk>/', views.workspace_pages, name='workspace-detail-page-slash'),
]

_api_urlpatterns = [
    path('', api.WorkspaceListAPI.as_view(), name='workspace-list'),
    path('<int:pk>/', api.WorkspaceDetailAPI.as_view(), name='workspace-detail'),
    path('<int:pk>/members/', api.WorkspaceMembersAPI.as_view(), name='workspace-members'),
    path(
        '<int:pk>/members/<int:member_pk>/',
        api.WorkspaceMemberDetailAPI.as_view(),
        name='workspace-member-detail',
    ),
    path('<int:pk>/summary/', api.WorkspaceSummaryAPI.as_view(), name='workspace-summary'),
    path('<int:pk>/projects/', api.WorkspaceProjectsAPI.as_view(), name='workspace-projects'),
    path('<int:pk>/datasets/', api.WorkspaceDatasetsAPI.as_view(), name='workspace-datasets'),
    path('<int:pk>/assign/', api.WorkspaceAssignDatasetAPI.as_view(), name='workspace-assign-dataset'),
    path('<int:pk>/workload/', api.WorkspaceWorkloadAPI.as_view(), name='workspace-workload'),
    path('<int:pk>/import/', api.WorkspaceImportAPI.as_view(), name='workspace-import'),
    path(
        '<int:pk>/import/predictions/',
        api.WorkspaceImportPredictionsAPI.as_view(),
        name='workspace-import-predictions',
    ),
    path('<int:pk>/file-uploads/', api.WorkspaceFileUploadsAPI.as_view(), name='workspace-file-uploads'),
    path(
        '<int:pk>/file-uploads/<int:upload_pk>/',
        api.WorkspaceFileUploadDetailAPI.as_view(),
        name='workspace-file-upload-detail',
    ),
]


urlpatterns = [
    path('api/workspaces/', include((_api_urlpatterns, app_name), namespace='api')),
    *_page_urlpatterns,
]
