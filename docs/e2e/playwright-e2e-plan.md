# Playwright E2E 테스트 계획 (SailLabel Phase 1–8)

이 문서는 **다음 세션에서 Playwright E2E를 바로 실행/구현**할 수 있도록 설계된
참조 문서입니다. 테스트 계정 · 로그인 플로우 · 역할별 시나리오 · 파일 배치 ·
디렉토리 구조가 모두 여기 포함되어 있습니다.

---

## 0. 다음 세션 수행 체크리스트 (TL;DR)

1. Backend / Frontend 서버 기동
   ```bash
   poetry run python label_studio/manage.py migrate
   poetry run python label_studio/manage.py seed_e2e_accounts
   poetry run python label_studio/manage.py runserver 0.0.0.0:8080
   # (프론트: yarn --cwd web dev:labelstudio  또는 빌드된 번들 사용)
   ```
2. Playwright 프로젝트 초기화 (아래 §4)
   ```bash
   cd web/apps/labelstudio-e2e-playwright
   pnpm init && pnpm add -D @playwright/test
   pnpm playwright install --with-deps chromium
   ```
3. 공통 설정 · 계정 fixture · 테스트 파일 생성 (§4 파일 트리)
4. 실행
   ```bash
   pnpm playwright test
   ```

---

## 1. 전제 · 서버 URL

| 항목 | 값 |
|---|---|
| Django 기본 포트 | `http://localhost:8080` |
| 로그인 엔드포인트 | `POST /user/login/` (Django form + CSRF) |
| 회원가입 엔드포인트 | `POST /user/signup/` |
| 대시보드 API | `GET /api/dashboard/summary/` |
| Whoami | `GET /api/current-user/whoami` |
| Review 액션 API | `POST /api/annotations/<pk>/accept\|reject\|release-lock/` |
| My Reviews API | `GET /api/current-user/reviews/`, `GET /api/users/me/reviews/` |
| Workspaces API | `GET/POST /api/workspaces/`, `/api/workspaces/<pk>/**` |

**피처 플래그 (프론트 메뉴/페이지 게이팅)**
- `fflag_workspace` — Workspaces 페이지 + Menubar 항목 (`/workspaces`)
- `fflag_batch_review` — My Reviews 페이지 + Menubar 항목 (`/reviews`)
- `fflag_all_feat_dia_1777_ls_homepage_short` — Home 대시보드 (`/`)
- `fflag_review_workflow` — 리뷰 워크플로우 (UI 노출용)
- `fflag_settlement` — 정산 (Settings > Settlement)

**E2E 실행 시 `feature_flags.json`에서 위 플래그들을 `"on": true`로 토글**해야
역할별 페이지가 메뉴에 나타납니다. (또는 `LocalStorage`에서 `fflag_*` 키를
수동 세팅할 수 있으며 이는 §6 fixture에서 처리)

---

## 2. 테스트 계정 (seed 명령으로 생성)

시드 명령:
```bash
poetry run python label_studio/manage.py seed_e2e_accounts
# 비밀번호를 바꾸고 싶으면:
poetry run python label_studio/manage.py seed_e2e_accounts --password 'YourSecret!'
```

생성되는 계정 (기본 비밀번호 `E2ETestPass!`):

| 키 (fixture name)   | Email                              | Org Role      | Workspace Role       | Project Role (on Alpha) | 비고 |
|---------------------|------------------------------------|---------------|-----------------------|--------------------------|------|
| `superAdmin`        | superadmin@e2e.saillabel.local     | super_admin   | —                     | —                        | `is_superuser=True`, 조직 소유자 |
| `workspaceManager`  | wsmanager@e2e.saillabel.local      | member        | workspace_manager     | —                        | `E2E Workspace`의 매니저 |
| `projectManager`    | pmanager@e2e.saillabel.local       | member        | —                     | project_manager          | |
| `reviewer`          | reviewer@e2e.saillabel.local       | member        | —                     | reviewer                 | |
| `annotator`         | annotator@e2e.saillabel.local      | member        | —                     | annotator                | |
| `plainMember`       | plainmember@e2e.saillabel.local    | member        | —                     | —                        | 아무 역할 없음, 음성 테스트용 |

