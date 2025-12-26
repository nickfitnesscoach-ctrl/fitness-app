# Инфраструктура EatFit24

> **Дата последнего обновления:** 2025-12-26  
> **Статус:** PRODUCTION-READY  
> **Docker Compose:** v2.x (без поля `version` в compose.yml)

---

## 1. Введение

Эта документация описывает инфраструктурную часть проекта EatFit24:

- **Docker Compose** — оркестрация контейнеров
- **Dockerfile** — сборка образов
- **Nginx** — маршрутизация запросов
- **CI/CD** — автоматический деплой

**Для кого:** разработчики с опытом Docker/Linux, которые будут поддерживать или расширять проект.

**Цель:** за 10–15 минут восстановить в голове всю схему, чтобы безопасно вносить изменения.

---

## 2. Общая архитектура системы

```
┌─────────────────────────────────────────────────────────────────┐
│                         ИНТЕРНЕТ                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ХОСТ-СЕРВЕР (VPS)                           │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    Nginx (host level)                       ││
│  │              HTTPS termination, SSL certificates            ││
│  │                   proxy_pass → :3000                        ││
│  └─────────────────────────────────────────────────────────────┘│
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────── Docker Network ───────────────────────┐   │
│  │                                                           │   │
│  │  ┌─────────────────────────────────────────────────────┐ │   │
│  │  │              frontend (nginx:alpine)                 │ │   │
│  │  │              порт 3000 (только localhost)            │ │   │
│  │  │  /app/* → React SPA                                  │ │   │
│  │  │  /api/* → proxy → backend:8000                       │ │   │
│  │  │  / → Landing                                         │ │   │
│  │  └─────────────────────────────────────────────────────┘ │   │
│  │                              │                            │   │
│  │                              ▼                            │   │
│  │  ┌─────────────────────────────────────────────────────┐ │   │
│  │  │              backend (Django + Gunicorn)             │ │   │
│  │  │              порт 8000 (только localhost)            │ │   │
│  │  └─────────────────────────────────────────────────────┘ │   │
│  │           │                              │                │   │
│  │           ▼                              ▼                │   │
│  │  ┌──────────────┐              ┌──────────────────────┐  │   │
│  │  │     db       │              │       redis          │  │   │
│  │  │  PostgreSQL  │              │  Celery Broker       │  │   │
│  │  └──────────────┘              └──────────────────────┘  │   │
│  │                                         │                 │   │
│  │                    ┌────────────────────┼────────────┐   │   │
│  │                    │                    │            │   │   │
│  │                    ▼                    ▼            │   │   │
│  │           ┌──────────────┐    ┌──────────────┐       │   │   │
│  │           │ celery-worker│    │ celery-beat  │       │   │   │
│  │           │ (фоновые AI) │    │ (scheduler)  │       │   │   │
│  │           └──────────────┘    └──────────────┘       │   │   │
│  │                                                       │   │   │
│  │  ┌─────────────────────────────────────────────────┐ │   │   │
│  │  │                   bot                            │ │   │   │
│  │  │            Telegram Bot (aiogram)                │ │   │   │
│  │  │            polling → telegram API                │ │   │   │
│  │  │            API calls → backend:8000              │ │   │   │
│  │  └─────────────────────────────────────────────────┘ │   │   │
│  │                                                       │   │   │
│  └───────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

> **Важно:** на сервере используется **два уровня Nginx**:
> 1. **Host-level Nginx** — SSL/TLS termination, HTTPS certificates (Let's Encrypt), проксирование на Docker (`:3000`)
> 2. **Frontend Nginx (в контейнере)** — SPA routing, API proxy к backend, раздача статики
>
> Эта документация описывает контейнерный Nginx (`frontend/nginx.conf`). Host-level настраивается отдельно на сервере.

### Ключевые принципы

| Принцип | Реализация |
|---------|------------|
| **Изоляция** | Все сервисы в одной Docker-сети, наружу — только Nginx |
| **Безопасность** | Все runtime-контейнеры работают без root (appuser / nginx) |
| **Ресурсы** | У каждого сервиса лимиты CPU/RAM |
| **Отказоустойчивость** | `restart: unless-stopped` для всех сервисов |

---

## 3. Docker Compose — подробный разбор

> **Файл:** `compose.yml`

### 3.1 db (PostgreSQL)

**Назначение:** основная база данных, хранит пользователей, планы питания, подписки, логи еды.

| Параметр | Значение | Комментарий |
|----------|----------|-------------|
| **Образ** | `postgres:15-alpine` | Alpine — минимальный размер |
| **Порты** | Не открыты | Доступен только внутри Docker-сети |
| **Volume** | `postgres_data` | Named volume, данные переживают `docker compose down` |
| **Лимиты** | 0.5 CPU / 512MB | Достаточно для текущей нагрузки |

**Критичные ENV:**
```bash
POSTGRES_DB       # имя базы
POSTGRES_USER     # пользователь
POSTGRES_PASSWORD # ОБЯЗАТЕЛЕН, compose упадёт без него
```

**Healthcheck:** `pg_isready` — backend не стартует, пока БД не готова.

---

### 3.2 redis

**Назначение:** брокер сообщений для Celery + кэш.

| Параметр | Значение | Комментарий |
|----------|----------|-------------|
| **Образ** | `redis:7-alpine` | — |
| **Порты** | Не открыты | Только внутри сети |
| **Volume** | `redis_data` | Персистентность через `--appendonly yes` |
| **Лимиты** | 0.5 CPU / 256MB | — |

**Почему append-only:** при перезапуске Redis восстановит очередь Celery, и задачи не потеряются.

---

### 3.3 backend (Django)

**Назначение:** REST API, бизнес-логика, авторизация, вебхуки YooKassa.

| Параметр | Значение | Комментарий |
|----------|----------|-------------|
| **Build** | `./backend/Dockerfile` | Multi-stage сборка |
| **Порты** | `127.0.0.1:8000:8000` | Только localhost, никогда не открывать наружу |
| **Volumes** | `staticfiles`, `media` | Django static + загруженные фото |
| **Лимиты** | 1.0 CPU / 768MB | Самый тяжёлый сервис |

**Depends on:** db (healthy), redis (healthy) — строгий порядок запуска.

**Healthcheck:** 
```bash
curl -f -H "Host: eatfit24.ru" http://localhost:8000/health/
```
> Заголовок `Host` нужен, потому что Django проверяет `ALLOWED_HOSTS`.

**Критичные ENV (из .env):**
- `SECRET_KEY` — Django secret, нельзя менять после запуска без миграций
- `POSTGRES_*` — подключение к БД
- `TELEGRAM_BOT_TOKEN` — для валидации WebApp init data
- `YOOKASSA_*` — платёжная система

---

### 3.4 celery-worker

**Назначение:** выполнение фоновых задач (AI анализ фото, авто-продление подписок).

| Параметр | Значение | Комментарий |
|----------|----------|-------------|
| **Build** | Тот же `./backend/Dockerfile` | Один образ, разные команды |
| **Command** | `celery -A config worker -l INFO --concurrency=2` | 2 воркера |
| **Лимиты** | 1.0 CPU / 512MB | AI-задачи потребляют ресурсы |

**Почему concurrency=2:** баланс между параллелизмом и потреблением RAM. При росте — увеличить.

---

### 3.5 celery-beat

**Назначение:** планировщик периодических задач (авто-продление, очистка).

| Параметр | Значение | Комментарий |
|----------|----------|-------------|
| **Command** | `celery -A config beat -l INFO` | — |
| **Лимиты** | 0.25 CPU / 256MB | Минимальная нагрузка |

> **Важно:** Beat должен быть ОДИН на весь кластер. При масштабировании не дублировать.

---

### 3.6 bot (Telegram)

**Назначение:** Telegram бот, отправка уведомлений, обработка команд.

| Параметр | Значение | Комментарий |
|----------|----------|-------------|
| **Build** | `./bot/Dockerfile` | — |
| **Порты** | Не открыты | Long-polling к Telegram API |
| **Лимиты** | 0.5 CPU / 256MB | — |

**Как общается с backend:** через `http://backend:8000` (внутри Docker-сети).

