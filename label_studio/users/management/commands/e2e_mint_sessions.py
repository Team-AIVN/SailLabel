"""Mint DB-backed Django sessions for seeded E2E accounts.

The SailLabel login page has moved to Keycloak-only SSO, so Playwright can
no longer POST credentials to ``/user/login/``. This command side-steps that
by writing a session row directly through ``SessionStore`` for each seeded
account and serialising the resulting ``sessionid`` + ``csrftoken`` cookies
into Playwright ``storageState`` JSON files.

Invoked once before the test suite (see ``playwright.config.ts``
``globalSetup``); fixtures then just consume the cached files.

Usage:
    poetry run python label_studio/manage.py e2e_mint_sessions --out-dir .auth
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from django.contrib.sessions.backends.db import SessionStore
from django.core.management.base import BaseCommand, CommandError
from django.middleware.csrf import _get_new_csrf_string

from users.models import User

# Must mirror `fixtures/accounts.ts` — RoleKey → seeded email.
ROLE_TO_EMAIL: dict[str, str] = {
    'superAdmin': 'superadmin@e2e.saillabel.local',
    'workspaceManager': 'wsmanager@e2e.saillabel.local',
    'projectManager': 'pmanager@e2e.saillabel.local',
    'reviewer': 'reviewer@e2e.saillabel.local',
    'annotator': 'annotator@e2e.saillabel.local',
    'plainMember': 'plainmember@e2e.saillabel.local',
}


class Command(BaseCommand):
    help = 'Mint DB sessions for seeded E2E accounts and emit Playwright storageState JSON files.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--out-dir', required=True,
            help='Directory to write <role>.json storageState files into.',
        )
        parser.add_argument(
            '--domain', default='localhost',
            help='Cookie domain (default: localhost — matches E2E_BASE_URL host).',
        )
        parser.add_argument(
            '--ttl-days', type=int, default=1,
            help='Cookie expiry in days (default: 1).',
        )

    def handle(self, *args, out_dir: str, domain: str, ttl_days: int, **_opts):
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        exp_ts = int((datetime.now(tz=timezone.utc) + timedelta(days=ttl_days)).timestamp())

        for role_key, email in ROLE_TO_EMAIL.items():
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                raise CommandError(
                    f'seed missing: {email!r} — run `manage.py seed_e2e_accounts` first',
                )

            session = SessionStore()
            session['_auth_user_id'] = str(user.pk)
            session['_auth_user_backend'] = 'django.contrib.auth.backends.ModelBackend'
            session['_auth_user_hash'] = user.get_session_auth_hash()
            # InactivitySessionTimeoutMiddleWare treats a missing `last_login`
            # as epoch 0 and force-logs-out the user. Stamp it so the minted
            # session doesn't get flushed on the first request (mirrors the
            # `stamp_last_login_on_session` signal in users/signals.py).
            session['last_login'] = time.time()
            session.save()

            csrf = _get_new_csrf_string()
            state = {
                'cookies': [
                    {
                        'name': 'sessionid',
                        'value': session.session_key,
                        'domain': domain,
                        'path': '/',
                        'expires': exp_ts,
                        'httpOnly': True,
                        'secure': False,
                        'sameSite': 'Lax',
                    },
                    {
                        'name': 'csrftoken',
                        'value': csrf,
                        'domain': domain,
                        'path': '/',
                        'expires': exp_ts,
                        'httpOnly': False,
                        'secure': False,
                        'sameSite': 'Lax',
                    },
                ],
                'origins': [],
            }
            target = out / f'{role_key}.json'
            target.write_text(json.dumps(state, indent=2))
            self.stdout.write(self.style.SUCCESS(
                f'  wrote {target.name:<28s} user={email}'
            ))

        self.stdout.write(self.style.SUCCESS(
            f'\n{len(ROLE_TO_EMAIL)} storageState files written to {out.resolve()}'
        ))
