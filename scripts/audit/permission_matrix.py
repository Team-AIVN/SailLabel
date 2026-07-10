"""권한 매트릭스 감사기 — 팀 앱(workspaces/reviews/compensation) 엔드포인트를
6개 역할 각각으로 **실제 호출**해서 (엔드포인트 x 메서드 x 역할) 상태코드 표를 뽑는다.

코드를 읽는 게 아니라 두드린다. 각 역할이 무엇을 할 수 있고 없는지가 표로 남아,
"라벨러가 워크스페이스를 지울 수 있나?" 같은 질문에 추정이 아니라 실측으로 답한다.

기대값(EXPECT)과 다른 칸은 ⚠ 로 표시된다. EXPECT 는 "이 역할은 여기서 성공/거부되어야
한다"는 우리의 의도이고, 실측이 그와 어긋나면 권한 구멍이거나 기대값이 틀린 것이다.

실행:
  DJANGO_DB=sqlite poetry run python label_studio/manage.py test \
    scripts.audit.permission_matrix --keepdb -v0   # (아래 러너 참고)

또는 스탠드얼론:
  DJANGO_DB=sqlite poetry run python scripts/audit/permission_matrix.py
"""

import os
import sys

import django

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'label_studio'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.label_studio')
os.environ.setdefault('DJANGO_DB', 'sqlite')


# 성공/거부의 의미. 2xx = 통과, 401/403 = 거부, 404 = (스코핑상) 안 보임.
def kind(status):
    if 200 <= status < 300:
        return 'OK'
    if status in (401, 403):
        return 'DENY'
    if status == 404:
        return 'HIDE'
    if status == 400:
        return 'BADREQ'  # 권한은 통과, 본문 문제 — 감사 관점에선 '접근 허용'에 가깝다
    return str(status)


# 각 (엔드포인트, 메서드) 를 어떻게 호출할지. url 은 시드 컨텍스트로 포맷된다.
# body 는 최소 유효 본문(권한 판정까지 도달시키는 용도).
def endpoints(ctx):
    ws, other_ws = ctx['ws'], ctx['other_ws']
    proj, ann, member_id, pool_id, user_id, payment_id = (
        ctx['project'], ctx['annotation'], ctx['member_id'], ctx['pool_id'], ctx['labeler_id'], ctx['payment_id']
    )
    return [
        # (라벨, 메서드, url, body 또는 None)
        ('workspaces.list', 'GET', '/api/workspaces/', None),
        ('workspaces.create', 'POST', '/api/workspaces/', {'title': '감사용 새 워크스페이스'}),
        ('workspace.detail', 'GET', f'/api/workspaces/{ws}/', None),
        ('workspace.update', 'PATCH', f'/api/workspaces/{ws}/', {'title': '이름변경 시도'}),
        ('workspace.delete', 'DELETE', f'/api/workspaces/{other_ws}/', None),  # 남의 삭제는 other_ws 로
        ('workspace.members.list', 'GET', f'/api/workspaces/{ws}/members/', None),
        ('workspace.members.add', 'POST', f'/api/workspaces/{ws}/members/', {'user': user_id, 'role': 'member'}),
        ('workspace.summary', 'GET', f'/api/workspaces/{ws}/summary/', None),
        ('workspace.projects', 'GET', f'/api/workspaces/{ws}/projects/', None),
        ('workspace.datasets', 'GET', f'/api/workspaces/{ws}/datasets/', None),
        ('workspace.workload', 'GET', f'/api/workspaces/{ws}/workload/', None),
        ('workspace.taskpools', 'GET', f'/api/workspaces/{ws}/task-pools/', None),
        ('review.candidates', 'GET', f'/api/projects/{proj}/review/candidates/', None),
        ('review.tasks', 'GET', f'/api/projects/{proj}/review/tasks/', None),
        ('review.progress', 'GET', f'/api/projects/{proj}/review/progress/', None),
        ('review.decide', 'POST', f'/api/annotations/{ann}/review/', {'decision': 'ACCEPT'}),
        ('comp.policy.get', 'GET', f'/api/projects/{proj}/compensation-policy/', None),
        (
            'comp.policy.set',
            'PUT',
            f'/api/projects/{proj}/compensation-policy/',
            {'currency': 'KRW', 'annotation_unit_price': 100, 'review_unit_price': 0},
        ),
        ('comp.dashboard', 'GET', f'/api/workspaces/{ws}/compensation/', None),
        (
            'comp.pay.create',
            'POST',
            f'/api/workspaces/{ws}/payments/',
            {'project': proj, 'user': user_id, 'currency': 'KRW', 'amount': 1},
        ),
    ]


