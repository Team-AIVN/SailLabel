"""데모 프로젝트 태스크 인플레이스 갱신 (wipe 없음).

Azure ``tasks/<base>.json`` 최신본으로 각 태스크의 ``data`` 와 ``predictions`` 를 교체하고,
프로젝트 ``label_config`` (LABEL_CONFIG_B64 주입) 와 ``model_version`` 을 맞춘다.
- 표 컬럼 순서: ``data.data_csv`` (CSV 문자열) + config의 ``<Table valueType="csv">`` 로 확정
  (Postgres jsonb 는 dict 키 순서를 보존하지 않으므로 array-of-dicts 로는 순서 제어 불가).
- 예측: prediction ``model_version`` 을 프로젝트 ``model_version`` 에도 반영해야 pre-fill 됨.
워크스페이스/프로젝트/초대/멤버십/주석은 전부 보존.

실행 (VM):
  docker compose exec -T -e UPDATE_CONFIRM=yes -e LABEL_CONFIG_B64=... \
    app python3 label_studio/manage.py shell < prod_update_task_data.py

안전장치: UPDATE_CONFIRM=yes 아니면 변경 없이 종료.
"""
import base64
import json
import os

if os.environ.get("UPDATE_CONFIRM") != "yes":
    raise SystemExit("[중단] UPDATE_CONFIRM=yes 아님 — 변경 없이 종료")

from io_storages.azure_blob.models import AzureBlobWorkspaceImportStorage
from projects.models import Project
from tasks.models import Prediction

proj = Project.objects.filter(title="선박 탐색 시연").order_by("id").last()
if proj is None:
    raise SystemExit("[중단] '선박 탐색 시연' 프로젝트 없음")

storage = AzureBlobWorkspaceImportStorage.objects.filter(task_pool=proj.task_pool).first()
if storage is None:
    raise SystemExit("[중단] 프로젝트 풀에 연결된 Azure 스토리지 없음")
container = storage.get_container()

cache = {}
n_data = n_pred = 0
model_version = None
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
    j = cache[base]
    if not j:
        continue
    if "data" in j:
        task.data = j["data"]  # {image, data_csv}
        task.save(update_fields=["data"])
        n_data += 1
    preds = j.get("predictions") or []
    if preds:
        Prediction.objects.filter(task=task).delete()
        for p in preds:
            mv = p.get("model_version") or "gpt-5.5"
            model_version = mv
            Prediction.objects.create(task=task, project=proj, result=p["result"], model_version=mv)
            n_pred += 1

# label_config (base64 주입) + model_version 반영
fields = []
b64 = os.environ.get("LABEL_CONFIG_B64")
if b64:
    cfg = base64.b64decode(b64).decode("utf-8")
    if "<Table" in cfg:
        proj.label_config = cfg
        fields.append("label_config")
if model_version:
    proj.model_version = model_version  # 예측 pre-fill 위해 프로젝트 model_version 일치
    fields.append("model_version")
if fields:
    proj.save(update_fields=fields)

print(f"[update] data {n_data} / predictions {n_pred} / model_version={proj.model_version}")
t0 = proj.tasks.order_by("id").first()
if t0:
    print("  data 키:", list((t0.data or {}).keys()))
print("DONE")
