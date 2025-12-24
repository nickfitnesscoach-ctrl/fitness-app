#!/bin/bash
# reset-celery-beat.sh
#
# Пересоздаёт Celery Beat контейнер для синхронизации с кодом
# Автоматизация Golden Rule: "Изменил beat_schedule → пересоздай celery-beat"
#
# Usage:
#   ./scripts/reset-celery-beat.sh
#
# Author: DevOps Agent (2025-12-24)
# Docs: docs/operations/celery-beat.md

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Celery Beat Reset Script${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Step 1: Verify we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}ERROR: docker-compose.yml not found${NC}"
    echo "Please run this script from /opt/EatFit24 directory"
    exit 1
fi

# Step 2: Show current schedule from code (before reset)
echo -e "${YELLOW}[1/5] Current schedule in code:${NC}"
sudo docker exec eatfit24-backend-1 python - <<'PY' 2>/dev/null || {
    echo -e "${RED}ERROR: Cannot read schedule from code${NC}"
    exit 1
}
from config.celery import app
print("=" * 50)
for k, v in app.conf.beat_schedule.items():
    print(f"✓ {k}")
    print(f"  schedule: {v['schedule']}")
    print(f"  task: {v['task']}")
    print()
print("=" * 50)
PY

# Step 3: Stop and remove Beat container
echo -e "${YELLOW}[2/5] Stopping and removing celery-beat container...${NC}"
sudo docker compose rm -f celery-beat

# Wait a moment for clean shutdown
sleep 2

# Step 4: Recreate Beat container
echo -e "${YELLOW}[3/5] Creating new celery-beat container...${NC}"
sudo docker compose up -d celery-beat

# Wait for Beat to start
echo -e "${YELLOW}[4/5] Waiting for Beat to start (5 seconds)...${NC}"
sleep 5

# Step 5: Verify Beat is running and show startup logs
echo -e "${YELLOW}[5/5] Verification:${NC}"

# Check container status
if sudo docker ps | grep -q "eatfit24-celery-beat-1"; then
    echo -e "${GREEN}✓ Container is running${NC}"
else
    echo -e "${RED}✗ Container is NOT running${NC}"
    echo "Logs:"
    sudo docker logs --tail 20 eatfit24-celery-beat-1
    exit 1
fi

# Show startup logs
echo ""
echo -e "${BLUE}Last 15 lines of Beat logs:${NC}"
sudo docker logs --tail 15 eatfit24-celery-beat-1

# Check for successful startup
if sudo docker logs --tail 50 eatfit24-celery-beat-1 | grep -q "beat: Starting..."; then
    echo ""
    echo -e "${GREEN}✓ Beat started successfully${NC}"
else
    echo ""
    echo -e "${RED}✗ Beat startup issue detected${NC}"
    exit 1
fi

# Final sanity check: compare code schedule with logs
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✓ Celery Beat reset completed!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Next steps:"
echo "  1. Monitor logs: sudo docker logs -f eatfit24-celery-beat-1"
echo "  2. Wait 1-2 minutes and check for 'Sending due task' messages"
echo "  3. Verify tasks execute on worker"
echo ""
echo -e "${YELLOW}Tip: If you changed beat_schedule, run this script again.${NC}"
