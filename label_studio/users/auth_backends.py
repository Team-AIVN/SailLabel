"""Keycloak helpers that are safe to import during Django settings load.

DRF resolves ``DEFAULT_AUTHENTICATION_CLASSES`` while the settings module is
still being imported (before the app registry is ready), so this module must
*not* import ``mozilla_django_oidc.auth``. The browser-flow backend lives in
``users.oidc_backend`` and is loaded lazily via ``AUTHENTICATION_BACKENDS``.

Provides:
- ``generate_username``: maps OIDC claims → unique Django username.
- ``_attach_default_organization``: JIT-attaches a user to an Organization.
- ``KeycloakBearerAuthentication``: DRF auth class validating
  ``Authorization: Bearer <access_token>`` against the Keycloak JWKS.
- ``keycloak_logout_url``: builds the Keycloak end-session URL used when
  mozilla-django-oidc logs the user out (OIDC_OP_LOGOUT_URL_METHOD).
"""

import logging
from urllib.parse import urlencode

from django.conf import settings
from django.db import transaction
from rest_framework import authentication, exceptions

logger = logging.getLogger(__name__)


def generate_username(claims):
    """Derive a stable, unique username from OIDC claims.

    Preference order: ``preferred_username`` → email local-part → ``sub``.
    """
    candidate = (
        claims.get('preferred_username')
        or (claims.get('email') or '').split('@')[0]
        or claims.get('sub')
        or ''
    )
    return candidate[:150]


def _attach_default_organization(user):
    """Ensure the user belongs to an Organization (mirrors save_user behaviour)."""
    # Imported lazily — organizations models can't be touched at settings-import time.
    from organizations.functions import create_organization
    from organizations.models import Organization

    if user.active_organization_id:
        logger.info(
            'Keycloak: user %s already has active_organization_id=%s, skip attach',
            user.email,
            user.active_organization_id,
        )
        return
    if Organization.objects.exists():
        org = Organization.objects.first()
        logger.info(
            'Keycloak: attaching user %s to existing org id=%s title=%r',
            user.email,
            org.pk,
            org.title,
        )
        org.add_user(user)
    else:
        logger.info('Keycloak: no organizations exist yet — creating default "SailLabel" for %s', user.email)
        org = create_organization(title='SailLabel', created_by=user)
    user.active_organization = org
    user.save(update_fields=['active_organization'])


class KeycloakBearerAuthentication(authentication.BaseAuthentication):
    """DRF auth class that verifies Keycloak access tokens on API requests.

    Caches the realm's JWKS per-process to avoid a network hit on every call.
    Users not yet present locally are JIT-provisioned from the token claims.
    """

    keyword = 'Bearer'
    _jwks_cache = None

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).split()
        if not header or header[0].lower() != self.keyword.lower().encode():
            return None
        if len(header) != 2:
            raise exceptions.AuthenticationFailed('Invalid bearer header')
        token = header[1].decode('utf-8')

        from jose.exceptions import JWTError

        try:
            claims = self._decode(token)
        except JWTError as exc:
            raise exceptions.AuthenticationFailed(f'Invalid Keycloak token: {exc}')

        email = (claims.get('email') or '').strip().lower()
        if not email:
            raise exceptions.AuthenticationFailed('Keycloak token missing email claim')

        from django.contrib.auth import get_user_model

        UserModel = get_user_model()
        user = UserModel.objects.filter(email__iexact=email).first()
        if user is None:
            with transaction.atomic():
                user = UserModel.objects.create(
                    email=email,
                    username=generate_username(claims),
                    first_name=claims.get('given_name', '') or '',
                    last_name=claims.get('family_name', '') or '',
                    is_active=True,
                )
                user.set_unusable_password()
                user.save(update_fields=['password'])
                _attach_default_organization(user)
        elif not user.is_active:
            raise exceptions.AuthenticationFailed('User is disabled')

        return (user, token)

    def authenticate_header(self, request):
        return self.keyword

    @classmethod
    def _get_jwks(cls):
        if cls._jwks_cache is None:
            import requests

            resp = requests.get(
                f'{settings.KEYCLOAK_REALM_URL}/protocol/openid-connect/certs',
                timeout=5,
            )
            resp.raise_for_status()
            cls._jwks_cache = resp.json()
        return cls._jwks_cache

    def _decode(self, token):
        from jose import jwt

        jwks = self._get_jwks()
        # Accept the client id or "account" (Keycloak's default audience for user tokens).
        return jwt.decode(
            token,
            jwks,
            algorithms=['RS256'],
            audience=[settings.KEYCLOAK_CLIENT_ID, 'account'],
            issuer=settings.KEYCLOAK_REALM_URL,
            options={'verify_at_hash': False},
        )


def keycloak_logout_url(request):
    """Build the Keycloak end-session URL used after Django logout.

    mozilla-django-oidc invokes this via ``OIDC_OP_LOGOUT_URL_METHOD``.
    """
    params = {'post_logout_redirect_uri': request.build_absolute_uri(settings.LOGOUT_REDIRECT_URL)}
    id_token = request.session.get('oidc_id_token')
    if id_token:
        params['id_token_hint'] = id_token
    if settings.KEYCLOAK_CLIENT_ID:
        params['client_id'] = settings.KEYCLOAK_CLIENT_ID
    return f'{settings.KEYCLOAK_REALM_URL}/protocol/openid-connect/logout?{urlencode(params)}'
