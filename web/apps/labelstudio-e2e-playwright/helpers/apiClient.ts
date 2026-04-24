import type { APIRequestContext, APIResponse } from '@playwright/test';

/**
 * Thin DRF wrapper — mostly exists so tests don't have to repeat the
 * `content-type` / `X-CSRFToken` boilerplate for unsafe methods.
 *
 * Django's DRF accepts JSON for the review endpoints; the session cookie
 * authenticates, and the `csrftoken` cookie (read from the context) needs to
 * be echoed via `X-CSRFToken` for POST/PATCH/DELETE.
 */
export class ApiClient {
  constructor(
    private readonly request: APIRequestContext,
    private readonly baseURL: string,
  ) {}

  private url(path: string): string {
    return `${this.baseURL.replace(/\/$/, '')}${path}`;
  }

  private async csrfHeader(): Promise<Record<string, string>> {
    const state = await this.request.storageState();
    const cookie = state.cookies.find((c) => c.name === 'csrftoken');
    return cookie ? { 'X-CSRFToken': cookie.value } : {};
  }

  async get(path: string, params?: Record<string, string | number>): Promise<APIResponse> {
    return this.request.get(this.url(path), { params });
  }

  async post(path: string, data: unknown = {}): Promise<APIResponse> {
    return this.request.post(this.url(path), {
      data,
      headers: { 'Content-Type': 'application/json', ...(await this.csrfHeader()) },
    });
  }

  async patch(path: string, data: unknown = {}): Promise<APIResponse> {
    return this.request.patch(this.url(path), {
      data,
      headers: { 'Content-Type': 'application/json', ...(await this.csrfHeader()) },
    });
  }

  async delete(path: string): Promise<APIResponse> {
    return this.request.delete(this.url(path), {
      headers: await this.csrfHeader(),
    });
  }

  // Review flow shortcuts -------------------------------------------------
  acceptAnnotation(pk: number | string, comment?: string) {
    return this.post(`/api/annotations/${pk}/accept/`, comment ? { comment } : {});
  }
  rejectAnnotation(pk: number | string, comment: string) {
    return this.post(`/api/annotations/${pk}/reject/`, { comment });
  }
  releaseLock(pk: number | string) {
    return this.post(`/api/annotations/${pk}/release-lock/`);
  }
  myReviews(params?: Record<string, string | number>) {
    return this.get('/api/current-user/reviews/', params);
  }
  dashboardSummary() {
    return this.get('/api/dashboard/summary/');
  }
  whoami() {
    return this.get('/api/current-user/whoami');
  }
}
