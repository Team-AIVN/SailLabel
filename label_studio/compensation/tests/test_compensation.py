"""Tests for compensation derivation and APIs.

The point of these tests is that qualified counts are derived from workflow history
and are immune to rejection/rework cycles: one data item never pays more than once.
"""

from decimal import Decimal

from compensation.models import PaymentRecord, ProjectCompensationPolicy
from compensation.services import compute_member_compensation, compute_workspace_compensation
from organizations.models import OrganizationMember
from organizations.tests.factories import OrganizationFactory
from projects.models import Project
from projects.tests.factories import ProjectFactory
from reviews import services as review_services
from rest_framework.test import APITestCase
from tasks.models import Annotation, Task
from users.tests.factories import UserFactory
from workspaces.models import Workspace, WorkspaceMember

CONFIG = '<View><Text name="t" value="$text"/><Choices name="c" toName="t"><Choice value="a"/></Choices></View>'


def _join_org(user, org):
    user.active_organization = org
    user.save(update_fields=['active_organization'])
    OrganizationMember.objects.get_or_create(user=user, organization=org)


class CompensationTests(APITestCase):
    def setUp(self):
        self.org = OrganizationFactory()
        self.manager = self.org.created_by
        _join_org(self.manager, self.org)
        self.annotator = UserFactory()
        _join_org(self.annotator, self.org)
        self.reviewer = UserFactory()
        _join_org(self.reviewer, self.org)

        self.workspace = Workspace.objects.create(
            title='WS', organization=self.org, created_by=self.manager
        )
        WorkspaceMember.objects.create(
            user=self.manager, workspace=self.workspace, role=WorkspaceMember.Role.WORKSPACE_MANAGER
        )
        WorkspaceMember.objects.create(
            user=self.annotator, workspace=self.workspace, role=WorkspaceMember.Role.MEMBER
        )
        WorkspaceMember.objects.create(
            user=self.reviewer, workspace=self.workspace, role=WorkspaceMember.Role.MEMBER
        )

        self.project = ProjectFactory(
            organization=self.org,
            created_by=self.manager,
            workspace=self.workspace,
            label_config=CONFIG,
            review_strategy=Project.ReviewStrategy.FULL_REVIEW,
        )
        ProjectCompensationPolicy.objects.create(
            project=self.project,
            currency='USD',
            annotation_unit_price=Decimal('0.05'),
            review_unit_price=Decimal('0.03'),
        )

    def _task(self, project=None):
        return Task.objects.create(project=project or self.project, data={'text': 'x'})

    def _annotate(self, task, user, was_cancelled=False):
        return Annotation.objects.create(
            task=task, project=task.project, completed_by=user, result=[],
            status=Annotation.Status.COMPLETED, was_cancelled=was_cancelled,
        )

    def test_skipped_annotation_earns_nothing(self):
        # A task with only a skip (was_cancelled) annotation must not pay the skipper.
        task = self._task()
        self._annotate(task, self.annotator, was_cancelled=True)
        task.review_status = Task.ReviewStatus.NOT_SELECTED
        task.save(update_fields=['review_status'])
        ann = compute_member_compensation(self.workspace, self.annotator)['projects']
        assert ann == []  # skip-only task: nothing qualifies

    def test_skip_then_relabel_credits_relabeler(self):
        # A skips, B relabels and it is accepted -> credit goes to B, not the earlier-id skipper.
        stranger = UserFactory()
        _join_org(stranger, self.org)
        WorkspaceMember.objects.create(user=stranger, workspace=self.workspace, role=WorkspaceMember.Role.MEMBER)
        task = self._task()
        self._annotate(task, self.annotator, was_cancelled=True)  # lower id skip
        real = self._annotate(task, stranger)  # higher id real work
        review_services.accept(real, self.reviewer)
        a = compute_member_compensation(self.workspace, self.annotator)['projects']
        b = compute_member_compensation(self.workspace, stranger)['projects'][0]
        assert a == []  # skipper earns nothing
        assert b['qualified_annotation_count'] == 1

    def test_payment_currency_must_match_policy(self):
        # setUp policy currency is USD; a EUR payment must be rejected.
        self.client.force_authenticate(user=self.manager)
        resp = self.client.post(
            f'/api/workspaces/{self.workspace.id}/payments/',
            {'user': self.annotator.id, 'currency': 'EUR', 'amount': '1.0', 'project': self.project.id},
            format='json',
        )
        assert resp.status_code == 400
        # no payment was recorded
        from compensation.models import PaymentRecord
        assert not PaymentRecord.objects.filter(project=self.project).exists()

    # --- core derivation ---

    def test_accepted_pays_annotation_and_review_once(self):
        task = self._task()
        ann = self._annotate(task, self.annotator)
        review_services.accept(ann, self.reviewer)

        counts = compute_member_compensation(self.workspace, self.annotator)
        ann_proj = counts['projects'][0]
        assert ann_proj['qualified_annotation_count'] == 1
        assert ann_proj['annotation_earnings'] == 0.05
        assert ann_proj['qualified_review_count'] == 0  # annotator did no review

        rev = compute_member_compensation(self.workspace, self.reviewer)['projects'][0]
        assert rev['qualified_review_count'] == 1
        assert rev['review_earnings'] == 0.03

    def test_rejection_cycles_do_not_increase_compensation(self):
        """Reject -> rework -> reject -> accept must still pay exactly one of each."""
        task = self._task()
        ann1 = self._annotate(task, self.annotator)
        review_services.reject(ann1, self.reviewer)  # task back to rework
        ann2 = self._annotate(task, self.annotator)  # revision
        review_services.reject(ann2, self.reviewer)
        ann3 = self._annotate(task, self.annotator)
        review_services.accept(ann3, self.reviewer)

        ann = compute_member_compensation(self.workspace, self.annotator)['projects'][0]
        assert ann['qualified_annotation_count'] == 1
        rev = compute_member_compensation(self.workspace, self.reviewer)['projects'][0]
        assert rev['qualified_review_count'] == 1

    def test_fix_and_accept_credits_original_annotator_not_reviewer(self):
        task = self._task()
        ann = self._annotate(task, self.annotator)
        review_services.fix_and_accept(ann, self.reviewer, content=[])
        task.refresh_from_db()
        assert task.review_status == Task.ReviewStatus.FIXED_AND_ACCEPTED

        # Annotation credit -> original annotator (reviewer authored the fix revision).
        ann_detail = compute_member_compensation(self.workspace, self.annotator)['projects']
        assert ann_detail and ann_detail[0]['qualified_annotation_count'] == 1
        # Reviewer gets the review credit, not an annotation credit.
        rev_detail = compute_member_compensation(self.workspace, self.reviewer)['projects'][0]
        assert rev_detail['qualified_review_count'] == 1
        assert rev_detail['qualified_annotation_count'] == 0

    def test_not_selected_pays_annotation_but_no_review(self):
        p = ProjectFactory(
            organization=self.org, created_by=self.manager, workspace=self.workspace,
            label_config=CONFIG, review_strategy=Project.ReviewStrategy.NONE,
        )
        ProjectCompensationPolicy.objects.create(
            project=p, currency='USD', annotation_unit_price=Decimal('0.05'), review_unit_price=Decimal('0.03')
        )
        task = self._task(project=p)
        self._annotate(task, self.annotator)
        task.refresh_from_db()
        assert task.review_status == Task.ReviewStatus.NOT_SELECTED

        rows = {(r['member_id'], r['currency']): r for r in compute_workspace_compensation(self.workspace)}
        row = rows[(self.annotator.id, 'USD')]
        assert row['annotation_count'] == 1
        assert row['review_count'] == 0

    # --- multi-currency aggregation + payment status ---

    def test_dashboard_rows_are_per_currency_with_status(self):
        # USD project (self.project) + a KRW project, both annotated+accepted by annotator.
        t1 = self._task()
        review_services.accept(self._annotate(t1, self.annotator), self.reviewer)

        krw = ProjectFactory(
            organization=self.org, created_by=self.manager, workspace=self.workspace,
            label_config=CONFIG, review_strategy=Project.ReviewStrategy.FULL_REVIEW,
        )
        ProjectCompensationPolicy.objects.create(
            project=krw, currency='KRW', annotation_unit_price=Decimal('500'), review_unit_price=Decimal('300')
        )
        t2 = Task.objects.create(project=krw, data={'text': 'y'})
        review_services.accept(self._annotate(t2, self.annotator), self.reviewer)

        # Partial USD payment to the annotator.
        PaymentRecord.objects.create(
            workspace=self.workspace, user=self.annotator, currency='USD', amount=Decimal('0.02')
        )

        rows = {(r['member_id'], r['currency']): r for r in compute_workspace_compensation(self.workspace)}
        usd = rows[(self.annotator.id, 'USD')]
        assert usd['total_earned'] == 0.05 and usd['total_paid'] == 0.02
        assert round(usd['remaining_balance'], 2) == 0.03
        assert usd['status'] == 'PARTIALLY_PAID'

        krw_row = rows[(self.annotator.id, 'KRW')]
        assert krw_row['total_earned'] == 500.0 and krw_row['status'] == 'UNPAID'

    # --- APIs ---

    def test_policy_put_requires_manager_and_persists(self):
        self.client.force_authenticate(user=self.annotator)  # not a manager
        resp = self.client.put(
            f'/api/projects/{self.project.id}/compensation-policy/',
            {'currency': 'EUR', 'annotation_unit_price': '1.0', 'review_unit_price': '0.5'},
            format='json',
        )
        assert resp.status_code == 403

        self.client.force_authenticate(user=self.manager)
        resp = self.client.put(
            f'/api/projects/{self.project.id}/compensation-policy/',
            {'currency': 'EUR', 'annotation_unit_price': '1.0', 'review_unit_price': '0.5'},
            format='json',
        )
        assert resp.status_code == 200
        self.project.compensation_policy.refresh_from_db()
        assert self.project.compensation_policy.currency == 'EUR'

    def test_record_payment_and_dashboard_endpoint(self):
        task = self._task()
        review_services.accept(self._annotate(task, self.annotator), self.reviewer)

        self.client.force_authenticate(user=self.manager)
        # Settlement is per project, so payments must name the project.
        resp = self.client.post(
            f'/api/workspaces/{self.workspace.id}/payments/',
            {'user': self.annotator.id, 'currency': 'USD', 'amount': '0.05', 'project': self.project.id},
            format='json',
        )
        assert resp.status_code == 201, resp.content

        resp = self.client.get(f'/api/workspaces/{self.workspace.id}/compensation/')
        assert resp.status_code == 200
        rows = {(r['member_id'], r['currency']): r for r in resp.json()['results']}
        assert rows[(self.annotator.id, 'USD')]['status'] == 'PAID'

    def test_payment_payee_must_be_member(self):
        stranger = UserFactory()
        _join_org(stranger, self.org)
        self.client.force_authenticate(user=self.manager)
        resp = self.client.post(
            f'/api/workspaces/{self.workspace.id}/payments/',
            {'user': stranger.id, 'currency': 'USD', 'amount': '1.0'},
            format='json',
        )
        assert resp.status_code == 400

    # --- 라벨링 보상은 검수와 분리: 제출 즉시 지급 -----------------------------

    def _counts(self, user):
        from compensation.services import qualified_counts_for_project

        return qualified_counts_for_project(self.project).get(user.id, {'annotation': 0, 'review': 0})

    def test_annotation_paid_on_submit_while_pending_review(self):
        """FULL_REVIEW 프로젝트라 제출 직후 상태는 PENDING — 그래도 라벨러는 즉시 지급 대상."""
        task = self._task()
        self._annotate(task, self.annotator)
        task.refresh_from_db()
        assert task.review_status == Task.ReviewStatus.PENDING

        assert self._counts(self.annotator)['annotation'] == 1
        # 검수는 아직 아무도 안 했으므로 리뷰 크레딧은 0.
        assert self._counts(self.reviewer)['review'] == 0

    def test_annotation_paid_even_when_rejected(self):
        """반려돼도 라벨링 크레딧은 유지되고, 재작업이 중복 지급을 만들지 않는다."""
        task = self._task()
        annotation = self._annotate(task, self.annotator)
        review_services.reject(annotation, self.reviewer, comment='다시')
        assert self._counts(self.annotator)['annotation'] == 1
        assert self._counts(self.reviewer)['review'] == 0  # 반려만으론 검수 보상 없음

        # 라벨러가 고쳐서 다시 제출해도 여전히 1건.
        annotation.result = [{'from_name': 'c', 'to_name': 't', 'type': 'choices', 'value': {'choices': ['a']}}]
        annotation.save()
        assert self._counts(self.annotator)['annotation'] == 1

    def test_review_credit_still_requires_acceptance(self):
        """검수 보상은 승인(또는 수정 후 승인)이 있어야만 잡힌다 — 라벨링과 별개."""
        task = self._task()
        annotation = self._annotate(task, self.annotator)
        assert self._counts(self.reviewer)['review'] == 0

        review_services.accept(annotation, self.reviewer)
        assert self._counts(self.reviewer)['review'] == 1
        assert self._counts(self.annotator)['annotation'] == 1  # 여전히 1건
        assert self._counts(self.annotator)['review'] == 0  # 라벨러에게 검수 크레딧은 없음

    # --- 단가 정책 저장 ---------------------------------------------------------

    def test_empty_put_no_longer_creates_a_silent_zero_policy(self):
        """빈 본문 PUT 은 400. 모델 기본값(USD, 0) 으로 조용히 정책이 생기면 안 된다.

        프론트의 api-proxy 가 PUT 에 Content-Type 을 안 붙여 body 를 통째로 누락시켰고,
        서버는 그걸 받아 'USD / 0원' 정책을 만들어 버렸다 (프로덕션에서 실제로 발생).
        """
        project = ProjectFactory(
            organization=self.org, created_by=self.manager, workspace=self.workspace, label_config=CONFIG
        )
        self.client.force_authenticate(self.manager)
        resp = self.client.put(f'/api/projects/{project.pk}/compensation-policy/', {}, format='json')
        assert resp.status_code == 400, resp.content
        assert not hasattr(project, 'compensation_policy') or project.compensation_policy is None

    def test_put_saves_currency_and_prices_then_allows_partial_edit(self):
        project = ProjectFactory(
            organization=self.org, created_by=self.manager, workspace=self.workspace, label_config=CONFIG
        )
        self.client.force_authenticate(self.manager)

        created = self.client.put(
            f'/api/projects/{project.pk}/compensation-policy/',
            {'currency': 'KRW', 'annotation_unit_price': 100, 'review_unit_price': 50},
            format='json',
        )
        assert created.status_code == 200, created.content
        assert created.json()['currency'] == 'KRW'
        assert Decimal(created.json()['annotation_unit_price']) == Decimal('100')

        # 생성 이후 단가 수정(부분 갱신)도 가능해야 한다 — 보상 화면의 '단가 저장'.
        updated = self.client.put(
            f'/api/projects/{project.pk}/compensation-policy/',
            {'annotation_unit_price': 250},
            format='json',
        )
        assert updated.status_code == 200, updated.content
        assert Decimal(updated.json()['annotation_unit_price']) == Decimal('250')
        assert updated.json()['currency'] == 'KRW'  # 기존 통화 유지

    # --- 초과 지급 차단 -----------------------------------------------------------

    def _pay(self, project, user, amount, currency='USD'):
        return self.client.post(
            f'/api/workspaces/{self.workspace.pk}/payments/',
            {'project': project.pk, 'user': user.pk, 'currency': currency, 'amount': amount},
            format='json',
        )

    def _earn_two_annotations(self):
        """단가 0.05 x 2건 = 0.10 적립."""
        for _ in range(2):
            task = self._task()
            self._annotate(task, self.annotator)

    def test_payment_cannot_exceed_earnings(self):
        self._earn_two_annotations()
        self.client.force_authenticate(self.manager)

        over = self._pay(self.project, self.annotator, '0.11')
        assert over.status_code == 400, over.content
        assert '잔액' in str(over.content, 'utf-8')
        assert PaymentRecord.objects.count() == 0

    def test_payment_up_to_the_balance_is_allowed(self):
        self._earn_two_annotations()
        self.client.force_authenticate(self.manager)

        exact = self._pay(self.project, self.annotator, '0.10')
        assert exact.status_code == 201, exact.content
        assert PaymentRecord.objects.count() == 1

    def test_second_payment_is_capped_by_what_remains(self):
        self._earn_two_annotations()
        self.client.force_authenticate(self.manager)

        assert self._pay(self.project, self.annotator, '0.06').status_code == 201
        # 남은 잔액 0.04 — 0.05 는 거부, 0.04 는 허용
        assert self._pay(self.project, self.annotator, '0.05').status_code == 400
        assert self._pay(self.project, self.annotator, '0.04').status_code == 201
        assert PaymentRecord.objects.count() == 2

    def test_payment_rejected_when_nothing_earned(self):
        """작업이 없으면 적립액 0 — 어떤 금액도 지급할 수 없다."""
        self.client.force_authenticate(self.manager)
        assert self._pay(self.project, self.annotator, '0.01').status_code == 400
        assert PaymentRecord.objects.count() == 0
