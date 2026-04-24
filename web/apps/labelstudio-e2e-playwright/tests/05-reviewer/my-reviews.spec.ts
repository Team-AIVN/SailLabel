/**
 * Reviewer — `/reviews` page + `/api/current-user/reviews/` endpoint.
 *
 * Surface checks: page renders when fflag_batch_review is ON, the API is
 * reachable, and the legacy + new URL shapes (`/api/current-user/reviews/`
 * and `/api/users/me/reviews/`) return the same payload.
 */
import { test, expect } from '../../fixtures/auth';

test('reviewer can open /reviews when fflag_batch_review is ON', async ({
  reviewerPage: page,
}: any) => {
  await page.goto('/reviews');
  // Page title / heading / table — any one suffices.
  const heading = page.getByRole('heading', { name: /my reviews/i });
  const table = page.locator('table');
  await expect(heading.or(table)).toBeVisible({ timeout: 10_000 });
});

test('current-user/reviews and users/me/reviews agree', async ({ reviewerApi }: any) => {
  const [a, b] = await Promise.all([
    reviewerApi.get('/api/current-user/reviews/'),
    reviewerApi.get('/api/users/me/reviews/'),
  ]);
  expect(a.ok()).toBeTruthy();
  expect(b.ok()).toBeTruthy();
  expect(await a.json()).toEqual(await b.json());
});
