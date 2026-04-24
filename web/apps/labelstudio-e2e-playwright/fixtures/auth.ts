/**
 * Role-scoped Playwright fixture.
 *
 * Per role, we log in once via the Django form endpoint, persist the
 * resulting cookies as `storageState`, and reuse that file across tests in
 * the same run. Subsequent test invocations that request `${role}Page`
 * receive a fresh BrowserContext already authenticated as that role.
 *
 * Fixture names exposed (one per RoleKey):
 *   superAdminPage, workspaceManagerPage, projectManagerPage,
 *   reviewerPage, annotatorPage, plainMemberPage
 *
 * Each also has an `${role}Api` companion returning an `ApiClient` bound to
 * the same session, and an `${role}Request` returning the raw
 * APIRequestContext.
 *
 * Playwright statically parses fixture names and the destructured parameter
 * names of fixture implementations — it does NOT evaluate template literals
 * or dynamic destructuring. That is why every fixture is written out
 * explicitly below rather than generated in a loop.
 */

import { test as base, expect, type Page, type APIRequestContext } from '@playwright/test';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { type RoleKey } from './accounts';
import { buildFlagInitScript } from '../helpers/featureFlags';
import { ApiClient } from '../helpers/apiClient';

const AUTH_DIR = path.resolve(__dirname, '..', '.auth');

function storageStatePath(role: RoleKey): string {
  const file = path.join(AUTH_DIR, `${role}.json`);
  if (!fs.existsSync(file)) {
    throw new Error(
      `[${role}] missing storageState at ${file}. ` +
      'Did global-setup.ts run? It should invoke `manage.py e2e_mint_sessions`.',
    );
  }
  return file;
}

function makePageFixture(role: RoleKey) {
  return async ({ browser, baseURL }: any, use: (p: Page) => Promise<void>) => {
    if (!baseURL) throw new Error('baseURL missing — check playwright.config.ts');
    const ctx = await browser.newContext({ storageState: storageStatePath(role), baseURL });
    await ctx.addInitScript(buildFlagInitScript());
    const page = await ctx.newPage();
    try {
      await use(page);
    } finally {
      await ctx.close();
    }
  };
}

function makeRequestFixture(role: RoleKey) {
  return async (
    { playwright, baseURL }: any,
    use: (r: APIRequestContext) => Promise<void>,
  ) => {
    if (!baseURL) throw new Error('baseURL missing');
    const req = await playwright.request.newContext({
      baseURL, storageState: storageStatePath(role),
    });
    try {
      await use(req);
    } finally {
      await req.dispose();
    }
  };
}

type RoleFixtures = {
  superAdminPage: Page;
  workspaceManagerPage: Page;
  projectManagerPage: Page;
  reviewerPage: Page;
  annotatorPage: Page;
  plainMemberPage: Page;

  superAdminRequest: APIRequestContext;
  workspaceManagerRequest: APIRequestContext;
  projectManagerRequest: APIRequestContext;
  reviewerRequest: APIRequestContext;
  annotatorRequest: APIRequestContext;
  plainMemberRequest: APIRequestContext;

  superAdminApi: ApiClient;
  workspaceManagerApi: ApiClient;
  projectManagerApi: ApiClient;
  reviewerApi: ApiClient;
  annotatorApi: ApiClient;
  plainMemberApi: ApiClient;
};

export const test = base.extend<RoleFixtures>({
  // ── Page fixtures ────────────────────────────────────────────────────
  superAdminPage: makePageFixture('superAdmin'),
  workspaceManagerPage: makePageFixture('workspaceManager'),
  projectManagerPage: makePageFixture('projectManager'),
  reviewerPage: makePageFixture('reviewer'),
  annotatorPage: makePageFixture('annotator'),
  plainMemberPage: makePageFixture('plainMember'),

  // ── Raw APIRequestContext fixtures ───────────────────────────────────
  superAdminRequest: makeRequestFixture('superAdmin'),
  workspaceManagerRequest: makeRequestFixture('workspaceManager'),
  projectManagerRequest: makeRequestFixture('projectManager'),
  reviewerRequest: makeRequestFixture('reviewer'),
  annotatorRequest: makeRequestFixture('annotator'),
  plainMemberRequest: makeRequestFixture('plainMember'),

  // ── ApiClient wrappers — literal destructuring per role ──────────────
  superAdminApi: async ({ superAdminRequest, baseURL }, use) => {
    await use(new ApiClient(superAdminRequest, baseURL!));
  },
  workspaceManagerApi: async ({ workspaceManagerRequest, baseURL }, use) => {
    await use(new ApiClient(workspaceManagerRequest, baseURL!));
  },
  projectManagerApi: async ({ projectManagerRequest, baseURL }, use) => {
    await use(new ApiClient(projectManagerRequest, baseURL!));
  },
  reviewerApi: async ({ reviewerRequest, baseURL }, use) => {
    await use(new ApiClient(reviewerRequest, baseURL!));
  },
  annotatorApi: async ({ annotatorRequest, baseURL }, use) => {
    await use(new ApiClient(annotatorRequest, baseURL!));
  },
  plainMemberApi: async ({ plainMemberRequest, baseURL }, use) => {
    await use(new ApiClient(plainMemberRequest, baseURL!));
  },
});

export { expect };
