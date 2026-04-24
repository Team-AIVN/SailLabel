/**
 * Project manager — settings surface access.
 *
 * Verifies that every settings tab (General/Labeling/Annotation/ML/Storage/
 * Predictions/DangerZone) is reachable for a PM on their project. We stop
 * short of asserting deep form behavior — the goal is surface-level access,
 * not widget regressions (those belong to more focused suites).
 */
import { test, expect } from '../../fixtures/auth';

const TAB_PATHS = ['/', '/labeling', '/annotation', '/ml', '/storage', '/predictions', '/danger-zone'];

async function findAlphaProjectId(api: any): Promise<number> {
  const resp = await api.get('/api/projects/', { page_size: 100 });
  expect(resp.ok()).toBeTruthy();
  const body = await resp.json();
  const list = Array.isArray(body) ? body : body.results ?? [];
  const alpha = list.find((p: any) => p.title === 'E2E Project Alpha');
  if (!alpha) throw new Error('E2E Project Alpha not found for project manager');
  return alpha.id;
}

test('project manager reaches every project settings tab', async ({
  projectManagerPage: page, projectManagerApi,
}: any) => {
  const id = await findAlphaProjectId(projectManagerApi);

  for (const tab of TAB_PATHS) {
    const url = `/projects/${id}/settings${tab}`;
    const resp = await page.goto(url);
    // 200 OR client-side routed render (Playwright sometimes reports null for SPA redirects).
    if (resp) expect(resp.status()).toBeLessThan(400);
    // The page container itself should render.
    await expect(page.locator('body')).toBeVisible();
  }
});

test('project manager dashboard lists managed project', async ({ projectManagerApi }: any) => {
  const resp = await projectManagerApi.dashboardSummary();
  const body = await resp.json();
  const titles = body.summary.project_manager.projects.map((p: any) => p.title);
  expect(titles).toContain('E2E Project Alpha');
});
