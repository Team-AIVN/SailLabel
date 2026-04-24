/**
 * Super admin — workspace management surface.
 *
 * Covers listing + create + soft-delete via the API (UI flow is exercised in
 * `workspace-scope.spec.ts`). These assertions rely on the seed fixture:
 * an organization exists, and `E2E Workspace` is the canonical seed workspace.
 */
import { test, expect } from '../../fixtures/auth';

test('super admin lists workspaces and sees the seed workspace', async ({ superAdminApi }: any) => {
  const resp = await superAdminApi.get('/api/workspaces/');
  expect(resp.ok()).toBeTruthy();
  const body = await resp.json();
  const results = Array.isArray(body) ? body : body.results ?? [];
  const titles = results.map((w: any) => w.title);
  expect(titles).toContain('E2E Workspace');
});

test('super admin creates and archives a workspace', async ({ superAdminApi }: any) => {
  const title = `E2E Ad Hoc ${Date.now()}`;
  const create = await superAdminApi.post('/api/workspaces/', { title, description: 'e2e' });
  expect(create.status()).toBe(201);
  const { id } = await create.json();

  // Archive (soft-delete): DELETE must leave the row but mark deleted_at.
  const del = await superAdminApi.delete(`/api/workspaces/${id}/`);
  expect([200, 204]).toContain(del.status());

  // List should no longer surface the archived workspace.
  const listAfter = await superAdminApi.get('/api/workspaces/');
  const afterBody = await listAfter.json();
  const afterResults = Array.isArray(afterBody) ? afterBody : afterBody.results ?? [];
  expect(afterResults.some((w: any) => w.id === id)).toBe(false);
});
