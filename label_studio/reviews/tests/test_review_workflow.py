"""Tests for the in-project annotation review workflow."""

from organizations.models import OrganizationMember
from organizations.tests.factories import OrganizationFactory
from projects.models import Project, ProjectMember
from projects.tests.factories import ProjectFactory
from rest_framework.test import APITestCase
from reviews.models import Review
from tasks.models import Annotation, Task
from users.constants import ProjectRole
from users.tests.factories import UserFactory

CONFIG = '<View><Text name="t" value="$text"/><Choices name="c" toName="t"><Choice value="a"/></Choices></View>'


def _join_org(user, org):
    user.active_organization = org
    user.save(update_fields=['active_organization'])
    OrganizationMember.objects.get_or_create(user=user, organization=org)


def _completed_annotation(task, user):
    return Annotation.objects.create(
        task=task, project=task.project, completed_by=user, result=[], status=Annotation.Status.COMPLETED
    )


class ReviewWorkflowTests(APITestCase):
    def setUp(self):
        self.org = OrganizationFactory()
        self.owner = self.org.created_by
        _join_org(self.owner, self.org)
        self.annotator = UserFactory()
        _join_org(self.annotator, self.org)
        self.reviewer = UserFactory()
        _join_org(self.reviewer, self.org)
        self.project = ProjectFactory(
            organization=self.org,
            created_by=self.owner,
            label_config=CONFIG,
            review_strategy=Project.ReviewStrategy.FULL_REVIEW,
        )
        ProjectMember.objects.create(user=self.reviewer, project=self.project, role=ProjectRole.REVIEWER)
        ProjectMember.objects.create(user=self.annotator, project=self.project, role=ProjectRole.ANNOTATOR)

    def _task(self):
        return Task.objects.create(project=self.project, data={'text': 'x'})

    # --- selection + revision tracking ---

    def test_full_review_selects_and_tracks_revision(self):
        task = self._task()
        ann = _completed_annotation(task, self.annotator)
        task.refresh_from_db()
        ann.refresh_from_db()
        assert ann.version == 1
        assert task.current_annotation_id == ann.id
        assert task.review_status == Task.ReviewStatus.PENDING

    def test_random_sampling_ratio_zero_not_selected(self):
        p = ProjectFactory(
            organization=self.org,
            created_by=self.owner,
            label_config=CONFIG,
            review_strategy=Project.ReviewStrategy.RANDOM_SAMPLING,
            review_ratio=0.0,
        )
        task = Task.objects.create(project=p, data={'text': 'x'})
        Annotation.objects.create(task=task, project=p, completed_by=self.annotator, result=[], status=Annotation.Status.COMPLETED)
        task.refresh_from_db()
        assert task.review_status == Task.ReviewStatus.NOT_SELECTED

    # --- review actions (via API) ---

    def test_accept(self):
        task = self._task()
        ann = _completed_annotation(task, self.annotator)
        self.client.force_authenticate(self.reviewer)
        r = self.client.post(f'/api/annotations/{ann.id}/review/', {'decision': 'ACCEPT', 'comment': 'ok'}, format='json')
        assert r.status_code == 201, r.content
        ann.refresh_from_db()
        task.refresh_from_db()
        assert ann.status == Annotation.Status.APPROVED
        assert task.review_status == Task.ReviewStatus.ACCEPTED
        assert Review.objects.filter(annotation=ann, decision='ACCEPT').exists()

    def test_reject_returns_to_queue_and_rework(self):
        task = self._task()
        ann = _completed_annotation(task, self.annotator)
        self.client.force_authenticate(self.reviewer)
        r = self.client.post(f'/api/annotations/{ann.id}/review/', {'decision': 'REJECT', 'comment': 'redo'}, format='json')
        assert r.status_code == 201, r.content
        ann.refresh_from_db()
        task.refresh_from_db()
        assert ann.status == Annotation.Status.REWORK_REQUIRED
        assert task.review_status == Task.ReviewStatus.REJECTED
        assert task.is_labeled is False
        # annotator submits a new revision -> v2, current, re-selected
        ann2 = _completed_annotation(task, self.annotator)
        task.refresh_from_db()
        ann2.refresh_from_db()
        assert ann2.version == 2
        assert task.current_annotation_id == ann2.id
        assert task.review_status == Task.ReviewStatus.PENDING
        # history preserved
        assert Annotation.objects.filter(task=task).count() == 2

    def test_fix_and_accept_updates_annotation_in_place(self):
        # Fix+Accept overwrites the reviewed annotation in place (single annotation, no
        # confusing second editor tab); the correction and status change stay on the
        # original annotation, and the change is preserved in the review record.
        task = self._task()
        ann = _completed_annotation(task, self.annotator)
        self.client.force_authenticate(self.reviewer)
        r = self.client.post(
            f'/api/annotations/{ann.id}/review/',
            {'decision': 'FIX_AND_ACCEPT', 'comment': 'fixed', 'content': [{'fixed': True}]},
            format='json',
        )
        assert r.status_code == 201, r.content
        task.refresh_from_db()
        ann.refresh_from_db()
        assert task.current_annotation_id == ann.id  # same annotation, updated in place
        assert ann.result == [{'fixed': True}]
        assert ann.status == Annotation.Status.APPROVED
        assert ann.completed_by_id == self.annotator.id  # credit stays with the annotator
        assert task.review_status == Task.ReviewStatus.FIXED_AND_ACCEPTED
        assert Annotation.objects.filter(task=task).count() == 1  # no extra revision row
        assert Review.objects.filter(annotation=ann, decision='FIX_AND_ACCEPT').exists()

    def test_fix_requires_content(self):
        task = self._task()
        ann = _completed_annotation(task, self.annotator)
        self.client.force_authenticate(self.reviewer)
        r = self.client.post(f'/api/annotations/{ann.id}/review/', {'decision': 'FIX_AND_ACCEPT'}, format='json')
        assert r.status_code == 400

    def test_non_reviewer_forbidden(self):
        task = self._task()
        ann = _completed_annotation(task, self.annotator)
        self.client.force_authenticate(self.annotator)  # annotator role, not reviewer
        r = self.client.post(f'/api/annotations/{ann.id}/review/', {'decision': 'ACCEPT'}, format='json')
        assert r.status_code == 403

    # --- progress + candidates ---

    def test_progress_and_candidates(self):
        # 4 tasks: 2 accepted, 1 fixed, 1 rejected
        tasks = [self._task() for _ in range(4)]
        anns = [_completed_annotation(t, self.annotator) for t in tasks]
        self.client.force_authenticate(self.reviewer)
        self.client.post(f'/api/annotations/{anns[0].id}/review/', {'decision': 'ACCEPT'}, format='json')
        self.client.post(f'/api/annotations/{anns[1].id}/review/', {'decision': 'ACCEPT'}, format='json')
        self.client.post(
            f'/api/annotations/{anns[2].id}/review/',
            {'decision': 'FIX_AND_ACCEPT', 'content': [{'x': 1}]},
            format='json',
        )
        self.client.post(f'/api/annotations/{anns[3].id}/review/', {'decision': 'REJECT'}, format='json')

        prog = self.client.get(f'/api/projects/{self.project.id}/review/progress/')
        assert prog.status_code == 200, prog.content
        body = prog.json()
        # 3 of 4 tasks have an APPROVED current annotation (2 accept + 1 fix) -> 75%
        assert body['annotation_progress'] == 75
        # all 4 were selected (FULL_REVIEW) and all 4 have a final decision -> 100%
        assert body['review_progress'] == 100
        assert body['total_tasks'] == 4

        # rejected task is back to PENDING only after re-annotation; candidates now = none pending
        cand = self.client.get(f'/api/projects/{self.project.id}/review/candidates/')
        assert cand.status_code == 200
        rows = cand.json()
        rows = rows['results'] if isinstance(rows, dict) and 'results' in rows else rows
        assert rows == []

    def test_review_tasks_list_columns_and_filter(self):
        tasks = [self._task() for _ in range(3)]
        anns = [_completed_annotation(t, self.annotator) for t in tasks]
        self.client.force_authenticate(self.reviewer)
        self.client.post(f'/api/annotations/{anns[0].id}/review/', {'decision': 'ACCEPT'}, format='json')

        res = self.client.get(f'/api/projects/{self.project.id}/review/tasks/')
        assert res.status_code == 200, res.content
        rows = res.json()
        rows = rows['results'] if isinstance(rows, dict) and 'results' in rows else rows
        assert len(rows) == 3
        first = rows[0]
        # Task List UI columns (reviews is a list of decisions; each carries its reviewer)
        for key in ('task_id', 'annotation_version', 'annotator', 'review_status', 'reviews'):
            assert key in first
        assert first['annotation_version'] == 1
        assert first['annotator']['id'] == self.annotator.id
        # the accepted task's reviews list carries the reviewer of the ACCEPT decision
        accepted = next(r for r in rows if r['review_status'] == 'ACCEPTED')
        assert accepted['reviews'] and accepted['reviews'][0]['reviewer']['id'] == self.reviewer.id

        # filter by review_status
        res2 = self.client.get(f'/api/projects/{self.project.id}/review/tasks/?review_status=ACCEPTED')
        rows2 = res2.json()
        rows2 = rows2['results'] if isinstance(rows2, dict) and 'results' in rows2 else rows2
        assert len(rows2) == 1
        assert rows2[0]['review_status'] == 'ACCEPTED'
        assert rows2[0]['reviews'][0]['reviewer']['id'] == self.reviewer.id

        # invalid filter -> 400
        bad = self.client.get(f'/api/projects/{self.project.id}/review/tasks/?review_status=NOPE')
        assert bad.status_code == 400


