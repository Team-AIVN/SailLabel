---
name: E2E Playwright plan location
description: Where the SailLabel Phase 1-8 Playwright E2E plan lives, how auth is bootstrapped (Keycloak-only UI → DB session minting), and the 6 role accounts.
type: project
---

Playwright harness lives at `web/apps/labelstudio-e2e-playwright/` and is operational — `pnpm test` runs 30 specs across 6 parallel workers, all role fixtures pre-authenticated.

**Why:** Phase 1-8 백엔드 기능(Workspace, RBAC 5역할, 리뷰 워크플로우, 배치 리뷰, 대시보드, 정산, 관측성)을 브라우저 경로로 재검증해 role-scoped UI/API 회귀를 잡으려는 목적. SailLabel의 로그인 UI가 Keycloak-only로 바뀐 뒤 기존 `/user/login/` form-POST 전략이 더 이상 동작하지 않아 세션 mint 방식으로 전환했다.

**How to apply:** 다음 세션에서 E2E 관련 작업을 할 때
1. 플랜 문서: `docs/e2e/playwright-e2e-plan.md`
2. 계정 시드: `poetry run python label_studio/manage.py seed_e2e_accounts` (비밀번호 `E2ETestPass!`)
3. 세션 mint: `poetry run python label_studio/manage.py e2e_mint_sessions --out-dir web/apps/labelstudio-e2e-playwright/.auth` — `globalSetup`이 자동 호출한다. Keycloak SSO 우회를 위해 DB-backed `SessionStore`에 `_auth_user_id/_auth_user_backend/_auth_user_hash/last_login`를 직접 쓰고 `sessionid`+`csrftoken` 쿠키를 Playwright `storageState` JSON으로 내보낸다. `last_login`이 없으면 `InactivitySessionTimeoutMiddleWare`가 세션을 즉시 flush하니 반드시 찍어야 한다.
4. 실행: `cd web/apps/labelstudio-e2e-playwright && pnpm test` — 이 한 줄이 install→globalSetup→6-worker 병렬 실행까지 커버한다.
5. 테스트 계정 6개 (`@e2e.saillabel.local`): superadmin/wsmanager/pmanager/reviewer/annotator/plainmember. fixture 이름은 각각 `superAdminApi`, `workspaceManagerApi`, `projectManagerApi`, `reviewerApi`, `annotatorApi`, `plainMemberApi` (및 `*Page`, `*Request`). Playwright는 fixture 이름을 **정적 source text**로 파싱하므로 `${role}Api` 같은 템플릿 키는 절대 쓰지 말 것 — `auth.ts`/스펙에서 6개 역할을 명시적으로 나열해야 한다.
6. 조직/워크스페이스/프로젝트 fixture: `E2E Organization` / `E2E Workspace` / `E2E Project Alpha`+`Beta`.
