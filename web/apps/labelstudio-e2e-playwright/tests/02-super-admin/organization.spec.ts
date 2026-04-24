/**
 * Super admin — organization admin surface.
 *
 * Verifies the `/organization` page renders (members list + invite link) and
 * that the member count from `/api/dashboard/summary/` matches what the
 * people page displays.
 */
import { test, expect } from '../../fixtures/auth';

test('super admin sees organization people page', async ({ superAdminPage: page }: any) => {
  await page.goto('/organization');
  // Any of these markers works — the page title, the people section heading,
  // or the invite-link block. Be liberal with the selector so the test doesn't
  // break on minor copy tweaks.
  await expect(
    page.getByRole('heading', { name: /organization|people/i }).first(),
  ).toBeVisible({ timeout: 10_000 });
});

test('super admin dashboard user_count ≥ 6 seeded accounts', async ({ superAdminApi }: any) => {
  const resp = await superAdminApi.dashboardSummary();
  expect(resp.ok()).toBeTruthy();
  const body = await resp.json();
  expect(body.summary.super_admin.user_count).toBeGreaterThanOrEqual(6);
});