# 기대 접근성: label -> {role: 'OK'|'DENY'|'HIDE'}.
# 'OK'는 2xx/400(권한 통과) 를 허용으로 본다. 여기 없는 조합은 표에만 나오고 판정 안 함.
EXPECT = {
    'workspace.delete': {'annotator': 'DENY', 'reviewer': 'DENY', 'project_manager': 'DENY'},
    'workspace.members.add': {'annotator': 'DENY', 'reviewer': 'DENY'},
    'comp.policy.set': {'annotator': 'DENY', 'reviewer': 'DENY', 'project_manager': 'DENY'},
    'comp.pay.create': {'annotator': 'DENY', 'reviewer': 'DENY'},
    'review.decide': {'annotator': 'DENY'},
    'workspace.update': {'annotator': 'DENY', 'reviewer': 'DENY'},
}


def run():
    import logging

    from django.test.utils import setup_test_environment, teardown_test_environment
    from django.test.runner import DiscoverRunner

    # Expected DENY cells raise PermissionDenied, which DRF/sentry log at ERROR with a full
    # traceback — pure noise that buries the table. Silence request logging for the audit.
    logging.getLogger('django.request').setLevel(logging.CRITICAL)
    logging.disable(logging.ERROR)

    setup_test_environment()
    runner = DiscoverRunner(verbosity=0)
    old_config = runner.setup_databases()
    try:
        _run_matrix()
    finally:
        runner.teardown_databases(old_config)
        teardown_test_environment()


def _seed():
    """워크스페이스 1 + 프로젝트 1 + 어노테이션 1 + 6개 역할 사용자."""
    from django.contrib.auth import get_user_model
    from organizations.models import Organization, OrganizationMember
    from projects.models import ProjectMember
    from projects.tests.factories import ProjectFactory
    from tasks.models import Annotation, Task
    from users.constants import ProjectRole
    from workspaces.models import Workspace, WorkspaceMember
    from compensation.models import PaymentRecord, ProjectCompensationPolicy

    User = get_user_model()
    CONFIG = '<View><Text name="t" value="$text"/><Choices name="c" toName="t"><Choice value="a"/></Choices></View>'

    def mk(email):
        u = User.objects.create_user(email, 'Str0ngPass!23', first_name=email.split('@')[0])
        return u

    sa = mk('sa@a.com')
    sa.is_superuser = sa.is_staff = True
    sa.save()
    org = Organization.create_organization(created_by=sa, title='org')
    users = {'super_admin': sa}
    for role in ('workspace_manager', 'project_manager', 'reviewer', 'annotator', 'member'):
        users[role] = mk(f'{role}@a.com')
    for u in users.values():
        OrganizationMember.objects.get_or_create(user=u, organization=org)
        u.active_organization = org
        u.save(update_fields=['active_organization'])

    ws = Workspace.objects.create(title='감사', organization=org, created_by=sa)
    other_ws = Workspace.objects.create(title='남의워크스페이스', organization=org, created_by=sa)
    WorkspaceMember.objects.create(user=users['workspace_manager'], workspace=ws,
                                   role=WorkspaceMember.Role.WORKSPACE_MANAGER)
    for role in ('project_manager', 'reviewer', 'annotator', 'member'):
        WorkspaceMember.objects.create(user=users[role], workspace=ws, role=WorkspaceMember.Role.MEMBER)

    project = ProjectFactory(organization=org, created_by=sa, workspace=ws, label_config=CONFIG, title='감사프로젝트')
    ProjectMember.objects.create(user=users['project_manager'], project=project, role=ProjectRole.PROJECT_MANAGER)
    ProjectMember.objects.create(user=users['reviewer'], project=project, role=ProjectRole.REVIEWER)
    ProjectMember.objects.create(user=users['annotator'], project=project, role=ProjectRole.ANNOTATOR)

    task = Task.objects.create(project=project, data={'text': 'x'})
    ann = Annotation.objects.create(task=task, project=project, completed_by=users['annotator'], result=[])
    ProjectCompensationPolicy.objects.create(project=project, currency='KRW', annotation_unit_price=100,
                                             review_unit_price=0, created_by=sa)
    pay = PaymentRecord.objects.create(workspace=ws, project=project, user=users['annotator'], currency='KRW',
                                       amount=1, created_by=sa)

    return {
        'users': users,
        'ws': ws.pk, 'other_ws': other_ws.pk, 'project': project.pk, 'annotation': ann.pk,
        'member_id': WorkspaceMember.objects.filter(workspace=ws, user=users['member']).first().pk,
        'pool_id': 0, 'labeler_id': users['annotator'].pk, 'payment_id': pay.pk,
    }