**공통 픽스처 데이터**
- Organization: `E2E Organization` (superAdmin이 소유자)
- Workspace: `E2E Workspace`
- Projects: `E2E Project Alpha`, `E2E Project Beta` (둘 다 워크스페이스에 배치)

---

## 3. 역할별 테스트 매트릭스

범례: ✅ 통과해야 할 시나리오, ❌ 차단되어야 할 시나리오.

### 3.1 Super Admin (`superAdmin`)
- ✅ `/` Home 대시보드 — `super_admin` 브랜치(`organization_count`, `workspace_count`, `user_count`, `project_count`, `completion`) 노출
- ✅ `/workspaces` 진입, 전체 워크스페이스 목록 조회, 신규 워크스페이스 생성
- ✅ `/organization` 진입 → 멤버 목록 조회 · 초대 링크 표시
- ✅ `/projects` 모든 프로젝트 노출, Project 설정 전체 접근
- ✅ Project Settings > `Settlement` 진입 — 가격 설정/배치 실행 가능
- ✅ Workspace Archive(soft-delete) 수행
- ❌ `sudo`적 행동이라도 `completed_by` 자기 자신인 annotation에 대해 Accept/Reject 403

### 3.2 Workspace Manager (`workspaceManager`)
- ✅ `/workspaces` 진입, 본인이 매니저인 `E2E Workspace` 표시
- ✅ 해당 워크스페이스 상세에서 프로젝트 목록 조회, 멤버 관리
- ✅ Home 대시보드 — `workspace_manager` 브랜치(`workspaces[]` 각 항목이 `workspace_id`,`title`,`project_count`,`completion`)
- ❌ `E2E Organization` 전체 관리자 페이지(`/organization`) 멤버 수정/초대는 403 혹은 비표시
- ❌ 관리하지 않는 다른 워크스페이스 PATCH/DELETE 403

### 3.3 Project Manager (`projectManager`)
- ✅ `/projects` → `E2E Project Alpha` 접근 → Data Manager 진입
- ✅ Project Settings 전체 탭(General/Labeling/Annotation/ML/Storage/Settlement/Predictions/DangerZone) 접근
- ✅ Home 대시보드 — `project_manager` 브랜치(`projects[]` 각 항목이 `project_id`,`title`,`total`,`finished`,`percent`,`type`,`worker_progress`,`estimated_settlement`)
- ✅ Settlement Settings에서 가격 설정 가능 (fflag_settlement ON)
- ❌ `/workspaces` 메뉴 항목은 보이나 자기 워크스페이스 아닌 경우 관리 불가
- ❌ `E2E Project Beta`(권한 없음) Settings 접근 403

### 3.4 Reviewer (`reviewer`)
- ✅ `/` Home 대시보드 — `reviewer` 브랜치(`pending_review`, `recent_decisions[]`)
- ✅ `/reviews` My Reviews 페이지 접근 (fflag_batch_review ON) — 빈 테이블 렌더링 확인
- ✅ `/projects/<alpha_id>/data` Data Manager 진입, 리뷰 모드 진입 가능
- ✅ WILL_REVIEWED 상태의 annotation에 대해 Accept/Reject API 호출 성공 (comment 필수 조건 포함)
- ✅ reject 수행 후 My Reviews 페이지에 reject 레코드 표시
- ❌ 본인이 `completed_by`인 annotation accept/reject 시 403 (self-review)
- ❌ Project Settings/Workspace 생성 등 관리자 액션 비노출/403

