/**
 * Dashboard payload shape — mirror of
 * `label_studio/dashboard/tests/test_api_matrix.py` at the HTTP layer.
 *
 * Playwright parses destructured fixture names as literal source text, so
 * each role has its own explicit test block rather than a dynamic loop.
 */
import { test, expect } from '../../fixtures/auth';
import type { ApiClient } from '../../helpers/apiClient';

const EXPECTED_KEYS = {
  super_admin: ['completion', 'organization_count', 'project_count', 'user_count', 'workspace_count'],
  workspace_manager: ['workspaces'],
  project_manager: ['projects'],
  annotator: ['deadlines', 'rejected_open', 'rejected_tasks', 'today_assigned'],
  reviewer: ['pending_review', 'recent_decisions'],
};

async function assertBranch(api: ApiClient, branch: keyof typeof EXPECTED_KEYS) {
  const resp = await api.dashboardSummary();
  expect(resp.ok()).toBeTruthy();
  const body = await resp.json();
  expect(body).toHaveProperty('roles');
  expect(body).toHaveProperty('summary');
  expect(body.summary).toHaveProperty(branch);
  const present = Object.keys(body.summary[branch]).sort();
  expect(present).toEqual([...EXPECTED_KEYS[branch]].sort());
}

test('superAdmin → summary.super_admin has canonical keys', async ({ superAdminApi }) => {
  await assertBranch(superAdminApi, 'super_admin');
});

test('workspaceManager → summary.workspace_manager has canonical keys', async ({ workspaceManagerApi }) => {
  await assertBranch(workspaceManagerApi, 'workspace_manager');
});

test('projectManager → summary.project_manager has canonical keys', async ({ projectManagerApi }) => {
  await assertBranch(projectManagerApi, 'project_manager');
});

test('annotator → summary.annotator has canonical keys', async ({ annotatorApi }) => {
  await assertBranch(annotatorApi, 'annotator');
});

test('reviewer → summary.reviewer has canonical keys', async ({ reviewerApi }) => {
  await assertBranch(reviewerApi, 'reviewer');
});

test('plainMember → envelope intact, summary empty', async ({ plainMemberApi }) => {
  const resp = await plainMemberApi.dashboardSummary();
  expect(resp.ok()).toBeTruthy();
  const body = await resp.json();
  expect(body.roles).toEqual([]);
  expect(body.summary).toEqual({});
  expect(body).toHaveProperty('organization_id');
  expect(body).toHaveProperty('generated_at');
});
