"""Browser-flow Keycloak backend for mozilla-django-oidc.

Kept in a separate module from ``users.auth_backends`` because importing
``mozilla_django_oidc.auth`` transitively imports ``django.contrib.auth.models``,
which requires the app registry to be ready. DRF resolves
``DEFAULT_AUTHENTICATION_CLASSES`` during settings import (before apps are
loaded), so anything referenced by that list must stay free of the OIDC
library. ``AUTHENTICATION_BACKENDS`` is only resolved at auth time, so this
module is safe to import there.
"""

import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from users.auth_backends import _attach_default_organization, generate_username

logger = logging.getLogger(__name__)

UserModel = get_user_model()


def _safe_claim_digest(claims):
    """Short debug representation of OIDC claims without leaking full tokens."""
    if not isinstance(claims, dict):
        return repr(claims)
    keys_of_interest = (
        'sub',
        'email',
        'email_verified',
        'preferred_username',
        'given_name',
        'family_name',
        'iss',
        'aud',
    )
    return {k: claims.get(k) for k in keys_of_interest if k in claims} | {
        '_all_keys': sorted(claims.keys())
    }


class KeycloakOIDCBackend(OIDCAuthenticationBackend):
    """Authorization-Code-flow backend backed by Keycloak.

    Looks the user up by email (case-insensitive) and creates them on first
    login. Keeps username/first/last name in sync with Keycloak on each login.
    """

    def filter_users_by_claims(self, claims):
        email = (claims.get('email') or '').strip()
        logger.info(
            'Keycloak: filter_users_by_claims email=%r claims=%s',
            email,
            _safe_claim_digest(claims),
        )
        if not email:
            return UserModel.objects.none()
        return UserModel.objects.filter(email__iexact=email)

    @transaction.atomic
    def create_user(self, claims):
        email = (claims.get('email') or '').strip().lower()
        if not email:
            logger.error(
                'Keycloak: create_user aborted — no email claim. claims=%s',
                _safe_claim_digest(claims),
            )
            raise ValueError('Keycloak token missing email claim')
        user = UserModel.objects.create(
            email=email,
            username=generate_username(claims),
            first_name=claims.get('given_name', '') or '',
            last_name=claims.get('family_name', '') or '',
            is_active=True,
        )
        user.set_unusable_password()
        user.save(update_fields=['password'])
        try:
            _attach_default_organization(user)
        except Exception:
            logger.exception('Keycloak: _attach_default_organization failed for %s', email)
            raise
        user.refresh_from_db(fields=['active_organization'])
        logger.info(
            'Keycloak: create_user done email=%s id=%s active_organization_id=%s',
            email,
            user.pk,
            user.active_organization_id,
        )
        return user

    def update_user(self, user, claims):
        changed_fields = []
        new_username = generate_username(claims)
        if new_username and user.username != new_username:
            user.username = new_username
            changed_fields.append('username')
        for field, claim in (('first_name', 'given_name'), ('last_name', 'family_name')):
            value = claims.get(claim, '') or ''
            if value and getattr(user, field) != value:
                setattr(user, field, value)
                changed_fields.append(field)
        if changed_fields:
            user.save(update_fields=changed_fields)
        try:
            _attach_default_organization(user)
        except Exception:
            logger.exception('Keycloak: _attach_default_organization failed for %s', user.email)
            raise
        user.refresh_from_db(fields=['active_organization'])
        logger.info(
            'Keycloak: update_user done email=%s id=%s active_organization_id=%s changed=%s',
            user.email,
            user.pk,
            user.active_organization_id,
            changed_fields,
        )
        return user
