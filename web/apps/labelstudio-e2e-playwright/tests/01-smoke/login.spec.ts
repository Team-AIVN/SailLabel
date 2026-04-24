/**
 * Smoke: each role logs in and `/api/current-user/whoami` returns their email.
 *
 * Playwright parses destructured fixture names as literal source text, so we
 * enumerate per-role tests explicitly rather than building them in a loop
 * (dynamic destructuring like `[`${role}Api`]` is not recognised).
 */
import { test, expect } from '../../fixtures/auth';
import { ACCOUNTS } from '../../fixtures/accounts';

test('superAdmin — whoami returns seeded email', async ({ superAdminApi }) => {
  const resp = await superAdminApi.whoami();
  expect(resp.ok()).toBeTruthy();
  expect((await resp.json()).email).toBe(ACCOUNTS.superAdmin.email);
});

test('workspaceManager — whoami returns seeded email', async ({ workspaceManagerApi }) => {
  const resp = await workspaceManagerApi.whoami();
  expect(resp.ok()).toBeTruthy();
  expect((await resp.json()).email).toBe(ACCOUNTS.workspaceManager.email);
});

test('projectManager — whoami returns seeded email', async ({ projectManagerApi }) => {
  const resp = await projectManagerApi.whoami();
  expect(resp.ok()).toBeTruthy();
  expect((await resp.json()).email).toBe(ACCOUNTS.projectManager.email);
});

test('reviewer — whoami returns seeded email', async ({ reviewerApi }) => {
  const resp = await reviewerApi.whoami();
  expect(resp.ok()).toBeTruthy();
  expect((await resp.json()).email).toBe(ACCOUNTS.reviewer.email);
});

test('annotator — whoami returns seeded email', async ({ annotatorApi }) => {
  const resp = await annotatorApi.whoami();
  expect(resp.ok()).toBeTruthy();
  expect((await resp.json()).email).toBe(ACCOUNTS.annotator.email);
});

test('plainMember — whoami returns seeded email', async ({ plainMemberApi }) => {
  const resp = await plainMemberApi.whoami();
  expect(resp.ok()).toBeTruthy();
  expect((await resp.json()).email).toBe(ACCOUNTS.plainMember.email);
});
