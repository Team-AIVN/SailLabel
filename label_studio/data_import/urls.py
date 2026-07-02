"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from django.urls import include, path

from . import api

app_name = 'data_import'

_api_urlpatterns = [path('file-upload/<int:pk>', api.FileUploadAPI.as_view(), name='file-upload-detail')]

_api_projects_urlpatterns = [
    # Project-scoped data import has moved to the workspace layer
    # (see workspaces.api: WorkspaceImportAPI / WorkspaceFileUploadsAPI). The legacy
    # /import, /import/predictions and /file-uploads routes were removed; data is now
    # uploaded into a workspace and assigned to projects.
    path('<int:pk>/tasks/bulk/', api.TasksBulkCreateAPI.as_view(), name='project-tasks-bulk-upload'),
    path('<int:pk>/reimport', api.ReImportAPI.as_view(), name='project-reimport'),
]

urlpatterns = [
    path('api/import/', include((_api_urlpatterns, app_name), namespace='api')),
    path('api/projects/', include((_api_projects_urlpatterns, app_name), namespace='api-projects')),
    # special endpoints for serving imported files
    path('data/upload/<path:filename>', api.UploadedFileResponse.as_view(), name='data-upload'),
    path('storage-data/uploaded/', api.DownloadStorageData.as_view(), name='storage-data-upload'),
]
