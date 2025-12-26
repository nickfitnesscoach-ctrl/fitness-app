#!/bin/bash
# Fix Critical Security Issues in Production .env
# Usage: ./scripts/fix-critical-security.sh

set -e

echo "=========================================="
echo "EatFit24 Critical Security Fixes"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ENV_FILE=".env"
ENV_BACKUP=".env.backup.$(date +%Y%m%d_%H%M%S)"

if [ ! -f "${ENV_FILE}" ]; then
    echo -e "${RED}❌ .env file not found!${NC}"
    exit 1
fi

echo -e "${YELLOW}>>> Creating backup: ${ENV_BACKUP}${NC}"
cp "${ENV_FILE}" "${ENV_BACKUP}"
echo -e "${GREEN}✅ Backup created${NC}"
echo ""

# Fix 1: Remove placeholder SECRET_KEY, use DJANGO_SECRET_KEY
echo ">>> [1/3] Fixing SECRET_KEY..."
if grep -q "^SECRET_KEY=CHANGE_ME" "${ENV_FILE}"; then
    echo -e "${YELLOW}Found placeholder SECRET_KEY${NC}"

    # Check if DJANGO_SECRET_KEY exists and is not placeholder
    if grep -q "^DJANGO_SECRET_KEY=" "${ENV_FILE}" && ! grep -q "^DJANGO_SECRET_KEY=CHANGE_ME" "${ENV_FILE}"; then
        DJANGO_KEY=$(grep "^DJANGO_SECRET_KEY=" "${ENV_FILE}" | cut -d'=' -f2-)
        echo -e "${GREEN}Using existing DJANGO_SECRET_KEY${NC}"

        # Remove old SECRET_KEY line
        sed -i.tmp '/^SECRET_KEY=CHANGE_ME/d' "${ENV_FILE}"

        # Remove DJANGO_SECRET_KEY line
        sed -i.tmp '/^DJANGO_SECRET_KEY=/d' "${ENV_FILE}"

        # Add correct SECRET_KEY
        echo "SECRET_KEY=${DJANGO_KEY}" >> "${ENV_FILE}"

        rm -f "${ENV_FILE}.tmp"
        echo -e "${GREEN}✅ SECRET_KEY fixed${NC}"
    else
        echo -e "${RED}❌ DJANGO_SECRET_KEY not found or also placeholder!${NC}"
        echo -e "${YELLOW}Generating new SECRET_KEY...${NC}"
        NEW_KEY=$(openssl rand -hex 32)
        sed -i.tmp "s|^SECRET_KEY=CHANGE_ME.*|SECRET_KEY=${NEW_KEY}|" "${ENV_FILE}"
        rm -f "${ENV_FILE}.tmp"
        echo -e "${GREEN}✅ Generated new SECRET_KEY${NC}"
    fi
else
    echo -e "${GREEN}✅ SECRET_KEY already configured${NC}"
fi
echo ""

# Fix 2: Generate SWAGGER_AUTH_PASSWORD
echo ">>> [2/3] Fixing SWAGGER_AUTH_PASSWORD..."
if grep -q "^SWAGGER_AUTH_PASSWORD=CHANGE_ME" "${ENV_FILE}"; then
    echo -e "${YELLOW}Found placeholder SWAGGER_AUTH_PASSWORD${NC}"
    NEW_SWAGGER_PASS=$(openssl rand -base64 16)
    sed -i.tmp "s|^SWAGGER_AUTH_PASSWORD=CHANGE_ME.*|SWAGGER_AUTH_PASSWORD=${NEW_SWAGGER_PASS}|" "${ENV_FILE}"
    rm -f "${ENV_FILE}.tmp"
    echo -e "${GREEN}✅ Generated new SWAGGER_AUTH_PASSWORD: ${NEW_SWAGGER_PASS}${NC}"
    echo -e "${YELLOW}⚠️  Save this password! You'll need it to access /swagger/${NC}"
else
    echo -e "${GREEN}✅ SWAGGER_AUTH_PASSWORD already configured${NC}"
fi
echo ""

# Fix 3: Check for other placeholders
echo ">>> [3/3] Checking for other placeholders..."
PLACEHOLDERS=$(grep -E "CHANGE_ME|your_|test_your" "${ENV_FILE}" | grep -v "^#" || true)

if [ -n "$PLACEHOLDERS" ]; then
    echo -e "${YELLOW}⚠️  Found other placeholders that need manual attention:${NC}"
    echo "$PLACEHOLDERS"
    echo ""
    echo -e "${YELLOW}These need to be fixed manually:${NC}"
    echo "  - OPENROUTER_API_KEY (get from https://openrouter.ai)"
    echo "  - YOOKASSA_* (get from YooKassa dashboard)"
else
    echo -e "${GREEN}✅ No other critical placeholders found${NC}"
fi
echo ""

echo "=========================================="
echo "Summary"
echo "=========================================="
echo -e "${GREEN}✅ Backup created: ${ENV_BACKUP}${NC}"
echo -e "${GREEN}✅ Critical security issues fixed${NC}"
echo ""
echo "Next steps:"
echo "  1. Review changes: diff .env ${ENV_BACKUP}"
echo "  2. If on production server, restart services:"
echo "     docker compose down && docker compose up -d"
echo "  3. Create Django superuser if needed:"
echo "     docker compose exec backend python manage.py createsuperuser"
echo ""
echo -e "${YELLOW}⚠️  Remember to delete backup after verification:${NC}"
echo "     rm ${ENV_BACKUP}"
echo ""
