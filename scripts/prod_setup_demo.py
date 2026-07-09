"""프로덕션 시연 세팅 (CI 전용, workflow에서 파이프로 주입).

동작: 관리자/유저/조직은 그대로 둔다. 기존 Project/Workspace 정리 후
      워크스페이스 1 + 태스크풀 1(Azure sync) + 프로젝트 1(라벨 config)만 생성.

안전장치: 환경변수 SETUP_CONFIRM=yes 가 아니면 아무것도 삭제/생성하지 않고 종료.
config: 환경변수 LABEL_CONFIG_B64(base64) 로 XML을 주입받는다(컨테이너엔 파일이 없으므로).
        없으면 LABEL_CONFIG_PATH(기본 scripts/labelconfig/config.xml) 파일에서 읽는다.
"""
import base64
import os

from django.contrib.auth import get_user_model
from io_storages.azure_blob.models import AzureBlobWorkspaceImportStorage
from organizations.models import Organization
from projects.models import Project
from tasks.models import Prediction, Task
from workspaces.models import TaskPool, Workspace

if os.environ.get("SETUP_CONFIRM") != "yes":
    raise SystemExit("[중단] SETUP_CONFIRM=yes 아님 — 아무 변경 없이 종료")

User = get_user_model()
admin = User.objects.filter(is_superuser=True).order_by("pk").first()
if admin is None:
    raise SystemExit("[중단] 슈퍼유저 없음 — 관리자 계정 확인 필요")
org = admin.active_organization or Organization.objects.first()
print(f"[keep] 관리자={admin.email}(pk={admin.pk}) org={org.id}  (유저/조직 유지)")

# 1) 예전 테스트 정리 — Project/Workspace 만 삭제
print(f"[정리 대상] projects={Project.objects.count()} workspaces={Workspace.objects.count()}")
Project.objects.all().delete()
Workspace.objects.all().delete()
print("[정리] 완료")

# 2) 워크스페이스 1 + 풀 1 + Azure sync (env 자격증명, container=label-images, prefix=tasks/)
ws = Workspace.objects.create(organization=org, title="테스트", created_by=admin)
pool = TaskPool.objects.create(workspace=ws, title="선박 시연 데이터셋", created_by=admin)
storage = AzureBlobWorkspaceImportStorage.objects.create(
    workspace=ws, title="tasks", container="label-images", prefix="tasks/",
    regex_filter=r".*\.json$", use_blob_urls=False, recursive_scan=True, task_pool=pool)
print("[sync]", storage.scan_and_create_source_items(), "/ pool items:", pool.items.count())

# 3) 프로젝트 1 (새 config + 사전라벨 표시 + 전수검수)
b64 = os.environ.get("LABEL_CONFIG_B64")
if b64:
    CONFIG = base64.b64decode(b64).decode("utf-8")
else:
    with open(os.environ.get("LABEL_CONFIG_PATH", "scripts/labelconfig/config.xml")) as f:
        CONFIG = f.read()
if "<Image" not in CONFIG or "<Table" not in CONFIG:
    raise SystemExit("[중단] label config가 비었거나 손상됨")
proj = Project.objects.create(
    title="선박 탐색 시연", organization=org, created_by=admin, workspace=ws,
    task_pool=pool, label_config=CONFIG, show_collab_predictions=True,
    model_version="ai-demo-v1", review_strategy=Project.ReviewStrategy.FULL_REVIEW)
print("[project]", proj.id, proj.title,
      "| tasks:", Task.objects.filter(project=proj).count(),
      "| predictions:", Prediction.objects.filter(task__project=proj).count())
print("DONE ws=%d project=%d" % (ws.id, proj.id))
