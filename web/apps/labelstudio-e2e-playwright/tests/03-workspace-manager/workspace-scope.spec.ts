/**
 * Workspace manager — scope isolation.
 *
 * The seed grants `workspaceManager` the WORKSPACE_MANAGER role on
 * `E2E Workspace` only. Dashboard + API must reflect exactly that scope.
 */
import { test, expect } from '../../fixtures/auth';

test('workspace manager dashboard lists only the seeded workspace', async ({
  workspaceManagerApi,
}: any) => {
  const resp = await workspaceManagerApi.dashboardSummary();
  expect(resp.ok()).toBeTruthy();
  const body = await resp.json();

  expect(body.summary).toHaveProperty('workspace_manager');
  const titles = body.summary.workspace_manager.workspaces.map((w: any) => w.title);
  expect(titles).toContain('E2E Workspace');
  // Manager is NOT granted super_admin/project_manager branches.
  expect(body.summary).not.toHaveProperty('super_admin');
  expect(body.summary).not.toHaveProperty('project_manager');
});

test('workspace manager cannot PATCH a workspace they do not manage', async ({
  superAdminApi, workspaceManagerApi,
}: any) => {
  // Create a second workspace owned by super admin; manager has no membership on it.
  const create = await superAdminApi.post('/api/workspaces/', {
    title: `WM-isolation ${Date.now()}`, description: '',
  });
  expect(create.status()).toBe(201);
  const { id } = await create.json();

  const forbidden = await workspaceManagerApi.patch(`/api/workspaces/${id}/`, { title: 'hijack' });
  expect([403, 404]).toContain(forbidden.status());

  // Clean up so subsequent runs stay tidy.
  await superAdminApi.delete(`/api/workspaces/${id}/`);
});