**Критичные ENV:**
- `TELEGRAM_BOT_TOKEN` — токен бота
- `BOT_ADMIN_ID` — Telegram ID администратора
- `BACKEND_URL` — URL Django API

---

### 3.7 frontend (Nginx + React SPA)

**Назначение:** отдача статики React-приложения + лендинга + проксирование API.

| Параметр | Значение | Комментарий |
|----------|----------|-------------|
| **Build** | `./frontend/Dockerfile` | Multi-stage: node → nginx |
| **Порты** | `127.0.0.1:3000:80` | Только localhost |
| **Лимиты** | 0.5 CPU / 128MB | Статика — минимум ресурсов |

**Build args (Vite):**
```yaml
VITE_API_URL=/api/v1              # встраивается в JS bundle
VITE_TELEGRAM_BOT_NAME            # имя бота для ссылок
VITE_TRAINER_INVITE_LINK          # invite link
```

> **Важно:** Vite-переменные "вшиваются" при сборке. Изменение требует пересборки образа.

---

## 4. Dockerfile — как и зачем собираются образы

### 4.1 backend/Dockerfile

```dockerfile
# Stage 1: Builder
FROM python:3.12-slim AS builder
# Устанавливает gcc, libpq-dev для компиляции psycopg2
# pip install --user → всё в /root/.local

# Stage 2: Runtime
FROM python:3.12-slim
# Создаёт non-root user: appuser
# Копирует зависимости из builder в /home/appuser/.local
# COPY --chown=appuser:appuser для правильных прав
# USER appuser — запуск под непривилегированным пользователем
```

