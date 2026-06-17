"""Tests for audit.models.AuditLog.

Two invariants to prove:
1. ``AuditLog.record()`` stores the event with correct target resolution.
2. Rows are immutable — ``save(update)`` and ``delete()`` raise RuntimeError.
"""

import pytest
from audit.models import AuditAction, AuditLog
from organizations.tests.factories import OrganizationFactory
from projects.tests.factories import ProjectFactory
from rest_framework.test import APITestCase
from users.tests.factories import UserFactory


class AuditLogRecordTests(APITestCase):
    def test_record_stores_event_and_resolves_target(self):
        org = OrganizationFactory()
        project = ProjectFactory(organization=org)
        actor = org.created_by

        entry = AuditLog.record(
            action=AuditAction.PROJECT_CREATED,
            actor=actor,
            organization=org,
            target=project,
            metadata={'title': project.title},
        )

        assert entry.pk is not None
        assert entry.action == AuditAction.PROJECT_CREATED
        assert entry.actor_id == actor.id
        assert entry.organization_id == org.id
        assert entry.target_type == 'projects.project'
        assert entry.target_id == project.pk
        assert entry.metadata == {'title': project.title}

    def test_record_without_target_leaves_empty_type(self):
        user = UserFactory()
        entry = AuditLog.record(
            action=AuditAction.DATA_EXPORTED,
            actor=user,
            metadata={'format': 'json'},
        )
        assert entry.target_type == ''
        assert entry.target_id is None


class AuditLogImmutabilityTests(APITestCase):
    def setUp(self):
        self.entry = AuditLog.record(action=AuditAction.ROLE_GRANTED, actor=UserFactory())

    def test_save_after_insert_raises(self):
        self.entry.metadata = {'tampered': True}
        with pytest.raises(RuntimeError, match='immutable'):
            self.entry.save()

    def test_delete_raises(self):
        with pytest.raises(RuntimeError, match='immutable'):
            self.entry.delete()
