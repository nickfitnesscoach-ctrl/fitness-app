# ⚡ QUICKSTART - EatFit24

> **⚠️ ВАЖНО:** Всегда `cp .env.local .env` перед локальной разработкой!

## 🚀 Запуск для разработки (5 минут)

```bash
# 1. Настройка окружения (ОБЯЗАТЕЛЬНО!)
cp .env.local .env

# 2. Запуск backend + БД + Redis + Celery (в DEV режиме)
docker compose -f compose.yml -f compose.dev.yml up -d

# 3. Запуск frontend (в отдельном терминале)
cd frontend && npm run dev
```

✅ Готово! Открыть http://localhost:5173/app (или 5174, если порт занят)

**Что получили:**
- Django runserver (автоперезагрузка при изменении кода)
- Dev-база `eatfit24_dev` (не мешает prod данным)
- Все секреты из `.env` (нет хардкода)

---

## 📦 Что запущено

| Сервис | URL | Описание |
|--------|-----|----------|
| Frontend | http://localhost:5173/app | Vite Dev Server (HMR) |
| Backend API | http://localhost:8000/api/v1/ | Django REST API |
| Swagger | http://localhost:8000/api/schema/swagger-ui/ | API документация |
| PostgreSQL | localhost:5432 | База данных |
| Redis | localhost:6379 | Кэш + Celery broker |

---

## 🔄 Запуск для production (на сервере)

```bash
# 1. Восстановить production конфигурацию
cp .env.example .env
nano .env  # Настроить prod-ключи (YOOKASSA_SECRET_KEY, DJANGO_SECRET_KEY и т.д.)

# 2. Проверить что ENV=production
grep "ENV=" .env

# 3. Запуск production (без compose.dev.yml!)
docker compose up -d --build

# 4. Проверка
docker compose ps
curl -k https://eatfit24.ru/health/
```

**КРИТИЧНО:** На сервере НЕ использовать `.env.local` и НЕ использовать `compose.dev.yml`!

---

## 🛠️ Полезные команды

```bash
# Перезапуск backend
docker compose restart backend

# Логи backend
docker compose logs -f backend

# Выполнить команду в контейнере
docker exec -it eatfit24-backend python manage.py shell

# Остановить всё
docker compose down

# Пересборка с нуля
docker compose down -v
docker compose up -d --build
```

---

## 📖 Полная документация

- **DEV.md** - Подробное руководство по разработке
- **CLAUDE.md** - Архитектура проекта и команды
- **backend/apps/billing/docs/** - Документация биллинга

---

## 🆘 Проблемы?

### Тарифы не загружаются

```bash
# Проверить настройки
docker exec eatfit24-backend python -c "from django.conf import settings; print(settings.ALLOWED_HOSTS, settings.DEBUG)"

# Должно быть: ['localhost', 'localhost:8000', '127.0.0.1', 'backend', 'backend:8000'] True
```

### Frontend не видит backend

```bash
# Проверить что backend запущен
curl http://localhost:8000/api/v1/billing/plans/

# Если 400/500 - пересоздать контейнер
docker compose up -d --force-recreate backend
```

### База данных не работает

```bash
# Пересоздать БД (УДАЛИТ ДАННЫЕ!)
docker compose down -v
docker compose up -d
```

---

**Нужна помощь?** Читай [DEV.md](./DEV.md) или спрашивай в Telegram!
