"""Azure ``tasks/*.json`` 최신 내용을 작업집합 항목과 프로젝트 태스크에 다시 반영한다 (비파괴).

왜 필요한가
-----------
``scan_and_create_source_items`` 는 파일 단위로 멱등하다 — 이미 가져온 blob 은 내용이
바뀌어도 **건너뛴다**(갱신하지 않는다). 그래서 Azure 의 JSON 을 새 형식으로 덮어써도
``TaskSourceItem`` 은 옛 내용을 들고 있고, 그 작업집합으로 새로 만든 프로젝트는
옛 데이터(예: ``data`` 배열, 옛 ``model_version``)를 그대로 복사받는다.

무엇을 하나
-----------
1. 클라우드 스토리지에서 온 ``TaskSourceItem`` 의 ``data`` / ``predictions`` 를 blob 최신본으로 교체
2. 모든 프로젝트의 태스크 ``data`` / ``predictions`` 를 같은 blob 기준으로 교체하고,
   프로젝트 ``model_version`` 을 예측의 model_version 과 맞춘다 (사전 라벨 pre-fill 조건)

어노테이션·검수 이력·워크스페이스·초대·멤버십은 아무것도 건드리지 않는다.

실행 (VM):
  docker compose exec -T -e REFRESH_CONFIRM=yes \
    app python3 label_studio/manage.py shell < prod_refresh_from_azure.py

안전장치: REFRESH_CONFIRM=yes 아니면 현재 상태만 출력하고 종료 (dry-run).
"""

import json
import os

DRY_RUN = os.environ.get('REFRESH_CONFIRM') != 'yes'

from io_storages.azure_blob.models import AzureBlobWorkspaceImportStorage
from projects.models import Project
from tasks.models import Prediction
from workspaces.models import TaskSourceItem

print('[모드]', 'DRY-RUN (변경 없음)' if DRY_RUN else '실제 갱신')

_blob_cache = {}


def load_blob(container, key):
    """blob 을 JSON 으로 읽고 캐시한다. 실패하면 None."""
    if key not in _blob_cache:
        try:
            _blob_cache[key] = json.loads(container.download_blob(key).readall())
        except Exception as e:
            print(f'  ! blob 읽기 실패 {key}: {e}')
            _blob_cache[key] = None
    return _blob_cache[key]


# --- 1) 작업집합 항목(TaskSourceItem) 갱신 -----------------------------------
item_updated = item_same = 0
for storage in AzureBlobWorkspaceImportStorage.objects.all():
    container = storage.get_container()
    container_name = str(storage.container)
    items = TaskSourceItem.objects.filter(workspace=storage.workspace, storage_key__isnull=False).order_by('id')
    for item in items:
        if not item.storage_key.startswith(f'{container_name}/'):
            continue
        blob_key = item.storage_key[len(container_name) + 1 :]
        if '#' in blob_key:  # CSV row items — 이 스크립트의 대상이 아님
            continue
        payload = load_blob(container, blob_key)
        if not payload or 'data' not in payload:
            continue
        new_data = payload['data']
        new_preds = payload.get('predictions') or None
        if item.data == new_data and item.predictions == new_preds:
            item_same += 1
            continue
        print(f'  [항목] {item.storage_key}: {sorted((item.data or {}).keys())} -> {sorted(new_data.keys())}')
        if not DRY_RUN:
            item.data = new_data
            item.predictions = new_preds
            item.save(update_fields=['data', 'predictions'])
        item_updated += 1

print(f'[작업집합 항목] 갱신 {item_updated} / 동일 {item_same}')


# --- 2) 프로젝트 태스크 갱신 --------------------------------------------------
def storage_for(project):
    pool_id = getattr(project, 'task_pool_id', None)
    if pool_id:
        st = AzureBlobWorkspaceImportStorage.objects.filter(task_pool_id=pool_id).first()
        if st:
            return st
    return AzureBlobWorkspaceImportStorage.objects.filter(workspace_id=project.workspace_id).first()


for project in Project.objects.filter(workspace__isnull=False).order_by('id'):
    storage = storage_for(project)
    if storage is None or not project.tasks.exists():
        continue
    container = storage.get_container()
    n_data = n_pred = n_skip = 0
    model_version = None
    for task in project.tasks.all().order_by('id'):
        image = (task.data or {}).get('image', '')
        base = image.rsplit('/', 1)[-1].rsplit('.', 1)[0]
        if not base:
            n_skip += 1
            continue
        payload = load_blob(container, f'tasks/{base}.json')
        if not payload or 'data' not in payload:
            n_skip += 1
            continue
        if task.data != payload['data']:
            if not DRY_RUN:
                task.data = payload['data']
                task.save(update_fields=['data'])
            n_data += 1
        preds = payload.get('predictions') or []
        if preds:
            model_version = preds[0].get('model_version') or model_version
            if not DRY_RUN:
                Prediction.objects.filter(task=task).delete()
                for p in preds:
                    Prediction.objects.create(
                        task=task, project=project, result=p['result'], model_version=p.get('model_version')
                    )
            n_pred += len(preds)

    if model_version and project.model_version != model_version and not DRY_RUN:
        project.model_version = model_version  # 예측 pre-fill 은 project.model_version 일치가 조건
        project.save(update_fields=['model_version'])

    first = project.tasks.order_by('id').first()
    print(
        f'  [프로젝트 {project.id}] {project.title!r}: data {n_data} / predictions {n_pred} / 스킵 {n_skip} '
        f'| model_version={model_version} | data 키={sorted((first.data or {}).keys()) if first else None}'
    )

print('DONE' if not DRY_RUN else 'DRY-RUN 종료 — 실제로 적용하려면 REFRESH_CONFIRM=yes')
