# URL 별 역할 접근 권한 (Permissions by URL)

이 문서는 [`permissions.md`](permissions.md)의 역할 정의를 기준으로, LabelSea가 제공하는 **모든 사용자 대상 페이지 URL**에 대해 역할별 접근 허용 여부를 정리한 것입니다.

## 역할 (Roles)

| 약어 | 역할 | 요약 |
| --- | --- | --- |
| **SA** | 전체 시스템 관리자 (Super Admin) | 플랫폼 전체 제어. 모든 URL 허용. |
| **WM** | 워크스페이스 관리자 (Workspace Manager) | 내 소속 워크스페이스의 **모든 기능**. |
| **PM** | 프로젝트 관리자 (Project Manager) | 내 소속 워크스페이스는 **조회만**(내 프로젝트·작업집합·멤버·보상), 내 소속 **프로젝트는 모든 기능**. |
| **LB** | 작업자: 라벨러 (Labeler) | 내 소속 프로젝트의 **라벨링 작업**. |
| **RV** | 작업자: 검수자 (Reviewer) | 내 소속 프로젝트의 **검수 작업**. |
| **PMb** | 프로젝트 멤버 / 작업 미할당 | 내 소속 프로젝트의 **작업 목록 조회만**. |
| **WMb** | 워크스페이스 멤버 | 내 소속 워크스페이스 메인 페이지의 **제목·설명 조회만**. |

## 범례 (Legend)

- **✅ 허용** — 해당 기능/페이지 접근 및 조작 허용
- **👁 조회만** — 페이지 접근은 가능하나 조회(읽기)만 가능, 관리·수정 불가
- **❌ 금지** — 접근 불가

> **범위(Scope) 주의:** 모든 ✅/👁은 **"내 소속" 범위**로 한정됩니다. 즉 자신이 속한 워크스페이스·프로젝트에 대해서만 허용되며, 소속되지 않은 워크스페이스/프로젝트는 SA를 제외하고 모두 ❌ 입니다.

---

## 1. 인증 · 내 계정 (모든 사용자)

| URL | 페이지 제목 | SA | WM | PM | LB | RV | PMb | WMb |
| --- | --- | :-: | :-: | :-: | :-: | :-: | :-: | :-: |
| `/user/login/` | 로그인 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `/user/signup/` | 회원가입 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `/logout/` | 로그아웃 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `/user/account/` | 내 계정 설정 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `/user/account/:sectionId` | 계정 설정 섹션 (프로필·비밀번호·API 토큰·단축키 등) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

*로그인/회원가입은 비인증 공개 페이지, 나머지는 본인 계정에 한해 모든 인증 사용자에게 허용됩니다.*

## 2. 홈

| URL | 페이지 제목 | SA | WM | PM | LB | RV | PMb | WMb |
| --- | --- | :-: | :-: | :-: | :-: | :-: | :-: | :-: |
| `/` | 홈 (대시보드) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

*모든 인증 사용자에게 노출되며, 표시되는 항목은 각자의 접근 범위로 필터링됩니다.*

## 3. 프로젝트

| URL | 페이지 제목 | SA | WM | PM | LB | RV | PMb | WMb |
| --- | --- | :-: | :-: | :-: | :-: | :-: | :-: | :-: |
| `/projects` | 프로젝트 목록 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| `/projects/:id` | 프로젝트 (→ `/data` 리다이렉트) | ✅ | ✅ | ✅ | ✅ | ✅ | 👁 | ❌ |
| `/projects/:id/data` | 데이터 매니저 (작업 목록 / 라벨링 진입) | ✅ | ✅ | ✅ | ✅ | ✅ | 👁 | ❌ |
| `/projects/:id/data/export` | 데이터 내보내기 (Export) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `/projects/:id/review` | 검수 (Review) | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |

*프로젝트 목록은 각 역할이 접근 가능한 프로젝트만 표시됩니다. `/data`에서 라벨러는 라벨링, 검수자는 검수, 미할당 멤버는 목록 조회만 가능합니다.*

## 4. 프로젝트 설정 (관리 기능)

프로젝트 설정은 **관리 기능**이므로 작업자(LB/RV/PMb)와 워크스페이스 멤버(WMb)는 모두 ❌ 입니다.

