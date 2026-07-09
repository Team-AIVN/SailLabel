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

    def _annotate(self, task, user):
        return Annotation.objects.create(
            task=task, project=task.project, completed_by=user, result=[], status=Annotation.Status.COMPLETED
        )

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
