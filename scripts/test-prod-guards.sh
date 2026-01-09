#!/usr/bin/env bash
#
# scripts/test-prod-guards.sh
#
# Тестирует PROD guards (fail-fast проверки).
# Проверяет, что backend НЕ стартует с неправильными настройками.
#
# Usage:
#   ./scripts/test-prod-guards.sh
#

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "========================================="
echo "PROD Guards Fail-Fast Test"
echo "========================================="
echo ""
echo "This script tests that PROD guards reject invalid configurations."
echo "Each test should FAIL to start the backend container."
echo ""

# Save original .env
if [ -f .env ]; then
    cp .env .env.backup
    echo "✓ Backed up .env to .env.backup"
fi

# Cleanup function
cleanup() {
    echo ""
    echo "Cleaning up..."
    docker compose -p test_prod_guards down -v 2>/dev/null || true
    if [ -f .env.backup ]; then
        mv .env.backup .env
        echo "✓ Restored original .env"
    fi
}

trap cleanup EXIT

# ==============================================================================
# Helper function to test guard
# ==============================================================================
test_guard() {
    local test_name="$1"
    local env_overrides="$2"
    local expected_error="$3"

    echo ""
    echo "-------------------------------------------"
    echo "Test: $test_name"
    echo "-------------------------------------------"
    echo "Environment overrides: $env_overrides"
    echo ""

    # Create temporary .env with overrides
    cat > .env.test <<EOF
DJANGO_SETTINGS_MODULE=config.settings.production
SECRET_KEY=test-secret-key-for-guards-test
ALLOWED_HOSTS=localhost
POSTGRES_DB=eatfit24_test
POSTGRES_USER=eatfit24_test
POSTGRES_PASSWORD=test_password
REDIS_URL=redis://redis:6379/3
CELERY_BROKER_URL=redis://redis:6379/3
CELERY_RESULT_BACKEND=redis://redis:6379/4
YOOKASSA_SHOP_ID=123456
YOOKASSA_SECRET_KEY=live_test_key
TELEGRAM_BOT_TOKEN=123:ABC
TELEGRAM_ADMINS=123456
$env_overrides
EOF

    # Try to start backend with test env
    if docker compose -p test_prod_guards --env-file .env.test up backend -d 2>&1 | grep -i "$expected_error"; then
        echo -e "${GREEN}✓ Guard PASSED: Backend rejected invalid config${NC}"
        PASSED=$((PASSED + 1))
    else
        echo -e "${RED}✗ Guard FAILED: Backend should have rejected this config${NC}"
        FAILED=$((FAILED + 1))
    fi

    # Cleanup
    docker compose -p test_prod_guards down -v 2>/dev/null || true
    rm -f .env.test
}

# ==============================================================================
# Test counters
# ==============================================================================
PASSED=0
FAILED=0

# ==============================================================================
# Test 1: APP_ENV != prod
# ==============================================================================
test_guard \
    "APP_ENV != prod" \
    "APP_ENV=dev" \
    "APP_ENV must be 'prod'"

# ==============================================================================
# Test 2: DEBUG=True
# ==============================================================================
test_guard \
    "DEBUG=True forbidden" \
    "APP_ENV=prod
DEBUG=True" \
    "DEBUG=True is forbidden"

# ==============================================================================
# Test 3: YOOKASSA_MODE != prod
# ==============================================================================
test_guard \
    "YOOKASSA_MODE != prod" \
    "APP_ENV=prod
YOOKASSA_MODE=test" \
    "YOOKASSA_MODE must be 'prod'"

# ==============================================================================
# Test 4: POSTGRES_DB contains _dev
# ==============================================================================
test_guard \
    "POSTGRES_DB contains _dev" \
    "APP_ENV=prod
YOOKASSA_MODE=prod
POSTGRES_DB=eatfit24_dev" \
    "Forbidden DB name"

# ==============================================================================
# Test 5: REDIS_URL missing
# ==============================================================================
test_guard \
    "REDIS_URL missing" \
    "APP_ENV=prod
YOOKASSA_MODE=prod
REDIS_URL=" \
    "REDIS_URL must be set"

# ==============================================================================
# Test 6: Test YooKassa key in PROD
# ==============================================================================
test_guard \
    "Test YooKassa key detected" \
    "APP_ENV=prod
YOOKASSA_MODE=prod
YOOKASSA_SECRET_KEY=test_this_is_test_key" \
    "Test YooKassa key detected"

# ==============================================================================
# Summary
# ==============================================================================
echo ""
echo "========================================="
echo "Test Summary"
echo "========================================="
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo ""

if [ "$FAILED" -gt 0 ]; then
    echo -e "${RED}Some guards are not working correctly!${NC}"
    echo "Review the output above and fix the guards in config/settings/production.py"
    exit 1
else
    echo -e "${GREEN}All guards are working correctly!${NC}"
    exit 0
fi
