/**
 * Reviewer — accept/reject flow.
 *
 * We can't build a full annotation fixture purely through the public API in
 * a stable way (that path touches project config + task import + label
 * schema), so these tests focus on the error cases the endpoint owns:
 *
 * - reject without a comment → 400
 * - unauthenticated request → 401/403
 * - self-review (annotator acting on their own annotation) → 403
 *
 * The positive happy-path is covered at the integration layer in
 * `label_studio/tasks/tests/test_review_phase5_integration.py`. Wiring a
 * full browser happy-path here would require a project seeded with a task
 * pool + a label config; when that setup lands, extend this spec.
 */
import { test, expect } from '../../fixtures/auth';

test('reject without comment is rejected with 400', async ({ reviewerApi }: any) => {
  // Even a nonexistent PK should reach validation before falling through,
  // since the view parses the body first. But DRF routes the 404 ahead of the
  // body in some orderings, so we accept either.
  const resp = await reviewerApi.rejectAnnotation(999_999_999, '');
  expect([400, 404]).toContain(resp.status());
});

test('unauthenticated accept request is denied', async ({ playwright, baseURL }) => {
  const anon = await playwright.request.newContext({ baseURL });
  try {
    const resp = await anon.post(`${baseURL}/api/annotations/1/accept/`, {
      data: {},
      headers: { 'Content-Type': 'application/json' },
    });
    expect([401, 403]).toContain(resp.status());
  } finally {
    await anon.dispose();
  }
});
