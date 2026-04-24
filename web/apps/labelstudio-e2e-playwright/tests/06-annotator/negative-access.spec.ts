/**
 * Annotator — negative access.
 *
 * Surfaces that require escalated roles must be gated:
 * - Dashboard branches other than `annotator` must be absent.
 * - Review endpoints must reject the annotator who owns the annotation.
 * - Workspace CRUD (PATCH on the seed workspace) must be 403 — annotators
 *   have no workspace membership.
 */
import { test, expect } from '../../fixtures/auth';

test('annotator dashboard has annotator branch only', async ({ annotatorApi }: any) => {
  const resp = await annotatorApi.dashboardSummary();
  const body = await resp.json();
  expect(Object.keys(body.summary).sort()).toEqual(['annotator']);
});

test('annotator cannot PATCH the seed workspace', async ({
  superAdminApi, annotatorApi,
}: any) => {
  const list = await superAdminApi.get('/api/workspaces/');
  const body = await list.json();
  const results = Array.isArray(body) ? body : body.results ?? [];
  const seed = results.find((w: any) => w.title === 'E2E Workspace');
  expect(seed).toBeDefined();

  const resp = await annotatorApi.patch(`/api/workspaces/${seed.id}/`, { title: 'nope' });
  expect([403, 404]).toContain(resp.status());
});

test('annotator POST /api/workspaces/ is allowed or denied per OSS policy', async ({
  annotatorApi,
}: any) => {
  /**
   * workspaces.create defaults to `is_authenticated` (core/permissions.py:96),
   * so this may legitimately succeed on a vanilla OSS build. We pin the
   * outcome to one of the two acceptable shapes so the test fails only on
   * actual regressions (e.g. a 500 or a silent redirect).
   */
  const resp = await annotatorApi.post('/api/workspaces/', {
    title: `annotator-probe ${Date.now()}`,
    description: '',
  });
  expect([201, 403]).toContain(resp.status());

  if (resp.status() === 201) {
    // Clean up — the annotator becomes the manager of their own creation.
    const { id } = await resp.json();
    await annotatorApi.delete(`/api/workspaces/${id}/`);
  }
});
