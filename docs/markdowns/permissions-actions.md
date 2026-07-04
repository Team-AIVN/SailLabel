# 권한: 액션(행동) 단위 범위 및 미정·애매 항목

## 이 문서의 목적

기존 권한 문서는 **"어떤 역할이 어떤 페이지를 볼 수 있나"**(접근/조회 매트릭스)에 집중돼 있습니다:

- [`permissions.md`](./permissions.md) — 역할 정의
- [`permissions-by-url.md`](./permissions-by-url.md) — URL별 접근(view) 매트릭스

하지만 **"그 역할이 실제로 무엇을 생성/수정/삭제할 수 있나"**(액션 단위)는 문서에 부분적으로만 정의돼 있고, 일부는 코드에서 명세와 다르게 동작하거나 아예 제한이 없습니다. 이 문서는 그 **액션 단위 권한의 현재 코드 상태 + 명세와의 차이 + 확정이 필요한 항목**을 모아둔 것입니다. (확정되면 각 항목을 `permissions.md`/코드에 반영)

> **참고 코드**: 역할 판별 `label_studio/users/rules.py`, 역할 해석 `label_studio/users/roles.py`, 권한 바인딩 `label_studio/*/rules.py`(`make_perm`), 강제 지점 각 앱 `api.py`의 `permission_required`.

## 범례

- **코드 강제**: ✅ 역할로 막힘 · ⚠️ 안 막힘(구멍) · 🔒 백엔드는 막지만 프론트 버튼/화면은 아직 안 막음
- **명세**: ✅ 명확 · ❓ 미정/애매/모순

---

## 1. 액션 단위 권한 현황

| 액션 | 명세상 허용(권장) | 현재 코드 강제 | 코드 | 명세 |
| --- | --- | --- | :--: | :--: |
| **프로젝트 생성** | WM / SA (추정) | `projects.create` = **is_authenticated (누구나)** — 라이브 테스트로 라벨러 생성 확인됨 | ⚠️ | ❓ |
| 프로젝트 설정 수정 | PM / WM / SA | `projects.change` = PM ∪ WM ∪ SA | ✅🔒 | ✅ |
| 프로젝트 삭제 | WM / SA (PM은 제한?) | `projects.delete` = PM ∪ WM ∪ SA → **PM도 삭제 가능** | ✅🔒 | ❓ |
| 프로젝트 멤버 초대/역할변경 | PM / WM / SA | `ProjectMembersAPI` POST=`projects.change` + 명시적 `is_super_admin ∨ is_project_manager_of` | ✅🔒 | ✅ |
| 데이터 내보내기(Export) | PM / WM / SA | `data_export` = `projects.change` (LB/RV ❌) | ✅🔒 | ✅ |
| **워크스페이스 생성** | SA? WM? (명세 없음) | `workspaces.create` = **is_authenticated (누구나)** | ⚠️ | ❓ |
| 워크스페이스 수정/삭제 | WM / SA | `workspaces.change`/`delete` = WM(=is_workspace_manager) | ✅🔒 | ✅ |
| 워크스페이스 멤버 초대 | WM / SA | `workspaces.invite` = WM | ✅🔒 | ✅ |
| 데이터셋 업로드 | WM (PM은? — 명세 모순) | `workspaces.change` = WM + 명시적 `is_workspace_manager` (PM ❌) | ✅🔒 | ❓ |
| 작업집합(TaskPool) 생성/수정/삭제 | WM | `workspaces.change` = WM | ✅🔒 | ✅ |
| 검수 결정(승인/반려/수정) | RV / PM / WM / SA (본인 작업물 제외) | `reviewer ∨ PM` + self-review 금지 가드 | ✅🔒 | ✅ |
| 보상 단가 정책 설정 | ? (명세 불명확) | `ProjectCompensationPolicy` PUT=`projects.change` (PM/WM/SA) | ✅🔒 | ❓ |
| 지급 기록(PaymentRecord) 생성 | WM / PM (정산 담당) | POST=`workspaces.view` → **워크스페이스 멤버 누구나** | ⚠️ | ❓ |

> 🔒 표시가 있는 항목은 **백엔드는 역할로 막지만, 프론트엔드에서 해당 버튼/페이지를 아직 숨기거나 차단하지 않았습니다** (Phase 2 프론트 게이팅 미완). 즉 지금은 권한 없는 사용자에게도 버튼이 보이고, 눌러야 403이 납니다.

---

## 2. 확정이 필요한 미정·애매 항목 (Open Questions)

### 2.1 프로젝트 생성 주체 ⚠️ (실제 구멍)
- **현재**: 로그인한 누구나 생성 가능 (`projects.create` = is_authenticated). 라벨러 계정으로 실제 생성됨을 확인.
- **명세**: 명확하지 않음. `permissions.md`상 "워크스페이스 관리자 = 워크스페이스 내 프로젝트 생성/수정/삭제". PM·라벨러의 생성 가부는 미기재.
- **결정 필요**: 생성은 **WM/SA만**? PM도 허용? → 정한 뒤 `projects.create`를 역할 predicate로 오버라이드.