### 3.5 Annotator (`annotator`)
- ✅ `/` Home 대시보드 — `annotator` 브랜치(`today_assigned`, `rejected_open`, `rejected_tasks[]`, `deadlines[]`)
- ✅ `/projects/<alpha_id>` 진입 → 라벨링 UI 가능 (`Start Labeling`)
- ✅ 본인에게 할당된 task에 annotation 제출 → FSM ASSIGNED → ANNOTATED 전이 반영
- ❌ `/reviews` 메뉴 비노출 (reviewer 역할 없음)
- ❌ `/organization` 초대/멤버 수정 403
- ❌ 리뷰 액션(accept/reject) 시도 시 권한 거부

### 3.6 Plain Member (`plainMember`) — 음성 테스트
- ✅ 로그인 성공, whoami `/api/current-user/whoami` 200
- ✅ Home 대시보드 — `roles: []`, `summary: {}` (envelope 유지)
- ❌ 모든 역할별 페이지 진입 차단 또는 빈 상태 노출
- ❌ 프로젝트/워크스페이스 생성 API 시도 시 빈 리스트 또는 권한 거부

---

## 4. Playwright 프로젝트 구조 (다음 세션에서 생성)

```
web/apps/labelstudio-e2e-playwright/
├── package.json
├── playwright.config.ts
├── tsconfig.json
├── .env.e2e                     # BASE_URL, E2E_PASSWORD 등
├── fixtures/
│   ├── auth.ts                  # role-scoped authenticated context
│   └── accounts.ts              # 계정 정의 (§2 테이블과 1:1)
├── helpers/
│   ├── login.ts                 # CSRF-aware form login
│   ├── featureFlags.ts          # localStorage에 fflag_* 주입
│   └── apiClient.ts             # DRF API 요청 래퍼 (accept/reject 등)
├── .auth/                       # storageState 저장 디렉토리 (gitignored)
└── tests/
    ├── 01-smoke/
    │   ├── login.spec.ts        # 각 계정 로그인 + whoami
    │   └── dashboard-shape.spec.ts  # 5개 역할 × summary 키 검증
    ├── 02-super-admin/
    │   ├── workspaces.spec.ts
    │   └── organization.spec.ts
    ├── 03-workspace-manager/
    │   └── workspace-scope.spec.ts
    ├── 04-project-manager/
    │   ├── settings-tabs.spec.ts
    │   └── settlement.spec.ts
    ├── 05-reviewer/
    │   ├── my-reviews.spec.ts
    │   └── accept-reject.spec.ts
    └── 06-annotator/
        ├── labeling-flow.spec.ts
        └── negative-access.spec.ts
```

### 4.1 `fixtures/accounts.ts` (§2 테이블의 코드 표현)

```ts
export type RoleKey =
  | 'superAdmin'
  | 'workspaceManager'
  | 'projectManager'
  | 'reviewer'
  | 'annotator'
  | 'plainMember';

export const ACCOUNTS: Record<RoleKey, { email: string; password: string }> = {
  superAdmin:       { email: 'superadmin@e2e.saillabel.local',   password: process.env.E2E_PASSWORD! },
  workspaceManager: { email: 'wsmanager@e2e.saillabel.local',    password: process.env.E2E_PASSWORD! },
  projectManager:   { email: 'pmanager@e2e.saillabel.local',     password: process.env.E2E_PASSWORD! },
  reviewer:         { email: 'reviewer@e2e.saillabel.local',     password: process.env.E2E_PASSWORD! },
  annotator:        { email: 'annotator@e2e.saillabel.local',    password: process.env.E2E_PASSWORD! },
  plainMember:      { email: 'plainmember@e2e.saillabel.local',  password: process.env.E2E_PASSWORD! },
};
```

### 4.2 `helpers/login.ts` — Django form 로그인

