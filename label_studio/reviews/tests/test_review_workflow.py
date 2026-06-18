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

    def test_fix_and_accept_creates_reviewer_revision(self):
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
        new = task.current_annotation
        assert new.id != ann.id
        assert new.completed_by_id == self.reviewer.id
        assert new.version == 2
        assert new.status == Annotation.Status.APPROVED
        assert new.parent_annotation_id == ann.id
        assert task.review_status == Task.ReviewStatus.FIXED_AND_ACCEPTED
        assert Annotation.objects.filter(task=task).count() == 2  # history preserved
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