### 2.2 워크스페이스 생성 주체 ⚠️ (실제 구멍)
- **현재**: 누구나 생성 가능 (`workspaces.create` = is_authenticated).
- **명세**: 워크스페이스 "생성" 주체가 문서에 없음. (닭-달걀 문제: WM이 되려면 누군가 워크스페이스를 만들고 WM을 배정해야 함 → 최초 생성은 SA만?)
- **결정 필요**: 워크스페이스 생성은 **SA 전용**? 생성 시 생성자를 자동으로 그 워크스페이스의 WM으로 배정?

### 2.3 프로젝트 삭제와 PM ❓ (명세 모순)
- **현재**: PM도 삭제 가능 (`projects.delete` = PM∪WM∪SA).
- **명세**: `permissions-by-url.md` 위험구역 행에 "PM은 설정 조회·수정은 가능하나 **삭제는 제한될 수 있음(⚠️)**".
- **결정 필요**: PM의 프로젝트 삭제를 **막을지**. 막는다면 `projects.delete`를 WM/SA로 좁힘.

### 2.4 PM의 데이터셋 업로드 권한 ❓ (명세 모순)
- **명세 모순**: `permissions.md`상 PM 주요권한에 "**데이터셋 업로드** 및 라벨링 인터페이스 설정"이 있으나, 데이터셋은 **워크스페이스 레벨**이고 PM은 워크스페이스에 대해 **조회만(👁)**.
- **현재**: 데이터셋 업로드 = WM 전용 (PM ❌) → PM의 명시된 주요권한과 어긋남.
- **결정 필요**: 데이터셋 업로드를 PM에게도 허용? 아니면 명세의 PM 설명에서 "데이터셋 업로드"를 뺄지.

### 2.5 지급 기록 생성 권한 ⚠️
- **현재**: `PaymentRecord` 생성 POST=`workspaces.view` → 워크스페이스 멤버(WMb 포함) 누구나 지급 기록 생성 가능.
- **명세**: 정산/지급은 WM(및 자기 프로젝트 한정 PM)의 업무.
- **결정 필요**: 생성 권한을 WM(+PM 자기 프로젝트)로 좁힐지.

### 2.6 보상 단가 정책 설정 주체 ❓
- **현재**: `projects.change`(PM/WM/SA)가 단가를 설정.
- **명세**: 단가를 누가 정하는지 명확치 않음(정산은 PM 업무로 서술되나 단가 결정 주체는 미기재).
- **결정 필요**: 단가 설정을 PM에게 허용? WM/SA만?

### 2.7 "프로젝트 멤버 / 작업 미할당"(PMb) 데이터 모델 부재 ❓
- **현재**: `ProjectMember.role`은 `project_manager`/`annotator`/`reviewer` 3종뿐이라 **"역할 없이 프로젝트에만 속한 멤버"**를 표현할 수 없음. → 스펙의 PMb(작업 목록 조회만) 상태를 만들 수 없음.
- **결정 필요**: PMb를 실제로 지원할지. 지원한다면 `role`에 `member`(무작업) 추가 등 모델 확장 필요.

### 2.8 프로젝트 생성자의 역할 ❓
- **현재**: 프로젝트를 만든 사람이 자동으로 그 프로젝트의 PM/멤버가 되지 않음 → 생성자의 `current_user_role`이 `null`로 나옴(자기 프로젝트에 대한 역할 없음).
- **결정 필요**: 생성 시 생성자를 자동으로 PM(또는 소속 워크스페이스 WM)으로 배정할지.

### 2.9 SA(Super Admin)의 범위 ❓
- **임시 결정됨**: SA = 조직 소유자(`organization.created_by`). ([users/rules.py](../../label_studio/users/rules.py) `is_super_admin`)
- **결정 필요(재확인)**: 조직 소유자를 SA로 볼지 / 명시적 `super_admin` 역할만 / Django superuser만. 또한 SA 권한이 **자기 조직 내부 전권**인지 **플랫폼 전체**인지(멀티 조직 시).

---

## 3. 이미 내린 임시 결정 (되돌리기 쉬움)

| 항목 | 결정 | 위치 |
| --- | --- | --- |
| SA 정의 | 조직 소유자(`organization.created_by`)를 SA로 인정 | `users/rules.py` `is_super_admin` |

---

## 4. 요약: 우선 처리 후보

- **🔴 실제 구멍(백엔드 미제한)**: 프로젝트 생성(2.1), 워크스페이스 생성(2.2), 지급 기록 생성(2.5)
- **🟡 명세 모순/미정**: 프로젝트 삭제·PM(2.3), PM 데이터셋 업로드(2.4), 단가 설정 주체(2.6), PMb 모델(2.7), 생성자 역할(2.8), SA 범위(2.9)
- **🟢 프론트 게이팅 미완(백엔드는 막힘)**: 표의 🔒 항목 전부 — Phase 2(2d 라우트 가드 / 2e 버튼 게이팅)에서 처리
