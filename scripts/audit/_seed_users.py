"""감사용 로컬 사용자/워크스페이스/프로젝트를 시드한다 (manage.py shell 로 파이프).

UI 스모크가 역할별로 로그인할 수 있도록 고정 이메일/비번의 사용자를 만든다.
로컬 sqlite 전용 — 프로덕션에서 절대 실행하지 말 것(가드 포함).
"""
import os

if 'sqlite' not in (os.environ.get('DJANGO_DB', '')):
    raise SystemExit('[중단] DJANGO_DB=sqlite 아님 — 감사 시드는 로컬 전용')

from django.contrib.auth import get_user_model
from organizations.models import Organization, OrganizationMember
from projects.models import ProjectMember
from projects.tests.factories import ProjectFactory
from tasks.models import Annotation, Task
from users.constants import ProjectRole
from workspaces.models import Workspace, WorkspaceMember
from compensation.models import ProjectCompensationPolicy

User = get_user_model()
PW = 'Str0ngPass!23'
CONFIG = '<View><Text name="t" value="$text"/><Choices name="c" toName="t"><Choice value="a"/></Choices></View>'

ROLES = {
    'sa@audit.local': 'super_admin',
    'wm@audit.local': 'workspace_manager',
    'an@audit.local': 'annotator',
}


def mk(email):
    u = User.objects.filter(email=email).first() or User.objects.create_user(email, PW, first_name=email.split('@')[0])
    u.set_password(PW)
    u.save()
    return u


sa = mk('sa@audit.local')
sa.is_superuser = sa.is_staff = True
sa.save()
org = Organization.objects.first() or Organization.create_organization(created_by=sa, title='org')
users = {e: mk(e) for e in ROLES}
for u in users.values():
    OrganizationMember.objects.get_or_create(user=u, organization=org)
    u.active_organization = org
    u.save(update_fields=['active_organization'])

ws = Workspace.objects.filter(title='감사 워크스페이스').first() or Workspace.objects.create(
    title='감사 워크스페이스', organization=org, created_by=sa
)
WorkspaceMember.objects.get_or_create(
    user=users['wm@audit.local'], workspace=ws, defaults={'role': WorkspaceMember.Role.WORKSPACE_MANAGER}
)
WorkspaceMember.objects.get_or_create(
    user=users['an@audit.local'], workspace=ws, defaults={'role': WorkspaceMember.Role.MEMBER}
)

proj = ws.projects.filter(title='감사 프로젝트').first()
if proj is None:
    proj = ProjectFactory(organization=org, created_by=sa, workspace=ws, label_config=CONFIG, title='감사 프로젝트')
    ProjectMember.objects.create(user=users['an@audit.local'], project=proj, role=ProjectRole.ANNOTATOR)
    task = Task.objects.create(project=proj, data={'text': 'x'})
    Annotation.objects.create(task=task, project=proj, completed_by=users['an@audit.local'], result=[])
    ProjectCompensationPolicy.objects.create(
        project=proj, currency='KRW', annotation_unit_price=100, review_unit_price=0, created_by=sa
    )

print(f'AUDIT SEED OK: users={list(ROLES)} ws={ws.pk} project={proj.pk}')