def _run_matrix():
    from rest_framework.test import APIClient

    ctx = _seed()
    roles = ['super_admin', 'workspace_manager', 'project_manager', 'reviewer', 'annotator', 'member']
    eps = endpoints(ctx)

    grid = {}  # label -> {role: kind}
    for label, method, url, body in eps:
        grid[label] = {'_m': method}
        for role in roles:
            client = APIClient()
            client.force_authenticate(ctx['users'][role])
            fn = getattr(client, method.lower())
            # Each call runs in a savepoint that is always rolled back, so a successful
            # write (create a workspace, add a member, record a payment) never leaks into
            # the next role's attempt. Without this, an earlier OK dirties the shared seed
            # and later calls fail for the wrong reason (e.g. a unique-title 500).
            # Give any create a per-role-unique title so a success by one role does not
            # collide with the next role's attempt on a unique constraint (which would
            # masquerade as a 500 "permission" result). We only care about the status the
            # permission layer produces, not about persisting the object.
            call_body = dict(body) if body else body
            if call_body and 'title' in call_body:
                call_body['title'] = f'{call_body["title"]}-{role}'
            try:
                resp = fn(url, call_body or {}, format='json') if call_body is not None else fn(url)
                grid[label][role] = kind(resp.status_code)
                if resp.status_code >= 500 and os.environ.get('AUDIT_DEBUG'):
                    print(f'\n!! 500 at {label}/{role}:\n{resp.content.decode()[:400]}\n')
            except Exception as e:  # a view raising (not returning) is itself a finding
                grid[label][role] = f'ERR:{type(e).__name__}'

    # --- 표 출력 ---
    rmap = {'super_admin': 'SA', 'workspace_manager': 'WM', 'project_manager': 'PM',
            'reviewer': 'RV', 'annotator': 'AN', 'member': 'MB'}
    head = f'{"":30} {"메서드":6} ' + ' '.join(f'{rmap[r]:>7}' for r in roles)
    print(head)
    print('-' * len(head))
    warnings = []
    for label, _m, _u, _b in eps:
        row = grid[label]
        cells = []
        for r in roles:
            got = row[r]
            exp = EXPECT.get(label, {}).get(r)
            flag = ''
            if exp:
                # DENY 기대인데 접근 허용(OK/BADREQ)됐거나, 그 반대면 경고
                allowed = got in ('OK', 'BADREQ', 'HIDE')  # HIDE=404 도 접근불가로 간주
                want_deny = exp == 'DENY'
                if want_deny and got in ('OK', 'BADREQ'):
                    flag = '⚠'
                    warnings.append(f'{label} / {r}: 거부 기대했으나 {got}')
                if not want_deny and got in ('DENY', 'HIDE'):
                    flag = '⚠'
                    warnings.append(f'{label} / {r}: 허용 기대했으나 {got}')
            cells.append(f'{got}{flag:>2}')
        print(f'{label:30} {row["_m"]:6} ' + ' '.join(f'{c:>7}' for c in cells))

    print('\n' + '=' * 60)
    if warnings:
        print(f'⚠ 기대와 다른 칸 {len(warnings)}개:')
        for w in warnings:
            print('  -', w)
    else:
        print('✅ EXPECT 에 정의된 모든 칸이 기대와 일치')
    print('\n범례: OK=2xx SA=슈퍼관리자 WM=워크스페이스매니저 PM=프로젝트매니저 RV=검수자 AN=라벨러 MB=멤버')
    print('     DENY=401/403  HIDE=404  BADREQ=400(권한통과, 본문문제)')


if __name__ == '__main__':
    django.setup()
    run()
