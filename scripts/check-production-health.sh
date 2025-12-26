#!/bin/bash
# Production Health Check Script for EatFit24
# Usage: ./scripts/check-production-health.sh

set -e

echo "=========================================="
echo "EatFit24 Production Health Check"
echo "Server: eatfit24.ru (85.198.81.133)"
echo "Date: $(date)"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check 1: Public HTTPS Endpoints
echo ">>> [1/7] Checking Public HTTPS Endpoints..."
echo ""

if curl -fsS -o /dev/null -w "HTTP %{http_code} in %{time_total}s\n" https://eatfit24.ru/health/; then
    echo -e "${GREEN}✅ Backend health endpoint OK${NC}"
else
    echo -e "${RED}❌ Backend health endpoint FAILED${NC}"
fi

if curl -fsS -o /dev/null -w "HTTP %{http_code} in %{time_total}s\n" https://eatfit24.ru/; then
    echo -e "${GREEN}✅ Frontend homepage OK${NC}"
else
    echo -e "${RED}❌ Frontend homepage FAILED${NC}"
fi

echo ""

# Check 2: Container Status
echo ">>> [2/7] Docker Container Status..."
echo ""
echo "Run this on server: docker compose ps"
echo ""

# Check 3: Container Resource Usage
echo ">>> [3/7] Container Resource Usage Check..."
echo ""
echo "Run this on server: docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}'"
echo ""

# Check 4: Recent Logs
echo ">>> [4/7] Recent Container Logs (last 20 lines)..."
echo ""
echo "Run on server:"
echo "  docker logs --tail 20 eatfit24-backend"
echo "  docker logs --tail 20 eatfit24-bot"
echo "  docker logs --tail 20 eatfit24-celery-worker"
echo ""

# Check 5: Database Connection
echo ">>> [5/7] Database Health..."
echo ""
echo "Run on server: docker exec eatfit24-db pg_isready -U foodmind"
echo ""

# Check 6: Redis Connection
echo ">>> [6/7] Redis Health..."
echo ""
echo "Run on server: docker exec eatfit24-redis redis-cli ping"
echo ""

# Check 7: Disk Usage
echo ">>> [7/7] Disk Space..."
echo ""
echo "Run on server: df -h /opt/EatFit24"
echo ""

echo "=========================================="
echo "Health Check Complete"
echo "=========================================="
echo ""
echo "For detailed container logs, SSH to server:"
echo "  ssh deploy@eatfit24.ru"
echo "  cd /opt/EatFit24"
echo "  docker compose logs -f"
echo ""
