#!/bin/bash
# Quick Deploy Script для включения Production Debug Mode
# EatFit24 - https://eatfit24.ru
# Автор: Claude Code
# Дата: 2025-12-07

set -e  # Exit on error

echo "========================================="
echo "EatFit24 Production Debug Mode Deployment"
echo "========================================="
echo ""

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Функция для SSH команд
run_ssh() {
    ssh root@85.198.81.133 "$1"
}

echo -e "${YELLOW}[1/5] Проверка локальных изменений...${NC}"
if [ ! -f "frontend/nginx.conf" ]; then
    echo -e "${RED}Ошибка: frontend/nginx.conf не найден!${NC}"
    exit 1
fi

if ! grep -q "X-Debug-Mode" frontend/nginx.conf; then
    echo -e "${RED}Ошибка: Debug Mode заголовки отсутствуют в nginx.conf!${NC}"
    echo "Добавьте заголовки согласно PRODUCTION_DEBUG_MODE_DEPLOY.md"
    exit 1
fi

echo -e "${GREEN}✓ Локальные файлы готовы${NC}"

echo ""
echo -e "${YELLOW}[2/5] Включение DEBUG_MODE_ENABLED на backend...${NC}"
read -p "Добавить DEBUG_MODE_ENABLED=true в .env на проде? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    run_ssh "cd /opt/foodmind && grep -q '^DEBUG_MODE_ENABLED=' .env && sed -i 's/^DEBUG_MODE_ENABLED=.*/DEBUG_MODE_ENABLED=true/' .env || echo 'DEBUG_MODE_ENABLED=true' >> .env"
    echo -e "${GREEN}✓ DEBUG_MODE_ENABLED=true добавлен${NC}"
else
    echo -e "${YELLOW}⚠ Пропущено. Убедитесь, что DEBUG_MODE_ENABLED=true установлен вручную!${NC}"
fi

echo ""
echo -e "${YELLOW}[3/5] Пересборка frontend...${NC}"
cd frontend
npm run build
cd ..
echo -e "${GREEN}✓ Frontend пересобран${NC}"

echo ""
echo -e "${YELLOW}[4/5] Деплой на production...${NC}"

echo "  - Остановка frontend контейнера..."
run_ssh "cd /opt/foodmind && docker-compose stop frontend"

echo "  - Копирование nginx.conf..."
scp frontend/nginx.conf root@85.198.81.133:/opt/foodmind/frontend/nginx.conf

echo "  - Копирование статики..."
scp -r frontend/dist/* root@85.198.81.133:/opt/foodmind/frontend/dist/

echo "  - Пересборка и запуск frontend..."
run_ssh "cd /opt/foodmind && docker-compose build frontend && docker-compose up -d frontend"

echo ""
echo -e "${YELLOW}[5/5] Перезапуск backend для подхвата DEBUG_MODE_ENABLED...${NC}"
run_ssh "cd /opt/foodmind && docker-compose restart backend celery-worker"

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}✓ Деплой завершен!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "Проверьте работоспособность:"
echo ""
echo "1. Откройте в браузере:"
echo "   https://eatfit24.ru/app?web_debug=1"
echo ""
echo "2. Ожидайте:"
echo "   - Красный баннер: BROWSER DEBUG MODE • USER: eatfit24_debug"
echo "   - Приложение работает (нет заглушки 'Откройте через Telegram')"
echo ""
echo "3. Проверьте DevTools → Network:"
echo "   - Request Headers должны содержать: X-Debug-Mode: true"
echo ""
echo "4. Проверьте backend логи:"
echo "   ssh root@85.198.81.133 'docker logs fm-backend -n 100 | grep DebugMode'"
echo ""
echo -e "${YELLOW}Подробная инструкция: PRODUCTION_DEBUG_MODE_DEPLOY.md${NC}"
