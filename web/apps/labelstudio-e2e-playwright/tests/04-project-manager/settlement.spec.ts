/**
 * Project manager — settlement settings (fflag_settlement).
 *
 * Happy path: PM opens Settlement, sets a project price, and the dashboard's
 * `estimated_settlement` block reflects the pricing currency.
 */
import { test, expect } from '../../fixtures/auth';

async function findAlphaProjectId(api: any): Promise<number> {
  const resp = await api.get('/api/projects/', { page_size: 100 });
  const body = await resp.json();
  const list = Array.isArray(body) ? body : body.results ?? [];
  return list.find((p: any) => p.title === 'E2E Project Alpha')!.id;
}

test('project manager can set pricing and dashboard reflects currency', async ({
  projectManagerApi,
}: any) => {
  const id = await findAlphaProjectId(projectManagerApi);

  // POST /api/projects/<id>/pricing/ might be PUT or PATCH depending on backend;
  // try PATCH on the canonical endpoint first.
  const setPricing = await projectManagerApi.patch(`/api/projects/${id}/pricing/`, {
    label_price: '100.00',
    review_price: '50.00',
    currency: 'KRW',
  });
  // 200 (updated) or 201 (created) — both acceptable.
  expect([200, 201]).toContain(setPricing.status());

  const dashboard = await projectManagerApi.dashboardSummary();
  const body = await dashboard.json();
  const target = body.summary.project_manager.projects.find((p: any) => p.project_id === id);
  expect(target).toBeDefined();
  // With pricing set, estimated_settlement must no longer be null.
  expect(target.estimated_settlement).not.toBeNull();
  expect(target.estimated_settlement.currency).toBe('KRW');
});
