"""프로젝트별 Azure 결과 저장 스토리지를 만들거나 경로를 다시 맞춘다 (비파괴).

``workspaces.signals.attach_azure_export_storage`` 는 **새로 만들어지는** 프로젝트에만
스토리지를 붙인다. 이미 존재하는 프로젝트(예: 데모)는 스토리지가 없거나, 옛 규칙인
``export/<project id>`` 를 가리키고 있다. 이 스크립트가 그 둘을 모두 현재 규칙인
``export/<워크스페이스명>/<프로젝트명>`` 으로 수렴시킨다.

블롭은 어노테이션 submit 시점마다 ``<prefix>/<task id>.json`` 으로 덮어쓰이며, 내용은
가져올 때 쓴 태스크 JSON 과 같은 형태(data + predictions + annotations)다.

실행 (VM):
  docker compose exec -T -e EXPORT_SETUP_CONFIRM=yes [-e BACKFILL=yes] \
    app python3 label_studio/manage.py shell < prod_setup_export_storage.py

안전장치:
  - EXPORT_SETUP_CONFIRM=yes 아니면 변경 없이 종료
  - BACKFILL=yes 일 때만 기존 어노테이션을 Azure 로 일괄 업로드(덮어쓰기, 삭제는 없음)
  - 워크스페이스/프로젝트/태스크/어노테이션은 아무것도 지우지 않는다
"""

import os

if os.environ.get('EXPORT_SETUP_CONFIRM') != 'yes':
    raise SystemExit('[중단] EXPORT_SETUP_CONFIRM=yes 아님 — 변경 없이 종료')

from core.utils.params import get_env
from io_storages.azure_blob.models import AzureBlobExportStorage
from projects.models import Project
from workspaces.signals import azure_export_prefix

container = get_env('AZURE_BLOB_DEFAULT_CONTAINER')
account = get_env('AZURE_BLOB_ACCOUNT_NAME')
key = get_env('AZURE_BLOB_ACCOUNT_KEY')
print(f'[env] container={container!r} account={account!r} key={"set" if key else None}')
if not (container and account and key):
    raise SystemExit(
        '[중단] Azure 기본 자격증명 미설정 — AZURE_BLOB_ACCOUNT_NAME / AZURE_BLOB_ACCOUNT_KEY / '
        'AZURE_BLOB_DEFAULT_CONTAINER 를 컨테이너 env 에 넣고 다시 실행할 것'
    )

backfill = os.environ.get('BACKFILL') == 'yes'
created = updated = kept = 0

for project in Project.objects.filter(workspace__isnull=False).order_by('id'):
    prefix = azure_export_prefix(project)
    storage = project.io_storages_azureblobexportstorages.first()
    if storage is None:
        storage = AzureBlobExportStorage.objects.create(
            project=project, title='결과 자동 저장 (Azure)', container=container, prefix=prefix
        )
        created += 1
        print(f'[생성] project={project.id} {project.title!r} -> {container}/{prefix}')
    elif storage.prefix != prefix or storage.container != container:
        old = f'{storage.container}/{storage.prefix}'
        storage.container, storage.prefix = container, prefix
        storage.save(update_fields=['container', 'prefix'])
        updated += 1
        print(f'[경로변경] project={project.id} {old} -> {container}/{prefix}')
    else:
        kept += 1
        print(f'[유지] project={project.id} -> {container}/{prefix}')

    if backfill:
        n = project.annotations.count()
        storage.save_all_annotations()
        print(f'  [백필] project={project.id} annotations={n} -> {container}/{prefix}/<task id>.json')

print(f'[export storage] 생성 {created} / 경로변경 {updated} / 유지 {kept} / 백필={backfill}')
print('DONE')