| URL | 페이지 제목 | SA | WM | PM | LB | RV | PMb | WMb |
| --- | --- | :-: | :-: | :-: | :-: | :-: | :-: | :-: |
| `/projects/:id/settings` | 프로젝트 설정 (일반 / General) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `/projects/:id/settings/annotation` | 어노테이션(작업) 설정 | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `/projects/:id/settings/labeling` | 라벨링 인터페이스 설정 | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `/projects/:id/settings/workers` | 작업자 할당 (라벨러 / 검수자) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `/projects/:id/settings/ml` | 머신러닝 모델 설정 | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `/projects/:id/settings/predictions` | 예측(Predictions) 설정 | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `/projects/:id/settings/storage` | 클라우드 스토리지 설정 | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `/projects/:id/settings/webhooks` | 웹훅(Webhooks) 설정 | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `/projects/:id/settings/danger-zone` | 위험 구역 (프로젝트 삭제) | ✅ | ✅ | ⚠️ | ❌ | ❌ | ❌ | ❌ |

- ⚠️ **위험 구역(프로젝트 삭제):** 프로젝트 생성·삭제는 워크스페이스 관리자(WM)/슈퍼관리자(SA)의 권한입니다. PM은 설정 조회·수정은 가능하나 삭제는 제한될 수 있습니다.
- **데이터셋 업로드는 워크스페이스 수준**에서만 이루어집니다(프로젝트에는 작업집합으로 할당). 프로젝트 설정의 스토리지는 연결 설정 용도입니다.

## 5. 워크스페이스

| URL | 페이지 제목 | SA | WM | PM | LB | RV | PMb | WMb |
| --- | --- | :-: | :-: | :-: | :-: | :-: | :-: | :-: |
| `/workspaces` | 워크스페이스 목록 | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |
| `/workspaces/:id` | 워크스페이스 상세 (기본: 프로젝트 탭) | ✅ | ✅ | 👁 | ❌ | ❌ | ❌ | 👁 |
| `/workspaces/:id?tab=projects` | └ 프로젝트 탭 | ✅ | ✅ | 👁 | ❌ | ❌ | ❌ | ❌ |
| `/workspaces/:id?tab=datasets` | └ 데이터셋 탭 | ✅ | ✅ | 👁 | ❌ | ❌ | ❌ | ❌ |
| `/workspaces/:id?tab=taskpools` | └ 작업집합 탭 | ✅ | ✅ | 👁 | ❌ | ❌ | ❌ | ❌ |
| `/workspaces/:id?tab=users` | └ 멤버 탭 | ✅ | ✅ | 👁 | ❌ | ❌ | ❌ | ❌ |
| `/workspaces/:id?tab=compensation` | └ 보상 탭 | ✅ | ✅ | 👁 | ❌ | ❌ | ❌ | ❌ |

- **WM:** 내 소속 워크스페이스의 프로젝트·데이터셋·작업집합·멤버·보상 **모든 기능**(생성·수정·삭제·업로드·정산 등).
- **PM(👁):** 워크스페이스 상세는 **조회만** 가능하며, 자신이 속한 프로젝트·작업집합·멤버·보상만 보입니다. 특히 **보상 탭은 자신이 관리하는 프로젝트만** 조회/정산 가능합니다(다른 프로젝트는 목록에도 표시되지 않음).
- **WMb(👁):** `/workspaces/:id` 접근 시 **워크스페이스 제목·설명(헤더)만** 볼 수 있으며, 프로젝트/데이터셋/작업집합/멤버/보상 **탭 내용은 ❌** 입니다.

## 6. 조직 · 시스템 관리 (Super Admin)

| URL | 페이지 제목 | SA | WM | PM | LB | RV | PMb | WMb |
| --- | --- | :-: | :-: | :-: | :-: | :-: | :-: | :-: |
| `/organization` · `/organization/` | 조직 구성원 (People) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `/organization/webhooks` | 조직 웹훅 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `/models` | 프롬프트 / 모델 관리 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

*조직 수준의 사용자 계정 관리는 Super Admin의 고유 권한입니다. 워크스페이스 관리자는 멤버 관리를 워크스페이스 상세의 `?tab=users`에서 수행합니다. `/models`는 기능 플래그에 따라 노출됩니다.*

