#!/usr/bin/env bash
# 감사 일괄 실행 — 배포 전에 이거 하나만 돌리면 된다.
#
#   1) 권한 매트릭스 (API, 브라우저 불필요) — 역할 x 엔드포인트 접근성 표
#   2) UI 스모크 (브라우저) — 역할별 화면 렌더 + 콘솔에러/실패요청 + 스크린샷
#
# 로컬 sqlite + 격리 데이터 디렉터리에서 돈다. 프로덕션/개발 DB 를 건드리지 않는다.
# 프론트가 빌드돼 있어야 UI 스모크가 앱 화면을 본다(없으면 빌드 안내).
#
# 사용:  bash scripts/audit/run_all.sh
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

DATA="${AUDIT_DATA_DIR:-/tmp/labelsea-audit-data}"
PORT="${AUDIT_PORT:-8899}"
DEVTOOLS_PORT="${AUDIT_DEVTOOLS_PORT:-9333}"
BASE="http://127.0.0.1:${PORT}"
export DJANGO_DB=sqlite
export LABEL_STUDIO_BASE_DATA_DIR="$DATA"
mkdir -p "$DATA"

echo "═══ 1. 권한 매트릭스 (API) ═══"
poetry run python scripts/audit/permission_matrix.py
echo

# ─── UI 스모크: 빌드 확인 → 서버 기동 → 시드 → 스모크 ───
BUNDLE="$ROOT/web/dist/apps/labelstudio/main.js"
if [ ! -f "$BUNDLE" ]; then
  echo "═══ 2. UI 스모크 — 건너뜀 ═══"
  echo "  프론트 번들이 없음: $BUNDLE"
  echo "  먼저 빌드:  (cd web && NODE_ENV=production npx nx run labelstudio:build:production)"
  exit 0
fi

echo "═══ 2. UI 스모크 (브라우저) ═══"
poetry run python label_studio/manage.py migrate --no-input >/dev/null 2>&1

# 서버 기동 (FRONTEND_HOSTNAME 을 자기 자신으로 — 안 그러면 번들이 localhost:8010 을 찾다 실패)
DEBUG=true FRONTEND_HOSTNAME="$BASE" \
  poetry run python label_studio/manage.py runserver "$PORT" --noreload >"$DATA/server.log" 2>&1 &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null; pkill -f "remote-debugging-port=$DEVTOOLS_PORT" 2>/dev/null' EXIT

# 서버 대기
for _ in $(seq 1 30); do
  curl -s -o /dev/null "$BASE/user/login/" && break || sleep 1
done

# 감사용 사용자 시드
poetry run python label_studio/manage.py shell < scripts/audit/_seed_users.py 2>&1 | grep -E "AUDIT SEED OK|중단" || true

BASE="$BASE" DEVTOOLS_PORT="$DEVTOOLS_PORT" poetry run python scripts/audit/ui_smoke.py