**Почему multi-stage:**
1. В builder есть gcc (30+ MB) — нужен для компиляции
2. В runtime — только runtime-зависимости (libpq5, curl)
3. Финальный образ ~150MB вместо ~400MB

**Риски при изменении:**
- Не убирать `useradd appuser` — это security hardening
- `PATH=/home/appuser/.local/bin:$PATH` — обязателен для pip packages
- Не добавлять `--trusted-host` — только PyPI

---

### 4.2 bot/Dockerfile

```dockerfile
FROM python:3.12-slim
# Устанавливает gcc (для aiohttp), postgresql-client, dos2unix
# Создаёт appuser, переключается на него
# ENTRYPOINT ["/entrypoint.sh"]
```

**Особенности:**
- `dos2unix` — конвертирует Windows CRLF в Unix LF (важно для Windows-разработки)
- Нет multi-stage — бот легче, сборка не критична

---

### 4.3 frontend/Dockerfile

```dockerfile
# Stage 1: Builder (node:20-alpine)
# npm ci + npm run build → статика в /app/dist

# Stage 2: Runtime (nginx:alpine)
# Копирует dist → /usr/share/nginx/html/app
# Копирует landing → /usr/share/nginx/html/landing
# Копирует nginx.conf → /etc/nginx/conf.d/default.conf
```

**Почему не добавлен USER:**
`nginx:alpine` уже работает под user `nginx` — это стандарт образа.

**Риски при изменении:**
- `nginx.conf` — критичный файл, см. раздел 5
- `VITE_*` args — при изменении пересобрать образ

---

## 5. Nginx — маршрутизация и безопасность

> **Файл:** `frontend/nginx.conf`

### 5.1 Маршрутизация

