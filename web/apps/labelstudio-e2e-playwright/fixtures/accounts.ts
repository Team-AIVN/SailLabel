/**
 * Role-scoped test accounts.
 *
 * The emails here must match the ones created by
 * `label_studio/manage.py seed_e2e_accounts` — fixtures in `auth.ts` look up
 * the per-role credentials by key.
 */

export type RoleKey =
  | 'superAdmin'
  | 'workspaceManager'
  | 'projectManager'
  | 'reviewer'
  | 'annotator'
  | 'plainMember';

const password = () => {
  const v = process.env.E2E_PASSWORD;
  if (!v) {
    throw new Error(
      'E2E_PASSWORD is not set — populate .env.e2e or export before running Playwright.',
    );
  }
  return v;
};

export const ACCOUNTS: Record<RoleKey, { email: string; password: string }> = {
  superAdmin: {
    email: 'superadmin@e2e.saillabel.local',
    get password() { return password(); },
  },
  workspaceManager: {
    email: 'wsmanager@e2e.saillabel.local',
    get password() { return password(); },
  },
  projectManager: {
    email: 'pmanager@e2e.saillabel.local',
    get password() { return password(); },
  },
  reviewer: {
    email: 'reviewer@e2e.saillabel.local',
    get password() { return password(); },
  },
  annotator: {
    email: 'annotator@e2e.saillabel.local',
    get password() { return password(); },
  },
  plainMember: {
    email: 'plainmember@e2e.saillabel.local',
    get password() { return password(); },
  },
};

export const ROLE_KEYS: readonly RoleKey[] = Object.keys(ACCOUNTS) as RoleKey[];
