# labelstudio-e2e-playwright

SailLabel Phase 1-8 Playwright E2E harness. Complements the unit /
integration tests under `label_studio/**/tests/` by running role-scoped
checks through the real HTTP + browser stack.

## Prerequisites

1. Django backend running on `http://localhost:8080`:
   ```bash
   poetry run python label_studio/manage.py migrate
   poetry run python label_studio/manage.py seed_e2e_accounts
   poetry run python label_studio/manage.py runserver 0.0.0.0:8080
   ```
   The login UI is now Keycloak-only, so Playwright can't POST credentials
   to `/user/login/`. Instead, the harness mints DB-backed Django sessions
   directly via `manage.py e2e_mint_sessions` and feeds the cookies in as
   Playwright `storageState`. Both the seed and mint commands need the same
   DB the running server is using.
2. Node 20+ with pnpm (or npm/yarn).

## Setup

```bash
cd web/apps/labelstudio-e2e-playwright
pnpm install
pnpm install:browsers    # downloads chromium with OS deps
```

Copy `.env.e2e` → override if your server runs elsewhere.

## Run

```bash
pnpm test                # full suite, headless — globalSetup mints sessions
pnpm test:smoke          # just 01-smoke — quick liveness check
pnpm test:headed         # watch the browser
pnpm test:ui             # Playwright UI mode
pnpm report              # open the last HTML report
```

`pnpm test` runs `global-setup.ts` once before workers start; it shells out
to `poetry run python label_studio/manage.py e2e_mint_sessions --out-dir
.auth`, which writes one `storageState` file per seeded role. Set
`E2E_SKIP_SESSION_MINT=1` to reuse the existing `.auth/` cache across quick
consecutive runs.

## Structure

- `fixtures/` — role-scoped Playwright fixtures (`superAdminPage`,
  `reviewerApi`, …). Each fixture simply loads `.auth/<role>.json` — the
  file is produced by `globalSetup`, not by per-worker login.
- `helpers/` — feature-flag bootstrap, DRF client wrapper.
- `global-setup.ts` — runs the Django mint command before the suite starts.
- `tests/0N-<role>/` — one directory per role. Every spec asserts one of:
  - a surface loads for the entitled role,
  - an unentitled role is blocked,
  - a role's dashboard payload has the expected shape.

## Adding tests

Import from `fixtures/auth.ts` rather than `@playwright/test` directly — the
extended `test` exposes the `{role}Page`, `{role}Api`, `{role}Request`
fixtures.

```ts
import { test, expect } from '../../fixtures/auth';

test('...', async ({ reviewerApi, reviewerPage }) => { ... });
```

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| All tests fail with `missing storageState at .auth/<role>.json` | `globalSetup` couldn't run the Django mint command — check poetry + `manage.py` work from the repo root |
| Every request returns 401 right after mint | session flushed by `InactivitySessionTimeoutMiddleWare` — confirm the mint command stamps `session['last_login']`; stale `.auth/` cache could also be to blame (delete `.auth/`) |
| Workspace/My Reviews page 404s | feature flags not injected — check `helpers/featureFlags.ts` init script actually runs for your build |
| `/api/projects/` returns empty for PM | project not created by the seed — re-run `seed_e2e_accounts` |
| CSRF 403 on POST | the ApiClient pulls `csrftoken` from storageState; if you built your own request context, add the `X-CSRFToken` header manually |