class ReviewAuditFixTests(APITestCase):
    """R1/R2/R4 regression tests from the audit."""

    def setUp(self):
        self.org = OrganizationFactory()
        self.owner = self.org.created_by
        _join_org(self.owner, self.org)
        self.annotator = UserFactory()
        _join_org(self.annotator, self.org)
        self.reviewer = UserFactory()
        _join_org(self.reviewer, self.org)

    def _project(self, strategy=Project.ReviewStrategy.RANDOM_SAMPLING, ratio=0.0):
        p = ProjectFactory(
            organization=self.org, created_by=self.owner, label_config=CONFIG,
            review_strategy=strategy, review_ratio=ratio, maximum_annotations=1,
        )
        ProjectMember.objects.create(user=self.reviewer, project=p, role=ProjectRole.REVIEWER)
        ProjectMember.objects.create(user=self.annotator, project=p, role=ProjectRole.ANNOTATOR)
        return p

    def test_R2_rework_revision_forces_pending_even_under_sampling(self):
        # RANDOM_SAMPLING ratio 0: fresh annotations are NOT_SELECTED, but a revision of a
        # previously reviewed task must go back to PENDING (never settle unreviewed).
        from reviews import services
        project = self._project(ratio=0.0)
        task = Task.objects.create(project=project, data={'text': 'x'})
        ann = _completed_annotation(task, self.annotator)
        task.refresh_from_db()
        assert task.review_status == Task.ReviewStatus.NOT_SELECTED
        services.reject(ann, self.reviewer)  # now REJECTED
        # labeler resubmits a new revision
        ann2 = _completed_annotation(task, self.annotator)
        task.refresh_from_db()
        assert task.review_status == Task.ReviewStatus.PENDING  # not NOT_SELECTED
        _ = ann2

    def test_R1_rejected_task_available_to_annotator_again(self):
        # After reject, the original annotator's own task must (a) not count as a lock and
        # (b) not be filtered out as "solved" — so the labeling flow can re-serve it.
        from projects.functions.next_task import get_not_solved_tasks_qs
        from reviews import services
        project = self._project(strategy=Project.ReviewStrategy.FULL_REVIEW)
        task = Task.objects.create(project=project, data={'text': 'x'})
        ann = _completed_annotation(task, self.annotator)
        assert task.has_lock(self.annotator) is True  # before reject: taken
        services.reject(ann, self.reviewer)
        task.refresh_from_db()
        assert task.has_lock(self.annotator) is False  # rework annotation no longer locks
        not_solved, *_ = get_not_solved_tasks_qs(
            self.annotator, project, project.tasks.all(), assigned_flag=None, queue_info=''
        )
        assert task.id in set(not_solved.values_list('id', flat=True))  # back in the queue

    def test_R4_custom_rule_strategy_rejected(self):
        self.client.force_authenticate(self.owner)
        project = self._project(strategy=Project.ReviewStrategy.FULL_REVIEW)
        resp = self.client.patch(
            f'/api/projects/{project.id}/', {'review_strategy': 'CUSTOM_RULE'}, format='json'
        )
        assert resp.status_code == 400
