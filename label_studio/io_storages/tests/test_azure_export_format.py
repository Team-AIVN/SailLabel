"""Azure export storage writes whole-task JSON under `export/<workspace>/<project>/`.

Locks in the two properties the demo workflow depends on:
1. blob key is `<prefix>/<task id>.json` (not `<annotation id>`), and
2. the payload keeps the shape of the task JSON we import from Azure — `data` plus
   fully expanded `predictions` — with `annotations` added.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from io_storages.azure_blob.models import AzureBlobExportStorage
from organizations.tests.factories import OrganizationFactory
from projects.tests.factories import ProjectFactory
from tasks.models import Annotation, Prediction, Task
from workspaces.models import Workspace

TEXT_CONFIG = '<View><Text name="text" value="$text"/><Choices name="c" toName="text"><Choice value="a"/></Choices></View>'
RESULT = [{'from_name': 'c', 'to_name': 'text', 'type': 'choices', 'value': {'choices': ['a']}}]


@pytest.mark.django_db
def test_save_annotation_writes_task_json():
    org = OrganizationFactory()
    ws = Workspace.objects.create(organization=org, title='테스트', created_by=org.created_by)
    project = ProjectFactory(
        organization=org, created_by=org.created_by, workspace=ws, title='선박 탐색 시연', label_config=TEXT_CONFIG
    )
    task = Task.objects.create(project=project, data={'text': 'hello'})
    Prediction.objects.create(task=task, project=project, result=RESULT, model_version='gpt-5.5')
    annotation = Annotation.objects.create(task=task, project=project, result=RESULT)

    storage = AzureBlobExportStorage.objects.create(
        project=project, title='결과', container='label-images', prefix='export/테스트/선박 탐색 시연'
    )

    blob = MagicMock()
    container = MagicMock()
    container.get_blob_client.return_value = blob
    with patch.object(AzureBlobExportStorage, 'get_container', return_value=container):
        storage.save_annotation(annotation)

    key = container.get_blob_client.call_args.args[0]
    assert key == f'export/테스트/선박 탐색 시연/{task.id}.json'

    payload = json.loads(blob.upload_blob.call_args.args[0])
    assert payload['data'] == {'text': 'hello'}
    # predictions expanded to objects, not bare PKs — this is what makes the file
    # round-trip back through the importer.
    assert [p['model_version'] for p in payload['predictions']] == ['gpt-5.5']
    assert payload['predictions'][0]['result'] == RESULT
    assert [a['result'] for a in payload['annotations']] == [RESULT]
