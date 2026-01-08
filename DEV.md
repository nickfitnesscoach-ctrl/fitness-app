# DEV.md - Руководство по локальной разработке EatFit24

> **⚠️ ВАЖНО: Переключение между dev и prod**
>
> - **Локально (dev):** `cp .env.local .env` → запуск с `docker-compose.dev.yml`
> - **На сервере (prod):** `cp .env.example .env` → настроить prod-ключи → запуск с `compose.yml`
> - **Никогда** не коммитьте `.env` или `.env.local` в git!

## 📋 Оглавление

- [Быстрый старт](#быстрый-старт)
- [Структура окружений](#структура-окружений)
- [Запуск локально](#запуск-локально)
- [Запуск на продакшн](#запуск-на-продакшн)
- [Отладка и troubleshooting](#отладка-и-troubleshooting)

---

## 🚀 Быстрый старт

### 1. Установка зависимостей

```bash
# Frontend
cd frontend
npm install

# Backend и Bot используют uv (устанавливаются в Docker)
```

### 2. Настройка окружения

```bash
# Скопируйте .env.local как основной файл для разработки
cp .env.local .env

# ВАЖНО: Не редактируйте .env напрямую!
# Все изменения делайте в .env.local, затем копируйте:
# nano .env.local
# cp .env.local .env
```

### 3. Запуск всех сервисов

```bash
# Запуск с docker-compose.dev.yml (рекомендуется)
docker compose -f compose.yml -f docker-compose.dev.yml up -d

# Запуск только фронтенда (Vite Dev Server с HMR)
cd frontend && npm run dev
```

### 4. Проверка работы

- **Frontend**: http://localhost:5173/app
- **Backend API**: http://localhost:8000/api/v1/
- **Swagger docs**: http://localhost:8000/api/schema/swagger-ui/

---

## 📁 Структура окружений

### Файлы окружения

| Файл | Назначение | В Git? | Где использовать |
|------|------------|--------|------------------|
| `.env.example` | Шаблон для production | ✅ Yes | Эталон для prod |
| `.env.local` | **Development** конфигурация | ❌ No | **Локальная разработка** |
| `.env` | Активный конфиг (копия .env.local или .env.example) | ❌ No | Docker Compose читает отсюда |

**Правило:**
- На локалке: `cp .env.local .env` перед запуском
- На сервере: `cp .env.example .env` и настроить prod-ключи

### Docker Compose файлы

| Файл | Назначение | Когда использовать |
|------|------------|-------------------|
| `compose.yml` | Production конфигурация | На сервере |
| `docker-compose.dev.yml` | Development overrides | Локальная разработка |
| `compose.yml.prod` | Backup production конфига | Резервная копия |

---

## 💻 Запуск локально

### Вариант 1: Docker Compose DEV (рекомендуется)

Этот вариант использует **live code reloading** для backend и bot:

```bash
# 1. Убедитесь что используете .env.local
cp .env.local .env

# 2. Запуск всех сервисов в DEV режиме
docker compose -f compose.yml -f docker-compose.dev.yml up -d

# 3. Проверка статуса
docker compose ps

# 4. Просмотр логов
docker compose logs -f backend
docker compose logs -f bot
```

**Что включено в DEV режиме:**

- ✅ `DEBUG=True` (подробные ошибки)
- ✅ `WEBAPP_DEBUG_MODE_ENABLED=True` (mock Telegram WebApp)
- ✅ Volume mounts для live reload (backend/bot код)
- ✅ Django runserver вместо Gunicorn (автоперезагрузка при изменении кода)
- ✅ YooKassa в test режиме
- ✅ Relaxed security (HTTP, без SSL redirect)
- ✅ Dev-изолированная БД (`eatfit24_dev`, не мешает продакшн данным)
- ✅ Все секреты загружаются из `.env` (нет хардкода в compose)

### Вариант 2: Только фронтенд (Vite Dev Server)

Если backend уже запущен в Docker:

```bash
cd frontend
npm run dev

# Откроется http://localhost:5173/app
```

**Особенности:**

- Hot Module Replacement (HMR)
- Vite proxy для `/api/v1` → `http://localhost:8000`
- Browser Debug Mode (mock Telegram WebApp)

### Вариант 3: Backend локально (без Docker)

Если хотите запустить backend вне Docker:

```bash
cd backend

# Установка зависимостей
uv sync

# Применить миграции
uv run python manage.py migrate

# Запуск dev сервера
uv run python manage.py runserver

# В другом терминале - Celery worker
uv run celery -A config worker -l INFO

# В третьем терминале - Celery beat
uv run celery -A config beat -l INFO
```

**Требования:**

- PostgreSQL запущен локально (или в Docker)
- Redis запущен локально (или в Docker)
- `.env` настроен с корректными `POSTGRES_HOST`, `REDIS_URL`

---

## 🚀 Запуск на продакшн

### На сервере (production)

```bash
# 1. Убедитесь что .env настроен для production
cat .env | grep ENV
# Должно быть: ENV=production

# 2. Остановка старых контейнеров
docker compose down

# 3. Сборка и запуск production
docker compose up -d --build

# 4. Проверка здоровья
docker compose ps
curl -H "Host: eatfit24.ru" http://localhost:8000/health/

# 5. Проверка логов
docker compose logs -f backend
```

**Критичные проверки перед деплоем:**

```bash
# ✅ Миграции созданы и закоммичены
cd backend
python manage.py makemigrations --check --dry-run

# ✅ Тесты проходят
pytest -v

# ✅ Git статус чистый
git status

# ✅ Pre-deploy script (если есть)
./scripts/pre-deploy-check.sh
```

### Переменные окружения для production

**Критичные отличия от DEV:**

```bash
# .env (production)
ENV=production
DEBUG=false
DJANGO_SETTINGS_MODULE=config.settings.production

# ALLOWED_HOSTS без localhost
ALLOWED_HOSTS=eatfit24.ru,www.eatfit24.ru,backend

# CSRF только HTTPS
CSRF_TRUSTED_ORIGINS=https://eatfit24.ru,https://www.eatfit24.ru

# Security включена
SECURE_SSL_REDIRECT=true
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true

# YooKassa PROD ключи
YOOKASSA_SECRET_KEY=live_XXXXXXX
YOOKASSA_MODE=prod
YOOKASSA_WEBHOOK_VERIFY_SIGNATURE=true

# Billing строгий режим
BILLING_STRICT_MODE=true
BILLING_RECURRING_ENABLED=true

# Collectstatic включен
RUN_COLLECTSTATIC=1
```

---

## 🔧 Отладка и Troubleshooting

### Проблема: Тарифы не загружаются

**Симптомы:** Ошибка "Не удалось загрузить тарифы" на странице `/subscription`

**Решение:**

```bash
# 1. Проверить что backend отвечает
curl http://localhost:8000/api/v1/billing/plans/

# 2. Проверить ALLOWED_HOSTS
docker exec eatfit24-backend env | grep ALLOWED_HOSTS
# Должно включать: localhost,backend,backend:8000

# 3. Проверить DJANGO_SETTINGS_MODULE
docker exec eatfit24-backend env | grep DJANGO_SETTINGS_MODULE
# Для DEV: config.settings.local

# 4. Проверить логи
docker compose logs backend | grep -i error
```

### Проблема: Django возвращает 400/500 ошибки

**Симптомы:** `DisallowedHost` или `Internal Server Error`

**Решение:**

```bash
# 1. Проверить что используется правильный .env
ls -la .env*

# 2. Пересоздать контейнер с новым .env
docker compose up -d --force-recreate backend

# 3. Проверить настройки внутри контейнера
docker exec eatfit24-backend python -c "from django.conf import settings; print('ALLOWED_HOSTS:', settings.ALLOWED_HOSTS); print('DEBUG:', settings.DEBUG)"
```

### Проблема: База данных не подключается

**Симптомы:** `could not connect to server` или `database does not exist`

**Решение:**

```bash
# 1. Проверить что PostgreSQL запущен
docker compose ps db

# 2. Проверить доступность
docker exec eatfit24-db pg_isready -U eatfit24

# 3. Проверить пароль в .env
cat .env | grep POSTGRES_PASSWORD

# 4. Пересоздать БД (ОСТОРОЖНО: удалит данные)
docker compose down -v
docker compose up -d db
docker compose up -d backend  # Применит миграции
```

### Проблема: Frontend не видит backend API

**Симптомы:** Network errors в DevTools, CORS ошибки

**Решение:**

```bash
# 1. Проверить Vite proxy настройки
cat frontend/vite.config.ts | grep -A 10 "proxy"

# 2. Проверить CORS в backend
docker compose logs backend | grep CORS

# 3. Проверить что backend слушает на правильном порту
docker compose ps backend
# Должно быть: 127.0.0.1:8000->8000/tcp

# 4. Проверить .env.development фронтенда
cat frontend/.env.development | grep VITE_API_URL
# Должно быть: VITE_API_URL=/api/v1
```

### Полезные команды

```bash
# Перезапуск одного сервиса
docker compose restart backend

# Пересоздание с пересборкой
docker compose up -d --build backend

# Просмотр переменных окружения
docker exec eatfit24-backend env | grep DJANGO

# Запуск команды в контейнере
docker exec eatfit24-backend python manage.py shell

# Очистка всех контейнеров и volumes
docker compose down -v
docker system prune -a

# Проверка использования памяти
docker stats --no-stream | grep eatfit24
```

---

## 📚 Дополнительные ресурсы

- **CLAUDE.md** - Инструкции для Claude Code (основная документация)
- **backend/apps/billing/docs/** - Документация биллинга
- **scripts/** - Утилиты для деплоя и проверок

---

## 🎯 Checklist для разработки

### Перед началом работы

- [ ] Скопирован `.env.local` → `.env`
- [ ] Проверены токены и ключи в `.env`
- [ ] Запущен Docker Compose DEV
- [ ] Frontend dev server работает (http://localhost:5173/app)
- [ ] Backend API отвечает (http://localhost:8000/health/)

### Перед коммитом

- [ ] `npm run lint` (frontend)
- [ ] `npm run type-check` (frontend)
- [ ] `pytest -v` (backend)
- [ ] Миграции созданы и закоммичены
- [ ] `.env.local` НЕ закоммичен (проверить `git status`)

### Перед деплоем (на сервере)

- [ ] **КРИТИЧНО:** Восстановлен production `.env` из `.env.example`
  ```bash
  # На сервере (НЕ локально!)
  cp .env.example .env
  nano .env  # Настроить production ключи
  ```
- [ ] Запущен `scripts/pre-deploy-check.sh`
- [ ] Все тесты зелёные
- [ ] Git статус чистый
- [ ] Создан tag или commit message с версией

---

**Вопросы?** Смотри [CLAUDE.md](./CLAUDE.md) или задай вопрос в Telegram.
