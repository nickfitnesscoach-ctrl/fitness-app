#!/bin/bash
# =============================================================================
# EatFit24 — PROD Smoke Test
# =============================================================================
#
# Что это:
#   Быстрая проверка продакшена после деплоя.
#   Скрипт НЕ меняет данные и НЕ делает опасных действий.
#
# Что проверяет:
#   1) Сайт открывается (HTML)
#   2) Backend жив (/health)
#   3) Публичный API работает (billing plans)
#   4) CORS настроен для Telegram WebApp
#   5) Приватный API защищён (billing/me без auth НЕ должен работать)
#
# Когда использовать:
#   - сразу после деплоя
#   - после изменений nginx / CORS / авторизации
#   - если "что-то не работает" и нужно быстро понять — это backend или фронт
#
# Как запускать:
#   ./prod_smoke_test.sh
#   ./prod_smoke_test.sh https://eatfit24.ru
#   ./prod_smoke_test.sh https://eatfit24.ru https://web.telegram.org
#
# Результат:
#   PASS  — всё критичное живо
#   FAIL  — проблема, смотреть сообщение выше
#
# =============================================================================

set -euo pipefail

BASE_URL="${1:-https://eatfit24.ru}"
ORIGIN="${2:-$BASE_URL}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

CONNECT_TIMEOUT=5
MAX_TIME=12

have_cmd() { command -v "$1" >/dev/null 2>&1; }

echo "============================================"
echo " EatFit24 Smoke Test"
echo " Target: $BASE_URL"
echo " Origin: $ORIGIN"
echo " Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================"
echo

# -----------------------------------------------------------------------------#
# Helper: HTTP request (status|headers|body)
# -----------------------------------------------------------------------------#
make_request() {
  local url="$1"
  local method="${2:-GET}"
  local extra_args="${3:-}"

  local tmp_body tmp_headers
  tmp_body="$(mktemp)"
  tmp_headers="$(mktemp)"

  # shellcheck disable=SC2086
  local http_code
  http_code=$(curl -sS -w "%{http_code}" -o "$tmp_body" -D "$tmp_headers" \
    --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" \
    -X "$method" \
    $extra_args \
    "$url" 2>/dev/null || echo "000")

  local body headers
  body="$(cat "$tmp_body")"
  headers="$(cat "$tmp_headers")"

  rm -f "$tmp_body" "$tmp_headers"

  echo "$http_code|$headers|$body"
}

fail() {
  echo -e "${RED}❌ FAIL:${NC} $1"
  exit 1
}

ok() {
  echo -e "${GREEN}✅ $1${NC}"
}

warn() {
  echo -e "${YELLOW}⚠️  $1${NC}"
}

# -----------------------------------------------------------------------------#
# 0) Front page check (optional but useful)
# -----------------------------------------------------------------------------#
echo -e "${YELLOW}[0/5] Front page...${NC}"
ROOT_RES="$(make_request "$BASE_URL/")"
ROOT_CODE="${ROOT_RES%%|*}"
ROOT_HEADERS_AND_BODY="${ROOT_RES#*|}"
ROOT_HEADERS="${ROOT_HEADERS_AND_BODY%%|*}"
ROOT_BODY="${ROOT_HEADERS_AND_BODY#*|}"

if [ "$ROOT_CODE" != "200" ]; then
  fail "Front page / returned $ROOT_CODE"
fi

if echo "$ROOT_HEADERS" | grep -qi "content-type: text/html"; then
  ok "Front page OK (200, text/html)"
else
  warn "Front page 200 but Content-Type is not text/html (check nginx/static)"
fi
echo

# -----------------------------------------------------------------------------#
# 1) Health
# -----------------------------------------------------------------------------#
echo -e "${YELLOW}[1/5] Health...${NC}"
HEALTH_RES="$(make_request "$BASE_URL/health/")"
HEALTH_CODE="${HEALTH_RES%%|*}"

if [ "$HEALTH_CODE" = "200" ]; then
  ok "Health OK (200)"
else
  fail "Health endpoint failed (status: $HEALTH_CODE)"
fi
echo

# -----------------------------------------------------------------------------#
# 2) Billing Plans (public JSON)
# -----------------------------------------------------------------------------#
echo -e "${YELLOW}[2/5] Billing Plans...${NC}"
PLANS_RES="$(make_request "$BASE_URL/api/v1/billing/plans/")"
PLANS_CODE="${PLANS_RES%%|*}"
PLANS_REST="${PLANS_RES#*|}"
PLANS_HEADERS="${PLANS_REST%%|*}"
PLANS_BODY="${PLANS_REST#*|}"

[ "$PLANS_CODE" = "200" ] || fail "Plans endpoint failed (status: $PLANS_CODE). Body: ${PLANS_BODY:0:200}"

if ! echo "$PLANS_HEADERS" | grep -qi "content-type: application/json"; then
  warn "Plans returned 200 but Content-Type is not application/json"
fi

# Validate JSON
if have_cmd jq; then
  echo "$PLANS_BODY" | jq -e . >/dev/null 2>&1 || fail "Plans returned invalid JSON"
  # Expect array
  echo "$PLANS_BODY" | jq -e 'type=="array"' >/dev/null 2>&1 || fail "Plans JSON is not an array"
  PLAN_COUNT="$(echo "$PLANS_BODY" | jq 'length')"
  ok "Plans OK (200) - array length: $PLAN_COUNT"
else
  # Fallback: basic check
  echo "$PLANS_BODY" | grep -q '^\[' || fail "Plans returned invalid JSON (not starting with [). Install jq for stronger validation."
  ok "Plans OK (200) - basic JSON check (jq not installed)"
fi
echo

# -----------------------------------------------------------------------------#
# 3) CORS preflight
# -----------------------------------------------------------------------------#
echo -e "${YELLOW}[3/5] CORS Preflight...${NC}"
CORS_RES="$(make_request "$BASE_URL/api/v1/billing/plans/" "OPTIONS" \
  "-H \"Origin: $ORIGIN\" -H \"Access-Control-Request-Method: GET\" -H \"Access-Control-Request-Headers: X-Telegram-Init-Data\"")"