---

## 역할별 접근 허용 URL 목록

### 전체 시스템 관리자 (SA)
- **모든 URL 허용** — 위 표의 전체 항목 + 아래 시스템/인프라(`/admin/` 등) 포함.

### 워크스페이스 관리자 (WM)
- `/`, `/user/account/*`, `/logout/`
- `/projects`, `/projects/:id`, `/projects/:id/data`, `/projects/:id/data/export`, `/projects/:id/review`
- `/projects/:id/settings` 및 모든 `/settings/*` 하위 페이지
- `/workspaces`, `/workspaces/:id` 및 모든 탭(`projects` · `datasets` · `taskpools` · `users` · `compensation`)
- *(범위: 내 소속 워크스페이스 및 그 안의 프로젝트)*

### 프로젝트 관리자 (PM)
- `/`, `/user/account/*`, `/logout/`
- `/projects`, `/projects/:id`, `/projects/:id/data`, `/projects/:id/data/export`, `/projects/:id/review`
- `/projects/:id/settings` 및 모든 `/settings/*` 하위 페이지 *(위험 구역의 프로젝트 삭제는 제한)*
- `/workspaces`, `/workspaces/:id` 및 모든 탭 — **조회만(👁)**, 보상 탭은 **내가 관리하는 프로젝트만**
- *(범위: 내 소속 프로젝트는 모든 기능, 워크스페이스는 조회만)*

### 라벨러 (LB)
- `/`, `/user/account/*`, `/logout/`
- `/projects` *(내가 할당된 프로젝트만)*
- `/projects/:id`, `/projects/:id/data` *(라벨링 작업)*
- *(그 외 검수·설정·내보내기·워크스페이스 관리 페이지는 모두 ❌)*

### 검수자 (RV)
- `/`, `/user/account/*`, `/logout/`
- `/projects` *(내가 할당된 프로젝트만)*
- `/projects/:id`, `/projects/:id/data`
- `/projects/:id/review` *(검수 작업 — 승인/반려/수정)*
- *(그 외 설정·내보내기·워크스페이스 관리 페이지는 모두 ❌)*

### 프로젝트 멤버 / 작업 미할당 (PMb)
- `/`, `/user/account/*`, `/logout/`
- `/projects` *(내가 속한 프로젝트만)*
- `/projects/:id`, `/projects/:id/data` — **작업 목록 조회만(👁)**
- *(라벨링·검수·설정·내보내기 등 모든 작업/관리 기능 ❌)*

### 워크스페이스 멤버 (WMb)
- `/`, `/user/account/*`, `/logout/`
- `/workspaces`, `/workspaces/:id` — **워크스페이스 제목·설명(헤더)만 조회(👁)**
- *(탭 내용, 프로젝트, 모든 작업/관리 기능 ❌)*

---

## 참고: 시스템 / 인프라 URL (제품 페이지 아님)

아래 URL은 역할 기반 제품 화면이 아니라 시스템/인프라 엔드포인트입니다.

| URL | 용도 | 접근 |
| --- | --- | --- |
| `/admin/` | Django 관리자 | Super Admin(django superuser)만 |
| `/api/**` | REST API | 각 API가 대응하는 페이지와 **동일한 역할 규칙** 적용 (백엔드 권한으로 강제) |
| `/docs/api/`, `/docs/api/swagger/` | API 문서 (ReDoc / Swagger) | 인증 사용자 |
| `/version/` | 플랫폼 버전 정보 | 인증 사용자 |
| `/health/`, `/metrics/` | 헬스 체크 / 메트릭 | 인프라 |
| `/feature-flags/` | 기능 플래그 설정 | 시스템 |
| `/static/**` | 정적 파일 | 공개 |
| `/oidc/**`, `/logout/` | Keycloak OIDC 인증 (활성화 시) | 인증 흐름 |

> **주의:** 위 매트릭스는 UI 라우트(페이지) 노출 기준입니다. 실제 데이터 접근 제어는 백엔드 API 권한(각 워크스페이스/프로젝트 멤버십 및 역할 검사)으로 강제되며, URL을 직접 호출해도 범위 밖 리소스는 서버에서 차단됩니다.
