"""데모 프로젝트 표 데이터 인플레이스 갱신 (wipe 없음).

Azure ``tasks/<base>.json`` 최신 내용으로 각 태스크의 ``data`` 를 교체한다.
LS ``<Table>`` 는 컬럼을 데이터(행 dict) 키 순서에서 뽑으므로, 컬럼 순서/이름 변경은
태스크 data 교체로 반영된다. 워크스페이스/프로젝트/초대/멤버십/주석은 전부 보존.

실행 (VM):
  docker compose exec -T -e UPDATE_CONFIRM=yes app python3 label_studio/manage.py shell < prod_update_task_data.py

안전장치: UPDATE_CONFIRM=yes 아니면 변경 없이 종료.
"""
import json
import os

if os.environ.get("UPDATE_CONFIRM") != "yes":
    raise SystemExit("[중단] UPDATE_CONFIRM=yes 아님 — 변경 없이 종료")

from io_storages.azure_blob.models import AzureBlobWorkspaceImportStorage
from projects.models import Project

proj = Project.objects.filter(title="선박 탐색 시연").order_by("id").last()
if proj is None:
    raise SystemExit("[중단] '선박 탐색 시연' 프로젝트 없음")

storage = AzureBlobWorkspaceImportStorage.objects.filter(task_pool=proj.task_pool).first()
if storage is None:
    raise SystemExit("[중단] 프로젝트 풀에 연결된 Azure 스토리지 없음")
container = storage.get_container()

cache = {}
updated = 0
total = proj.tasks.count()
for task in proj.tasks.all().order_by("id"):
    img = (task.data or {}).get("image", "")
    base = img.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    if not base:
        print(f"  ! task {task.id}: image 없음, 스킵")
        continue
    if base not in cache:
        try:
            cache[base] = json.loads(container.download_blob(f"tasks/{base}.json").readall())
        except Exception as e:
            print(f"  ! tasks/{base}.json 다운로드 실패: {e}")
            cache[base] = None
    newj = cache[base]
    if not newj or "data" not in newj:
        continue
    task.data = newj["data"]  # image + 재정렬된 표 행
    task.save(update_fields=["data"])
    updated += 1

print(f"[update] 태스크 data 갱신: {updated}/{total}")
t0 = proj.tasks.order_by("id").first()
if t0 and t0.data.get("data"):
    print("  적용된 컬럼 순서:", list(t0.data["data"][0].keys()))
print("DONE")