| URL | Обработка | Комментарий |
|-----|-----------|-------------|
| `/` | `landing/index.html` | Главная лендинга |
| `/offer`, `/privacy`, `/contacts` | `landing/*.html` | Статичные страницы |
| `/landing/*` | Static files | CSS/изображения лендинга |
| `/app/*` | React SPA | Все под-роуты → `/app/index.html` |
| `/app/assets/*` | Static with cache | Vite assets, кэш 1 год |
| `/api/*` | `proxy_pass → backend:8000` | Django REST API |
| `/media/*` | `proxy_pass → backend:8000` | Загруженные фото |

### 5.2 Проксирование API — ключевые моменты

```nginx
location /api/ {
    proxy_pass http://backend:8000/api/;
    
    # Стандартные заголовки
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # КРИТИЧНО: Telegram auth headers
    proxy_set_header X-Telegram-Init-Data $http_x_telegram_init_data;
    proxy_set_header X-Telegram-ID $http_x_telegram_id;
    # ... и другие X-Telegram-* заголовки
}
```

> **Почему явно перечислены заголовки:**  
> Nginx по умолчанию НЕ прокидывает заголовки с подчёркиваниями.  
> Telegram WebApp отправляет `X-Telegram-Init-Data`, и без явного `proxy_set_header` Django его не увидит.

### 5.3 Почему CORS не на уровне Nginx

```nginx
# CORS handled by Django middleware (corsheaders)
# DO NOT add wildcard CORS here - security risk!
```

**Причины:**
1. Django знает, какие endpoints публичные, а какие требуют auth
2. Django `corsheaders` позволяет точно настроить `CORS_ALLOWED_ORIGINS`
3. Wildcard CORS (`Access-Control-Allow-Origin: *`) — дыра в безопасности

### 5.4 Content Security Policy (CSP)

```nginx
add_header Content-Security-Policy "frame-ancestors 'self' https://web.telegram.org https://*.web.telegram.org https://telegram.org https://*.telegram.org;" always;
```

**Зачем:** позволяет Telegram Web App встраивать наш сайт в iframe.  
Без этого заголовка приложение не откроется в Telegram Web.

### 5.5 Кэширование

| Ресурс | Cache-Control | Почему |
|--------|---------------|--------|
| `/app/` (HTML) | `no-store, no-cache` | Всегда свежий SPA |
| `/app/assets/` | `1y, immutable` | Vite добавляет хэши в имена файлов |
| Лендинг HTML | `1h` | Редко меняется |
| Лендинг CSS/img | `1d` | — |

### 5.6 server_name _

```nginx
server_name _;
```

Это "catch-all" — принимает запросы на любые хосты.

> **Когда изменить:** если на сервере будет второй сайт, нужно явно указать:
> ```nginx
> server_name eatfit24.ru www.eatfit24.ru;
> ```

---

## 6. CI/CD — как работает деплой

### 6.1 Архитектура workflows

```
.github/workflows/
├── backend.yml   # CI: тесты, lint → только проверка, не деплой
├── bot.yml       # CI: тесты, lint → только проверка, не деплой
└── deploy.yml    # CD: деплой на VPS при push в main
```

### 6.2 backend.yml и bot.yml — CI

**Триггеры:**
- Push в `main` с изменениями в `backend/**` или `bot/**`
- Pull request в `main`
- Ручной запуск (`workflow_dispatch`)

**Что делает (backend.yml):**
1. Запускает PostgreSQL и Redis как services
2. Устанавливает Python 3.12
3. **Guardrail** — запрещает `datetime.now()` / `datetime.utcnow()`  
   (нужно использовать `django.utils.timezone.now()`)
4. `python manage.py check` — Django system checks
5. `python manage.py migrate` — применяет миграции
6. `python manage.py test` — запускает тесты

**Что делает (bot.yml):**
1. Lint с Ruff (non-blocking)
2. Проверка форматирования Black (non-blocking)
3. `pytest` — тесты бота

### 6.3 deploy.yml — CD

**Триггеры:**
```yaml
on:
  push:
    branches: [main]
    paths:
      - "backend/**"
      - "bot/**"
      - "frontend/**"
      - "compose.yml"
      - ".github/workflows/deploy.yml"
  workflow_dispatch:
    inputs:
      services:
        description: "Services to deploy (comma-separated or 'all')"
```