CORS_CODE="${CORS_RES%%|*}"
CORS_REST="${CORS_RES#*|}"
CORS_HEADERS="${CORS_REST%%|*}"

# OPTIONS may return 200/204 depending on stack
if [ "$CORS_CODE" != "200" ] && [ "$CORS_CODE" != "204" ]; then
  fail "CORS preflight returned $CORS_CODE"
fi

echo "$CORS_HEADERS" | grep -qi "access-control-allow-origin" || fail "CORS missing Access-Control-Allow-Origin"
echo "$CORS_HEADERS" | grep -qi "access-control-allow-headers" || fail "CORS missing Access-Control-Allow-Headers"

if echo "$CORS_HEADERS" | grep -qi "x-telegram-init-data"; then
  ok "CORS OK ($CORS_CODE) - x-telegram-init-data allowed"
else
  warn "CORS OK ($CORS_CODE) but x-telegram-init-data not explicitly listed (may still work if allow-headers=*)"
fi
echo

# -----------------------------------------------------------------------------#
# 4) Auth guard check (billing/me should NOT be public)
# -----------------------------------------------------------------------------#
echo -e "${YELLOW}[4/5] Auth Guard (billing/me)...${NC}"
ME_RES="$(make_request "$BASE_URL/api/v1/billing/me/")"
ME_CODE="${ME_RES%%|*}"

if [ "$ME_CODE" = "401" ] || [ "$ME_CODE" = "403" ]; then
  ok "Auth guard OK ($ME_CODE without auth)"
elif [ "$ME_CODE" = "200" ]; then
  fail "SECURITY: billing/me returns 200 without auth (debug mode or auth bypass!)"
else
  fail "Unexpected status from billing/me: $ME_CODE"
fi
echo

# -----------------------------------------------------------------------------#
# 5) Summary
# -----------------------------------------------------------------------------#
echo -e "${YELLOW}[5/5] Summary${NC}"
echo "============================================"
echo -e "${GREEN}PASS${NC} - critical checks OK"
echo "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
echo
echo "Manual verification (recommended):"
echo "  1) Open Mini App in Telegram"
echo "  2) Ensure requests include X-Telegram-Init-Data"
echo "  3) Verify /api/v1/billing/me/ returns 200 WITH valid auth"
echo "============================================"
