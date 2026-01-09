#!/usr/bin/env bash
#
# scripts/test-isolation.sh
#
# Тестирует физическую изоляцию DEV/PROD окружений.
#
# Usage:
#   ./scripts/test-isolation.sh
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================="
echo "DEV/PROD Isolation Test"
echo "========================================="
echo ""

# ==============================================================================
# 1. Docker Projects Isolation
# ==============================================================================
echo "1. Testing Docker projects isolation..."
echo ""

echo "Listing Docker Compose projects:"
docker compose ls
echo ""

# ==============================================================================
# 2. Volumes Isolation
# ==============================================================================
echo "2. Testing volumes isolation..."
echo ""

echo "DEV volumes (should have eatfit24_dev prefix):"
docker volume ls | grep "eatfit24_dev" || echo -e "${RED}No DEV volumes found${NC}"
echo ""

echo "PROD volumes (should have eatfit24 prefix without _dev):"
docker volume ls | grep "eatfit24" | grep -v "eatfit24_dev" || echo -e "${RED}No PROD volumes found${NC}"
echo ""

# ==============================================================================
# 3. Networks Isolation
# ==============================================================================
echo "3. Testing networks isolation..."
echo ""

echo "DEV network:"
docker network ls | grep "eatfit24_dev" || echo -e "${RED}No DEV network found${NC}"
echo ""

echo "PROD network:"
docker network ls | grep "eatfit24" | grep -v "eatfit24_dev" || echo -e "${RED}No PROD network found${NC}"
echo ""

# ==============================================================================
# 4. Containers Isolation
# ==============================================================================
echo "4. Testing containers isolation..."
echo ""

DEV_CONTAINERS=$(docker ps -a --filter "name=eatfit24_dev" --format "{{.Names}}" | wc -l)
PROD_CONTAINERS=$(docker ps -a --filter "name=eatfit24-" --format "{{.Names}}" | wc -l)

echo "DEV containers found: $DEV_CONTAINERS"
docker ps -a --filter "name=eatfit24_dev" --format "table {{.Names}}\t{{.Status}}" || true
echo ""

echo "PROD containers found: $PROD_CONTAINERS"
docker ps -a --filter "name=eatfit24-" --format "table {{.Names}}\t{{.Status}}" || true
echo ""

# ==============================================================================
# 5. Database Isolation (if containers are running)
# ==============================================================================
echo "5. Testing database isolation..."
echo ""

if [ "$DEV_CONTAINERS" -gt 0 ]; then
    echo "Checking DEV database..."
    DEV_DB=$(docker compose -p eatfit24_dev exec -T backend python -c "import os; print(os.getenv('POSTGRES_DB', 'N/A'))" 2>/dev/null || echo "N/A")
    DEV_APP_ENV=$(docker compose -p eatfit24_dev exec -T backend python -c "import os; print(os.getenv('APP_ENV', 'N/A'))" 2>/dev/null || echo "N/A")
    echo -e "  POSTGRES_DB: ${YELLOW}${DEV_DB}${NC}"
    echo -e "  APP_ENV: ${YELLOW}${DEV_APP_ENV}${NC}"

    if [[ "$DEV_DB" == *"_dev"* ]] && [[ "$DEV_APP_ENV" == "dev" ]]; then
        echo -e "  ${GREEN}✓ DEV database is correctly isolated${NC}"
    else
        echo -e "  ${RED}✗ DEV database configuration issue${NC}"
    fi
else
    echo -e "${YELLOW}Skipped: DEV containers not running${NC}"
fi
echo ""

if [ "$PROD_CONTAINERS" -gt 0 ]; then
    echo "Checking PROD database..."
    PROD_DB=$(docker compose -p eatfit24 exec -T backend python -c "import os; print(os.getenv('POSTGRES_DB', 'N/A'))" 2>/dev/null || echo "N/A")
    PROD_APP_ENV=$(docker compose -p eatfit24 exec -T backend python -c "import os; print(os.getenv('APP_ENV', 'N/A'))" 2>/dev/null || echo "N/A")
    echo -e "  POSTGRES_DB: ${YELLOW}${PROD_DB}${NC}"
    echo -e "  APP_ENV: ${YELLOW}${PROD_APP_ENV}${NC}"

    if [[ "$PROD_DB" != *"_dev"* ]] && [[ "$PROD_APP_ENV" == "prod" ]]; then
        echo -e "  ${GREEN}✓ PROD database is correctly isolated${NC}"
    else
        echo -e "  ${RED}✗ PROD database configuration issue${NC}"
    fi
else
    echo -e "${YELLOW}Skipped: PROD containers not running${NC}"
fi
echo ""

# ==============================================================================
# 6. Redis/Celery Isolation
# ==============================================================================
echo "6. Testing Redis/Celery isolation..."
echo ""

if [ "$DEV_CONTAINERS" -gt 0 ]; then
    echo "Checking DEV Redis..."
    DEV_REDIS=$(docker compose -p eatfit24_dev exec -T backend python -c "import os; print(os.getenv('CELERY_BROKER_URL', 'N/A'))" 2>/dev/null || echo "N/A")
    echo -e "  CELERY_BROKER_URL: ${YELLOW}${DEV_REDIS}${NC}"

    if [[ "$DEV_REDIS" == *"/0"* ]] || [[ "$DEV_REDIS" == *"/1"* ]]; then
        echo -e "  ${GREEN}✓ DEV Redis DB index is correct (0 or 1)${NC}"
    else
        echo -e "  ${RED}✗ DEV Redis DB index issue${NC}"
    fi
else
    echo -e "${YELLOW}Skipped: DEV containers not running${NC}"
fi
echo ""

if [ "$PROD_CONTAINERS" -gt 0 ]; then
    echo "Checking PROD Redis..."
    PROD_REDIS=$(docker compose -p eatfit24 exec -T backend python -c "import os; print(os.getenv('CELERY_BROKER_URL', 'N/A'))" 2>/dev/null || echo "N/A")
    echo -e "  CELERY_BROKER_URL: ${YELLOW}${PROD_REDIS}${NC}"

    if [[ "$PROD_REDIS" == *"/1"* ]] || [[ "$PROD_REDIS" == *"/2"* ]]; then
        echo -e "  ${GREEN}✓ PROD Redis DB index is correct (1 or 2)${NC}"
    else
        echo -e "  ${RED}✗ PROD Redis DB index issue${NC}"
    fi
else
    echo -e "${YELLOW}Skipped: PROD containers not running${NC}"
fi
echo ""

# ==============================================================================
# Summary
# ==============================================================================
echo "========================================="
echo "Test Summary"
echo "========================================="
echo ""
echo "✓ Check volumes, networks, and containers in output above"
echo "✓ DEV and PROD should have different prefixes"
echo "✓ Database names should be different (e.g., eatfit24_dev vs eatfit24_prod)"
echo "✓ Redis DB indexes should be different (DEV: 0/1, PROD: 1/2)"
echo ""
echo "If any tests failed, review the output and fix configuration."
echo ""
