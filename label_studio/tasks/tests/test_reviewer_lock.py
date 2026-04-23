"""Tests for ReviewerLock — per-annotation reviewer concurrency guard.

Covers the contract the Phase 5 random-review dispatcher relies on:
- Two reviewers cannot both hold a live lock on the same annotation.
- Expired locks do not block a new acquirer.
- The same reviewer reacquiring extends the TTL instead of failing.
- `release()` is idempotent.
"""

import datetime

import pytest  # type: ignore[import]
from django.utils.timezone import now
from tasks.models import ReviewerLock
from tasks.tests.factories import AnnotationFactory
from users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_acquire_creates_lock_when_annotation_is_free():
    annotation = AnnotationFactory()
    reviewer = UserFactory()

    lock, created = ReviewerLock.acquire(annotation, reviewer)

    assert created is True
    assert lock.user_id == reviewer.id
    assert lock.annotation_id == annotation.id
    assert lock.expire_at > now()


def test_second_reviewer_cannot_acquire_live_lock():
    annotation = AnnotationFactory()
    first = UserFactory()
    second = UserFactory()

    ReviewerLock.acquire(annotation, first)
    existing, created = ReviewerLock.acquire(annotation, second)

    assert created is False
    assert existing.user_id == first.id
    # Exactly one lock row persists.
    assert ReviewerLock.objects.filter(annotation=annotation).count() == 1


def test_same_reviewer_reacquiring_refreshes_ttl():
    annotation = AnnotationFactory()
    reviewer = UserFactory()

    first_lock, _ = ReviewerLock.acquire(annotation, reviewer, ttl_seconds=60)
    original_expiry = first_lock.expire_at

    refreshed, created = ReviewerLock.acquire(annotation, reviewer, ttl_seconds=7200)

    assert created is False
    assert refreshed.pk == first_lock.pk
    refreshed.refresh_from_db()
    assert refreshed.expire_at > original_expiry


def test_expired_lock_does_not_block_new_acquirer():
    annotation = AnnotationFactory()
    stale_user = UserFactory()
    new_user = UserFactory()

    stale = ReviewerLock.objects.create(
        annotation=annotation, user=stale_user,
        expire_at=now() - datetime.timedelta(seconds=1),
    )
    assert stale.is_expired()

    lock, created = ReviewerLock.acquire(annotation, new_user)

    assert created is True
    assert lock.user_id == new_user.id
    # The stale lock is deleted by clear_expired().
    assert not ReviewerLock.objects.filter(pk=stale.pk).exists()


def test_release_deletes_and_is_idempotent():
    annotation = AnnotationFactory()
    reviewer = UserFactory()
    lock, _ = ReviewerLock.acquire(annotation, reviewer)

    lock.release()
    assert not ReviewerLock.objects.filter(pk=lock.pk).exists()

    # Calling release again on a detached instance must not blow up.
    lock.release()


def test_clear_expired_scoped_to_annotation():
    a, b = AnnotationFactory(), AnnotationFactory()
    u1, u2 = UserFactory(), UserFactory()
    past = now() - datetime.timedelta(seconds=1)
    ReviewerLock.objects.create(annotation=a, user=u1, expire_at=past)
    ReviewerLock.objects.create(annotation=b, user=u2, expire_at=past)

    deleted = ReviewerLock.clear_expired(annotation=a)

    assert deleted == 1
    assert not ReviewerLock.objects.filter(annotation=a).exists()
    # Unrelated expired lock on `b` is untouched when scoped.
    assert ReviewerLock.objects.filter(annotation=b).exists()


def test_cascade_delete_annotation_removes_locks():
    annotation = AnnotationFactory()
    reviewer = UserFactory()
    ReviewerLock.acquire(annotation, reviewer)

    annotation.delete()

    assert ReviewerLock.objects.filter(user=reviewer).count() == 0
