# 감사 도구 (audit)

코드를 읽는 대신 **실제로 호출/클릭**해서 프로젝트의 상태를 표로 뽑는 검사기들.
"이럴 것이다"가 아니라 "이렇다"를 남긴다. 배포 전에 돌려 회귀를 잡는 용도.

## 한 번에 실행

```bash
bash scripts/audit/run_all.sh
```

로컬 sqlite + 격리 데이터 디렉터리(`/tmp/labelsea-audit-data`)에서 돈다. 개발/프로덕션
DB 를 건드리지 않는다. UI 스모크는 프론트 번들(`web/dist`)이 있어야 앱 화면을 본다:

```bash
(cd web && NODE_ENV=production npx nx run labelstudio:build:production)   # 최초 1회, nx 증분 캐시로 이후 빠름
```

## 도구

### permission_matrix.py — 권한 매트릭스 (API, 브라우저 불필요)

팀 앱(workspaces/reviews/compensation) 엔드포인트를 6개 역할 각각으로 **실제 호출**해서
`(엔드포인트 x 메서드 x 역할)` 상태코드 표를 낸다. `EXPECT` 에 적은 의도와 다른 칸은 `⚠`.

- OK=2xx, DENY=401/403, HIDE=404, BADREQ=400(권한통과·본문문제), ERR:=뷰가 예외를 던짐
- 새 엔드포인트 → `endpoints()` 와 (해당되면) `EXPECT` 에 한 줄 추가.

### ui_smoke.py — UI 스모크 (브라우저)

역할별로 **실제 로그인**해서 핵심 화면을 헤드리스 크롬으로 열고, 콘솔 에러/실패 네트워크
요청을 수집하고 스크린샷을 `out/<role>__<page>.png` 로 남긴다. 외부 파이썬 패키지 없이
stdlib 만으로 크롬 CDP(WebSocket)를 직접 몬다.

- `run_all.sh` 가 서버 기동·시드·`FRONTEND_HOSTNAME` 설정까지 해준다. 단독 실행하려면
  서버가 떠 있고 `_seed_users.py` 가 시드된 상태여야 한다.

### _seed_users.py — 감사용 시드 (로컬 전용, 프로덕션 가드 포함)

`sa@/wm@/an@audit.local` (비번 `Str0ngPass!23`) + 워크스페이스/프로젝트/어노테이션.

## 도구 자체를 의심할 것 (실측 사례)

- 권한 매트릭스 초판은 모든 역할이 **같은 제목**으로 워크스페이스를 만들어 unique 제약
  500 을 "권한 버그"로 오인했다. → create 본문 title 을 역할별 유니크로.
- UI 스모크 초판은 `FRONTEND_HOSTNAME` 이 `localhost:8010`(안 뜬 HMR)을 가리켜 모든
  화면에서 `ERR_CONNECTION_REFUSED` 를 냈다. 제품 버그가 아니라 실행 환경 문제. → 서버를
  `FRONTEND_HOSTNAME=자기자신` 으로 띄운다.

도구가 무언가를 잡으면 **제품 버그인지 하네스 결함인지 먼저 판별**한다. 거짓 양성은 진짜
버그를 놓치는 것만큼 위험하다.
