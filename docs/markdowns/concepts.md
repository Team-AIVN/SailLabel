# 개념별 정보 및 소속 관계

LabelSea의 핵심 개념(모델)과 그 역할, 소속(부모)·소유(자식) 관계를 정리한 문서입니다.
멀티테넌시 계층은 **Organization → Workspace → Project → Task** 순서로 내려갑니다.

## 전체 계층 개요

```
Organization (조직)
└── Workspace (워크스페이스)
    ├── WorkspaceMember (워크스페이스 참여자)
    ├── WorkspaceFileUpload (데이터셋 파일)
    │   └── TaskSourceItem (작업 원천 항목)
    ├── TaskPool (작업집합)
    │   └── TaskPoolItem (작업집합 항목 = TaskSourceItem 연결)
    ├── PaymentRecord (지급 기록)
    └── Project (프로젝트) ─ task_pool 1개 선택
        ├── ProjectMember (프로젝트 참여자: PM/라벨러/검수자)
        ├── ProjectCompensationPolicy (보상 단가 정책, 1:1)
        └── Task (작업)
            ├── Annotation (라벨링 결과, 리비전 체인)
            └── Review (검수 기록)
```

## 개념 테이블

| 제목 | 역할 | 소속 (부모) | 소유 (자식) |
| --- | --- | --- | --- |
| **Organization** (조직) | 하나의 고객사/팀 단위. 플랫폼 최상위 테넌트로, 그 아래로 여러 워크스페이스와 프로젝트를 가집니다. | 없음 (최상위) | Workspaces, Projects, OrganizationMembers |
| **OrganizationMember** (조직 멤버십) | 사용자와 조직의 연결(소속) 관계. 소프트 삭제(`deleted_at`)로 탈퇴를 표현합니다. | - Organization (조직)<br>- User (사용자) | 없음 (연결 테이블) |
| **Workspace** (워크스페이스) | 여러 프로젝트를 하나의 작업 공간으로 묶고, 다음을 통합 관리합니다.<br>- 참여자 목록 및 권한 — WorkspaceMember로 관리<br>- 데이터셋 — 워크스페이스 단위로 업로드된 데이터 풀 (WorkspaceFileUpload)<br>- 작업집합(TaskPool) — 데이터셋 항목을 큐레이션한 작업 단위<br>- 프로젝트 진행도 대시보드 — 소속 프로젝트들의 현황 집계<br>- 비용 정산/지불 — 프로젝트별 작업량 기반 보상 산정 및 지급 기록 | - Organization (조직, 필수) | Projects, WorkspaceMembers, WorkspaceFileUploads, TaskSourceItems, TaskPools, PaymentRecords |
| **WorkspaceMember** (워크스페이스 멤버십) | 사용자와 워크스페이스의 연결 관계 + 워크스페이스 역할. 역할: `workspace_manager`(관리자) / `member`(멤버). | - Workspace (워크스페이스)<br>- User (사용자) | 없음 (연결 테이블, 역할 정보 보유) |
| **WorkspaceFileUpload** (데이터셋) | 워크스페이스 단위로 업로드된 원본 파일. 워크스페이스의 기본 데이터 풀이며, 업로드 시 파싱되어 작업 원천 항목(TaskSourceItem)으로 전개됩니다. JSON/CSV는 여러 항목으로, 미디어 파일 1개는 항목 1개로 변환됩니다. | - Workspace (워크스페이스)<br>- User (업로더) | TaskSourceItems |
| **TaskSourceItem** (작업 원천 항목) | 데이터셋에서 파싱된 개별 데이터 항목. 작업집합(TaskPool)에 담을 수 있는 최소 선택 단위입니다. 이미지+CSV 페어는 하나의 `pair` 항목으로 병합됩니다. | - WorkspaceFileUpload (원본 데이터셋)<br>- Workspace (조회용 비정규화) | TaskPoolItems |
| **TaskPool** (작업집합) | 작업 원천 항목들을 큐레이션한 작업 세트. 프로젝트는 원본 데이터셋 대신 작업집합 하나를 선택하며, 원본 데이터 접근 권한은 워크스페이스 관리자에게만 남습니다. | - Workspace (워크스페이스) | TaskPoolItems, Projects (같은 작업집합을 여러 프로젝트가 선택 가능) |
| **TaskPoolItem** (작업집합 항목) | 작업 원천 항목이 특정 작업집합에 담겨 있음을 나타내는 연결 관계. (task_pool, task_source_item) 조합은 유일합니다. | - TaskPool (작업집합)<br>- TaskSourceItem (원천 항목) | 없음 (연결 테이블) |
| **Project** (프로젝트) | 하나의 작업집합에 대한 라벨링 작업 단위. 라벨링 인터페이스(label config), 검수 전략(`review_strategy`: 없음/랜덤 샘플링/전수 검수/커스텀, `review_ratio`), 마감일·태그, 참여자(라벨러/검수자/PM), 보상 단가 정책을 가집니다. 생성 시 선택한 작업집합의 항목들이 Task로 구체화(materialize)됩니다. | - Workspace (워크스페이스)<br>- Organization (조직)<br>- TaskPool (선택한 작업집합 1개) | Tasks, ProjectMembers, ProjectCompensationPolicy (1:1), PaymentRecords |
| **ProjectMember** (프로젝트 멤버십) | 사용자와 프로젝트의 연결 관계 + 프로젝트 역할. 역할: `project_manager`(프로젝트 관리자) / `annotator`(라벨러) / `reviewer`(검수자). 소프트 삭제로 해제를 표현합니다. | - Project (프로젝트)<br>- User (사용자) | 없음 (연결 테이블, 역할 정보 보유) |
| **Task** (작업) | 라벨링 대상이 되는 개별 작업 단위. 작업집합 항목에서 구체화된 데이터(`data`)를 담으며, 검수 상태(`review_status`: 미선정/검수 대기/승인/반려/수정 후 승인)와 최신 활성 리비전 포인터(`current_annotation`)를 가집니다. | - Project (프로젝트) | Annotations, Predictions |
| **Annotation** (라벨링 결과) | 라벨러가 제출한 라벨링 결과. 리비전 모델로, 반려 후 재작업 시 `version`이 증가하며 `parent_annotation`으로 이전 리비전과 체인을 이룹니다. 작성자(`completed_by`)와 상태(status)를 가지며, 제출된 리비전이 검수 대상이 됩니다. | - Task (작업)<br>- Project (조회용 비정규화)<br>- User (`completed_by` 작성자) | Reviews, Annotations (후속 리비전) |
| **Review** (검수 기록) | 검수자가 특정 라벨링 리비전에 내린 결정. 결정: `ACCEPT`(승인) / `REJECT`(반려) / `FIX_AND_ACCEPT`(수정 후 승인) + 코멘트. Task가 아닌 Annotation 리비전에 연결되어 라벨링·검수 이력 전체가 추적됩니다. `stage` 필드는 다단계 검수 확장용입니다. | - Annotation (검수 대상 리비전)<br>- Project (조회용 비정규화)<br>- User (`reviewer` 검수자) | 없음 (이력 레코드) |
| **ProjectCompensationPolicy** (보상 단가 정책) | 프로젝트별 단가 설정: 통화(`currency`), 라벨링 건당 단가(`annotation_unit_price`), 검수 건당 단가(`review_unit_price`). **보상액은 저장되지 않고** 이 단가 × 검수/라벨링 이력에서 산출한 인정 건수로 조회 시점에 계산됩니다. | - Project (프로젝트, 1:1) | 없음 (단가 입력값만 보유) |
| **PaymentRecord** (지급 기록) | 작업자에게 지급한 금액의 수기 장부 기록(실제 송금 없음). 정산 단위는 **프로젝트별**: (프로젝트, 사용자, 통화) 기준으로 지급 합계와 산출된 보상액을 비교해 잔액·정산 상태를 도출합니다. | - Workspace (기록 소속 워크스페이스)<br>- Project (정산 대상 프로젝트)<br>- User (지급 대상 작업자) | 없음 (이력 레코드) |
| **User** (사용자) | 플랫폼 사용자. 멤버십 테이블을 통해 각 계층에 소속되며, 계층별로 서로 다른 역할을 가질 수 있습니다 (예: A 프로젝트의 라벨러이면서 B 프로젝트의 검수자). | - OrganizationMember → 조직 소속<br>- WorkspaceMember → 워크스페이스 소속 (관리자/멤버)<br>- ProjectMember → 프로젝트 소속 (PM/라벨러/검수자) | Annotations, Reviews, PaymentRecords, WorkspaceFileUploads |

## 참고

- **연결 테이블(멤버십)**: OrganizationMember, WorkspaceMember, ProjectMember는 사용자↔컨테이너의 N:M 관계를 표현하며, 역할과 소프트 삭제 정보를 함께 보유합니다. 역할별 접근 범위는 [permissions.md](./permissions.md)와 [permissions-by-url.md](./permissions-by-url.md)를 참고하세요.
- **비정규화 FK**: Annotation.project, Review.project, TaskSourceItem.workspace는 조회 성능을 위한 중복 참조이며, 논리적 부모는 각각 Task, Annotation, WorkspaceFileUpload입니다.
- **보상 산출 원칙**: 보상액(earnings)은 어디에도 저장되지 않습니다. ProjectCompensationPolicy(단가) + Annotation/Review 이력(인정 건수)에서 조회할 때마다 재계산되어 항상 재현 가능합니다. PaymentRecord만이 저장되는 정산 데이터입니다.
- **DB 테이블명**: 용어 변경(DatasetItem→TaskSourceItem, WorkPool→TaskPool) 시 기존 데이터 보호를 위해 DB 테이블명은 레거시(`dataset_item`, `work_pool`, `work_pool_item`)로 유지되었습니다. 코드·API·UI는 모두 새 용어를 사용합니다.
