/**
 * Global setup — runs once before all Playwright workers start.
 *
 * Invokes the Django management command that mints a DB session per seeded
 * E2E account and serialises cookies as Playwright storageState JSON. After
 * this runs, every role fixture in `fixtures/auth.ts` has a pre-authenticated
 * storage file waiting at `.auth/<role>.json`.
 *
 * Opt out by setting `E2E_SKIP_SESSION_MINT=1` — useful if you want to reuse
 * a stale `.auth/` cache across consecutive quick runs.
 *
 * Assumes the Django server + Postgres the command talks to is the same one
 * the tests will hit (they share the `django_session` table).
 */

import { spawnSync } from 'node:child_process';
import * as path from 'node:path';
import * as fs from 'node:fs';

export default async function globalSetup() {
  if (process.env.E2E_SKIP_SESSION_MINT === '1') {
    // eslint-disable-next-line no-console
    console.log('[globalSetup] E2E_SKIP_SESSION_MINT=1 — reusing existing .auth/ cache');
    return;
  }

  const harnessDir = __dirname;
  // Repo root is four levels up: web/apps/labelstudio-e2e-playwright/ → repo/
  const repoRoot = path.resolve(harnessDir, '..', '..', '..');
  const authDir = path.join(harnessDir, '.auth');

  fs.mkdirSync(authDir, { recursive: true });

  const args = [
    'run', 'python', 'label_studio/manage.py',
    'e2e_mint_sessions', '--out-dir', authDir,
  ];
  // eslint-disable-next-line no-console
  console.log(`[globalSetup] poetry ${args.join(' ')}`);

  const res = spawnSync('poetry', args, {
    cwd: repoRoot,
    stdio: 'inherit',
    env: process.env,
  });
  if (res.status !== 0) {
    throw new Error(
      `[globalSetup] e2e_mint_sessions failed (exit=${res.status}). ` +
      'Ensure the backend DB is accessible and seed_e2e_accounts was run.',
    );
  }
}
