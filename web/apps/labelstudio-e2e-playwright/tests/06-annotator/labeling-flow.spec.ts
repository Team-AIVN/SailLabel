/**
 * Annotator — labeling surface access.
 *
 * Asserts the annotator can navigate to their project's data manager and
 * reach the labeling UI. Annotation submission proper depends on a label
 * config + task pool; we just verify the surface loads for now.
 */
import { test, expect } from '../../fixtures/auth';

async function findAlphaProjectId(api: any): Promise<number> {
  const resp = await api.get('/api/projects/', { page_size: 100 });
  const body = await resp.json();
  const list = Array.isArray(body) ? body : body.results ?? [];
  const alpha = list.find((p: any) => p.title === 'E2E Project Alpha');
  if (!alpha) throw new Error('Annotator cannot see E2E Project Alpha');
  return alpha.id;
}

test('annotator can open data manager for their project', async ({
  annotatorPage: page, annotatorApi,
}: any) => {
  const id = await findAlphaProjectId(annotatorApi);
  const resp = await page.goto(`/projects/${id}/data`);
  if (resp) expect(resp.status()).toBeLessThan(400);
  await expect(page.locator('body')).toBeVisible();
});

test('annotator dashboard carries deadlines/rejected_tasks arrays', async ({
  annotatorApi,
}: any) => {
  const resp = await annotatorApi.dashboardSummary();
  const body = await resp.json();
  expect(body.summary).toHaveProperty('annotator');
  expect(Array.isArray(body.summary.annotator.deadlines)).toBe(true);
  expect(Array.isArray(body.summary.annotator.rejected_tasks)).toBe(true);
  expect(typeof body.summary.annotator.today_assigned).toBe('number');
});