```ts
import type { APIRequestContext, BrowserContext } from '@playwright/test';

/** Login via Django form. Preserves session in the given BrowserContext. */
export async function loginViaForm(
  request: APIRequestContext,
  baseURL: string,
  email: string,
  password: string,
): Promise<void> {
  // 1) Fetch login page to obtain CSRF token.
  const page = await request.get(`${baseURL}/user/login/`);
  const html = await page.text();
  const csrf = /name="csrfmiddlewaretoken" value="([^"]+)"/.exec(html)?.[1];
  if (!csrf) throw new Error('csrf token not found on /user/login/');

  // 2) POST credentials. Django sets sessionid cookie on success.
  const resp = await request.post(`${baseURL}/user/login/`, {
    form: { csrfmiddlewaretoken: csrf, email, password, persist_session: 'on' },
    headers: { Referer: `${baseURL}/user/login/` },
  });
  if (!resp.ok() && resp.status() !== 302) {
    throw new Error(`login failed (${resp.status()}) for ${email}`);
  }
}
```

### 4.3 `fixtures/auth.ts` — role별 storageState 자동 생성

Playwright `test.extend` 기반 fixture. 테스트 시작 시 role별 로그인 세션을
한 번 수행해 `storageState`로 저장, 이후 브라우저 컨텍스트는 그 세션을 재사용.

```ts
import { test as base, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { ACCOUNTS, RoleKey } from './accounts';
import { loginViaForm } from '../helpers/login';

const AUTH_DIR = path.resolve(__dirname, '../.auth');
fs.mkdirSync(AUTH_DIR, { recursive: true });

type Fixtures = Record<`${RoleKey}Page`, import('@playwright/test').Page>;

export const test = base.extend<Fixtures>(
  Object.fromEntries(
    Object.keys(ACCOUNTS).map((role) => [
      `${role}Page`,
      async ({ browser, playwright, baseURL }, use) => {
        const file = path.join(AUTH_DIR, `${role}.json`);
        if (!fs.existsSync(file)) {
          const req = await playwright.request.newContext({ baseURL });
          const { email, password } = ACCOUNTS[role as RoleKey];
          await loginViaForm(req, baseURL!, email, password);
          await req.storageState({ path: file });
          await req.dispose();
        }
        const ctx = await browser.newContext({ storageState: file, baseURL });
        // 프론트 피처 플래그를 localStorage에 주입 (index.js의 isFF 로직 호환)
        await ctx.addInitScript(() => {
          const flags = ['fflag_workspace', 'fflag_batch_review',
            'fflag_all_feat_dia_1777_ls_homepage_short',
            'fflag_review_workflow', 'fflag_settlement'];
          flags.forEach((k) => localStorage.setItem(k, 'true'));
        });
        const page = await ctx.newPage();
        await use(page);
        await ctx.close();
      },
    ]),
  ) as any,
);
export { expect };
```

사용 예:
```ts
import { test, expect } from '../fixtures/auth';

test('super admin sees workspaces menu', async ({ superAdminPage: page }) => {
  await page.goto('/workspaces');
  await expect(page.getByRole('heading', { name: /workspaces/i })).toBeVisible();
});
```

### 4.4 `playwright.config.ts` 요지

```ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  reporter: [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:8080',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
});
```

### 4.5 `.env.e2e` 템플릿

```
E2E_BASE_URL=http://localhost:8080
E2E_PASSWORD=E2ETestPass!
```

---

## 5. 대표 테스트 스펙 예시 (다음 세션에서 그대로 옮겨 쓸 수 있음)

### 5.1 `tests/01-smoke/dashboard-shape.spec.ts`

5개 역할 × summary 키 셋 검증. 백엔드 단위 테스트
(`dashboard/tests/test_api_matrix.py`)와 동일한 계약을 브라우저 경로로 재검증.