**Защита от параллельных деплоев:**
```yaml
concurrency:
  group: deploy-main
  cancel-in-progress: true
```
> Если два коммита подряд — первый деплой отменяется, выполняется только последний.

**Последовательность действий на сервере:**

| Шаг | Действие | Обработка ошибок |
|-----|----------|------------------|
| 1 | Setup variables | — |
| 2 | Check project dir exists | При первом запуске — клонирует репо, требует ручной `.env` |
| 3 | Check `.env` exists | Fail если нет `.env` |
| 4 | Save current commit | Для rollback |
| 5 | `git fetch + reset --hard` | При ошибке — fresh clone с сохранением `.env` |
| 6 | Verify `compose.yml` | — |
| 7 | `docker compose up -d --build` | При ошибке — автоматический rollback |
| 8 | Wait 20s | Даём контейнерам подняться |
| 9 | Health checks | Backend, Frontend, HTTPS |

**Автоматический rollback:**
Если `docker compose up` падает, скрипт:
1. Откатывает git к предыдущему коммиту
2. Запускает `docker compose up` снова
3. Если rollback успешен — деплой считается OK

> **Ограничение:** Rollback работает ТОЛЬКО если проблема связана с кодом или сборкой образа.
> Ошибки в данных (`.env`, secrets, внешние API) rollback не исправляет.
4. Если rollback тоже упал — manual intervention required

### 6.4 Типичные ошибки при деплое

| Ошибка | Причина | Решение |
|--------|---------|---------|
| `POSTGRES_PASSWORD is required` | Нет `.env` на сервере | Создать `.env` из `.env.example` |
| `Backend health check failed` | Django не стартует | Смотреть `docker logs eatfit24-backend` |
| `Permission denied` | Неправильные права на `/opt/EatFit24` | `chown -R username:username /opt/EatFit24` |
| `Image build failed` | Ошибка в Dockerfile или requirements.txt | Собрать локально, проверить |
| Rollback тоже упал | Фатальная ошибка | SSH на сервер, `docker compose logs` |

---

## 7. ENV и конфигурация

### 7.1 Принцип работы

```
.env (на сервере, НЕ в git)
    ↓
compose.yml (env_file: .env)
    ↓
Контейнеры получают переменные
```

### 7.2 Критичные переменные

| Переменная | Сервис | Описание |
|------------|--------|----------|
| `SECRET_KEY` | backend | Django secret, менять нельзя |
| `POSTGRES_PASSWORD` | db, backend | Пароль БД, обязателен |
| `TELEGRAM_BOT_TOKEN` | backend, bot | Токен бота |
| `YOOKASSA_SHOP_ID` | backend | ID магазина YooKassa |
| `YOOKASSA_SECRET_KEY` | backend | Секретный ключ YooKassa |
| `OPENROUTER_API_KEY` | AI Proxy | Ключ для AI API |
| `BOT_ADMIN_ID` | bot | Telegram ID админа |

### 7.3 Где хранить секреты

| Место | Назначение |
|-------|------------|
| `.env` на сервере | Production secrets |
| `.env.example` в git | Шаблон без реальных значений |
| GitHub Secrets | Только для CI/CD (VPS_SSH_KEY, etc.) |

> **НИКОГДА не коммитить:**
> - `.env` с реальными секретами
> - Любые токены в коде
> - SSH-ключи

### 7.4 Vite переменные (frontend)

```yaml
build:
  args:
    - VITE_API_URL=/api/v1
    - VITE_TELEGRAM_BOT_NAME=${TELEGRAM_BOT_NAME:-EatFit24_bot}
```

Vite встраивает `VITE_*` в JavaScript bundle при сборке.  
**Изменение требует пересборки образа.**

---

## 8. Границы ответственности

### ❌ Что НЕ нужно делать

