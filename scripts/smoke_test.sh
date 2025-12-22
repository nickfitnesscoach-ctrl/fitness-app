#!/bin/bash
# =============================================================================
# EatFit24 PROD Smoke Test Script
# =============================================================================
# Usage: ./smoke_test.sh [BASE_URL]
# Default: https://eatfit24.ru
#
# This script checks critical endpoints and env vars to verify PROD is healthy.
# =============================================================================

set -e

BASE_URL="${1:-https://eatfit24.ru}"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "============================================"
echo " EatFit24 PROD Smoke Test"
echo " Target: $BASE_URL"
echo "============================================"
echo

# -----------------------------------------------------------------------------
# 1. Health Check
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[1/5] Health Check...${NC}"
HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/health/" 2>/dev/null || echo "000")

if [ "$HEALTH_STATUS" = "200" ]; then
    echo -e "${GREEN}✅ Health OK (200)${NC}"
else
    echo -e "${RED}❌ Health FAILED (status: $HEALTH_STATUS)${NC}"
    echo "   Possible issues: backend not running, nginx misconfigured"
    exit 1
fi
echo

# -----------------------------------------------------------------------------
# 2. Billing Plans (Public Endpoint)
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[2/5] Billing Plans...${NC}"
PLANS_RESPONSE=$(curl -s "$BASE_URL/api/v1/billing/plans/" 2>/dev/null || echo "error")
PLANS_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/billing/plans/" 2>/dev/null || echo "000")

if [ "$PLANS_STATUS" = "200" ]; then
    # Check if response contains "code" (plans exist)
    if echo "$PLANS_RESPONSE" | grep -q '"code"'; then
        PLAN_COUNT=$(echo "$PLANS_RESPONSE" | grep -o '"code"' | wc -l)
        echo -e "${GREEN}✅ Plans OK (200) - Found $PLAN_COUNT plan(s)${NC}"
    else
        echo -e "${YELLOW}⚠️ Plans 200 but empty - check DB has active plans${NC}"
    fi
else
    echo -e "${RED}❌ Plans FAILED (status: $PLANS_STATUS)${NC}"
    echo "   Response: ${PLANS_RESPONSE:0:200}"
    exit 1
fi
echo

# -----------------------------------------------------------------------------
# 3. CORS Headers Check
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[3/5] CORS Headers...${NC}"
CORS_HEADERS=$(curl -s -I -X OPTIONS "$BASE_URL/api/v1/billing/plans/" \
    -H "Origin: https://eatfit24.ru" \
    -H "Access-Control-Request-Method: GET" \
    -H "Access-Control-Request-Headers: X-Telegram-Init-Data" 2>/dev/null || echo "error")

if echo "$CORS_HEADERS" | grep -qi "access-control-allow-origin"; then
    echo -e "${GREEN}✅ CORS headers present${NC}"
    # Check for initData header specifically
    if echo "$CORS_HEADERS" | grep -qi "x-telegram-init-data"; then
        echo -e "${GREEN}   x-telegram-init-data allowed ✓${NC}"
    else
        echo -e "${YELLOW}   ⚠️ x-telegram-init-data not explicitly listed (may still work)${NC}"
    fi
else
    echo -e "${RED}❌ CORS headers missing${NC}"
    echo "   Check CORS_ALLOWED_ORIGINS in backend settings"
fi
echo

# -----------------------------------------------------------------------------
# 4. Billing Me (Auth Required - should return 401/403 without auth)
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[4/5] Billing Me (auth check)...${NC}"
ME_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/billing/me/" 2>/dev/null || echo "000")

if [ "$ME_STATUS" = "401" ] || [ "$ME_STATUS" = "403" ]; then
    echo -e "${GREEN}✅ Auth check OK (returns $ME_STATUS without auth)${NC}"
elif [ "$ME_STATUS" = "200" ]; then
    echo -e "${YELLOW}⚠️ Returns 200 without auth - auth bypass may be enabled${NC}"
else
    echo -e "${RED}❌ Unexpected status: $ME_STATUS${NC}"
fi
echo

# -----------------------------------------------------------------------------
# 5. Additional Info
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[5/5] Summary...${NC}"
echo "============================================"
echo -e "${GREEN}✓ Core endpoints responding${NC}"
echo ""
echo "Next steps for full verification:"
echo "  1. Open Mini App in Telegram"
echo "  2. Check Network tab for X-Telegram-Init-Data header"
echo "  3. Verify /api/v1/billing/me/ returns 200 with auth"
echo ""
echo "If auth still fails, check backend logs:"
echo "  docker compose logs --tail=50 backend | grep TelegramAuth"
echo "============================================"