```ts
import { test, expect } from '../../fixtures/auth';

const EXPECTED_KEYS: Record<string, string[]> = {
  super_admin:       ['organization_count','workspace_count','user_count','project_count','completion'],
  workspace_manager: ['workspaces'],
  project_manager:   ['projects'],
  annotator:         ['today_assigned','rejected_open','rejected_tasks','deadlines'],
  reviewer:          ['pending_review','recent_decisions'],
};

for (const [rolePage, branch] of [
  ['superAdminPage','super_admin'],
  ['workspaceManagerPage','workspace_manager'],
  ['projectManagerPage','project_manager'],
  ['annotatorPage','annotator'],
  ['reviewerPage','reviewer'],
] as const) {
  test(`${branch} summary carries its canonical keys`, async ({ [rolePage]: page }: any) => {
    const resp = await page.request.get('/api/dashboard/summary/');
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(Object.keys(body.summary)).toContain(branch);
    for (const k of EXPECTED_KEYS[branch]) {
      expect(body.summary[branch]).toHaveProperty(k);
    }
  });
}
```

### 5.2 `tests/05-reviewer/accept-reject.spec.ts`

```ts
import { test, expect } from '../../fixtures/auth';

test('reviewer rejects annotation — reason persists + self-review blocked', async ({
  reviewerPage, annotatorPage,
}) => {
  // 1) annotator가 태스크 생성 + WILL_REVIEWED까지 드라이브는 백엔드 API로 사전에 준비
  //    (별도 helper에서 StateManager 대신 DRF 액션 API를 호출)
  // 2) reviewer가 /api/annotations/<pk>/reject/에 comment=''로 호출 → 400 기대
  const bad = await reviewerPage.request.post('/api/annotations/1/reject/', { data: {} });
  expect(bad.status()).toBe(400);

  // 3) 본인이 주석 저자인 경우 403 기대 (self-review guard)
  const self = await annotatorPage.request.post('/api/annotations/<self-authored-pk>/reject/',
    { data: { comment: 'self' } });
  expect(self.status()).toBe(403);
});
```

### 5.3 `tests/06-annotator/negative-access.spec.ts`

```ts
import { test, expect } from '../../fixtures/auth';

test('annotator cannot see /workspaces admin surface', async ({ annotatorPage: page }) => {
  await page.goto('/workspaces');
  // fflag_workspace이 ON이라도 annotator는 워크스페이스 관리 버튼이 노출되지 않는다
  await expect(page.getByRole('button', { name: /create workspace/i })).toHaveCount(0);
});
```

---

## 6. 다음 세션의 실행 명령 (요약)

```bash
# 1) 계정 준비
poetry run python label_studio/manage.py migrate
poetry run python label_studio/manage.py seed_e2e_accounts

# 2) 서버 기동 (터미널 A)
poetry run python label_studio/manage.py runserver 0.0.0.0:8080

# 3) Playwright 셋업 + 실행 (터미널 B)
mkdir -p web/apps/labelstudio-e2e-playwright && cd $_
pnpm init
pnpm add -D @playwright/test dotenv
pnpm playwright install --with-deps chromium
# (§4의 playwright.config.ts / fixtures / tests 트리 생성 후)
pnpm playwright test --reporter=list
```

---

## 7. 확장 여지 (우선순위 낮음)

- **LaunchDarkly 대체:** `feature_flags.json`을 env로 가리키도록 바꾸고
  테스트 실행 전 임시 플래그 파일을 복사하는 훅 추가.
- **다중 조직:** `plainMember`가 다른 조직에서는 `super_admin`인 케이스로
  크로스-조직 격리 검증.
- **Batch review HTTP 경로:** 현재 단위 테스트(`test_batch_review.py`)만 있지만
  `fflag_batch_review` ON 상태에서 UI 버튼으로 batch 라우팅하는 E2E 시나리오
  추가 가능 (`/projects/<id>/data`의 `Start Review` 버튼).

---

## 8. 현재 세션에서 이미 준비된 것

- `label_studio/users/management/commands/seed_e2e_accounts.py` — 계정 시드 커맨드
- 이 문서 — `docs/e2e/playwright-e2e-plan.md`

Playwright 프로젝트 자체는 아직 생성되지 않았습니다. 다음 세션 시작 시 §4
파일 트리를 그대로 구현하면 됩니다.
