"""프로덕션 DB 초기화 (CI 전용, workflow에서 파이프로 주입).

동작: 슈퍼유저(관리자)와 소속 조직만 남기고 나머지를 전부 삭제한다.
      - Project / Workspace 전체 삭제 (Task/Annotation/Prediction/Review,
        TaskPool/스토리지, 보상 정책·지급기록까지 FK CASCADE 로 함께 삭제)
      - 슈퍼유저가 아닌 모든 User 삭제
      - 혹시 남은 고아 데이터(Task/Annotation/Prediction/Review/PaymentRecord) 정리
      Azure Blob(이미지/export)은 건드리지 않는다 — DB 만 비운다.

안전장치: 환경변수 WIPE_CONFIRM=yes 가 아니면 아무것도 삭제하지 않고 종료.
"""
import os

from django.contrib.auth import get_user_model
from django.db import transaction

from compensation.models import PaymentRecord, ProjectCompensationPolicy
from organizations.models import Organization
from projects.models import Project
from reviews.models import Review
from tasks.models import Annotation, Prediction, Task
from workspaces.models import TaskPool, Workspace

if os.environ.get("WIPE_CONFIRM") != "yes":
    raise SystemExit("[중단] WIPE_CONFIRM=yes 아님 — 아무 변경 없이 종료")

User = get_user_model()

admins = list(User.objects.filter(is_superuser=True).order_by("pk"))
if not admins:
    raise SystemExit("[중단] 슈퍼유저 없음 — 관리자 계정 확인 필요(전부 삭제 방지)")
keep_ids = [a.pk for a in admins]
org = admins[0].active_organization or Organization.objects.first()
print(f"[keep] 관리자 {[a.email for a in admins]} (pk={keep_ids}) org={getattr(org, 'id', None)}")

print("[before]",
      "users=%d" % User.objects.count(),
      "orgs=%d" % Organization.objects.count(),
      "workspaces=%d" % Workspace.objects.count(),
      "projects=%d" % Project.objects.count(),
      "tasks=%d" % Task.objects.count(),
      "annotations=%d" % Annotation.objects.count(),
      "predictions=%d" % Prediction.objects.count(),
      "payments=%d" % PaymentRecord.objects.count())

with transaction.atomic():
    # 1) 프로젝트/워크스페이스 삭제 → 태스크·어노테이션·예측·리뷰·풀·스토리지·보상 CASCADE
    Project.objects.all().delete()
    Workspace.objects.all().delete()

    # 2) 고아 데이터 정리 (워크스페이스/프로젝트에 안 걸려 있던 것들)
    Review.objects.all().delete()
    Annotation.objects.all().delete()
    Prediction.objects.all().delete()
    Task.objects.all().delete()
    ProjectCompensationPolicy.objects.all().delete()
    PaymentRecord.objects.all().delete()

    # 3) 슈퍼유저 아닌 모든 사용자 삭제 (관리자 계정만 유지)
    deleted_users, _ = User.objects.exclude(pk__in=keep_ids).delete()

print("[after]",
      "users=%d" % User.objects.count(),
      "orgs=%d" % Organization.objects.count(),
      "workspaces=%d" % Workspace.objects.count(),
      "projects=%d" % Project.objects.count(),
      "tasks=%d" % Task.objects.count(),
      "annotations=%d" % Annotation.objects.count(),
      "predictions=%d" % Prediction.objects.count(),
      "payments=%d" % PaymentRecord.objects.count(),
      "pools=%d" % TaskPool.objects.count())
print("DONE kept_admins=%s" % keep_ids)