| Действие | Почему опасно |
|----------|---------------|
| Открывать `8000` порт наружу | Backend без HTTPS, без защиты от DDoS |
| Добавлять новые сервисы "на всякий случай" | Увеличивает attack surface и потребление ресурсов |
| Хранить секреты в Dockerfile | Secrets остаются в layer cache |
| Менять nginx.conf без понимания | Можно сломать Telegram auth или SPA routing |
| Убирать `USER appuser` из Dockerfile | При RCE атакующий получит root в контейнере |
| Использовать `latest` теги образов | Деплой становится невоспроизводимым |
| Добавлять wildcard CORS | Любой сайт сможет делать API-запросы от лица пользователя |

### ✅ Что МОЖНО безопасно менять

| Действие | Условие |
|----------|---------|
| Увеличить resource limits | Если не хватает RAM/CPU |
| Добавить ENV переменную | Если не секрет — в `.env.example`, если секрет — только в `.env` на сервере |
| Увеличить celery concurrency | При росте нагрузки |
| Добавить healthcheck | Улучшает мониторинг |
| Обновить версию образа | Проверить changelog, протестировать локально |

---

## 9. Чеклист перед изменениями

### Перед правками

- [ ] Понять, какие сервисы затронуты
- [ ] Проверить, не сломает ли это auth-цепочку (nginx → backend)
- [ ] Собрать и протестировать локально (`docker compose up --build`)
- [ ] Если меняется Dockerfile — проверить, что образ собирается

### После деплоя

- [ ] `docker compose ps` — все сервисы UP?
- [ ] `curl http://127.0.0.1:8000/health/` — backend отвечает?
- [ ] `curl http://127.0.0.1:3000/` — frontend отвечает?
- [ ] `curl https://eatfit24.ru/health/` — HTTPS работает?
- [ ] `docker logs eatfit24-backend --tail 50` — нет ошибок?
- [ ] Telegram Mini App открывается и авторизует?

### Если что-то сломалось

1. `docker compose logs --tail 100` — общие логи
2. `docker logs eatfit24-backend --tail 100` — логи конкретного сервиса
3. `docker compose down && docker compose up -d` — перезапуск
4. Если не помогает — откатить коммит:
   ```bash
   git log --oneline -5      # найти предыдущий коммит
   git reset --hard <hash>   # откатиться
   docker compose up -d --build
   ```

---

## Приложение A: Полезные команды

```bash
# Статус сервисов
docker compose ps

# Логи всех сервисов (последние 100 строк)
docker compose logs --tail 100

# Логи конкретного сервиса в реальном времени
docker logs -f eatfit24-backend

# Перезапуск всех сервисов
docker compose restart

# Полный перезапуск с пересборкой
docker compose down && docker compose up -d --build

# Войти в контейнер
docker exec -it eatfit24-backend bash

# Django shell
docker exec -it eatfit24-backend python manage.py shell

# Применить миграции вручную
docker exec -it eatfit24-backend python manage.py migrate

# Очистить неиспользуемые образы
docker image prune -a

# Проверить использование ресурсов
docker stats
```

---

## Приложение B: Структура файлов

```
/
├── compose.yml                    # Главный docker-compose
├── .env                           # Секреты (НЕ в git!)
├── .env.example                   # Шаблон для .env
│
├── backend/
│   ├── Dockerfile                 # Multi-stage сборка Django
│   ├── entrypoint.sh              # Миграции + collectstatic + gunicorn
│   └── requirements.txt
│
├── bot/
│   ├── Dockerfile                 # Сборка Telegram бота
│   ├── entrypoint.sh
│   └── requirements.txt
│
├── frontend/
│   ├── Dockerfile                 # Multi-stage: node → nginx
│   ├── nginx.conf                 # Routing, proxy, CSP
│   └── public/landing/            # Статичный лендинг
│
└── .github/workflows/
    ├── backend.yml                # CI: тесты backend
    ├── bot.yml                    # CI: тесты bot
    └── deploy.yml                 # CD: деплой на VPS
```
